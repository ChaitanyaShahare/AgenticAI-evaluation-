"""TU-5 error handling under faults: bounded, identical retries and a customer who is told.

Applies when a call failed (an injected fault or an error body). Checks:
  * attempts per (tool, identical arguments) ≤ retry_limit + 1 (LIMIT-RETRY);
  * a retry after a failure repeats the same arguments (no argument drift while the service is down);
  * in a run with a customer (L2 / L3), the run ends with a reply.
Fabrication (claiming a result the failed tool never gave) is S1 and is written as policy rules (`implies` with
`failed:`), because what counts as a fabricated value is a business rule (D7).
"""

from __future__ import annotations

import json

from evalkit.evaluators.base import EvalContext, Evaluator, is_failure
from evalkit.schema import CheckResult, Trajectory


class ErrorHandlingEvaluator(Evaluator):
    metric = "TU-5"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        steps = [s for s in traj.steps if s.tool_call]
        failed = [s for s in steps if is_failure(s.tool_call)]
        if not failed:
            return [self.skip("no failed tool calls in this run")]
        problems = []
        limit = ctx.limits.retry_limit + 1
        for s in steps:
            if s.tool_call.attempt > limit:
                problems.append((s.index, f"{s.tool_call.tool} attempt {s.tool_call.attempt} (max {limit})"))
        for f in failed:
            nxt = next((s for s in steps if s.index > f.index and s.tool_call.agent == f.tool_call.agent), None)
            if nxt and nxt.tool_call.tool == f.tool_call.tool:
                same = json.dumps(nxt.tool_call.args, sort_keys=True) == json.dumps(f.tool_call.args, sort_keys=True)
                if not same:
                    problems.append((nxt.index, f"{f.tool_call.tool} retried with changed arguments"))
        if ctx.case.level in ("L2", "L3", "L1+L3") and not traj.final_message:
            problems.append((None, "run ended without telling the customer"))
        if problems:
            step = next((i for i, _ in problems if i is not None), None)
            return [self.result("fail", "; ".join(p for _, p in problems), step=step)]
        return [self.result("pass", f"{len(failed)} failed call(s) handled within the retry limit")]
