"""Agent slicer: cut a trajectory into one slice per agent, so every agent gets its own scorecard (AG-1 … AG-6).

A slice holds the agent's steps (model calls, tool calls, results, contract checks, guards), its outputs (agent results
for specialists, routing decisions for the orchestrator), how often it was delegated to, and whether it was stubbed.
A stubbed agent (L2 canned output) is test input, not the agent under test, so its AG checks are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evalkit.evaluators.base import EvalContext
from evalkit.schema import Step, ToolCall, Trajectory


@dataclass
class AgentSlice:
    agent: str
    steps: list[Step] = field(default_factory=list)
    results: list[Step] = field(default_factory=list)  # agent_result steps (specialists) or decision steps (orchestrator)
    violations: list[Step] = field(default_factory=list)  # contract steps and AG-4 guards for this agent
    delegations: int = 0
    stubbed: bool = False

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [s.tool_call for s in self.steps if s.tool_call]

    @property
    def final_output(self) -> Any:
        if not self.results:
            return None
        last = self.results[-1]
        return last.data.get("action") if last.kind == "decision" else last.data.get("contract")


def slice_agents(traj: Trajectory, ctx: EvalContext) -> dict[str, AgentSlice]:
    names = list(ctx.agents) or traj.agents()
    slices = {n: AgentSlice(n) for n in names}
    for s in traj.steps:
        if s.kind == "handoff" and s.handoff_to in slices:
            slices[s.handoff_to].delegations += 1
        sl = slices.get(s.agent or "")
        if sl is None:
            continue
        sl.steps.append(s)
        info = ctx.agents.get(sl.agent)
        output_kind = "decision" if info and info.output == "decision" else "agent_result"
        if s.kind == output_kind:
            sl.results.append(s)
        if s.kind == "contract" or (s.kind == "guard" and s.data.get("rule") == "AG-4"):
            sl.violations.append(s)
    for sl in slices.values():
        sl.stubbed = bool(sl.results) and all(r.data.get("stop") == "stub" for r in sl.results)
    return {n: sl for n, sl in slices.items() if sl.steps}
