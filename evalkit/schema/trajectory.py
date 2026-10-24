"""Canonical trajectory: the contract between adapters (which produce it) and evaluators (which consume it).

Nothing downstream knows which agent framework produced a run. An adapter maps its framework's run record into these
models; every evaluator reads only these models. Steps are ordered; tool calls carry the agent that made them, so the
trajectory can be sliced per agent (per-agent metrics AG-1 … AG-6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StepKind = Literal["llm", "tool", "handoff", "interrupt", "message", "user", "guard", "contract", "decision", "agent_result", "note"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCall(_Model):
    call_id: str
    agent: str  # agent that issued the call
    tool: str
    args: dict[str, Any]
    result: Any | None = None  # what the tool returned (a raw string for malformed bodies)
    status: Literal["ok", "error", "timeout"] = "ok"
    attempt: int = 1  # per (tool, identical arguments) within the run
    latency_ms: int | None = None
    fault_injected: str | None = None  # "<profile>:<behaviour>", set by the harness, never by the agent


class Step(_Model):
    index: int
    kind: StepKind
    agent: str | None = None
    tool_call: ToolCall | None = None
    handoff_to: str | None = None
    content: str | None = None  # message text, guard / contract detail
    data: dict[str, Any] = Field(default_factory=dict)  # kind-specific details (usage, decision, violations, …)


class RunMeta(_Model):
    run_id: str
    case_id: str
    trial: int
    project: str
    adapter: str
    models: dict[str, str]  # role -> model ID
    effort: dict[str, str] = Field(default_factory=dict)
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    package_versions: dict[str, str] = Field(default_factory=dict)
    seed: int | None = None
    as_of: str | None = None
    started_at: str | None = None  # wall clock; informational only, never compared
    duration_s: float | None = None
    usage: dict[str, dict[str, int]] = Field(default_factory=dict)  # model -> token counts


class Trajectory(_Model):
    meta: RunMeta
    user_turns: list[str] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    final_message: str | None = None
    end_state: dict[str, Any] = Field(default_factory=dict)  # system-of-record state after the run (graded by TR-1)
    agent_outputs: dict[str, Any] = Field(default_factory=dict)  # agent -> its state slice / contract (AG-1, AG-4)
    error: str | None = None  # harness-level failure (exception, recursion limit, …)

    # ---------------------------------------------------------------- views used by evaluators
    def tool_calls(self, agent: str | None = None) -> list[ToolCall]:
        return [s.tool_call for s in self.steps if s.tool_call and (agent is None or s.tool_call.agent == agent)]

    def tool_sequence(self, agent: str | None = None) -> list[str]:
        return [c.tool for c in self.tool_calls(agent)]

    def handoffs(self) -> list[str]:
        return [s.handoff_to for s in self.steps if s.kind == "handoff" and s.handoff_to]

    def agents(self) -> list[str]:
        return sorted({s.agent for s in self.steps if s.agent})

    def agent_slice(self, agent: str) -> list[Step]:
        """The steps one agent produced: its model calls, tool calls, results and contract checks."""
        return [s for s in self.steps if s.agent == agent]

    def messages(self) -> list[str]:
        return [s.content for s in self.steps if s.kind == "message" and s.content]

    # ---------------------------------------------------------------- persistence
    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> Trajectory:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
