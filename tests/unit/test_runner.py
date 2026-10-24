"""Harness runner: planning (run modes, k trials), sandboxing, output layout, clock check — all offline."""

from __future__ import annotations

import json
import sqlite3

import pytest

from evalkit.harness.clock import ClockMismatch, check_clock
from evalkit.harness.runner import execute, make_plan
from evalkit.schema import Trajectory
from tests.recordings import flt021_client
from tests.scripted_client import clean_client


@pytest.fixture(autouse=True)
def runs_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALKIT_RUNS_DIR", str(tmp_path / "runs"))
    return tmp_path / "runs"


def test_run_mode_sizes_match_the_plan():
    smoke, gate, full = (make_plan("kyc_onboarding", mode=m) for m in ("smoke", "gate", "full"))
    assert (len(smoke.items), len(gate.items), len(full.items)) == (10, 210, 250)
    assert all(t == 1 for _, t in smoke.items)  # smoke is k = 1 by design
    assert {c.severity for c, _ in gate.items} == {"S1"} and len({c.case_id for c, _ in gate.items}) == 70


def test_case_plan_and_trial_override():
    p = make_plan("kyc_onboarding", case_ids=["KYC-FLT-021", "KYC-GLD-002"])
    assert [(c.case_id, t) for c, t in p.items] == [("KYC-FLT-021", 1), ("KYC-FLT-021", 2), ("KYC-FLT-021", 3), ("KYC-GLD-002", 1)]
    assert len(make_plan("kyc_onboarding", case_ids=["KYC-FLT-021"], trials=1).items) == 1
    with pytest.raises(KeyError, match="KYC-NOPE"):
        make_plan("kyc_onboarding", case_ids=["KYC-NOPE"])


def test_execute_writes_trajectories_records_and_manifest(runs_tmp):
    plan = make_plan("kyc_onboarding", case_ids=["KYC-GLD-001", "KYC-FLT-021"], trials=2, run_id="t")
    scripts = {"KYC-GLD-001": clean_client, "KYC-FLT-021": flt021_client}
    summary = execute(plan, client_factory=lambda c, t: scripts[c.case_id](), max_workers=2, progress=lambda _m: None)
    run = runs_tmp / "t"
    assert [(r.case_id, r.trial) for r in summary.records] == [
        ("KYC-FLT-021", 1),
        ("KYC-FLT-021", 2),
        ("KYC-GLD-001", 1),
        ("KYC-GLD-001", 2),
    ]
    assert not summary.errors
    gld = next(r for r in summary.records if r.case_id == "KYC-GLD-001")
    assert gld.end_state["status"] == "APPROVED" and gld.tool_calls == 17  # 4 hand-offs + 4 DOC + 3 IDV + 2 SCR + 2 RSK + create + finalize
    flt = next(r for r in summary.records if r.case_id == "KYC-FLT-021")
    assert flt.faults_injected == 3
    lines = [json.loads(x) for x in (run / "trials.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 4
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["client"] == "injected" and len(manifest["items"]) == 4
    t = Trajectory.load(run / "trajectories" / "KYC-GLD-001" / "t2.json")
    assert t.meta.trial == 2 and t.end_state["record_id"] == "REC-001"


def test_each_trial_gets_its_own_database(runs_tmp):
    plan = make_plan("kyc_onboarding", case_ids=["KYC-GLD-001"], trials=2, run_id="iso")
    execute(plan, client_factory=lambda c, t: clean_client(), max_workers=1, progress=lambda _m: None)
    for k in (1, 2):
        con = sqlite3.connect(runs_tmp / "iso" / "db" / "KYC-GLD-001" / f"t{k}.sqlite")
        assert con.execute("SELECT count(*) FROM customer_records").fetchone()[0] == 1  # trial 2 did not see trial 1's record
        assert {r[0] for r in con.execute("SELECT DISTINCT trial FROM audit_events")} == {k}
        con.close()


def test_clock_mismatch_fails_fast():
    from evalkit.config import repo_root

    seed = repo_root() / "projects" / "kyc_onboarding" / "data" / "kyc_synthetic.sqlite"
    check_clock(seed, "2026-11-02")
    with pytest.raises(ClockMismatch, match="2026-11-02"):
        check_clock(seed, "2026-12-01")
