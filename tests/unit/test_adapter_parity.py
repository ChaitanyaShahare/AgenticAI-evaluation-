"""LangGraph adapter: event → Trajectory mapping, end state, agent outputs, error capture, and parity with the recordings.

Parity: re-running the three scripted recordings must give the stored trajectories exactly (apart from wall clock,
durations and installed versions). The OTel adapter's parity half arrives with that adapter (descoped in WP4).
"""

from __future__ import annotations

import json

import pytest

from evalkit.adapters.langgraph_adapter import events_to_steps, read_end_state
from evalkit.config import repo_root
from evalkit.schema import Trajectory
from tests.recordings import RECORDINGS, SCRIPTS, normalise, record

ROOT = repo_root()


@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    import os

    tmp = tmp_path_factory.mktemp("runs")
    old = os.environ.get("EVALKIT_RUNS_DIR")
    os.environ["EVALKIT_RUNS_DIR"] = str(tmp)
    out = tmp_path_factory.mktemp("rec")
    try:
        record(out, tmp)
    finally:
        if old is None:
            os.environ.pop("EVALKIT_RUNS_DIR", None)
        else:
            os.environ["EVALKIT_RUNS_DIR"] = old
    return out


@pytest.mark.parametrize("case_id", sorted(SCRIPTS))
def test_rerun_matches_recording(fresh, case_id):
    stored = normalise(json.loads((RECORDINGS / f"{case_id}.json").read_text(encoding="utf-8")))
    again = normalise(json.loads((fresh / f"{case_id}.json").read_text(encoding="utf-8")))
    assert again == stored, "trajectory mapping changed; if intended, refresh with: uv run python -m tests.recordings --write"


def test_golden_trajectory_content():
    t = Trajectory.load(RECORDINGS / "KYC-GLD-001.json")
    assert t.handoffs() == ["doc_extraction", "identity", "screening", "risk"]
    assert t.tool_sequence("screening") == ["sanctions_screen", "pep_check"]
    assert t.tool_sequence("risk") == ["fetch_risk_policy", "compute_risk_score"]
    assert t.end_state["status"] == "APPROVED" and t.end_state["reason_codes"] == [] and t.end_state["risk_score"] == 22
    assert set(t.agent_outputs) == {"doc_extraction", "identity", "screening", "risk"}
    assert any(s.kind == "interrupt" and s.data["decision"] == "APPROVE" for s in t.steps)
    assert t.meta.models == {"supervisor": "claude-sonnet-5-5", "specialist": "claude-haiku-5-5"}
    assert set(t.meta.prompt_hashes) == {"supervisor", "doc_extraction", "identity", "screening", "risk"}
    assert t.meta.usage["claude-sonnet-5-5"]["calls"] == 7 and t.final_message == "Your account is open."


def test_l1_trajectory_has_faults_and_one_agent():
    t = Trajectory.load(RECORDINGS / "KYC-FLT-021.json")
    assert t.agents() == ["identity"]
    pan = [c for c in t.tool_calls() if c.tool == "verify_pan"]
    assert [(c.status, c.attempt, c.fault_injected) for c in pan] == [
        ("timeout", 1, "FP-01:TIMEOUT"),
        ("error", 2, "FP-01:HTTP_500"),
        ("error", 3, "FP-01:HTTP_500"),
    ]
    assert t.agent_outputs["identity"]["overall"] == "UNVERIFIED" and t.agent_outputs["identity"]["pan_status"] == "UNAVAILABLE"


def test_l2_trajectory_flags_slice_violation():
    t = Trajectory.load(RECORDINGS / "KYC-HND-109.json")
    contract_steps = [s for s in t.steps if s.kind == "contract" and s.agent == "screening"]
    assert contract_steps and contract_steps[0].data["violations"][0].startswith("SLICE-1")
    assert "risk" not in t.agent_outputs["screening"] and t.end_state["risk_tier"] == "LOW"


def test_unknown_event_kinds_are_kept_as_notes():
    steps = events_to_steps([{"kind": "something_new", "agent": "x", "detail": 1}])
    assert steps[0].kind == "note" and steps[0].content == "something_new" and steps[0].data == {"agent": "x", "detail": 1}


def test_end_state_decodes_json_columns(tmp_path):
    import sqlite3

    db = tmp_path / "e.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE a (id TEXT, status TEXT, reason_codes_json TEXT)")
    con.execute("INSERT INTO a VALUES ('X', 'PENDING_INFO', '[\"DOC_MISSING\"]')")
    con.commit()
    con.close()
    assert read_end_state(db, "SELECT status, reason_codes_json FROM a WHERE id = :id", {"id": "X"}) == {
        "status": "PENDING_INFO",
        "reason_codes": ["DOC_MISSING"],
    }


def test_runner_crash_becomes_an_error_trajectory(tmp_path, monkeypatch):
    """A crashing run is graded as a failure, never lost."""
    from evalkit.adapters.langgraph_adapter import LangGraphAdapter
    from evalkit.config import load_eval_config, load_project_config
    from projects.kyc_onboarding.cases import list_cases

    pdir = ROOT / "projects" / "kyc_onboarding"
    pcfg = load_project_config(pdir / "project.yaml").model_copy(update={"runner": "tests.unit.test_adapter_parity:_boom"})
    case = next(c for c in list_cases() if c.case_id == "KYC-GLD-001")
    t = LangGraphAdapter(pcfg, pdir, load_eval_config()).run(case, 1, "r", tmp_path / "none.sqlite")
    assert t.error.startswith("RuntimeError: boom") and t.steps == [] and t.end_state == {}


def _boom(*a, **k):
    raise RuntimeError("boom")
