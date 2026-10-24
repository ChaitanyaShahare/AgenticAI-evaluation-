"""AG-6 agent efficiency (S3, report only): the agent's distinct calls ÷ its actual calls; retries and loops counted."""

from __future__ import annotations

from evalkit.evaluators.agent.slicer import AgentSlice
from evalkit.evaluators.base import Evaluator
from evalkit.evaluators.trajectory.efficiency import distinct_calls
from evalkit.schema import CheckResult


class AgentEfficiencyEvaluator(Evaluator):
    metric = "AG-6"
    severity = "S3"

    def evaluate_agent(self, sl: AgentSlice) -> CheckResult:
        calls = sl.tool_calls
        if not calls:
            return self.skip("agent made no tool calls", agent=sl.agent)
        distinct = distinct_calls(calls)
        retries = sum(1 for c in calls if c.attempt > 1)
        score = round(distinct / len(calls), 3)
        return self.result("pass", f"{distinct} distinct ÷ {len(calls)} calls; {retries} retr{'y' if retries == 1 else 'ies'}",
                           score=score, agent=sl.agent)  # fmt: skip
