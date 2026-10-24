"""Corporate routing stub (decision D6): non-individual applicants are routed out of this channel with no KYC checks.

The Supervisor calls route_to_corporate_stub, then finalizes the application as REJECTED with reason
OUT_OF_SCOPE_CUSTOMER_TYPE and the corporate-channel guidance returned by the stub.
"""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.sut.agents import tool_event


def corporate_node(rt, state: dict[str, Any]) -> dict[str, Any]:
    action = state.get("next_action") or {}
    out = rt.registry.call("supervisor", "route_to_corporate_stub", {"reason": (action.get("reason") or "non-individual applicant")[:300]})
    return {
        "last_result": {"action": "route_corporate", "status": out.status, "result": out.result},
        "events": [tool_event(out, "supervisor")],
    }
