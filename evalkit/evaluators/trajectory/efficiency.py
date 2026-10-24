"""TR-6 step efficiency (S3, report only): reference ÷ actual tool calls, loops and the step limit.

Without a reference trajectory the reference is the number of distinct calls (same tool and identical arguments), so
retries and loops lower the score. Exceeding max_steps_per_run Supervisor steps fails the check.
"""

from __future__ import annotations

import json

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory


def distinct_calls(calls) -> int:
    return len({(c.agent, c.tool, json.dumps(c.args, sort_keys=True, default=str)) for c in calls})


class StepEfficiencyEvaluator(Evaluator):
    metric = "TR-6"
    severity = "S3"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        calls = traj.tool_calls()
        if not calls:
            return [self.skip("no tool calls")]
        refs = ctx.case.reference
        if refs and all(r in ctx.references for r in refs):
            ref, basis = sum(len(ctx.references[r]) for r in refs), "reference"
        else:
            ref, basis = distinct_calls(calls), "distinct calls"
        score = round(min(1.0, ref / len(calls)), 3)
        steps = sum(1 for s in traj.steps if s.kind == "decision")
        detail = f"{basis} {ref} ÷ actual {len(calls)} calls; {steps} Supervisor step(s)"
        if steps > ctx.limits.max_steps:
            return [self.result("fail", f"{detail} > limit {ctx.limits.max_steps}", score=score)]
        return [self.result("pass", detail, score=score)]
