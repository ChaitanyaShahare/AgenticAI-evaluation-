"""cost.json: token use per model and per agent, run time, money when prices are known, and budget alerts.

Tokens come from each trajectory's llm steps (agents) and the judge's own count (judges). Money is computed only from
prices written in configs/eval.yaml › budget.pricing (USD per million tokens) — never guessed; without them the cost
is reported as unknown. Each run's cost is added to a monthly ledger (runs/cost_ledger.jsonl); when the month's total
reaches a fraction of budget.monthly_limit_inr listed in budget.alert_at, an alert is raised.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evalkit.schema import Trajectory

TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
PRICE_KEY = {
    "input_tokens": "input",
    "output_tokens": "output",
    "cache_read_input_tokens": "cache_read",
    "cache_creation_input_tokens": "cache_write",
}


def usage(trajectories: list[Trajectory]) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """(per model, per agent) token totals and call counts."""
    by_model: dict[str, dict[str, int]] = {}
    by_agent: dict[str, dict[str, int]] = {}
    for t in trajectories:
        for s in t.steps:
            if s.kind != "llm":
                continue
            u = s.data.get("usage") or {}
            for bucket, key in ((by_model, s.data.get("model") or "?"), (by_agent, s.agent or "?")):
                row = bucket.setdefault(key, {"calls": 0, **dict.fromkeys(TOKEN_KEYS, 0)})
                row["calls"] += 1
                for k in TOKEN_KEYS:
                    row[k] += int(u.get(k) or 0)
    return by_model, by_agent


def money(by_model: dict[str, dict[str, int]], pricing: dict[str, dict[str, float | None]]) -> tuple[float | None, list[str]]:
    """USD for the token totals, or None with the models whose prices are missing."""
    total, missing = 0.0, []
    for model, row in by_model.items():
        p = pricing.get(model)
        p = p.model_dump() if hasattr(p, "model_dump") else (p or {})
        for k in TOKEN_KEYS:
            if row.get(k):
                price = p.get(PRICE_KEY[k])
                if price is None:
                    missing.append(model)
                    break
                total += row[k] / 1e6 * price
    return (None, sorted(set(missing))) if missing else (round(total, 4), [])


def alerts(month_inr: float | None, limit_inr: float | None, alert_at: list[float]) -> list[str]:
    if limit_inr is None:
        return ["no monthly budget set (configs/eval.yaml › budget.monthly_limit_inr) — alerts are off"]
    if month_inr is None:
        return ["the month's spend is unknown (prices or the USD→INR rate are not set) — alerts cannot be evaluated"]
    used = month_inr / limit_inr
    return [f"budget alert: {used:.0%} of the monthly ₹{limit_inr:,.0f} used (threshold {a:.0%})" for a in sorted(alert_at) if used >= a]


def write_cost(
    run_dir: Path, run_id: str, trajectories: list[Trajectory], budget: Any, ledger: Path, judge_usage: dict | None = None
) -> dict:
    by_model, by_agent = usage(trajectories)
    if judge_usage:
        row = by_model.setdefault(judge_usage["model"], {"calls": 0, **dict.fromkeys(TOKEN_KEYS, 0)})
        for k in ("calls", *TOKEN_KEYS):
            row[k] += int(judge_usage.get(k) or 0)
        by_agent["judge"] = {k: int(judge_usage.get(k) or 0) for k in ("calls", *TOKEN_KEYS)}
    usd, missing = money(by_model, budget.pricing or {})
    inr = round(usd * budget.usd_to_inr, 2) if usd is not None and budget.usd_to_inr else None
    month = datetime.now(UTC).strftime("%Y-%m")
    month_inr = inr
    if ledger.is_file():
        prior = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        prior = [p for p in prior if p.get("month") == month and p.get("run_id") != run_id]
        known = [p.get("inr") for p in prior]
        month_inr = None if inr is None or any(v is None for v in known) else round(inr + sum(known), 2)
    doc = {
        "run_id": run_id,
        "month": month,
        "trials": len(trajectories),
        "duration_s": round(sum(t.meta.duration_s or 0 for t in trajectories), 1),
        "by_model": by_model,
        "by_agent": by_agent,
        "usd": usd,
        "inr": inr,
        "prices_missing_for": missing,
        "month_to_date_inr": month_inr,
        "alerts": alerts(month_inr, budget.monthly_limit_inr, budget.alert_at),
    }
    (run_dir / "cost.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"run_id": run_id, "month": month, "usd": usd, "inr": inr}) + "\n")
    return doc
