"""Hand-off tools and L2 stub behaviour.

transfer_to_<agent> records the hand-off. When the case carries an L2 stub profile for that agent (agent_stubs),
the stub's canned output contract is returned instead of running the specialist (status STUB); otherwise the
graph runs the real specialist (status DELEGATED). attempt_no counts delegations to the same agent in the run,
so a stub can vary by attempt (0 = every attempt).
"""

from __future__ import annotations

import json
from typing import Any

from projects.kyc_onboarding.tools.mocks.db import ToolContext

SPECIALISTS = ("doc_extraction", "identity", "screening", "risk")
CORPORATE_GUIDANCE = (
    "We can only open accounts for individual customers in this channel. "
    "Please contact our corporate banking team to open an account for your organisation."
)


def stub_contract(ctx: ToolContext, agent: str, attempt: int) -> Any | None:
    if not ctx.profile_ids:
        return None
    marks = ",".join("?" * len(ctx.profile_ids))
    rows = ctx.all(
        f"SELECT attempt_no, contract_json FROM agent_stubs WHERE agent = ? AND profile_id IN ({marks})", (agent, *ctx.profile_ids)
    )
    exact = [r for r in rows if r["attempt_no"] == attempt] or [r for r in rows if r["attempt_no"] == 0]
    return json.loads(exact[0]["contract_json"]) if exact else None


def canned_state(ctx: ToolContext) -> dict[str, Any] | None:
    """L1 supervisor cases (STUB-05 / 06 / 08): the full state the supervisor starts from."""
    return stub_contract(ctx, "state", 1)


def _transfer(ctx: ToolContext, agent: str) -> dict[str, Any]:
    attempt = ctx.next_seq(f"handoff:{agent}")
    contract = stub_contract(ctx, agent, attempt)
    if contract is not None:
        if agent == "risk" and isinstance(contract, dict) and contract.get("status") == "OK" and ctx.application_id:
            # the stub stands in for the engine call, so it records the engine's result like compute_risk_score would
            ctx.write(
                "UPDATE applications SET risk_score = ?, risk_tier = ?, updated_at = ? WHERE application_id = ?",
                (contract.get("score"), contract.get("tier"), ctx.now(), ctx.application_id),
            )
        return {"status": "STUB", "agent": agent, "contract": contract}
    return {"status": "DELEGATED", "agent": agent}


def transfer_to_doc_extraction(ctx: ToolContext, reason: str) -> dict[str, Any]:
    return _transfer(ctx, "doc_extraction")


def transfer_to_identity(ctx: ToolContext, reason: str) -> dict[str, Any]:
    return _transfer(ctx, "identity")


def transfer_to_screening(ctx: ToolContext, reason: str) -> dict[str, Any]:
    return _transfer(ctx, "screening")


def transfer_to_risk(ctx: ToolContext, reason: str) -> dict[str, Any]:
    return _transfer(ctx, "risk")


def route_to_corporate_stub(ctx: ToolContext, reason: str) -> dict[str, Any]:
    return {"status": "ROUTED", "channel": "CORPORATE", "message": CORPORATE_GUIDANCE}
