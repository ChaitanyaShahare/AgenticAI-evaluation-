"""Identity verification agent (AG-IDV): verify_pan → ckyc_lookup → check_address_proof into state.identity.

Model: builds the arguments from the profile, retries a failed call at most twice, never invents a PAN.
Code: derives the contract from the registry answers — the agent reports a match, it never decides one, so a mismatch
can never be upgraded (requirement sheet row 6). A failed or missing call leaves the check UNAVAILABLE / UNVERIFIED.
"""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.contracts import validate_slice
from projects.kyc_onboarding.sut.agents import Executor, SpecialistResult
from projects.kyc_onboarding.sut.lab.defects import LAB4_MAX_ATTEMPTS
from projects.kyc_onboarding.sut.llm import dumps, load_prompt, run_tool_loop

AGENT = "identity"
FINISH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["notes"],
    "properties": {"notes": {"type": "string", "description": "What you checked and anything the Supervisor should know"}},
}


def build_identity(ex: Executor, profile: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    pan_ok = ex.ok("verify_pan")
    if not profile.get("pan"):
        pan_status, name_match, dob_match = "MISSING", None, None
        reasons.append("PAN_MISSING")
    elif pan_ok:
        r = pan_ok[-1].result
        pan_status, name_match, dob_match = r.get("status", "UNAVAILABLE"), r.get("name_match"), r.get("dob_match")
    else:
        pan_status, name_match, dob_match = "UNAVAILABLE", None, None
        reasons.append("PAN_CHECK_UNAVAILABLE" if ex.last("verify_pan") else "PAN_NOT_CHECKED")

    ck = ex.ok("ckyc_lookup")
    ckyc_no = ck[-1].result.get("ckyc_no") if ck else None
    ckyc_status = "UNAVAILABLE" if not ck else ("FOUND" if ckyc_no else "NOT_FOUND")

    ad = [o for o in ex.ok("check_address_proof") if o.result.get("status")]
    address_status = ad[-1].result["status"] if ad else "UNVERIFIED"  # empty / failed / not called → UNVERIFIED, never assumed MATCH
    if not ad:
        reasons.append("ADDRESS_CHECK_UNAVAILABLE" if ex.last("check_address_proof") else "ADDRESS_NOT_CHECKED")

    if pan_status == "VALID" and address_status == "MATCH":
        overall = "VERIFIED"
    elif pan_status == "MISMATCH" or address_status == "MISMATCH":
        overall = "MISMATCH"
    else:
        overall = "UNVERIFIED"
    return {
        "pan_status": pan_status,
        "name_match": name_match,
        "dob_match": dob_match,
        "ckyc_no": ckyc_no,
        "ckyc_status": ckyc_status,
        "address_status": address_status,
        "overall": overall,
        "reasons": reasons,
    }


def run(rt, profile: dict[str, Any], reason: str) -> SpecialistResult:
    system, _ = load_prompt("identity")
    ex = Executor(rt.registry, AGENT)
    proof = (profile.get("field_sources") or {}).get("address")
    task = dumps(
        {
            "task": "Verify the applicant's identity.",
            "supervisor_note": reason,
            "profile": {k: profile.get(k) for k in ("full_name", "dob", "pan", "address")},
            "address_proof_doc_id": proof,
        }
    )
    loop = run_tool_loop(
        rt.client, rt.specialist, AGENT, system, task, [rt.registry.specs[t] for t in rt.registry.tools_for(AGENT)], FINISH_SCHEMA, ex
    )
    events = list(loop.events)
    if "LAB-4" in rt.lab:  # LAB-4: keep retrying a failed verify_pan with the same arguments
        last = ex.last("verify_pan")
        while last and not ex.ok("verify_pan") and last.attempt < LAB4_MAX_ATTEMPTS:
            _, _, ev = ex("verify_pan", dict(last.args))
            events.append(ev)
            last = ex.last("verify_pan")
    contract, violations = validate_slice(AGENT, build_identity(ex, profile))
    if loop.stop != "finished":
        violations.append(f"AG-4: agent did not submit a result ({loop.stop}); contract built from the calls it made")
    return SpecialistResult(AGENT, contract, violations, events, loop.stop, loop.finish_input)
