"""Document extraction tools (contract rows 1–2). The IDP mock returns what is printed; masking is the agent's job."""

from __future__ import annotations

from typing import Any

from projects.kyc_onboarding.tools.mocks.db import ToolContext


def classify_document(ctx: ToolContext, doc_id: str) -> dict[str, Any]:
    if not ctx.visible_doc(doc_id):
        return {"error": "DOC_NOT_FOUND", "details": f"{doc_id} has not been uploaded in this application"}
    row = ctx.one("SELECT doc_type, quality_score FROM documents WHERE doc_id = ?", (doc_id,))
    if row is None:
        return {"error": "DOC_NOT_FOUND", "details": doc_id}
    return {"doc_id": doc_id, "doc_type": row["doc_type"], "quality_score": row["quality_score"]}


def extract_document(ctx: ToolContext, doc_id: str, doc_type: str) -> dict[str, Any]:
    if not ctx.visible_doc(doc_id):
        return {"error": "DOC_NOT_FOUND", "details": f"{doc_id} has not been uploaded in this application"}
    doc = ctx.one("SELECT doc_type, ocr_text FROM documents WHERE doc_id = ?", (doc_id,))
    if doc is None:
        return {"error": "DOC_NOT_FOUND", "details": doc_id}
    if doc["doc_type"] != doc_type:
        return {"error": "DOC_TYPE_MISMATCH", "details": f"{doc_id} is {doc['doc_type']}, not {doc_type}"}
    fields = {
        r["field_name"]: {"value": r["field_value"], "confidence": r["confidence"]}
        for r in ctx.all("SELECT field_name, field_value, confidence FROM document_fields WHERE doc_id = ? ORDER BY field_name", (doc_id,))
    }
    return {"doc_id": doc_id, "doc_type": doc_type, "fields": fields, "raw_text": doc["ocr_text"]}
