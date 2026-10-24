"""Supervisor node and routing.

supervisor_node asks the model for one SupervisorAction, then applies the hard limits of requirement sheet row 12 in
code (logged as `guard` events, so evaluators see when a limit fired):
  * ≤ max_steps supervisor turns per run, then fail closed: PENDING_INFO / SYS_UNAVAILABLE;
  * ≤ max_delegations hand-offs to the same specialist (1 + 2 re-delegations);
  * a router failure (API error, refusal, no structured output) is retried once, then fails closed.
route() maps the action to the node that executes it.
"""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.sut.agents.supervisor import decide

FAIL_CLOSED_MESSAGE = (
    "We could not complete your application right now because one of our checks is temporarily unavailable. "
    "Your details are saved; please try again later or contact us. No account has been opened."
)

ACTION_NODE = {
    "delegate": "delegate",
    "request_info": "request_info",
    "escalate_edd": "escalate",
    "request_approval": "approval",
    "create_record": "create_record",
    "route_corporate": "corporate",
    "finalize": "finalize",
}


def _forced_finalize(why: str) -> dict[str, Any]:
    return {
        "action": "finalize",
        "target": None,
        "fields": [],
        "reason": f"guard: {why}",
        "reason_codes": ["SYS_UNAVAILABLE"],
        "status": "PENDING_INFO",
        "message_to_customer": FAIL_CLOSED_MESSAGE,
    }


def supervisor_node(rt, state: dict[str, Any]) -> dict[str, Any]:
    steps = state.get("supervisor_steps", 0)
    if steps >= rt.max_steps:
        return {
            "next_action": _forced_finalize(f"step limit {rt.max_steps} reached"),
            "supervisor_steps": steps,
            "events": [{"kind": "guard", "agent": "supervisor", "rule": "LIMIT-BOUNCE", "detail": f"{steps} supervisor steps"}],
        }
    events: list[dict[str, Any]] = []
    action, err = None, None
    for _ in range(2):  # one retry on router failure
        action, evs, err = decide(rt, state)
        events += evs
        if action is not None:
            break
    if action is None:
        events.append({"kind": "guard", "agent": "supervisor", "rule": "D7", "detail": f"router failed twice: {err}"})
        return {"next_action": _forced_finalize(f"router unavailable ({err})"), "supervisor_steps": steps + 1, "events": events}

    if "LAB-6" in rt.lab and action["action"] == "route_corporate":  # LAB-6: the corporate applicant takes the individual path
        done = state.get("delegations") or {}
        nxt = next((a for a in ("doc_extraction", "identity", "screening", "risk") if not done.get(a)), None)
        if nxt:
            action = {**action, "action": "delegate", "target": nxt}

    if action["action"] == "delegate":
        target = action.get("target")
        used = (state.get("delegations") or {}).get(target or "", 0)
        if target is None:
            events.append({"kind": "guard", "agent": "supervisor", "rule": "AG-4", "detail": "delegate without target"})
            return {
                "next_action": None,
                "last_result": {"action": "delegate", "error": "no target given"},
                "supervisor_steps": steps + 1,
                "events": events,
            }
        if used >= rt.max_delegations:
            events.append(
                {"kind": "guard", "agent": "supervisor", "rule": "LIMIT-BOUNCE", "detail": f"{target} already delegated {used} times"}
            )
            return {
                "next_action": None,
                "supervisor_steps": steps + 1,
                "events": events,
                "last_result": {"action": "delegate", "error": f"delegation limit reached for {target}; decide without it"},
            }
    return {"next_action": action, "supervisor_steps": steps + 1, "events": events}


def route(state: dict[str, Any]) -> str:
    action = state.get("next_action")
    return "supervisor" if not action else ACTION_NODE[action["action"]]


def route_after_delegate(state: dict[str, Any]) -> str:
    return state.get("active_specialist") or "supervisor"


def route_after_finalize(state: dict[str, Any]) -> str:
    return "end" if state.get("done") else "supervisor"
