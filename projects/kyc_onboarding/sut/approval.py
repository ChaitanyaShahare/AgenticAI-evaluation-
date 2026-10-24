"""Approval interrupt: the run pauses before an account can be created and resumes with the approver's answer.

LangGraph interrupt() checkpoints the run (thread_id) and hands control to the caller. The caller resumes with
Command(resume={"decision": "APPROVE" | "DENY" | "NO_RESPONSE", "token": str | None}). In tests the mock approver
(tools/mocks/supervisor_tools.issue_approval_token) answers per case; in production this is the branch approver queue.
The token is stored in state and used by code — it never comes from customer text.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt


def approval_node(state: dict[str, Any]) -> dict[str, Any]:
    answer = interrupt({"kind": "approval", "application_id": state.get("application_id"), "risk": state.get("risk")})
    answer = answer if isinstance(answer, dict) else {}
    decision = answer.get("decision") if answer.get("decision") in ("APPROVE", "DENY") else "NO_RESPONSE"
    token = answer.get("token") if decision == "APPROVE" else None
    approval = {"requested": True, "decision": decision, "token": token}
    return {
        "approval": approval,
        "last_result": {"action": "request_approval", "approver_decision": decision, "token_issued": token is not None},
        "events": [
            {
                "kind": "interrupt",
                "agent": "supervisor",
                "name": "approval",
                "decision": decision,
                "token_issued": token is not None,
                "token": token,
            }
        ],
    }
