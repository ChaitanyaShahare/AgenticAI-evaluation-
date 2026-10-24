"""Sanctions / PEP screening tools (contract rows 6–7).

Screening is a lookup table, not live fuzzy matching, so planted scores (0.749, 0.75, 0.78 …) stay exact.
Every response is persisted in screening_results under a screening_ref, including override responses (MO-02),
because compute_risk_score needs the ref to apply the screening override.
"""

from __future__ import annotations

import json
from typing import Any

from projects.kyc_onboarding.tools.mocks.db import ToolContext, norm


def _candidates(ctx: ToolContext, list_type: str, full_name: str, dob: str) -> list[dict[str, Any]]:
    floor = float(ctx.config("screening_return_floor"))
    rows = ctx.all(
        "SELECT entry_id, match_score, matched_fields_json FROM screening_index "
        "WHERE query_name_norm = ? AND query_dob = ? AND list_type = ? AND match_score >= ? ORDER BY match_score DESC, entry_id",
        (norm(full_name), dob, list_type, floor),
    )
    out = []
    for r in rows:
        c: dict[str, Any] = {"entry_id": r["entry_id"], "score": r["match_score"], "matched_fields": json.loads(r["matched_fields_json"])}
        if list_type == "PEP":
            pep = ctx.one("SELECT full_name, pep_category FROM pep_list WHERE entry_id = ?", (r["entry_id"],))
            c.update(list="PEP", name=pep["full_name"], category=pep["pep_category"])
        else:
            san = ctx.one("SELECT list_name, full_name FROM sanctions_list WHERE entry_id = ?", (r["entry_id"],))
            c.update(list=san["list_name"], name=san["full_name"])
        out.append(c)
    return out


def persist(ctx: ToolContext, tool: str, request: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Assign a screening_ref, store the response, and return it with the ref."""
    if "error" in response:
        return response
    n = ctx.one("SELECT count(*) AS n FROM screening_results")["n"] + 1
    ref = f"SCR-{n:04d}"
    body = {"screening_ref": ref, **{k: v for k, v in response.items() if k not in ("screening_ref", "status")}}
    body.setdefault("lists_version", ctx.config("lists_version"))
    if tool == "pep_check":
        body.setdefault("hit", any(c["score"] >= float(ctx.config("screening_hit_threshold")) for c in body.get("candidates", [])))
    max_score = max((c["score"] for c in body.get("candidates", [])), default=None)
    ctx.write(
        "INSERT INTO screening_results VALUES (?,?,?,?,?,?,?)",
        (
            ref,
            ctx.application_id,
            tool,
            json.dumps(request, ensure_ascii=False),
            json.dumps(body, ensure_ascii=False),
            max_score,
            ctx.now(),
        ),
    )
    return body


def sanctions_screen(ctx: ToolContext, full_name: str, dob: str, nationality: str) -> dict[str, Any]:
    request = {"full_name": full_name, "dob": dob, "nationality": nationality}
    return persist(ctx, "sanctions_screen", request, {"candidates": _candidates(ctx, "SANCTIONS", full_name, dob)})


def pep_check(ctx: ToolContext, full_name: str, dob: str) -> dict[str, Any]:
    request = {"full_name": full_name, "dob": dob}
    return persist(ctx, "pep_check", request, {"candidates": _candidates(ctx, "PEP", full_name, dob)})
