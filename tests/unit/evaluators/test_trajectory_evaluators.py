"""TR-1, TR-2, TR-5, TR-6, TR-7 on good recordings and their bad variants."""

from __future__ import annotations

import pytest

from evalkit.evaluators.base import Limits
from evalkit.evaluators.trajectory.efficiency import StepEfficiencyEvaluator
from evalkit.evaluators.trajectory.end_state import EndStateEvaluator
from evalkit.evaluators.trajectory.handoff import HandoffEvaluator
from evalkit.evaluators.trajectory.match import TrajectoryMatchEvaluator, sequences_match
from evalkit.evaluators.trajectory.reliability import pass_hat_k
from evalkit.schema import CaseResult, CheckResult
from tests.unit.evaluators.conftest import ctx_for, load, with_end_state


def one(ev, traj, ctx):
    res = ev.evaluate(traj, ctx)
    assert len(res) == 1
    return res[0]


# ---------------------------------------------------------------- TR-1
def test_tr1_end_state(suite):
    good = load("KYC-GLD-001")
    assert one(EndStateEvaluator(), good, ctx_for(suite, good)).verdict == "pass"
    bad = with_end_state(good, status="PENDING_EDD", record_id=None)
    res = one(EndStateEvaluator(), bad, ctx_for(suite, bad))
    assert res.verdict == "fail" and res.severity == "S1"  # takes the case's severity
    assert "status PENDING_EDD ≠ APPROVED" in res.detail and "record_id" in res.detail
    assert "risk_score 99" in one(EndStateEvaluator(), with_end_state(good, risk_score=99), ctx_for(suite, good)).detail
    assert "reason_codes" in one(EndStateEvaluator(), with_end_state(good, reason_codes=["HIGH_RISK"]), ctx_for(suite, good)).detail


def test_tr1_skips_agent_level_and_fails_crashed_runs(suite):
    flt = load("KYC-FLT-021")
    assert one(EndStateEvaluator(), flt, ctx_for(suite, flt)).verdict == "skip"
    crashed = load("KYC-GLD-001").model_copy(update={"end_state": {}, "error": "RuntimeError: boom\ntrace"})
    assert "boom" in one(EndStateEvaluator(), crashed, ctx_for(suite, crashed)).detail


# ---------------------------------------------------------------- TR-2
@pytest.mark.parametrize(
    ("actual", "mode", "ok"),
    [
        (["a", "b"], "strict", True), (["b", "a"], "strict", False),
        (["b", "a"], "unordered", True), (["a", "a", "b"], "unordered", False),
        (["a"], "subset", True), (["a", "c"], "subset", False),
        (["a", "b", "c"], "superset", True), (["a"], "superset", False),
    ],
)  # fmt: skip
def test_tr2_match_modes(actual, mode, ok):
    assert sequences_match(actual, ["a", "b"], mode)[0] is ok


def test_tr2_against_reference(suite):
    good = load("KYC-GLD-001")
    shipped = one(TrajectoryMatchEvaluator(), good, ctx_for(suite, good))  # the RT-01 file
    assert shipped.verdict == "pass" and "not yet reviewed" not in shipped.detail  # reviewed by the QE Lead
    unreviewed = one(TrajectoryMatchEvaluator(), good, ctx_for(suite, good, unreviewed_references={"RT-01"}))
    assert "RT-01 not yet reviewed" in unreviewed.detail
    no_ref = good.model_copy(update={"meta": good.meta.model_copy(update={"case_id": "KYC-HND-109"})})
    assert one(TrajectoryMatchEvaluator(), no_ref, ctx_for(suite, no_ref)).verdict == "skip"  # case names no reference
    ref = {"RT-01": ["verify_pan", "sanctions_screen", "pep_check", "create_customer_record"]}
    assert one(TrajectoryMatchEvaluator(), good, ctx_for(suite, good, references=ref)).verdict == "pass"  # superset
    ref_extra = {"RT-01": [*ref["RT-01"], "escalate_to_edd"]}
    assert "escalate_to_edd" in one(TrajectoryMatchEvaluator(), good, ctx_for(suite, good, references=ref_extra)).detail


# ---------------------------------------------------------------- TR-5
def test_tr5_handoffs(suite):
    good = load("KYC-GLD-001")
    assert one(HandoffEvaluator(), good, ctx_for(suite, good)).verdict == "pass"
    lost = good.model_copy(update={"steps": [s for s in good.steps if not (s.kind == "agent_result" and s.agent == "identity")]})
    res = one(HandoffEvaluator(), lost, ctx_for(suite, lost))
    assert res.verdict == "fail" and "identity got no result" in res.detail and res.score == 0.75
    assert "delegated 1 times" in one(HandoffEvaluator(), good, ctx_for(suite, good, limits=Limits(max_bounces=-1))).detail
    assert one(HandoffEvaluator(), load("KYC-FLT-021"), ctx_for(suite, load("KYC-FLT-021"))).verdict == "skip"


# ---------------------------------------------------------------- TR-6
def test_tr6_efficiency(suite):
    flt = load("KYC-FLT-021")
    res = one(StepEfficiencyEvaluator(), flt, ctx_for(suite, flt))
    assert res.severity == "S3" and res.score == 0.6  # 3 distinct of 5 calls (two retries)
    good = load("KYC-GLD-001")
    assert one(StepEfficiencyEvaluator(), good, ctx_for(suite, good, limits=Limits(max_steps=3))).verdict == "fail"


# ---------------------------------------------------------------- TR-7
def _trial(case, trial, verdict, metric="TR-1", severity="S1"):
    return CaseResult(case_id=case, trial=trial, checks=[CheckResult(metric=metric, verdict=verdict, severity=severity)])


def test_tr7_pass_hat_k_and_flaky():
    results = [_trial("A", t, "pass") for t in (1, 2, 3)] + [_trial("B", 1, "pass"), _trial("B", 2, "fail"), _trial("C", 1, "pass")]
    states = {("A", t): {"status": "APPROVED"} for t in (1, 2, 3)} | {("B", 1): {}, ("B", 2): {}}
    checks, flaky = pass_hat_k(results, states)
    assert checks["A"].verdict == "pass" and checks["B"].verdict == "fail" and checks["C"].verdict == "skip"
    assert flaky == ["B"]
    states[("A", 2)] = {"status": "PENDING_INFO"}
    assert pass_hat_k(results, states)[1] == ["A", "B"]  # end state differs between trials
    s3_only = [_trial("D", 1, "pass"), _trial("D", 2, "fail", "TR-6", "S3")]
    assert pass_hat_k(s3_only, {})[0]["D"].verdict == "pass"  # an S3 miss does not fail a trial
