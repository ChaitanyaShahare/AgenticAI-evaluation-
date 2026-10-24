"""Run one catalogue case through the KYC graph (used by the M1 golden check now, and by the LangGraph adapter in WP4).

    final = run_case(trial_db, "KYC-GLD-001", run_id="r1", trial=1)
    final.state["decision"]   # {'status': 'APPROVED', 'reason_codes': []}

The trial database must be a private copy of the seed (the mocks write to it). The approval interrupt is answered by
the mock approver for the case (APPROVE / DENY / NO_RESPONSE from test_cases.approver_response).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.types import Command

from evalkit.config import load_env, load_eval_config
from projects.kyc_onboarding.contracts import SLICES
from projects.kyc_onboarding.sut.graph import SPECIALIST_MODULES, KYCRuntime, build_graph
from projects.kyc_onboarding.sut.lab import defects
from projects.kyc_onboarding.sut.llm import load_prompt, make_client, settings_for
from projects.kyc_onboarding.tools.mocks.handoff_tools import canned_state
from projects.kyc_onboarding.tools.mocks.screening_tools import pep_check, sanctions_screen
from projects.kyc_onboarding.tools.mocks.supervisor_tools import issue_approval_token
from projects.kyc_onboarding.tools.registry import ToolRegistry

PROMPTS = ("supervisor", "doc_extraction", "identity", "screening", "risk")


SPECIALIST_OF = {"DOC": "doc_extraction", "IDV": "identity", "SCR": "screening", "RSK": "risk"}


@dataclass
class CaseRun:
    case_id: str
    state: dict[str, Any]
    registry: ToolRegistry
    interrupts: int
    mode: str = "graph"  # graph (L2 / L3 / L1 supervisor) | specialist (L1 specialist only)

    @property
    def end_state_params(self) -> dict[str, Any]:
        """Parameters for project.yaml end_state_query."""
        return {"application_id": self.registry.ctx.application_id}


def _run_start(reg: ToolRegistry, cfg) -> dict[str, Any]:
    ctx = reg.ctx
    return {
        "kind": "run_start",
        "case_id": ctx.case_id,
        "run_id": ctx.run_id,
        "trial": ctx.trial,
        "models": {"supervisor": cfg.models.supervisor, "specialist": cfg.models.specialist},
        "effort": {"supervisor": cfg.effort.supervisor, "specialist": cfg.effort.specialist},
        "prompt_hashes": {p: load_prompt(p)[1] for p in PROMPTS},
        "as_of": cfg.determinism.as_of,
        "seed": cfg.determinism.seed,
        # what the system was given at the start; evaluators use it as a grounding source (TU-4)
        "inputs": {"application_id": ctx.application_id, "applicant_id": ctx.applicant_id},
    }


def initial_state(reg: ToolRegistry, cfg) -> dict[str, Any]:
    ctx = reg.ctx
    form_row = ctx.one(
        "SELECT customer_type, product, nationality, occupation, income_band FROM applicants WHERE applicant_id = ?", (ctx.applicant_id,)
    )
    docs = [
        r["doc_id"]
        for r in ctx.all("SELECT doc_id FROM case_documents WHERE case_id = ? AND uploaded_at_turn = 1 ORDER BY doc_id", (ctx.case_id,))
    ]
    state: dict[str, Any] = {
        "application_id": ctx.application_id,
        "applicant_id": ctx.applicant_id,
        "form": dict(form_row) if form_row else {},
        "customer_messages": [ctx.first_turn] if ctx.first_turn else [],
        "documents": docs,
        "profile": None,
        "identity": None,
        "screening": None,
        "risk": None,
        "contract_errors": {},
        "delegations": {},
        "supervisor_steps": 0,
        "approval": {"requested": False},
        "record_id": None,
        "edd_case_id": None,
        "decision": None,
        "done": False,
        "replies": [],
        "events": [_run_start(reg, cfg)],
    }
    state["events"][0]["inputs"].update(form=state["form"], documents=docs)
    canned = canned_state(ctx)  # L1 supervisor cases start from a full canned state (STUB-05/06/08)
    if canned:
        for k in ("profile", "identity", "screening", "risk"):
            state[k] = canned.get(k)
        state["events"].append(
            {
                "kind": "canned_state",
                "profile_ids": ctx.profile_ids,
                "state": {k: state[k] for k in ("profile", "identity", "screening", "risk")},
            }
        )
    return state


def build_runtime(reg: ToolRegistry, client=None, cfg=None) -> KYCRuntime:
    cfg = cfg or load_eval_config()
    ctx = reg.ctx

    def new_documents() -> list[str]:
        return [
            r["doc_id"]
            for r in ctx.all(
                "SELECT doc_id FROM case_documents WHERE case_id = ? AND uploaded_at_turn = ? ORDER BY doc_id", (ctx.case_id, ctx.turn)
            )
        ]

    return KYCRuntime(
        registry=reg,
        client=client or make_client(),
        supervisor=settings_for(cfg, "supervisor"),
        specialist=settings_for(cfg, "specialist"),
        max_steps=cfg.max_steps_per_run,
        max_delegations=1 + cfg.max_bounces_per_specialist,
        hit_min=float(ctx.config("screening_hit_threshold")),
        near_min=float(ctx.config("screening_near_threshold")),
        doc_quality_min=float(ctx.config("doc_quality_threshold")),
        lists_version=ctx.config("lists_version"),
        policy_version=cfg.determinism.risk_policy_version,
        new_documents=new_documents if ctx.case_id else None,
        lab=defects.active(),
    )


# ---------------------------------------------------------------- L1 specialist cases
def fixture_profile(reg: ToolRegistry) -> dict[str, Any]:
    """The profile an L1 identity / screening / risk case starts from: what a correct document agent would extract from the
    applicant's own documents (so 'R K SHARMA' initials on APP-050's PAN card, and no PAN for APP-051)."""
    ctx = reg.ctx
    docs = ctx.all(
        "SELECT doc_id, doc_type FROM documents WHERE applicant_id = ? AND has_injection = 0 ORDER BY doc_id", (ctx.applicant_id,)
    )
    fields = lambda d: {r["field_name"]: r["field_value"] for r in ctx.all("SELECT * FROM document_fields WHERE doc_id = ?", (d,))}  # noqa: E731
    pan_doc = next((d["doc_id"] for d in docs if d["doc_type"] == "PAN_CARD"), None)
    proof = next((d["doc_id"] for d in docs if d["doc_type"] in ("UTILITY_BILL", "PASSPORT", "AADHAAR_MASKED")), None)
    name_doc = pan_doc or proof
    f_name, f_proof = (fields(name_doc) if name_doc else {}), (fields(proof) if proof else {})
    return {
        "full_name": f_name.get("full_name"),
        "dob": f_name.get("dob"),
        "pan": f_name.get("pan") if pan_doc else None,
        "aadhaar_last4": None,
        "address": f_proof.get("address"),
        "nationality": None,
        "doc_types": sorted({d["doc_type"] for d in docs}),
        "quality_flags": [],
        "missing_fields": [],
        "injection_suspected": False,
        "field_confidence": {},
        "field_sources": {k: v for k, v in (("full_name", name_doc), ("address", proof)) if v},
    }


def _l1_note(ctx) -> str:
    raw = ctx.one("SELECT customer_turns FROM test_cases WHERE case_id = ?", (ctx.case_id,))["customer_turns"] or ""
    return raw.split("—", 1)[1].strip() if "—" in raw else "L1 isolation run"


def _specialist_inputs(reg: ToolRegistry, agent: str) -> Any:
    ctx = reg.ctx
    if agent == "doc_extraction":
        return [
            r["doc_id"]
            for r in ctx.all("SELECT doc_id FROM case_documents WHERE case_id = ? AND uploaded_at_turn = 1 ORDER BY doc_id", (ctx.case_id,))
        ]
    profile = fixture_profile(reg)
    if agent == "identity":
        return profile
    form = ctx.one("SELECT nationality FROM applicants WHERE applicant_id = ?", (ctx.applicant_id,))
    subject = {"full_name": profile["full_name"], "dob": profile["dob"], "nationality": form["nationality"] if form else None}
    if agent == "screening":
        return subject
    # risk: upstream screening is prepared by the harness directly against the mocks (not part of the agent under test)
    refs = [
        sanctions_screen(ctx, subject["full_name"], subject["dob"], subject["nationality"] or "IN")["screening_ref"],
        pep_check(ctx, subject["full_name"], subject["dob"])["screening_ref"],
    ]
    return {"applicant_id": ctx.applicant_id, "product": "SAVINGS", "screening_refs": refs}


def run_specialist_case(reg: ToolRegistry, agent: str, rt: KYCRuntime, cfg) -> dict[str, Any]:
    inputs = _specialist_inputs(reg, agent)
    res = SPECIALIST_MODULES[agent].run(rt, inputs, _l1_note(reg.ctx))
    events = [_run_start(reg, cfg), {"kind": "l1_task", "agent": agent, "inputs": inputs}, *res.events]
    if res.violations:
        events.append({"kind": "contract", "agent": agent, "violations": res.violations})
    events.append({"kind": "agent_result", "agent": agent, "stop": res.stop, "contract": res.contract, "submitted": res.submitted})
    return {
        "application_id": reg.ctx.application_id,
        "applicant_id": reg.ctx.applicant_id,
        SLICES[agent]: res.contract,
        "contract_errors": {agent: res.violations},
        "replies": [],
        "customer_messages": [],
        "decision": None,
        "events": events,
    }


def run_case(db_path: Path, case_id: str, run_id: str = "adhoc", trial: int = 1, client=None, cfg=None, max_interrupts: int = 3) -> CaseRun:
    load_env()
    cfg = cfg or load_eval_config()
    reg = ToolRegistry.for_case(db_path, case_id, run_id=run_id, trial=trial)
    rt = build_runtime(reg, client=client, cfg=cfg)
    row = reg.ctx.one("SELECT level, primary_agent FROM test_cases WHERE case_id = ?", (case_id,))
    if row["level"] == "L1" and row["primary_agent"] in SPECIALIST_OF:
        return CaseRun(case_id, run_specialist_case(reg, SPECIALIST_OF[row["primary_agent"]], rt, cfg), reg, 0, mode="specialist")
    graph = build_graph(rt)
    config = {"configurable": {"thread_id": f"{run_id}:{case_id}:{trial}"}, "recursion_limit": 200}
    result = graph.invoke(initial_state(reg, cfg), config)
    interrupts = 0
    while "__interrupt__" in result and interrupts < max_interrupts:
        interrupts += 1
        decision = reg.ctx.approver_response or "NO_RESPONSE"
        token = issue_approval_token(reg.ctx, decision) if decision in ("APPROVE", "DENY") else None
        result = graph.invoke(Command(resume={"decision": decision, "token": token}), config)
    return CaseRun(case_id, graph.get_state(config).values, reg, interrupts)
