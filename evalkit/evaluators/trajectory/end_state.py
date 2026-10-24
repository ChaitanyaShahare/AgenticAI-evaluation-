"""TR-1 task success: the system-of-record state after the run equals the case's expectation.

Compares the applications row read by the adapter (status, risk tier and score, record created, reason codes) with the
expectation stated in the case. Only fields the case states are compared. The check takes the case's severity: an S1
case with the wrong outcome is an S1 failure.
"""

from __future__ import annotations

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory


class EndStateEvaluator(Evaluator):
    metric = "TR-1"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        exp, end, sev = ctx.case.expected, traj.end_state, ctx.case.severity
        if exp.get("status") is None:
            return [self.skip("no end-state expectation (agent-level case — graded by AG-1)")]
        if traj.error and not end:
            return [self.result("fail", f"run failed before an end state was written: {traj.error.splitlines()[0]}", severity=sev)]
        diffs = []
        if end.get("status") != exp["status"]:
            diffs.append(f"status {end.get('status')} ≠ {exp['status']}")
        if exp.get("risk_tier") is not None and end.get("risk_tier") != exp["risk_tier"]:
            diffs.append(f"risk_tier {end.get('risk_tier')} ≠ {exp['risk_tier']}")
        if exp.get("risk_score") is not None and end.get("risk_score") != exp["risk_score"]:
            diffs.append(f"risk_score {end.get('risk_score')} ≠ {exp['risk_score']}")
        if exp.get("record") is not None and bool(end.get("record_id")) != exp["record"]:
            diffs.append(f"record_id {end.get('record_id')!r} (expected {'a record' if exp['record'] else 'none'})")
        if exp.get("reason_codes") is not None and sorted(end.get("reason_codes") or []) != sorted(exp["reason_codes"]):
            diffs.append(f"reason_codes {end.get('reason_codes')} ≠ {exp['reason_codes']}")
        if diffs:
            return [self.result("fail", "; ".join(diffs), severity=sev)]
        return [self.result("pass", f"end state {exp['status']} as expected", severity=sev)]
