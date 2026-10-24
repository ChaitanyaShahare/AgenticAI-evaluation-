"""Reports, cost and the WP8 exit check: a seeded defect turns the run red and names the failing rule, and the HTML
report never contains an unmasked identifier. Offline: recordings and fake clients only."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

from evalkit import cli
from evalkit.config import load_eval_config, repo_root
from evalkit.evaluators.bfsi.pii import load_recognizers
from evalkit.harness.cost import alerts, money, usage, write_cost
from evalkit.reporting.html_report import ReportLeak, build_report
from evalkit.reporting.junit_writer import check_name
from evalkit.reporting.redaction import Redactor
from evalkit.schema import CheckResult
from tests.unit.evaluators.conftest import drop_tool, load, with_reply

ROOT = repo_root()


@pytest.fixture(scope="module")
def redactor():
    return Redactor(load_recognizers(ROOT / "configs" / "pii_recognizers.yaml"))


def write_traj(folder, traj, name="t1.json"):
    folder.mkdir(parents=True, exist_ok=True)
    return traj.save(folder / name)


# ---------------------------------------------------------------- exit check
def test_seeded_defect_turns_the_run_red_and_names_the_rule(tmp_path, capsys):
    """LAB-1-style defect: pep_check skipped. CI must fail and say KYC-GLD-001 · TR-3 (R1)."""
    write_traj(tmp_path / "in", drop_tool(load("KYC-GLD-001"), "pep_check"))
    code = cli.main(["grade", str(tmp_path / "in"), "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 1  # FAIL, not INCOMPLETE: an S1 failure decides
    assert "KYC-GLD-001 t1 · TR-3 (R1): R1: fail — pep_check not done before create_customer_record" in out
    root = ET.parse(tmp_path / "out" / "junit.xml").getroot()
    failed = {tc.get("name") for tc in root.iter("testcase") if tc.find("failure") is not None}
    assert {"KYC-GLD-001 t1 · TR-3 (R1)", "KYC-GLD-001 t1 · TR-4 (P1.record)"} <= failed


def test_report_never_contains_an_unmasked_identifier(tmp_path, redactor):
    leaky = with_reply(load("KYC-GLD-001"), "Approved for PAN ZQBPI1137K, Aadhaar 9000 0332 5982, card 4111 1111 1111 1111.")
    write_traj(tmp_path / "in", leaky)
    cli.main(["grade", str(tmp_path / "in"), "--out", str(tmp_path / "out")])
    html = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert redactor.leaks(html) == []
    assert "ZQBPI1137K" not in html and "…137K" in html  # shown masked, so a reviewer still sees the leak
    junit = (tmp_path / "out" / "junit.xml").read_text(encoding="utf-8")
    assert redactor.leaks(junit) == [] and "MASK-IN_PAN" in junit


def test_report_refuses_to_write_a_leak(tmp_path, redactor, monkeypatch):
    from evalkit.config.registry import ProjectSuite
    from evalkit.evaluators.grader import grade, summary
    from evalkit.scoring.gates import evaluate_gates

    suite = ProjectSuite.load("kyc_onboarding")
    traj = with_reply(load("KYC-GLD-001"), "PAN ZQBPI1137K")
    graded = grade(suite, [traj])
    verdict = evaluate_gates(None, graded.results, suite.cases)
    monkeypatch.setattr(redactor, "deep", lambda obj: obj)  # a redaction bug
    with pytest.raises(ReportLeak, match="identifier"):
        build_report(tmp_path / "r.html", summary=summary(graded, suite), graded=graded, verdict=verdict, trajectories=[traj],
                     redactor=redactor, run_id="t", project="kyc_onboarding")  # fmt: skip
    assert not (tmp_path / "r.html").exists()


def test_report_highlights_the_failing_step(tmp_path):
    write_traj(tmp_path / "in", drop_tool(load("KYC-GLD-001"), "pep_check"))
    cli.main(["grade", str(tmp_path / "in"), "--out", str(tmp_path / "out")])
    html = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert '<tr class="failing">' in html and "Per-agent scorecards" in html and "Gate" in html


# ---------------------------------------------------------------- junit names
def test_check_names():
    c = CheckResult(metric="AG-5", agent="identity", rule="GR-IDV.no-upgrade", verdict="fail", severity="S1")
    assert check_name("KYC-AGT-IDV-050", 2, c) == "KYC-AGT-IDV-050 t2 · AG-5 (GR-IDV.no-upgrade) [identity]"
    assert check_name("KYC-GLD-001", 1, CheckResult(metric="TU-4", verdict="pass", severity="S1")) == "KYC-GLD-001 t1 · TU-4"


# ---------------------------------------------------------------- cost
def test_usage_is_summed_per_model_and_agent():
    by_model, by_agent = usage([load("live/KYC-GLD-001")])
    assert set(by_model) == {"claude-sonnet-5-5", "claude-haiku-5-5"} and by_model["claude-sonnet-5-5"]["calls"] == 7
    assert {"supervisor", "doc_extraction", "identity", "screening", "risk"} <= set(by_agent)


def test_money_is_never_guessed():
    by_model = {"m": {"calls": 1, "input_tokens": 1_000_000, "output_tokens": 500_000, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0}}  # fmt: skip
    assert money(by_model, {}) == (None, ["m"])
    assert money(by_model, {"m": {"input": 3.0, "output": 15.0}}) == (10.5, [])


def test_budget_alerts():
    assert "alerts are off" in alerts(100, None, [0.5, 0.8])[0]
    assert "cannot be evaluated" in alerts(None, 1000, [0.5, 0.8])[0]
    assert alerts(400, 1000, [0.5, 0.8]) == []
    assert [a.split("(")[1] for a in alerts(850, 1000, [0.5, 0.8])] == ["threshold 50%)", "threshold 80%)"]


def test_cost_ledger_adds_up_the_month(tmp_path):
    budget = load_eval_config().budget.model_copy(update={
        "monthly_limit_inr": 1.0, "usd_to_inr": 100.0,
        "pricing": {"claude-sonnet-5-5": {"input": 1, "output": 1, "cache_read": 1, "cache_write": 1},
                    "claude-haiku-5-5": {"input": 1, "output": 1, "cache_read": 1, "cache_write": 1}},
    })  # fmt: skip
    ledger = tmp_path / "ledger.jsonl"
    t = [load("live/KYC-GLD-001")]
    first = write_cost(tmp_path, "r1", t, budget, ledger)
    second = write_cost(tmp_path, "r2", t, budget, ledger)
    assert first["usd"] is not None and second["month_to_date_inr"] == pytest.approx(2 * first["inr"])
    assert json.loads((tmp_path / "cost.json").read_text(encoding="utf-8"))["run_id"] == "r2"
    assert second["alerts"]  # 2 × the run's ₹ is past 50% of a ₹1 budget


def test_judge_tokens_are_counted(tmp_path):
    from evalkit.config.registry import ProjectSuite
    from evalkit.evaluators.judges import load_judges_config
    from evalkit.evaluators.judges.cache import JudgeCache
    from evalkit.evaluators.judges.deepeval_metrics import TASK_COMPLETION
    from evalkit.evaluators.judges.geval_rubric import RubricJudge, Verdict

    class Fake:
        def __init__(self):
            self.messages = self

        def parse(self, **kw):
            u = SimpleNamespace(input_tokens=1200, output_tokens=150, cache_read_input_tokens=0, cache_creation_input_tokens=300)
            return SimpleNamespace(stop_reason="end_turn", usage=u, parsed_output=Verdict(reason="ok", score=3))

    suite = ProjectSuite.load("kyc_onboarding")
    t = load("KYC-GLD-001")
    judge = RubricJudge(Fake(), load_judges_config(), JudgeCache(tmp_path))
    judge.score(t, suite.context(suite.cases["KYC-GLD-001"]), TASK_COMPLETION)
    assert (judge.usage["calls"], judge.usage["input_tokens"], judge.usage["cache_creation_input_tokens"]) == (1, 1200, 300)


# ---------------------------------------------------------------- commands
def test_report_and_full_commands(tmp_path, capsys, monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: pytest.fail("no live client in these commands"))
    write_traj(tmp_path / "in", load("KYC-GLD-001"))
    assert cli.main(["report", str(tmp_path / "in"), "--out", str(tmp_path / "out")]) == 0
    assert {p.name for p in (tmp_path / "out").iterdir()} >= {"report.html", "junit.xml", "results.jsonl", "cost.json", "gate.json"}
    assert cli.main(["full"]) == 0
    assert "dry run — no model calls made" in capsys.readouterr().out


def test_report_shows_every_trial_timeline_even_after_renumbering(tmp_path):
    """Two recordings of the same case and trial: the grader renumbers one; the report must still show both timelines."""
    write_traj(tmp_path / "in", load("KYC-GLD-001"), "a.json")
    write_traj(tmp_path / "in", load("live/KYC-GLD-001"), "b.json")
    cli.main(["grade", str(tmp_path / "in"), "--out", str(tmp_path / "out")])
    html = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert "KYC-GLD-001 t2" in html and "(0 steps)" not in html
