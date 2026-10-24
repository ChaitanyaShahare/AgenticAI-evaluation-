"""TU-1 … TU-6 on good recordings and their bad variants."""

from __future__ import annotations

from evalkit.evaluators.tooluse.arguments import ArgumentCorrectnessEvaluator, SchemaValidityEvaluator
from evalkit.evaluators.tooluse.error_handling import ErrorHandlingEvaluator
from evalkit.evaluators.tooluse.grounding import GroundingEvaluator
from evalkit.evaluators.tooluse.reconciliation import ReconciliationEvaluator, figures
from evalkit.evaluators.tooluse.selection import ToolSelectionEvaluator
from tests.unit.evaluators.conftest import add_call, ctx_for, drop_tool, edit_call, load, set_output, with_reply


def one(ev, traj, ctx):
    res = ev.evaluate(traj, ctx)
    assert len(res) == 1
    return res[0]


def test_tu1_selection(suite):
    good = load("KYC-GLD-001")
    ctx = ctx_for(suite, good)
    assert one(ToolSelectionEvaluator(), good, ctx).score == 1.0
    res = one(ToolSelectionEvaluator(), drop_tool(good, "pep_check"), ctx)
    assert res.verdict == "fail" and "missing pep_check" in res.detail and res.score < 1
    esc = add_call(good, "supervisor", "escalate_to_edd", {"application_id": "APL-001", "reason_codes": ["HIGH_RISK"]})
    assert "forbidden called: escalate_to_edd" in one(ToolSelectionEvaluator(), esc, ctx).detail


def test_tu2_schema(suite):
    good = load("KYC-GLD-001")
    assert one(SchemaValidityEvaluator(), good, ctx_for(suite, good)).verdict == "pass"
    bad = edit_call(good, "verify_pan", args={"extra": 1})
    res = one(SchemaValidityEvaluator(), bad, ctx_for(suite, bad))
    assert res.verdict == "fail" and "verify_pan" in res.detail and res.evidence_step is not None


def test_tu3_argument_values_with_name_normalisation(suite):
    good = load("KYC-GLD-001")
    assert one(ArgumentCorrectnessEvaluator(), good, ctx_for(suite, good)).verdict == "skip"
    case = suite.cases["KYC-GLD-001"]
    exp = {**case.expected, "arguments": {"verify_pan": {"full_name": "ananya  iyer", "dob": "1994-03-12"}}}
    ctx = ctx_for(suite, good, case=case.model_copy(update={"expected": exp}))
    assert one(ArgumentCorrectnessEvaluator(), good, ctx).verdict == "pass"
    wrong = edit_call(good, "verify_pan", args={"dob": "1992-07-15"})
    assert "dob" in one(ArgumentCorrectnessEvaluator(), wrong, ctx).detail


def test_tu4_grounding(suite):
    good = load("KYC-GLD-001")
    res = one(GroundingEvaluator(), good, ctx_for(suite, good))
    assert res.verdict == "pass" and res.severity == "S1"
    invented = edit_call(good, "compute_risk_score", args={"applicant_id": "APP-777"})
    res = one(GroundingEvaluator(), invented, ctx_for(suite, invented))
    assert res.verdict == "fail" and "APP-777" in res.detail
    guessed = edit_call(good, "verify_pan", args={"dob": "1990-01-01"})
    assert "1990-01-01" in one(GroundingEvaluator(), guessed, ctx_for(suite, guessed)).detail


def test_tu4_customer_text_is_a_source(suite):
    good = load("KYC-GLD-001")
    said = good.model_copy(update={"user_turns": ["My application is APL-123"]})
    used = edit_call(said, "finalize_application", args={"application_id": "APL-123"})
    assert one(GroundingEvaluator(), used, ctx_for(suite, used)).verdict == "pass"


def test_tu5_error_handling(suite):
    flt = load("KYC-FLT-021")
    ctx = ctx_for(suite, flt)
    assert one(ErrorHandlingEvaluator(), flt, ctx).verdict == "pass"
    assert "attempt 4" in one(ErrorHandlingEvaluator(), edit_call(flt, "verify_pan", attempt=4), ctx).detail
    drift = flt.model_copy(update={"steps": list(flt.steps)})
    calls = [i for i, s in enumerate(drift.steps) if s.tool_call and s.tool_call.tool == "verify_pan"]
    second = drift.steps[calls[1]]
    drift.steps[calls[1]] = second.model_copy(
        update={"tool_call": second.tool_call.model_copy(update={"args": {**second.tool_call.args, "dob": "1988-11-03"}})}
    )
    assert "changed arguments" in one(ErrorHandlingEvaluator(), drift, ctx).detail
    assert one(ErrorHandlingEvaluator(), load("KYC-GLD-001"), ctx_for(suite, load("KYC-GLD-001"))).verdict == "skip"


def test_tu6_figures_parse_indian_notation():
    found = dict(figures("Bill ₹1,240.00, income 5 lakh, 2 crore, 91% match, on 2026-11-02 09:00 for REC-001 under v3"))
    assert {"1,240.00", "5 lakh", "2 crore", "91%"} <= set(found)
    assert 500000 in found["5 lakh"] and 0.91 in found["91%"] and 1240.0 in found["1,240.00"]
    assert not any(k.startswith(("001", "3", "2026", "09")) for k in found)


def test_tu6_reconciliation(suite):
    good = load("KYC-GLD-001")
    assert one(ReconciliationEvaluator(), good, ctx_for(suite, good)).verdict == "pass"
    wrong = with_reply(good, "Approved. Your risk score is 35.")
    res = one(ReconciliationEvaluator(), wrong, ctx_for(suite, wrong))
    assert res.verdict == "fail" and res.severity == "S1" and "35" in res.detail
    restated = set_output(good, "risk", explanation="Engine returned 22 (LOW); thresholds 40 / 70")
    assert one(ReconciliationEvaluator(), restated, ctx_for(suite, restated)).verdict == "pass"
