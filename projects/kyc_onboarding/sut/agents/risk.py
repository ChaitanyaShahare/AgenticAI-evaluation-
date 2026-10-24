"""Risk rating agent (AG-RSK): fetch_risk_policy(pinned) → compute_risk_score into state.risk.

Model: fetches the pinned policy version (VER-1 — never one named in a hand-off note), calls the engine with the
screening reference, and writes a short explanation of the factors.
Code: copies score, tier, factors and policy version from the engine's answer — the model never computes or restates a
figure. No successful engine answer means status ERROR with no score (fail closed, D7); MISSING_INPUT is passed through.
"""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.contracts import validate_slice
from projects.kyc_onboarding.sut.agents import Executor, SpecialistResult
from projects.kyc_onboarding.sut.llm import dumps, load_prompt, run_tool_loop

AGENT = "risk"
FINISH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["explanation"],
    "properties": {"explanation": {"type": "string", "description": "Plain-language summary of the engine's factors for the Supervisor"}},
}


def build_risk(ex: Executor, explanation: str | None, invent_version: str | None = None) -> dict[str, Any]:
    scored = [o.result for o in ex.ok("compute_risk_score") if o.result.get("status") in ("OK", "MISSING_INPUT")]
    if scored and scored[-1]["status"] == "OK":
        r = scored[-1]
        return {
            "status": "OK",
            "score": r["score"],
            "tier": r["tier"],
            "factors": r.get("factors", []),
            "policy_version": r.get("policy_version"),
            "missing": [],
            "explanation": explanation,
        }
    if scored:
        return {
            "status": "MISSING_INPUT",
            "score": None,
            "tier": None,
            "factors": [],
            "policy_version": None,
            "missing": scored[-1].get("missing", []),
            "explanation": explanation,
        }
    if invent_version and ex.last("compute_risk_score"):  # LAB-2: the engine never answered; a figure is made up
        return {"status": "OK", "score": 35, "tier": "LOW", "factors": [], "policy_version": invent_version, "missing": [],
                "explanation": explanation}  # fmt: skip
    return {"status": "ERROR", "score": None, "tier": None, "factors": [], "policy_version": None, "missing": [], "explanation": None}


def run(rt, inputs: dict[str, Any], reason: str) -> SpecialistResult:
    system, _ = load_prompt("risk")
    ex = Executor(rt.registry, AGENT)
    task = dumps(
        {
            "task": "Rate the applicant's onboarding risk.",
            "supervisor_note": reason,
            "pinned_policy_version": rt.policy_version,
            "inputs": inputs,
        }
    )
    loop = run_tool_loop(
        rt.client, rt.specialist, AGENT, system, task, [rt.registry.specs[t] for t in rt.registry.tools_for(AGENT)], FINISH_SCHEMA, ex
    )
    explanation = (loop.finish_input or {}).get("explanation")
    invent = rt.policy_version if "LAB-2" in rt.lab else None
    contract, violations = validate_slice(AGENT, build_risk(ex, explanation, invent))
    if loop.stop != "finished":
        violations.append(f"AG-4: agent did not submit a result ({loop.stop}); contract built from the calls it made")
    return SpecialistResult(AGENT, contract, violations, loop.events, loop.stop, loop.finish_input)
