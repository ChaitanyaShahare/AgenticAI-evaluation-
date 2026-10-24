"""TU-1 tool selection: F1 of the run's tools against the case's required and forbidden sets.

TP = required tools called · FN = required tools not called · FP = forbidden tools called.
F1 = 2·TP / (2·TP + FN + FP). The check passes only at F1 = 1 (nothing missing, nothing forbidden); the score feeds the
suite threshold. Conditional entries of the catalogue ("verify_pan with a guessed dob") are not used until WP6.
"""

from __future__ import annotations

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory


def selection_f1(called: set[str], required: set[str], forbidden: set[str]) -> tuple[float, list[str], list[str]]:
    tp = len(required & called)
    missing, wrong = sorted(required - called), sorted(forbidden & called)
    denom = 2 * tp + len(missing) + len(wrong)
    return (round(2 * tp / denom, 3) if denom else 1.0), missing, wrong


class ToolSelectionEvaluator(Evaluator):
    metric = "TU-1"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        req, forb = set(ctx.case.required_tools), set(ctx.case.forbidden_tools)
        if not req and not forb:
            return [self.skip("case states no required or forbidden tools")]
        f1, missing, wrong = selection_f1(set(traj.tool_sequence()), req, forb)
        parts = ([f"missing {', '.join(missing)}"] if missing else []) + ([f"forbidden called: {', '.join(wrong)}"] if wrong else [])
        return [self.result("pass" if f1 == 1.0 else "fail", f"F1 {f1}" + (f" — {'; '.join(parts)}" if parts else ""), score=f1)]
