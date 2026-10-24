"""LangGraph state of one KYC application.

One slice per specialist (profile / identity / screening / risk), written only by that specialist's node (SLICE-1).
`events` is the run log the adapter turns into a Trajectory (WP4): every LLM call, tool call, hand-off, interrupt,
guard and contract check is appended, never rewritten. `replies` holds what the Supervisor said to the customer.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class Approval(TypedDict, total=False):
    requested: bool
    decision: str | None  # APPROVE | DENY | NO_RESPONSE (from the approver step only)
    token: str | None  # issued by the approver; never taken from customer text (KYC-ADV-036)


class KYCState(TypedDict, total=False):
    # application in session
    application_id: str
    applicant_id: str
    form: dict[str, Any]  # application form: customer_type, product, nationality, occupation, income_band
    customer_messages: Annotated[list[str], operator.add]
    documents: Annotated[list[str], operator.add]  # uploaded document IDs, in upload order

    # specialist slices (contracts in projects/kyc_onboarding/contracts.py)
    profile: dict[str, Any] | None
    identity: dict[str, Any] | None
    screening: dict[str, Any] | None
    risk: dict[str, Any] | None
    contract_errors: dict[str, list[str]]  # agent -> violations of its last result

    # supervisor bookkeeping
    next_action: dict[str, Any] | None  # last SupervisorAction
    last_result: dict[str, Any] | None  # outcome of the last executed action, shown to the Supervisor
    delegations: dict[str, int]  # specialist -> hand-offs so far
    active_specialist: str | None  # set by the delegate node when a real specialist must run
    supervisor_steps: int
    approval: Approval
    record_id: str | None
    edd_case_id: str | None
    decision: dict[str, Any] | None  # {status, reason_codes} once finalized
    done: bool

    # trajectory material
    replies: Annotated[list[str], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
