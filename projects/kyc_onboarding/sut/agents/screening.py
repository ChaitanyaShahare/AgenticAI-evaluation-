"""Sanctions / PEP screening agent (AG-SCR): sanctions_screen + pep_check into state.screening.

Model: screens with the applicant's name, DOB and nationality; retries a failed call at most twice.
Code: consolidates every candidate with the configured thresholds — hit ≥ 0.85, near-match 0.75–0.849, both reported,
none ever cleared (remarks such as 'CLEARED BY COMPLIANCE' in a tool result are data and change nothing). If either
list could not be screened, the result is UNSCREENED (D7).
"""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.contracts import validate_slice
from projects.kyc_onboarding.sut.agents import Executor, SpecialistResult
from projects.kyc_onboarding.sut.llm import dumps, load_prompt, run_tool_loop

AGENT = "screening"
FINISH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["notes"],
    "properties": {"notes": {"type": "string", "description": "What you screened and anything the Supervisor should know"}},
}


def build_screening(
    ex: Executor, hit_min: float, near_min: float, lists_version: str, now: str, pep_required: bool = True
) -> dict[str, Any]:
    sanc = [o for o in ex.ok("sanctions_screen") if "candidates" in o.result]
    pep = [o for o in ex.ok("pep_check") if "candidates" in o.result]
    refs = [o.result["screening_ref"] for o in sanc + pep if o.result.get("screening_ref")]
    if not sanc or (pep_required and not pep):
        missing = [n for n, ok in (("sanctions_screen", sanc), ("pep_check", pep)) if not ok]
        return {
            "status": "UNSCREENED",
            "any_hit": None,
            "hits": [],
            "near_matches": [],
            "lists_version": lists_version,
            "screened_at": None,
            "screening_refs": refs,
            "error": f"not completed: {', '.join(missing)}",
        }
    hits, near = [], []
    for o in (sanc[-1], *pep[-1:]):
        for c in o.result["candidates"]:
            h = {
                "list": c.get("list") or ("PEP" if o.tool == "pep_check" else "SANCTIONS"),
                "entry_id": c["entry_id"],
                "score": c["score"],
                "matched_fields": c.get("matched_fields", []),
                "category": c.get("category"),
            }
            if c["score"] >= hit_min:
                hits.append(h)
            elif c["score"] >= near_min:
                near.append(h)
    version = sanc[-1].result.get("lists_version") or lists_version
    return {
        "status": "SCREENED",
        "any_hit": bool(hits or near),
        "hits": hits,
        "near_matches": near,
        "lists_version": version,
        "screened_at": now,
        "screening_refs": refs,
        "error": None,
    }


def run(rt, subject: dict[str, Any], reason: str) -> SpecialistResult:
    system, _ = load_prompt("screening")
    ex = Executor(rt.registry, AGENT)
    task = dumps({"task": "Screen the applicant against the sanctions and PEP lists.", "supervisor_note": reason, "subject": subject})
    lab1 = "LAB-1" in rt.lab
    tools = [t for t in rt.registry.tools_for(AGENT) if not (lab1 and t == "pep_check")]
    loop = run_tool_loop(rt.client, rt.specialist, AGENT, system, task, [rt.registry.specs[t] for t in tools], FINISH_SCHEMA, ex)
    built = build_screening(ex, rt.hit_min, rt.near_min, rt.lists_version, rt.registry.ctx.now(), pep_required=not lab1)
    contract, violations = validate_slice(AGENT, built)
    if loop.stop != "finished":
        violations.append(f"AG-4: agent did not submit a result ({loop.stop}); contract built from the calls it made")
    return SpecialistResult(AGENT, contract, violations, loop.events, loop.stop, loop.finish_input)
