"""Agent slicer and AG-1 … AG-6 for each of the five agents, plus the full grader on the recordings."""

from __future__ import annotations

import pytest

from evalkit.evaluators.agent.arguments import AgentArgumentsEvaluator
from evalkit.evaluators.agent.contract import AgentContractEvaluator
from evalkit.evaluators.agent.efficiency import AgentEfficiencyEvaluator
from evalkit.evaluators.agent.guardrails import GuardrailCoverageEvaluator
from evalkit.evaluators.agent.slicer import slice_agents
from evalkit.evaluators.agent.task_success import AgentTaskSuccessEvaluator
from evalkit.evaluators.agent.tool_selection import AgentToolSelectionEvaluator
from evalkit.evaluators.grader import grade
from evalkit.schema import Step
from tests.unit.evaluators.conftest import ctx_for, drop_tool, edit_call, load, set_output, with_end_state

AGENTS = ["supervisor", "doc_extraction", "identity", "screening", "risk"]


def slices(suite, traj, **kw):
    ctx = ctx_for(suite, traj, **kw)
    return slice_agents(traj, ctx), ctx


def test_slicer_gives_one_slice_per_agent(suite):
    sl, _ = slices(suite, load("KYC-GLD-001"))
    assert list(sl) == AGENTS
    assert [c.tool for c in sl["screening"].tool_calls] == ["sanctions_screen", "pep_check"]
    assert sl["identity"].delegations == 1 and not sl["identity"].stubbed
    assert sl["supervisor"].final_output["action"] == "finalize"
    hnd, _ = slices(suite, load("KYC-HND-109"))
    assert [a for a, s in hnd.items() if s.stubbed] == AGENTS[1:]
    assert hnd["screening"].violations and "SLICE-1" in hnd["screening"].violations[0].content


def test_ag1_supervisor_is_graded_on_the_outcome(suite):
    good = load("KYC-GLD-001")
    sl, ctx = slices(suite, good)
    assert AgentTaskSuccessEvaluator().evaluate_agent(sl["supervisor"], good, ctx).verdict == "pass"
    bad = with_end_state(good, status="REJECTED")
    res = AgentTaskSuccessEvaluator().evaluate_agent(sl["supervisor"], bad, ctx)
    assert res.verdict == "fail" and res.agent == "supervisor" and res.metric == "AG-1"


def test_ag1_specialist_against_expected_output(suite):
    flt = load("KYC-FLT-021")
    sl, ctx = slices(suite, flt)
    assert AgentTaskSuccessEvaluator().evaluate_agent(sl["identity"], flt, ctx).verdict == "pass"  # the shipped expectation
    case = suite.cases["KYC-FLT-021"]
    unstated = case.model_copy(update={"expected": {**case.expected, "agent_outputs": {}}})
    assert AgentTaskSuccessEvaluator().evaluate_agent(sl["identity"], flt, ctx_for(suite, flt, case=unstated)).verdict == "skip"
    exp = {**case.expected, "agent_outputs": {"identity": {"pan_status": "UNAVAILABLE", "overall": "unverified"}}}
    ctx = ctx_for(suite, flt, case=case.model_copy(update={"expected": exp}))
    assert AgentTaskSuccessEvaluator().evaluate_agent(sl["identity"], flt, ctx).verdict == "pass"
    upgraded = set_output(flt, "identity", overall="VERIFIED")
    sl2, _ = slices(suite, upgraded)
    res = AgentTaskSuccessEvaluator().evaluate_agent(sl2["identity"], upgraded, ctx)
    assert res.verdict == "fail" and "overall" in res.detail and res.severity == "S1"


def test_ag2_tool_selection_and_allow_list(suite):
    good = load("KYC-GLD-001")
    sl, ctx = slices(suite, good)
    for a in AGENTS:
        assert AgentToolSelectionEvaluator().evaluate_agent(sl[a], ctx).score == 1.0, a
        assert AgentToolSelectionEvaluator().allow_list(sl[a], ctx).verdict == "pass", a
    sl, ctx = slices(suite, drop_tool(good, "pep_check"))
    assert "missing pep_check" in AgentToolSelectionEvaluator().evaluate_agent(sl["screening"], ctx).detail
    wrong = edit_call(good, "verify_pan", agent="screening")
    sl, ctx = slices(suite, wrong)
    res = AgentToolSelectionEvaluator().allow_list(sl["screening"], ctx)
    assert res.verdict == "fail" and res.metric == "TU-7" and res.severity == "S1"


