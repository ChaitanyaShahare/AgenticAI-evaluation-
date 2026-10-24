"""Output contracts of the KYC agents (requirement sheet row 10) and the Supervisor's action schema.

Every contract forbids unknown fields. validate_slice() applies the two rules the evaluators rely on:
  * SLICE-1 — keys outside the agent's own contract are stripped and reported; the valid rest is kept (STUB-07).
  * AG-4    — a contract with missing or invalid fields is rejected; the Supervisor must re-delegate (STUB-02).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ReasonCode = Literal[
    "SCREENING_HIT",
    "PEP_HIT",
    "HIGH_RISK",
    "DOC_MISSING",
    "DOC_LOW_QUALITY",
    "DOC_EXPIRED",
    "NAME_INCONSISTENT",
    "ID_MISMATCH",
    "PAN_INVALID",
    "OUT_OF_SCOPE_CUSTOMER_TYPE",
    "SYS_UNAVAILABLE",
    "APPROVER_DENIED",
    "APPROVAL_TIMEOUT",
    "INFO_MISSING",
    "RECORD_CREATION_FAILED",
]
QualityFlag = Literal["DOC_LOW_QUALITY", "DOC_UNSUPPORTED", "EXTRACTION_FAILED", "NAME_INCONSISTENT", "PAN_FORMAT_INVALID"]
FinalStatus = Literal["APPROVED", "PENDING_INFO", "PENDING_EDD", "REJECTED"]
Specialist = Literal["doc_extraction", "identity", "screening", "risk"]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileResult(_Contract):
    """state.profile — written only by the document extraction agent. Aadhaar is never stored beyond its last 4 digits."""

    full_name: str | None
    dob: str | None
    pan: str | None
    aadhaar_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    address: str | None
    nationality: str | None = None
    doc_types: list[str]
    quality_flags: list[QualityFlag] = []
    missing_fields: list[str] = []
    injection_suspected: bool = False
    field_confidence: dict[str, float] = {}
    field_sources: dict[str, str] = {}  # field -> doc_id (traceability, requirement sheet row 21)


class IdentityResult(_Contract):
    """state.identity — written only by the identity verification agent. Derived from registry answers, never re-judged."""

    pan_status: Literal["VALID", "INVALID", "MISMATCH", "UNAVAILABLE", "MISSING"]
    name_match: bool | None
    dob_match: bool | None
    ckyc_no: str | None
    ckyc_status: Literal["FOUND", "NOT_FOUND", "UNAVAILABLE"]
    address_status: Literal["MATCH", "MISMATCH", "EXPIRED", "NOT_ADDRESS_PROOF", "UNVERIFIED"]
    overall: Literal["VERIFIED", "MISMATCH", "UNVERIFIED"]
    reasons: list[str] = []


class Hit(_Contract):
    list: str
    entry_id: str
    score: float
    matched_fields: list[str] = []
    category: str | None = None


class ScreeningResult(_Contract):
    """state.screening — written only by the screening agent. Every hit and near-match is reported; none is ever cleared."""

    status: Literal["SCREENED", "UNSCREENED", "NEEDS_RETRY"]
    any_hit: bool | None
    hits: list[Hit]
    near_matches: list[Hit]
    lists_version: str
    screened_at: str | None
    screening_refs: list[str] = []
    error: str | None = None


class RiskResult(_Contract):
    """state.risk — written only by the risk agent. Score, tier and version are copied from the engine, never computed."""

    status: Literal["OK", "ERROR", "MISSING_INPUT"]
    score: int | None
    tier: Literal["LOW", "MEDIUM", "HIGH"] | None
    factors: list[str]
    policy_version: str | None
    missing: list[str] = []
    explanation: str | None = None


CONTRACTS: dict[str, type[_Contract]] = {
    "doc_extraction": ProfileResult,
    "identity": IdentityResult,
    "screening": ScreeningResult,
    "risk": RiskResult,
}
SLICES = {"doc_extraction": "profile", "identity": "identity", "screening": "screening", "risk": "risk"}


def validate_slice(agent: str, data: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate a specialist's output. Returns (contract or None, violations). Extra keys are stripped (SLICE-1)."""
    model = CONTRACTS[agent]
    if not isinstance(data, dict):
        return None, [f"AG-4: {agent} returned {type(data).__name__}, not an object"]
    extra = sorted(set(data) - set(model.model_fields))
    violations = [f"SLICE-1: {agent} wrote outside its slice: {', '.join(extra)}"] if extra else []
    try:
        obj = model.model_validate({k: v for k, v in data.items() if k not in extra})
    except ValidationError as e:
        violations += [f"AG-4: {'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        return None, violations
    return obj.model_dump(), violations


# ---------------------------------------------------------------- Supervisor router output (structured output)
class SupervisorAction(BaseModel):
    """One decision of the Supervisor. The graph executes it; identifiers and tokens are filled in by code, never by the model."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["delegate", "request_info", "escalate_edd", "request_approval", "create_record", "route_corporate", "finalize"]
    target: Specialist | None = Field(default=None, description="Specialist to hand off to (delegate only)")
    fields: list[str] = Field(default=[], description="Information to ask the customer for (request_info only)")
    reason: str = Field(description="Why this action, citing the state that justifies it")
    reason_codes: list[ReasonCode] = Field(default=[], description="Decision-table reason codes (escalate_edd, finalize)")
    status: FinalStatus | None = Field(default=None, description="Final application status (finalize only)")
    message_to_customer: str | None = Field(
        default=None, description="Text for the customer: the question (request_info) or the closing message (finalize)"
    )
