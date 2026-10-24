"""AG-1 agent task success: the agent's output equals the expected contract values.

Specialists: case.expected["agent_outputs"][agent] = {field: value} (dot paths allowed), compared after name
normalisation. A value may instead be a matcher, or a list of matchers that must all hold, for partial expectations:
{contains: DOC_LOW_QUALITY}, [{contains: full_name}, {contains: dob}] (matchers as in the policy engine). A case
without per-agent expectations skips AG-1 for specialists. Orchestrator: its task is the run's outcome, so AG-1
equals TR-1 when the case states an end state. Takes the case's severity, like TR-1.
"""

from __future__ import annotations

from evalkit.evaluators.agent.slicer import AgentSlice
from evalkit.evaluators.base import EvalContext, Evaluator, get_path, norm_text
from evalkit.evaluators.policy_engine import MATCHERS, values_match
from evalkit.evaluators.trajectory.end_state import EndStateEvaluator
from evalkit.schema import CheckResult, Trajectory


def is_matcher(want) -> bool:
    """{contains: X}, {in: [..]}, {exists: false} … — the policy engine's matchers, for partial expectations."""
    return isinstance(want, dict) and bool(want) and set(want) <= set(MATCHERS)


class AgentTaskSuccessEvaluator(Evaluator):
    metric = "AG-1"
    severity = "S2"

    def evaluate_agent(self, sl: AgentSlice, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        info, sev = ctx.agents.get(sl.agent), ctx.case.severity
        if info and info.role == "orchestrator":
            tr1 = EndStateEvaluator().evaluate(traj, ctx)[0]
            return tr1.model_copy(update={"metric": self.metric, "agent": sl.agent})
        expected = (ctx.case.expected.get("agent_outputs") or {}).get(sl.agent)
        if not expected:
            return self.skip("no expected output for this agent yet (structured from the catalogue in WP6)", agent=sl.agent)
        out = sl.final_output
        if out is None:
            return self.result("fail", "agent produced no valid output", agent=sl.agent, severity=sev)
        diffs = []
        for path, want in expected.items():
            have = get_path(out, path)
            value = have[0] if have else None
            if is_matcher(want) or (isinstance(want, list) and want and all(is_matcher(w) for w in want)):
                specs = want if isinstance(want, list) else [want]
                if not all(values_match(have, w) for w in specs):
                    diffs.append(f"{path} = {value!r}, expected {want!r}")
            elif (norm_text(value) if value is not None else None) != (norm_text(want) if want is not None else None):
                diffs.append(f"{path} = {value!r}, expected {want!r}")
        if diffs:
            return self.result("fail", "; ".join(diffs), agent=sl.agent, severity=sev)
        return self.result("pass", f"{len(expected)} field(s) as expected", agent=sl.agent, severity=sev)
