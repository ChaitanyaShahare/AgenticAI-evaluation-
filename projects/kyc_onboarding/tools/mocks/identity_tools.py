"""Identity verification tools (contract rows 3–5). The registry decides name / DOB match; the agent reports it."""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.tools.mocks.db import ToolContext, norm


def verify_pan(ctx: ToolContext, pan: str, full_name: str, dob: str) -> dict[str, Any]:
    row = ctx.one("SELECT registered_name, dob, pan_status FROM pan_registry WHERE pan = ?", (pan,))
    if row is None or row["pan_status"] == "DEACTIVATED":
        return {"status": "INVALID", "name_match": None, "dob_match": None}
    name_match = norm(row["registered_name"]) == norm(full_name)
    dob_match = row["dob"] == dob
    return {"status": "VALID" if name_match and dob_match else "MISMATCH", "name_match": name_match, "dob_match": dob_match}


def ckyc_lookup(ctx: ToolContext, pan: str, dob: str) -> dict[str, Any]:
    row = ctx.one("SELECT ckyc_no FROM ckyc_records WHERE pan = ? AND dob = ?", (pan, dob))
    ckyc_no = row["ckyc_no"] if row else None
    if ckyc_no and ctx.application_id:  # recorded on the application (D9: absence is non-blocking)
        ctx.write("UPDATE applications SET ckyc_no = ?, updated_at = ? WHERE application_id = ?", (ckyc_no, ctx.now(), ctx.application_id))
    return {"ckyc_no": ckyc_no}


def check_address_proof(ctx: ToolContext, doc_id: str, address: str) -> dict[str, Any]:
    if not ctx.visible_doc(doc_id):
        return {"error": "DOC_NOT_FOUND", "details": f"{doc_id} has not been uploaded in this application"}
    row = ctx.one("SELECT validity, address_on_document FROM v_address_proof_validity WHERE doc_id = ?", (doc_id,))
    if row is None:
        return {"error": "DOC_NOT_FOUND", "details": doc_id}
    if row["validity"] != "VALID":
        return {"status": row["validity"]}  # EXPIRED or NOT_ADDRESS_PROOF, on the test clock
    on_doc = row["address_on_document"]
    return {"status": "MATCH" if on_doc and norm(on_doc) == norm(address) else "MISMATCH"}
