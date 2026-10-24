"""Supervisor agent (AG-SUP): plans the onboarding, delegates in order, applies decision table D1–D10, talks to the customer.

Each turn the Supervisor reads a data-minimised brief of the state (PAN masked to the last 4) and returns one
SupervisorAction as structured output. The graph executes it. Identifiers and the approval token are filled in by code,
never by the model, so a token typed by the customer can never reach create_customer_record (KYC-ADV-036).
"""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.contracts import SupervisorAction
from projects.kyc_onboarding.sut.llm import dumps, load_prompt, structured_call

AGENT = "supervisor"


def _mask_pan(pan: str | None) -> str | None:
    return None if not pan else "******" + str(pan)[-4:]


def brief(state: dict[str, Any], rt) -> dict[str, Any]:
    """What the Supervisor sees. Stable key order (sorted on dump) keeps the prompt byte-stable between turns."""
    p = state.get("profile")
    profile = (
        None
        if p is None
        else {
            "full_name": p.get("full_name"),
            "dob": p.get("dob"),
            "pan": _mask_pan(p.get("pan")),
            "aadhaar_last4": p.get("aadhaar_last4"),
            "nationality": p.get("nationality"),
            "doc_types": p.get("doc_types"),
            "quality_flags": p.get("quality_flags"),
            "missing_fields": p.get("missing_fields"),
            "injection_suspected": p.get("injection_suspected"),
            "address_present": bool(p.get("address")),
        }
    )
    form = state.get("form") or {}
    return {
        "application_id": state.get("application_id"),
        "application_form": {k: form.get(k) for k in ("customer_type", "product", "nationality", "occupation", "income_band")},
        "customer_messages": state.get("customer_messages", []),
        "uploaded_documents": state.get("documents", []),
        "profile": profile,
        "identity": state.get("identity"),
        "screening": state.get("screening"),
        "risk": state.get("risk"),
        "contract_errors": state.get("contract_errors") or {},
        "delegations_so_far": state.get("delegations") or {},
        "max_delegations_per_specialist": rt.max_delegations,
        "approval": state.get("approval") or {"requested": False},
        "record_id": state.get("record_id"),
        "edd_case_id": state.get("edd_case_id"),
        "last_action_result": state.get("last_result"),
        "steps_used": state.get("supervisor_steps", 0),
        "steps_limit": rt.max_steps,
    }


def decide(rt, state: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    """One routing decision: (action dict or None, events, error)."""
    system, _ = load_prompt("supervisor")
    user = "Current state of the application (JSON):\n" + dumps(brief(state, rt)) + "\n\nDecide the single next action."
    parsed, ev, err = structured_call(rt.client, rt.supervisor, AGENT, system, user, SupervisorAction)
    if parsed is None:
        return None, [ev], err or "no structured output"
    action = parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed)
    return action, [ev, {"kind": "decision", "agent": AGENT, "action": action}], None
