"""Shared pieces of the KYC agents: the registry-backed tool executor and the specialist result type.

Design rule (Agent Requirement sheet row 6): the model chooses and calls tools — arguments, retries, when to stop — and
deterministic code builds the agent's output contract from the recorded tool outcomes. So a hit can never be cleared, a
mismatch never upgraded and a score never invented by the model, while the agent's tool use stays fully observable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evalkit.harness.fault_hook import ToolOutcome


@dataclass
class SpecialistResult:
    agent: str
    contract: dict[str, Any] | None  # validated slice, or None when the contract was invalid / missing
    violations: list[str]
    events: list[dict[str, Any]]
    stop: str  # how the model loop ended (finished, refusal, turn_limit, …)
    submitted: dict[str, Any] | None = None
    note: str | None = None  # a remark for the Supervisor, shown in its next brief


def tool_event(out: ToolOutcome, agent: str) -> dict[str, Any]:
    return {
        "kind": "tool",
        "agent": agent,
        "tool": out.tool,
        "args": out.args,
        "status": out.status,
        "result": out.result,
        "fault_injected": out.fault_injected,
        "attempt": out.attempt,
        "latency_ms": out.latency_ms,
    }


@dataclass
class Executor:
    """Runs one agent's tool calls through the registry and keeps the outcomes for the contract builder."""

    registry: Any
    agent: str
    outcomes: list[ToolOutcome] = field(default_factory=list)

    def __call__(self, name: str, args: dict[str, Any]) -> tuple[str, bool, dict[str, Any]]:
        out = self.registry.call(self.agent, name, args)
        self.outcomes.append(out)
        return out.for_agent(), out.status != "ok", tool_event(out, self.agent)

    def ok(self, tool: str) -> list[ToolOutcome]:
        """Successful, well-formed outcomes of one tool, in call order."""
        return [o for o in self.outcomes if o.tool == tool and o.status == "ok" and isinstance(o.result, dict)]

    def last(self, tool: str) -> ToolOutcome | None:
        calls = [o for o in self.outcomes if o.tool == tool]
        return calls[-1] if calls else None
