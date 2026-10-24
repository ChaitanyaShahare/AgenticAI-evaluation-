"""TR-2 trajectory match: the run's tool sequence against the case's reference trajectory, in the case's match mode.

Modes (agentevals semantics, on tool names):
  strict     same calls in the same order
  unordered  same calls, any order (multiset)
  subset     every call the run made is in the reference (no extra tools)
  superset   every reference call appears in the run (extra calls allowed)
Reference trajectories live in projects/<name>/reference_trajectories/RT-*.json; a case without one is skipped.
"""

from __future__ import annotations

from collections import Counter

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory


def sequences_match(actual: list[str], reference: list[str], mode: str) -> tuple[bool, str]:
    if mode == "strict":
        ok = actual == reference
        return ok, "" if ok else f"order or content differs: {actual} vs {reference}"
    if mode == "unordered":
        extra, missing = Counter(actual) - Counter(reference), Counter(reference) - Counter(actual)
        ok = not extra and not missing
        return ok, "" if ok else f"missing {dict(missing)}, extra {dict(extra)}"
    if mode == "subset":
        extra = sorted(set(actual) - set(reference))
        return not extra, "" if not extra else f"calls outside the reference: {extra}"
    if mode == "superset":
        missing = sorted(set(reference) - set(actual))
        return not missing, "" if not missing else f"reference calls missing: {missing}"
    raise ValueError(f"unknown match mode {mode}")


class TrajectoryMatchEvaluator(Evaluator):
    metric = "TR-2"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        mode, refs = ctx.case.match_mode, ctx.case.reference
        if not mode or not refs:
            return [self.skip("case states no match mode or reference trajectory")]
        missing = [r for r in refs if r not in ctx.references]
        if missing:
            return [self.skip(f"reference trajectory {', '.join(missing)} not written yet")]
        reference = [t for r in refs for t in ctx.references[r]]
        ok, why = sequences_match(traj.tool_sequence(), reference, mode)
        unreviewed = sorted(set(refs) & ctx.unreviewed_references)
        note = f" (reference {', '.join(unreviewed)} not yet reviewed)" if unreviewed else ""
        return [self.result("pass" if ok else "fail", f"{mode} match vs {', '.join(refs)}{note}" + (f": {why}" if why else ""))]
