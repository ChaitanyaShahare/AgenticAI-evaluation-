"""AG-4 output-contract validity: every output the agent wrote validates against its contract (agents.yaml › contract),
and the run logged no contract violation for it (missing fields, invalid values, keys outside its slice — SLICE-1).
"""

from __future__ import annotations

from pydantic import ValidationError

from evalkit.evaluators.agent.slicer import AgentSlice
from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult


class AgentContractEvaluator(Evaluator):
    metric = "AG-4"
    severity = "S2"

    def evaluate_agent(self, sl: AgentSlice, ctx: EvalContext) -> CheckResult:
        info = ctx.agents.get(sl.agent)
        if info is None or info.contract is None:
            return self.skip("no contract configured for this agent (agents.yaml › contract)", agent=sl.agent)
        if not sl.results:
            return self.result("fail", "agent wrote no output", agent=sl.agent)
        if sl.violations:
            v = sl.violations[0]
            return self.result("fail", v.content or "contract violation logged", agent=sl.agent, step=v.index)
        for r in sl.results:
            out = r.data.get("action") if r.kind == "decision" else r.data.get("contract")
            if out is None:
                return self.result("fail", "output rejected (no valid contract)", agent=sl.agent, step=r.index)
            try:
                info.contract.model_validate(out)
            except ValidationError as e:
                first = e.errors()[0]
                where = ".".join(str(x) for x in first["loc"]) or "(output)"
                return self.result("fail", f"{where}: {first['msg']}", agent=sl.agent, step=r.index)
        return self.result("pass", f"{len(sl.results)} output(s) valid against {info.contract.__name__}", agent=sl.agent)