def test_ag3_arguments(suite):
    good = load("KYC-GLD-001")
    sl, ctx = slices(suite, good)
    for a in AGENTS:
        assert AgentArgumentsEvaluator().evaluate_agent(sl[a], good, ctx).verdict == "pass", a
    bad = edit_call(good, "compute_risk_score", args={"applicant_id": "APP-777"})
    sl, ctx = slices(suite, bad)
    res = AgentArgumentsEvaluator().evaluate_agent(sl["risk"], bad, ctx)
    assert res.verdict == "fail" and res.score == 0.5 and "APP-777" in res.detail


def test_ag4_contract(suite):
    good = load("KYC-GLD-001")
    sl, ctx = slices(suite, good)
    for a in AGENTS:
        assert AgentContractEvaluator().evaluate_agent(sl[a], ctx).verdict == "pass", a
    invalid = set_output(good, "identity", overall="PROBABLY_FINE")
    sl, ctx = slices(suite, invalid)
    assert "overall" in AgentContractEvaluator().evaluate_agent(sl["identity"], ctx).detail
    flagged = good.model_copy(update={"steps": [*good.steps, Step(index=999, kind="contract", agent="risk", content="AG-4: tier missing")]})
    sl, ctx = slices(suite, flagged)
    assert "tier missing" in AgentContractEvaluator().evaluate_agent(sl["risk"], ctx).detail


def test_ag5_reports_missing_guardrails(suite, engine_policy):
    good = load("KYC-GLD-001")
    sl, ctx = slices(suite, good, policy=None)
    assert GuardrailCoverageEvaluator().evaluate_agent(sl["risk"], ctx).verdict == "skip"
    sl, ctx = slices(suite, good)  # the KYC policy has a guardrail for every agent
    assert all(GuardrailCoverageEvaluator().evaluate_agent(sl[a], ctx) is None for a in AGENTS)
    sl, ctx = slices(suite, good, policy=engine_policy)
    assert GuardrailCoverageEvaluator().evaluate_agent(sl["risk"], ctx) is None  # the engine's AG-5 rule covers risk
    assert "no AG-5 guardrail" in GuardrailCoverageEvaluator().evaluate_agent(sl["screening"], ctx).detail


def test_ag6_efficiency_counts_retries(suite):
    sl, _ = slices(suite, load("KYC-FLT-021"))
    res = AgentEfficiencyEvaluator().evaluate_agent(sl["identity"])
    assert res.score == 0.6 and "2 retries" in res.detail and res.severity == "S3"


@pytest.mark.parametrize("name", ["KYC-GLD-001", "KYC-HND-109", "KYC-FLT-021", "live/KYC-GLD-001"])
def test_grader_has_no_failures_or_errors_on_recordings(suite, name):
    graded = grade(suite, [load(name)])
    bad = [f"{c.metric} {c.agent}: {c.detail}" for c in graded.results[0].checks if c.verdict in ("fail", "error")]
    assert bad == []
    assert graded.results[0].passed


def test_grader_builds_five_scorecards_for_an_l3_run(suite):
    graded = grade(suite, [load("KYC-GLD-001")])
    assert list(graded.scorecards) == AGENTS
    for card in graded.scorecards.values():
        assert {"AG-2", "AG-3", "AG-4", "AG-6", "TU-7"} <= set(card["metrics"]) and card["gate"] == 1


def test_grader_records_evaluator_errors(suite, monkeypatch):
    from evalkit.evaluators.trajectory.end_state import EndStateEvaluator

    monkeypatch.setattr(EndStateEvaluator, "evaluate", lambda self, t, c: 1 / 0)
    res = grade(suite, [load("KYC-GLD-001")]).results[0]
    err = next(c for c in res.checks if c.metric == "TR-1" and c.rule is None)
    assert err.verdict == "error" and "ZeroDivisionError" in err.detail
