"""BF-6 audit completeness (S1): the run record is enough to reconstruct and defend the decision.

Required: run ID, model per role and a prompt hash for every agent that acted; every tool call with its status and, when
it succeeded, its result; every approval step with its decision; every Supervisor decision with a reason; and, when the
run reached a final status, the reason codes in the end state. A run that crashed (trajectory error) fails.
"""

from __future__ import annotations

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory


def audit_gaps(traj: Trajectory, ctx: EvalContext) -> list[tuple[int | None, str]]:
    gaps: list[tuple[int | None, str]] = []
    m = traj.meta
    if traj.error:
        gaps.append((None, f"run crashed: {traj.error.splitlines()[0]}"))
    if not m.run_id:
        gaps.append((None, "no run ID"))
    if not m.models:
        gaps.append((None, "models not recorded"))
    acted = {s.agent for s in traj.steps if s.agent and s.kind in ("llm", "tool", "decision")}
    missing_hash = sorted(a for a in acted if ctx.agents and a in ctx.agents and a not in m.prompt_hashes)
    if missing_hash:
        gaps.append((None, f"no prompt hash for {', '.join(missing_hash)}"))
    for s in traj.steps:
        c = s.tool_call
        if c and c.status == "ok" and c.result is None:
            gaps.append((s.index, f"{c.tool} result not recorded"))
        if s.kind == "interrupt" and not s.data.get("decision"):
            gaps.append((s.index, "approval step without a decision"))
        if s.kind == "decision" and not ((s.data.get("action") or {}).get("reason") or "").strip():
            gaps.append((s.index, "Supervisor decision without a reason"))
    if traj.end_state.get("status") not in (None, "NEW") and traj.end_state.get("reason_codes") is None:
        gaps.append((None, "final status without reason codes"))
    return gaps


class AuditCompletenessEvaluator(Evaluator):
    metric = "BF-6"
    severity = "S1"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        gaps = audit_gaps(traj, ctx)
        if gaps:
            step = next((i for i, _ in gaps if i is not None), None)
            return [self.result("fail", "; ".join(g for _, g in gaps[:4]), step=step)]
        return [self.result("pass", f"audit record complete ({len(traj.tool_calls())} tool calls, {len(traj.steps)} steps)")]
