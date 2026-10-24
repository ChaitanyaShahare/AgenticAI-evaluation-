"""Primary adapter: runs a case with the project's runner and maps its run events into a Trajectory.

The runner drives the LangGraph graph (interrupts included) and returns the run record described in
evalkit/adapters/base.py. This module only knows that protocol, so other LangGraph projects reuse it unchanged.
"""

from __future__ import annotations

import json
import sqlite3
import time
import traceback
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from evalkit.adapters.base import AgentAdapter, import_ref
from evalkit.schema import RunMeta, Step, TestCase, ToolCall, Trajectory

PACKAGES = ("evalkit", "bfsi-agent-eval", "langgraph", "langchain-core", "anthropic", "pydantic")


def package_versions() -> dict[str, str]:
    out = {}
    for p in PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            continue
    return out


def events_to_steps(events: list[dict[str, Any]]) -> list[Step]:
    steps: list[Step] = []
    calls = 0
    for ev in events:
        k, i, agent = ev.get("kind"), len(steps), ev.get("agent")
        if k == "tool":
            calls += 1
            tc = ToolCall(
                call_id=f"c{calls:03d}",
                agent=agent,
                tool=ev["tool"],
                args=ev.get("args") or {},
                result=ev.get("result"),
                status=ev.get("status", "ok"),
                attempt=ev.get("attempt", 1),
                latency_ms=ev.get("latency_ms"),
                fault_injected=ev.get("fault_injected"),
            )
            steps.append(Step(index=i, kind="tool", agent=agent, tool_call=tc))
        elif k == "llm":
            steps.append(
                Step(
                    index=i,
                    kind="llm",
                    agent=agent,
                    data={x: ev.get(x) for x in ("model", "effort", "purpose", "stop_reason", "usage", "error") if ev.get(x) is not None},
                )
            )
        elif k == "handoff":
            steps.append(Step(index=i, kind="handoff", agent=agent, handoff_to=ev.get("to"), data={"status": ev.get("status")}))
        elif k == "interrupt":
            steps.append(
                Step(index=i, kind="interrupt", agent=agent, data={x: ev.get(x) for x in ("name", "decision", "token_issued", "token")})
            )
        elif k == "message":
            steps.append(Step(index=i, kind="message", agent=agent, content=ev.get("content"), data={"final": bool(ev.get("final"))}))
        elif k == "user":
            steps.append(Step(index=i, kind="user", content=ev.get("content"), data={"new_documents": ev.get("new_documents") or []}))
        elif k == "decision":
            steps.append(Step(index=i, kind="decision", agent=agent, data={"action": ev.get("action")}))
        elif k == "guard":
            steps.append(Step(index=i, kind="guard", agent=agent, content=ev.get("detail"), data={"rule": ev.get("rule")}))
        elif k == "contract":
            v = ev.get("violations") or []
            steps.append(Step(index=i, kind="contract", agent=agent, content="; ".join(v), data={"violations": v}))
        elif k == "agent_result":
            steps.append(
                Step(
                    index=i,
                    kind="agent_result",
                    agent=agent,
                    data={"stop": ev.get("stop"), "contract": ev.get("contract"), "submitted": ev.get("submitted")},
                )
            )
        else:
            steps.append(Step(index=i, kind="note", agent=agent, content=k, data={x: y for x, y in ev.items() if x != "kind"}))
    return steps


def usage_by_model(events: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for ev in events:
        if ev.get("kind") == "llm" and ev.get("model"):
            u = out.setdefault(
                ev["model"],
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
            )
            u["calls"] += 1
            for key, val in (ev.get("usage") or {}).items():
                u[key] = u.get(key, 0) + int(val or 0)
    return out


def read_end_state(db_path: Path, query: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run end_state_query on the trial database. Columns ending in _json are decoded and lose the suffix."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(query, params).fetchone()
    finally:
        con.close()
    if row is None:
        return {}
    out = {}
    for k in row.keys():
        v = row[k]
        if k.endswith("_json") and isinstance(v, str):
            out[k[:-5]] = json.loads(v)
        else:
            out[k] = v
    return out


class LangGraphAdapter(AgentAdapter):
    name = "langgraph"

    def run(self, case: TestCase, trial: int, run_id: str, db_path: Path, client=None) -> Trajectory:
        runner = import_ref(self.project.runner)
        started, t0 = datetime.now(UTC).isoformat(timespec="seconds"), time.perf_counter()
        error, state, params = None, {}, None
        try:
            record = runner(db_path, case.case_id, run_id=run_id, trial=trial, client=client, cfg=self.eval_cfg)
            state, params = record.state, record.end_state_params
        except Exception as e:  # graded as a failed run, never lost
            error = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=6)}"
        events = list(state.get("events") or [])
        start = next((e for e in events if e.get("kind") == "run_start"), {})
        meta = RunMeta(
            run_id=run_id,
            case_id=case.case_id,
            trial=trial,
            project=self.project.project,
            adapter=self.name,
            models=start.get("models") or {"supervisor": self.eval_cfg.models.supervisor, "specialist": self.eval_cfg.models.specialist},
            effort=start.get("effort") or {},
            prompt_hashes=start.get("prompt_hashes") or {},
            package_versions=package_versions(),
            seed=start.get("seed", self.eval_cfg.determinism.seed),
            as_of=start.get("as_of", self.eval_cfg.determinism.as_of),
            started_at=started,
            duration_s=round(time.perf_counter() - t0, 3),
            usage=usage_by_model(events),
        )
        steps = events_to_steps(events)
        user_turns = list(state.get("customer_messages") or [])
        replies = list(state.get("replies") or [])
        outputs = {s.agent: s.data.get("contract") for s in steps if s.kind == "agent_result" and s.agent}
        end_state = {}
        if params is not None:
            try:
                end_state = read_end_state(db_path, self.project.end_state_query, params)
            except Exception as e:
                error = (error or "") + f"end_state_query failed: {type(e).__name__}: {e}"
        return Trajectory(
            meta=meta,
            user_turns=user_turns,
            steps=steps,
            final_message=replies[-1] if replies else None,
            end_state=end_state,
            agent_outputs=outputs,
            error=error,
        )
