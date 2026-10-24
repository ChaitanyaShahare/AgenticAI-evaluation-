"""Supervisor tools (contract rows 10–13) and the approval-token store used by the mock approver.

Write tools act only on the application in session (no third-party actions, KYC-ADV-038). They do not second-guess
the supervisor's decisions — for example finalize_application(APPROVED) without a record is allowed — because
catching wrong decisions is the evaluators' job, not the system of record's.
"""

from __future__ import annotations

import json
from typing import Any

from projects.kyc_onboarding.tools.mocks.db import ToolContext


def _guard(ctx: ToolContext, application_id: str) -> dict[str, Any] | None:
    if not ctx.in_session(application_id):
        return {"error": "APPLICATION_NOT_IN_SESSION", "details": f"{application_id} is not the application being onboarded"}
    if ctx.one("SELECT 1 FROM applications WHERE application_id = ?", (application_id,)) is None:
        return {"error": "UNKNOWN_APPLICATION", "details": application_id}
    return None


def request_customer_info(ctx: ToolContext, fields: list[str], reason: str) -> dict[str, Any]:
    if ctx.application_id:
        ctx.write(
            "INSERT INTO info_requests (application_id, fields_json, reason, created_at) VALUES (?,?,?,?)",
            (ctx.application_id, json.dumps(fields), reason, ctx.now()),
        )
    scripted, reply = ctx.next_customer_reply()
    if not scripted or reply is None:
        return {"status": "NO_RESPONSE", "customer_reply": None}
    if ctx.form_updates and ctx.applicant_id:  # e.g. KYC-MIS-083: occupation and income supplied on request
        for col, val in ctx.form_updates.items():
            if col not in ("occupation", "income_band", "nationality"):
                raise ValueError(f"form update for unsupported column {col!r}")
            ctx.write(f"UPDATE applicants SET {col} = ? WHERE applicant_id = ?", (val, ctx.applicant_id))
    ctx.turn += 1  # documents uploaded with this reply become visible
    return {"status": "ANSWERED", "customer_reply": reply}


def escalate_to_edd(ctx: ToolContext, application_id: str, reason_codes: list[str]) -> dict[str, Any]:
    if err := _guard(ctx, application_id):
        return err
    edd_case_id = f"EDD-{application_id[4:]}-{ctx.next_seq('edd'):02d}"
    ts = ctx.now()
    ctx.write("INSERT INTO edd_cases VALUES (?,?,?,?)", (edd_case_id, application_id, json.dumps(reason_codes), ts))
    ctx.write("UPDATE applications SET updated_at = ? WHERE application_id = ?", (ts, application_id))
    return {"edd_case_id": edd_case_id}


def create_customer_record(ctx: ToolContext, application_id: str, approval_token: str) -> dict[str, Any]:
    if err := _guard(ctx, application_id):
        return err
    tok = ctx.one("SELECT decision, consumed FROM approval_tokens WHERE token = ? AND application_id = ?", (approval_token, application_id))
    if tok is None or tok["decision"] != "APPROVE" or tok["consumed"]:
        return {"error": "UNAUTHORISED", "details": "approval token missing, denied, already used or for another application"}
    if ctx.one("SELECT 1 FROM customer_records WHERE application_id = ?", (application_id,)):
        return {"error": "DUPLICATE_RECORD", "details": f"a customer record already exists for {application_id}"}
    applicant = ctx.one("SELECT applicant_id FROM applications WHERE application_id = ?", (application_id,))["applicant_id"]
    record_id = f"REC-{application_id[4:]}"
    ts = ctx.now()
    ctx.write("INSERT INTO customer_records VALUES (?,?,?,?)", (record_id, application_id, applicant, ts))
    ctx.write("UPDATE approval_tokens SET consumed = 1 WHERE token = ?", (approval_token,))
    ctx.write("UPDATE applications SET record_id = ?, updated_at = ? WHERE application_id = ?", (record_id, ts, application_id))
    return {"record_id": record_id}


def finalize_application(ctx: ToolContext, application_id: str, status: str, reason_codes: list[str]) -> dict[str, Any]:
    if err := _guard(ctx, application_id):
        return err
    ctx.write(
        "UPDATE applications SET status = ?, reason_codes_json = ?, updated_at = ? WHERE application_id = ?",
        (status, json.dumps(reason_codes), ctx.now(), application_id),
    )
    return {"status": status}


def issue_approval_token(ctx: ToolContext, decision: str | None = None) -> str | None:
    """Mock approver at the approval interrupt. APPROVE → usable token; DENY → token create_customer_record rejects;
    NO_RESPONSE / None → nothing (contract: Mock approver). Defaults to the case's approver_response."""
    decision = decision or ctx.approver_response
    if decision not in ("APPROVE", "DENY") or ctx.application_id is None:
        return None
    token = f"APR-{ctx.application_id[4:]}-{ctx.next_seq('token'):02d}"
    ctx.write(
        "INSERT INTO approval_tokens (token, application_id, decision, issued_at) VALUES (?,?,?,?)",
        (token, ctx.application_id, decision, ctx.now()),
    )
    return token
