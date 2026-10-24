"""KYC onboarding graph: an explicit LangGraph StateGraph with a Supervisor and four specialists.

    START → supervisor ─┬─ delegate ─┬─ doc_extraction ─┐
                        │            ├─ identity ───────┤
                        │            ├─ screening ──────┤→ supervisor
                        │            ├─ risk ───────────┤
                        │            └─ (L2 stub) ──────┘
                        ├─ request_info / escalate / approval (interrupt) / create_record / corporate → supervisor
                        └─ finalize → END (or back to supervisor if finalizing failed)

Every specialist returns control to the Supervisor, so each hand-off is its own step in the trajectory. Model IDs and
effort come from configs/eval.yaml. build_graph() is the project entrypoint named in project.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from projects.kyc_onboarding.contracts import SLICES, validate_slice
from projects.kyc_onboarding.sut.agents import doc_extraction, identity, risk, screening, tool_event
from projects.kyc_onboarding.sut.approval import approval_node
from projects.kyc_onboarding.sut.corporate_stub import corporate_node
from projects.kyc_onboarding.sut.llm import ModelSettings
from projects.kyc_onboarding.sut.router import route, route_after_delegate, route_after_finalize, supervisor_node
from projects.kyc_onboarding.sut.state import KYCState

SPECIALIST_MODULES = {"doc_extraction": doc_extraction, "identity": identity, "screening": screening, "risk": risk}
DEFAULT_CLOSING = "Thank you. We have recorded the outcome of your application and will contact you with any next steps."


@dataclass
class KYCRuntime:
    """Everything the nodes need for one run. Built by projects/kyc_onboarding/sut/run.py."""

    registry: Any  # ToolRegistry for this case and trial
    client: Any  # anthropic.Anthropic (or a scripted stand-in in tests)
    supervisor: ModelSettings
    specialist: ModelSettings
    max_steps: int
    max_delegations: int
    hit_min: float
    near_min: float
    doc_quality_min: float
    lists_version: str
    policy_version: str
    new_documents: Any = None  # callable() -> doc IDs that became visible after a customer reply
    lab: frozenset[str] = frozenset()  # seeded-defect switches (sut/lab/defects.py); empty except in `evalkit lab`

    @property
    def application_id(self) -> str:
        return self.registry.ctx.application_id


# ---------------------------------------------------------------- action nodes
def _call(rt: KYCRuntime, tool: str, args: dict[str, Any]):
    out = rt.registry.call("supervisor", tool, args)
    return out, [tool_event(out, "supervisor")]


def delegate_node(rt: KYCRuntime, state: dict[str, Any]) -> dict[str, Any]:
    action = state["next_action"]
    target = action["target"]
    counts = dict(state.get("delegations") or {})
    counts[target] = counts.get(target, 0) + 1
    out, events = _call(rt, f"transfer_to_{target}", {"reason": (action.get("reason") or "next step")[:300]})
    events.append({"kind": "handoff", "agent": "supervisor", "to": target, "status": (out.result or {}).get("status")})
    update: dict[str, Any] = {"delegations": counts, "events": events, "active_specialist": None}
    if out.status == "ok" and out.result.get("status") == "STUB":  # L2: canned contract instead of the real agent
        contract, violations = validate_slice(target, out.result["contract"])
        update[SLICES[target]] = contract
        update["contract_errors"] = {**(state.get("contract_errors") or {}), target: violations}
        update["last_result"] = {"action": "delegate", "agent": target, "contract_valid": contract is not None, "violations": violations}
        if violations:
            events.append({"kind": "contract", "agent": target, "violations": violations})
        events.append({"kind": "agent_result", "agent": target, "stop": "stub", "contract": contract, "submitted": out.result["contract"]})
    elif out.status == "ok":
        update["active_specialist"] = target
    else:
        update["last_result"] = {"action": "delegate", "agent": target, "error": out.result}
    return update


def _specialist_inputs(state: dict[str, Any], target: str) -> tuple[Any, str | None]:
    p, form = state.get("profile"), state.get("form") or {}
    if target == "doc_extraction":
        return list(dict.fromkeys(state.get("documents") or [])), None
    if p is None:
        return None, "no applicant profile in state yet"
    if target == "identity":
        return p, None
    if target == "screening":
        return {"full_name": p.get("full_name"), "dob": p.get("dob"), "nationality": p.get("nationality") or form.get("nationality")}, None
    refs = (state.get("screening") or {}).get("screening_refs") or []
    return {"applicant_id": state.get("applicant_id"), "product": form.get("product") or "SAVINGS", "screening_refs": refs}, None


def specialist_node(rt: KYCRuntime, target: str, state: dict[str, Any]) -> dict[str, Any]:
    inputs, missing = _specialist_inputs(state, target)
    reason = (state.get("next_action") or {}).get("reason") or ""
    if missing:
        violations = [f"precondition: {missing}"]
        return {
            SLICES[target]: None,
            "active_specialist": None,
            "contract_errors": {**(state.get("contract_errors") or {}), target: violations},
            "last_result": {"action": "delegate", "agent": target, "contract_valid": False, "violations": violations},
            "events": [{"kind": "contract", "agent": target, "violations": violations}],
        }
    res = SPECIALIST_MODULES[target].run(rt, inputs, reason)
    events = list(res.events)
    if res.violations:
        events.append({"kind": "contract", "agent": target, "violations": res.violations})
    events.append({"kind": "agent_result", "agent": target, "stop": res.stop, "contract": res.contract, "submitted": res.submitted})
    return {
        SLICES[target]: res.contract,
        "active_specialist": None,
        "contract_errors": {**(state.get("contract_errors") or {}), target: res.violations},
        "last_result": {
            "action": "delegate",
            "agent": target,
            "contract_valid": res.contract is not None,
            "agent_stop": res.stop,
            "violations": res.violations,
            **({"agent_note": res.note} if res.note else {}),
        },
        "events": events,
    }


def request_info_node(rt: KYCRuntime, state: dict[str, Any]) -> dict[str, Any]:
    action = state["next_action"]
    question = action.get("message_to_customer") or "Could you please provide the missing information?"
    fields = action.get("fields") or ["information"]
    out, events = _call(
        rt, "request_customer_info", {"fields": fields[:10], "reason": (action.get("reason") or "information needed")[:300]}
    )
    update: dict[str, Any] = {"replies": [question], "events": [{"kind": "message", "agent": "supervisor", "content": question}, *events]}
    reply = (out.result or {}).get("customer_reply") if out.status == "ok" else None
    new_docs = list(rt.new_documents()) if (reply and rt.new_documents) else []
    if reply:
        update["customer_messages"] = [reply]
        events.append({"kind": "user", "content": reply, "new_documents": new_docs})
    if new_docs:
        update["documents"] = new_docs
    update["last_result"] = {
        "action": "request_info",
        "status": (out.result or {}).get("status", out.status),
        "customer_reply": reply,
        "new_documents": new_docs,
    }
    return update


def escalate_node(rt: KYCRuntime, state: dict[str, Any]) -> dict[str, Any]:
    action = state["next_action"]
    out, events = _call(rt, "escalate_to_edd", {"application_id": rt.application_id, "reason_codes": action.get("reason_codes") or []})
    update = {"events": events, "last_result": {"action": "escalate_edd", "status": out.status, "result": out.result}}
    if out.status == "ok":
        update["edd_case_id"] = out.result.get("edd_case_id")
    return update


def create_record_node(rt: KYCRuntime, state: dict[str, Any]) -> dict[str, Any]:
    token = (state.get("approval") or {}).get("token") or "NO_TOKEN"  # from the approver step only (A1); never from the model
    out, events = _call(rt, "create_customer_record", {"application_id": rt.application_id, "approval_token": token})
    update = {"events": events, "last_result": {"action": "create_record", "status": out.status, "result": out.result}}
    if out.status == "ok":
        update["record_id"] = out.result.get("record_id")
    return update


def finalize_node(rt: KYCRuntime, state: dict[str, Any]) -> dict[str, Any]:
    action = state["next_action"]
    if not action.get("status"):
        return {"last_result": {"action": "finalize", "error": "finalize needs a status"}, "done": False}
    out, events = _call(
        rt,
        "finalize_application",
        {"application_id": rt.application_id, "status": action["status"], "reason_codes": action.get("reason_codes") or []},
    )
    if out.status != "ok":
        return {"events": events, "done": False, "last_result": {"action": "finalize", "status": out.status, "result": out.result}}
    message = action.get("message_to_customer") or DEFAULT_CLOSING
    return {
        "events": [*events, {"kind": "message", "agent": "supervisor", "content": message, "final": True}],
        "replies": [message],
        "decision": {"status": action["status"], "reason_codes": action.get("reason_codes") or []},
        "done": True,
        "last_result": {"action": "finalize", "status": "ok"},
    }


# ---------------------------------------------------------------- graph
def build_graph(rt: KYCRuntime, checkpointer=None):
    g = StateGraph(KYCState)
    g.add_node("supervisor", lambda s: supervisor_node(rt, s))
    g.add_node("delegate", lambda s: delegate_node(rt, s))
    for name in SPECIALIST_MODULES:
        g.add_node(name, lambda s, _n=name: specialist_node(rt, _n, s))
        g.add_edge(name, "supervisor")
    g.add_node("request_info", lambda s: request_info_node(rt, s))
    g.add_node("escalate", lambda s: escalate_node(rt, s))
    g.add_node("approval", approval_node)
    g.add_node("create_record", lambda s: create_record_node(rt, s))
    g.add_node("corporate", lambda s: corporate_node(rt, s))
    g.add_node("finalize", lambda s: finalize_node(rt, s))

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        route,
        {
            **{n: n for n in ("delegate", "request_info", "escalate", "approval", "create_record", "corporate", "finalize")},
            "supervisor": "supervisor",
        },
    )
    g.add_conditional_edges("delegate", route_after_delegate, {**{n: n for n in SPECIALIST_MODULES}, "supervisor": "supervisor"})
    for n in ("request_info", "escalate", "approval", "create_record", "corporate"):
        g.add_edge(n, "supervisor")
    g.add_conditional_edges("finalize", route_after_finalize, {"end": END, "supervisor": "supervisor"})
    return g.compile(checkpointer=checkpointer or InMemorySaver())
