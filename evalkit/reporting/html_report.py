"""report.html: verdict, gate table, per-agent scorecards, suite metrics, cost, and per trial its checks and a trajectory
timeline with the failing steps highlighted.

Everything shown is redacted first (reporting/redaction.py). The finished page is scanned again; if any identifier is
still present the report is not written and the run fails loudly — a report must never leak PII.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from evalkit.reporting.junit_writer import check_name
from evalkit.reporting.redaction import Redactor
from evalkit.schema import Trajectory

TEMPLATES = Path(__file__).resolve().parent / "templates"


class ReportLeak(RuntimeError):
    """The rendered report still contains an identifier."""


def _clip(v: Any, n: int = 180) -> str:
    text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return text if len(text) <= n else text[: n - 1] + "…"


def _order(c) -> tuple:
    """Failures first, then errors, then the rest by metric."""
    return (c.verdict != "fail", c.verdict != "error", c.metric)


def timeline(traj: Trajectory) -> list[dict[str, Any]]:
    rows = []
    for s in traj.steps:
        if s.tool_call:
            c = s.tool_call
            what = f"{c.tool}({_clip(c.args, 140)}) → {c.status}: {_clip(c.result)}" + (
                f"  [fault {c.fault_injected}]" if c.fault_injected else ""
            )
        elif s.kind == "handoff":
            what = f"hand-off to {s.handoff_to} ({s.data.get('status')})"
        elif s.kind == "decision":
            a = s.data.get("action") or {}
            what = f"{a.get('action')} {a.get('target') or ''} — {_clip(a.get('reason'), 220)}"
        elif s.kind == "llm":
            what = f"{s.data.get('model')} ({s.data.get('purpose')}, {s.data.get('stop_reason')})"
        elif s.kind == "agent_result":
            what = f"result ({s.data.get('stop')}): {_clip(s.data.get('contract'), 220)}"
        else:
            what = _clip(s.content or s.data, 220)
        rows.append({"index": s.index, "kind": s.kind, "agent": s.agent or "", "what": what})
    return rows


def build_report(path: Path, *, summary: dict, graded, verdict, trajectories: list[Trajectory], redactor: Redactor, run_id: str,
                 project: str, cost: dict | None = None) -> Path:  # fmt: skip
    trajs = {(t.meta.case_id, t.meta.trial): t for t in trajectories}
    trials = []
    for r in graded.results:
        failing = {c.evidence_step for c in r.checks if c.verdict in ("fail", "error") and c.evidence_step is not None}
        t = trajs.get((r.case_id, r.trial))
        bad = [c for c in r.checks if c.verdict in ("fail", "error")]
        trials.append({
            "case_id": r.case_id,
            "trial": r.trial,
            "passed": r.passed,
            "s1": sum(c.severity == "S1" for c in bad),
            "checks": [{**c.model_dump(), "name": check_name(r.case_id, r.trial, c)} for c in sorted(r.checks, key=_order)],
            "timeline": [{**row, "failing": row["index"] in failing} for row in (timeline(t) if t else [])],
            "final": t.final_message if t else None,
            "end_state": t.end_state if t else {},
        })  # fmt: skip
    trials.sort(key=lambda x: (x["passed"], x["case_id"], x["trial"]))
    context = redactor.deep({
        "project": project,
        "run_id": run_id,
        "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "verdict": verdict.verdict,
        "reasons": verdict.reasons,
        "gate_lines": [vars(line) for line in verdict.lines],
        "s1_failures": verdict.s1_failures,
        "agents": summary["agents"],
        "suite": summary["suite"],
        "notes": summary["notes"],
        "flaky": summary["flaky"],
        "pass_k": summary["pass_k"],
        "trials": trials,
        "cost": cost,
        "ag_cols": ["AG-1", "AG-2", "AG-3", "AG-4", "AG-5", "TU-7", "AG-6"],
    })  # fmt: skip
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    html = env.get_template("report.html.j2").render(**context)
    if leaks := redactor.leaks(html):
        raise ReportLeak(f"report.html would contain {len(leaks)} identifier(s) ({', '.join(e for e, _ in leaks[:3])}); not written")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8", newline="\n")
    return path
