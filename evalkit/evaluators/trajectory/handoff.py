"""TR-5 hand-off accuracy: every delegation goes to a known specialist, gets an answer, and bounces stay within limit.

Per hand-off: the target is an agent in agents.yaml, and the target's result (or a guard that stopped the run) follows
before the next hand-off. Per run: delegations to one specialist ≤ 1 + max_bounces_per_specialist (LIMIT-BOUNCE).
Score = share of hand-offs that were valid.
"""

from __future__ import annotations

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory


class HandoffEvaluator(Evaluator):
    metric = "TR-5"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        hand = [s for s in traj.steps if s.kind == "handoff"]
        if not hand:
            return [self.skip("no hand-offs in this run")]
        bad, counts = [], {}
        for n, h in enumerate(hand):
            target = h.handoff_to or ""
            counts[target] = counts.get(target, 0) + 1
            nxt = hand[n + 1].index if n + 1 < len(hand) else len(traj.steps)
            window = [s for s in traj.steps if h.index < s.index < nxt]
            if ctx.agents and target not in ctx.agents:
                bad.append((h.index, f"hand-off to unknown agent {target!r}"))
            elif not any((s.kind == "agent_result" and s.agent == target) or s.kind == "guard" for s in window):
                bad.append((h.index, f"hand-off to {target} got no result"))
            if counts[target] > 1 + ctx.limits.max_bounces:
                bad.append((h.index, f"{target} delegated {counts[target]} times (limit {1 + ctx.limits.max_bounces})"))
        score = round(1 - len({i for i, _ in bad}) / len(hand), 3)
        if bad:
            return [self.result("fail", "; ".join(m for _, m in bad), score=score, step=bad[0][0])]
        return [self.result("pass", f"{len(hand)} hand-off(s) valid", score=1.0)]
