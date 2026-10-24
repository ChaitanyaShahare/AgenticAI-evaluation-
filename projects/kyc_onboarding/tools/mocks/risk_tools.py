"""Risk rating tools (contract rows 8–9).

compute_risk_score resolves screening_ref to its application and considers every screening result of that
application in the run (sanctions and PEP are separate calls with separate refs). A ref is still required, so a
risk agent that skips screening cannot reach the right tier by accident. The engine records its own score and tier
on the application: the graded tier is the engine's, never a figure restated by an agent.
"""

from __future__ import annotations

import json
from typing import Any

from projects.kyc_onboarding.tools.mocks.db import ToolContext


def _tier(ctx: ToolContext, score: int, version: str) -> str:
    p = ctx.one("SELECT medium_from, high_from FROM risk_policy WHERE version = ?", (version,))
    return "HIGH" if score >= p["high_from"] else "MEDIUM" if score >= p["medium_from"] else "LOW"


def fetch_risk_policy(ctx: ToolContext, version: str) -> dict[str, Any]:
    row = ctx.one("SELECT * FROM risk_policy WHERE version = ?", (version,))
    if row is None:
        return {"error": "VERSION_NOT_FOUND", "details": version}
    return {
        "version": row["version"],
        "status": row["status"],
        "medium_from": row["medium_from"],
        "high_from": row["high_from"],
        "factors": json.loads(row["factors_json"]),
    }


def compute_risk_score(ctx: ToolContext, applicant_id: str, screening_ref: str, product: str) -> dict[str, Any]:
    if ctx.applicant_id and applicant_id != ctx.applicant_id:
        return {"error": "APPLICANT_NOT_IN_SESSION", "details": applicant_id}
    ref = ctx.one("SELECT application_id FROM screening_results WHERE screening_ref = ?", (screening_ref,))
    if ref is None:
        return {
            "error": "SCREENING_REF_NOT_FOUND",
            "details": f"{screening_ref} was not issued by sanctions_screen or pep_check in this run",
        }
    app = ctx.one("SELECT occupation, income_band FROM applicants WHERE applicant_id = ?", (applicant_id,))
    inputs = ctx.one("SELECT * FROM risk_engine_inputs WHERE applicant_id = ?", (applicant_id,))
    if app is None or inputs is None:
        return {"error": "UNKNOWN_APPLICANT", "details": applicant_id}
    missing = [f for f in ("occupation", "income_band") if not app[f]]
    if missing:
        return {"status": "MISSING_INPUT", "missing": missing}

    if ref["application_id"] is None:
        scores = ctx.all("SELECT max_score FROM screening_results WHERE screening_ref = ?", (screening_ref,))
    else:
        scores = ctx.all("SELECT max_score FROM screening_results WHERE application_id = ?", (ref["application_id"],))
    near = float(ctx.config("screening_near_threshold"))
    version = ctx.config("risk_policy_current")
    if any(s["max_score"] is not None and s["max_score"] >= near for s in scores):
        score, factors = 100, ["SCREENING_HIT"]
    else:
        score = inputs["base_score"]
        factors = json.loads(inputs["factors_json"])
        if not factors:  # occupation / income supplied later by the customer (KYC-MIS-083)
            occ = app["occupation"]
            cat = (
                "SALARIED"
                if occ.startswith("Salaried")
                else "SELF_EMPLOYED"
                if occ.startswith("Self-employed")
                else occ.split(" ")[0].upper()
            )
            factors = [f"OCCUPATION:{cat}", f"INCOME:{app['income_band']}"]
    tier = _tier(ctx, score, version)
    if ctx.application_id:
        ctx.write(
            "UPDATE applications SET risk_score = ?, risk_tier = ?, updated_at = ? WHERE application_id = ?",
            (score, tier, ctx.now(), ctx.application_id),
        )
    return {"status": "OK", "score": score, "tier": tier, "factors": factors, "policy_version": version}
