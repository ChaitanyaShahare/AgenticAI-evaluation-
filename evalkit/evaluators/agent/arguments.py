"""AG-3 agent argument correctness: share of the agent's calls whose arguments are schema-valid, grounded and, where the
case states expectations, correct (TU-2 + TU-4 + TU-3 restricted to the agent's own calls).
"""

from __future__ import annotations

from evalkit.evaluators.agent.slicer import AgentSlice
from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.evaluators.tooluse.arguments import args_correct, schema_errors
from evalkit.evaluators.tooluse.grounding import checked_values, grounded, source_text
from evalkit.schema import CheckResult, Trajectory


class AgentArgumentsEvaluator(Evaluator):
    metric = "AG-3"
    severity = "S2"

    def evaluate_agent(self, sl: AgentSlice, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        steps = [s for s in sl.steps if s.tool_call]
        if not steps:
            return self.skip("agent made no tool calls", agent=sl.agent)
        expected = ctx.case.expected.get("arguments") or {}
        bad = []
        for s in steps:
            c = s.tool_call
            problems = schema_errors(c, ctx)[:1]
            text = source_text(traj, s.index, ctx)
            problems += [f"{c.tool}.{k} = {v!r} ungrounded" for k, v in checked_values(c.args) if not grounded(v, text)]
            problems += args_correct(c, expected[c.tool]) if c.tool in expected else []
            if problems:
                bad.append((s.index, problems[0]))
        score = round(1 - len(bad) / len(steps), 3)
        if bad:
            return self.result("fail", "; ".join(p for _, p in bad[:3]), score=score, agent=sl.agent, step=bad[0][0])
        return self.result("pass", f"{len(steps)} call(s) with valid, grounded arguments", score=1.0, agent=sl.agent)
