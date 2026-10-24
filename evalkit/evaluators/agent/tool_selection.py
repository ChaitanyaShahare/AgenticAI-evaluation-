"""AG-2 agent tool selection: F1 of the agent's calls against its share of the case's required / forbidden tools.

The agent's share is the case's tools whose spec names this agent (x-agent). Any call outside the agent's allow-list is
also reported here as a TU-7 S1 failure attributed to the agent.
"""

from __future__ import annotations

from evalkit.evaluators.agent.slicer import AgentSlice
from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.evaluators.tooluse.selection import selection_f1
from evalkit.schema import CheckResult


class AgentToolSelectionEvaluator(Evaluator):
    metric = "AG-2"
    severity = "S2"

    def allow_list(self, sl: AgentSlice, ctx: EvalContext) -> CheckResult:
        for s in sl.steps:
            c = s.tool_call
            if c and ctx.owner(c.tool) != sl.agent:
                owner = ctx.owner(c.tool) or "no agent"
                return self.result(
                    "fail", f"called {c.tool}, which belongs to {owner}", agent=sl.agent, step=s.index, severity="S1", metric="TU-7"
                )
        return self.result("pass", "all calls inside the allow-list", agent=sl.agent, severity="S1", metric="TU-7")

    def evaluate_agent(self, sl: AgentSlice, ctx: EvalContext) -> CheckResult:
        mine = lambda tools: {t for t in tools if ctx.owner(t) == sl.agent}  # noqa: E731
        req, forb = mine(ctx.case.required_tools), mine(ctx.case.forbidden_tools)
        if not req and not forb:
            return self.skip("case states no required or forbidden tools for this agent", agent=sl.agent)
        f1, missing, wrong = selection_f1({c.tool for c in sl.tool_calls}, req, forb)
        parts = ([f"missing {', '.join(missing)}"] if missing else []) + ([f"forbidden called: {', '.join(wrong)}"] if wrong else [])
        detail = f"F1 {f1}" + (f" — {'; '.join(parts)}" if parts else "")
        return self.result("pass" if f1 == 1.0 else "fail", detail, score=f1, agent=sl.agent)
