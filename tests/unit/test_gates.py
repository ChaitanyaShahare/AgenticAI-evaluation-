"""Composite scores, gate verdicts and exit codes.

Thresholds here are test values, chosen to exercise the gate logic; the real thresholds in configs/gates.yaml are
human-owned (SOP §3.10).
"""

from __future__ import annotations

from evalkit.cli import main
from evalkit.config.loader import GatesConfig, Threshold
from evalkit.schema import CaseResult, CheckResult, TestCase
from evalkit.scoring.composite import agent_score, case_score
from evalkit.scoring.gates import evaluate_gates, load_gates


def chk(metric, verdict, severity="S2", score=None, agent=None):
    return CheckResult(metric=metric, verdict=verdict, severity=severity, score=score, agent=agent)


def case(cid, pattern="Golden path"):
    return TestCase(case_id=cid, level="L3", primary_agent="E2E", pattern=pattern, severity="S1", trials=1, run_sets=["gate"])


CASES = {"A": case("A"), "B": case("B", "Edge cases")}


def gates(**kw):
    return GatesConfig(version=1, owner="tests", **kw)


def test_case_composite_rescales_and_applies_g():
    full = [
        chk("TR-1", "pass", score=1.0),
        chk("TR-2", "fail", score=0.0),
        chk("TU-3", "pass", score=1.0),
        chk("TU-5", "skip"),
        chk("TR-6", "pass", score=0.5),
    ]
    c = case_score(full)
    assert c.used == ["TR-1", "TR-2", "TU-3", "TR-6"] and c.score == round((0.4 + 0.2 + 0.05) / 0.9, 3) and c.gate == 1
    c = case_score([*full, chk("BF-1", "fail", "S1")])
    assert c.gate == 0 and c.score == 0.0 and c.s1_failures == 1
    assert case_score([chk("BF-6", "pass", "S1")]).score is None  # nothing measured is not 0 and not 1


def test_agent_composite_uses_only_the_agents_checks():
    checks = [
        chk("AG-1", "pass", agent="risk", score=1.0),
        chk("AG-2", "pass", agent="risk", score=0.5),
        chk("AG-5", "fail", "S1", agent="identity"),
    ]
    assert agent_score(checks, "risk").score == round((0.4 + 0.125) / 0.65, 3)
    assert agent_score(checks, "identity").gate == 0


def test_no_gates_file_never_passes(tmp_path):
    p = tmp_path / "gates.yaml"
    p.write_text("# thresholds to be written by the QE Lead\n", encoding="utf-8")
    assert load_gates(p) is None
    v = evaluate_gates(None, [], CASES)
    assert v.verdict == "NO_GATES" and v.exit_code == 2


def test_pass_fail_incomplete():
    results = [CaseResult(case_id="A", trial=1, checks=[chk("TR-1", "pass", score=1.0), chk("BF-6", "pass", "S1")]),
               CaseResult(case_id="B", trial=1, checks=[chk("TR-1", "fail", score=0.0)])]  # fmt: skip
    golden = Threshold(metric="TR-1", patterns=["Golden path"], min=0.95)
    v = evaluate_gates(gates(thresholds=[golden]), results, CASES)
    assert v.verdict == "PASS" and v.exit_code == 0
    v = evaluate_gates(gates(thresholds=[golden, Threshold(metric="TR-1", min=0.95)]), results, CASES)
    assert v.verdict == "FAIL" and v.exit_code == 1 and v.lines[1].value == 0.5
    v = evaluate_gates(gates(thresholds=[golden, Threshold(metric="TR-2", min=0.9)]), results, CASES)
    assert v.verdict == "INCOMPLETE" and "TR-2" in v.reasons[0]
    v = evaluate_gates(gates(thresholds=[Threshold(metric="TR-1", min=0.95)], report_only=["TR-1"]), results, CASES)
    assert v.verdict == "PASS"


def test_s1_zero_tolerance_and_agent_scope():
    checks = [
        chk("AG-2", "pass", agent="risk", score=1.0),
        chk("AG-2", "fail", agent="identity", score=0.5),
        chk("AG-5", "fail", "S1", agent="identity"),
    ]
    results = [CaseResult(case_id="A", trial=1, checks=checks)]
    v = evaluate_gates(gates(), results, CASES)
    assert v.verdict == "FAIL" and "· AG-5 [identity]" in v.s1_failures[0]
    v = evaluate_gates(
        gates(s1_zero_tolerance=False, thresholds=[Threshold(metric="AG-2", scope="agent", stat="mean_score", min=0.9)]), results, CASES
    )
    assert [(line.name.split(": ")[1].rstrip(")"), line.ok) for line in v.lines] == [("identity", False), ("risk", True)]


def test_flaky_suite_is_suspended():
    results = [CaseResult(case_id="A", trial=t, checks=[chk("TR-1", "pass", score=1.0)]) for t in (1, 2, 3)]
    v = evaluate_gates(gates(), results, CASES, flaky=["A"])
    assert v.verdict == "SUSPENDED" and v.exit_code == 2


def test_cli_grade_on_recordings_writes_results(tmp_path, capsys):
    from evalkit.config import repo_root

    code = main(["grade", str(repo_root() / "projects" / "kyc_onboarding" / "recorded_runs"), "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 2 and "Gate: INCOMPLETE" in out and "Per-agent scorecards" in out  # some thresholds unmeasured on 4 recordings
    assert (tmp_path / "results.jsonl").stat().st_size > 0 and (tmp_path / "scorecard.json").is_file()
