"""AG-5 agent-specific guardrails (S1).

Guardrails are policy rules with `agent: <name>` and `metric: AG-5` (for example: Supervisor never writes without an
approval token; document extraction keeps Aadhaar to the last 4 digits; identity never upgrades a mismatch; screening
never clears a hit; risk score and tier equal the engine's output). The policy engine runs them; this module reports,
per agent, whether the policy has any guardrail for it, so a missing guardrail shows as a gap in the scorecard instead
of an empty row.
"""

from __future__ import annotations

from evalkit.evaluators.agent.slicer import AgentSlice
from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult


class GuardrailCoverageEvaluator(Evaluator):
    metric = "AG-5"
    severity = "S1"

    def evaluate_agent(self, sl: AgentSlice, ctx: EvalContext) -> CheckResult | None:
        if ctx.policy is None:
            return self.skip("no policy file yet — guardrails are policy rules with agent and metric AG-5", agent=sl.agent)
        if any(r.agent == sl.agent and r.metric_id == "AG-5" for r in ctx.policy.rules):
            return None  # the policy engine's checks are the AG-5 results
        return self.skip("the policy has no AG-5 guardrail rule for this agent", agent=sl.agent)
