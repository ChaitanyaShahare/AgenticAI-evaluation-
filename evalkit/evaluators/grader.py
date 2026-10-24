"""Grade a set of trajectories: every trial check, every agent's scorecard checks, the group checks, then pass^k.

    suite = ProjectSuite.load("kyc_onboarding")
    graded = grade(suite, trajectories)          # offline: no model calls
    graded.results       one CaseResult per case × trial
    graded.case_checks   case-level checks (TR-7 pass^k)
    graded.scorecards    per-agent scorecards (AG-1 … AG-6, TU-7, AG-5)

An evaluator that raises is recorded as an `error` check with the exception, never dropped: a broken evaluator must be
visible in the report, and an error on an S1 metric fails the gate like a failure.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path

from evalkit.config.registry import AGENT_EVALUATORS, GROUP_EVALUATORS, METRICS, TRIAL_EVALUATORS, ProjectSuite
from evalkit.evaluators.agent.slicer import slice_agents
from evalkit.evaluators.base import EvalContext
from evalkit.evaluators.trajectory.reliability import pass_hat_k, trial_passed
from evalkit.reporting.redaction import Redactor
from evalkit.schema import CaseResult, CheckResult, Trajectory
from evalkit.scoring.aggregate import agent_scorecards, by_pattern, case_scores, suite_stats


@dataclass
class Graded:
    results: list[CaseResult]
    case_checks: dict[str, CheckResult]
    flaky: list[str]
    scorecards: dict[str, dict]
    notes: list[str] = field(default_factory=list)
    trajectories: list[Trajectory] = field(default_factory=list)  # as graded (a duplicate trial gets a new number)


def _error(metric: str, exc: Exception, agent: str | None = None) -> CheckResult:
    where = traceback.extract_tb(exc.__traceback__)[-1]
    return CheckResult(
        metric=metric,
        agent=agent,
        verdict="error",
        severity=METRICS.get(metric, ("", "S2"))[1],
        detail=f"evaluator error: {type(exc).__name__}: {exc} ({Path(where.filename).name}:{where.lineno})",
    )


def agent_checks(traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
    out: list[CheckResult] = []
    for name, sl in slice_agents(traj, ctx).items():
        if sl.stubbed:
            out.append(
                CheckResult(metric="AG-4", agent=name, verdict="skip", severity="S2", detail="stubbed in this case (L2 canned output)")
            )
            continue
        ev = {m: cls() for m, cls in AGENT_EVALUATORS.items()}
        calls = [
            ("AG-1", ev["AG-1"].evaluate_agent, (sl, traj, ctx)),
            ("AG-2", ev["AG-2"].evaluate_agent, (sl, ctx)),
            ("TU-7", ev["AG-2"].allow_list, (sl, ctx)),
            ("AG-3", ev["AG-3"].evaluate_agent, (sl, traj, ctx)),
            ("AG-4", ev["AG-4"].evaluate_agent, (sl, ctx)),
            ("AG-5", ev["AG-5"].evaluate_agent, (sl, ctx)),
            ("AG-6", ev["AG-6"].evaluate_agent, (sl,)),
        ]
        for metric, fn, fn_args in calls:
            try:
                res = fn(*fn_args)
            except Exception as e:  # noqa: BLE001 — recorded, not swallowed
                res = _error(metric, e, name)
            if res is not None:
                out.append(res)
    return out


def grade_trial(traj: Trajectory, ctx: EvalContext) -> CaseResult:
    checks: list[CheckResult] = []
    for cls in TRIAL_EVALUATORS:
        try:
            checks += cls().evaluate(traj, ctx)
        except Exception as e:  # noqa: BLE001
            checks.append(_error(cls.metric if cls.metric != "POLICY" else "TR-3", e))
    checks += agent_checks(traj, ctx)
    return CaseResult(case_id=traj.meta.case_id, trial=traj.meta.trial, checks=checks)


def redact(check: CheckResult, suite: ProjectSuite) -> CheckResult:
    """Mask any identifier a check detail quotes (a TU-4 detail may name the PAN it could not ground)."""
    detail = Redactor(suite.base.recognizers).text(check.detail)
    return check if detail == check.detail else check.model_copy(update={"detail": detail})


def grade(suite: ProjectSuite, trajectories: list[Trajectory], judge=None, rubrics: list | None = None) -> Graded:
    """judge: an optional RubricJudge (judges/geval_rubric.py) — advisory S3 checks per rubric; None grades without judges."""
    notes = list(suite.notes)
    runs: dict[str, list[tuple[Trajectory, EvalContext]]] = {}
    results: dict[tuple[str, int], CaseResult] = {}
    for traj in sorted(trajectories, key=lambda t: (t.meta.case_id, t.meta.trial)):
        case = suite.cases.get(traj.meta.case_id)
        if case is None:
            notes.append(f"{traj.meta.case_id}: not a case of project {suite.project} — skipped")
            continue
        ctx = suite.context(case)
        if (case.case_id, traj.meta.trial) in results:  # same case and trial twice (e.g. a scripted and a live recording)
            trial = max(t for c, t in results if c == case.case_id) + 1
            notes.append(f"{case.case_id}: trial {traj.meta.trial} appears twice (run {traj.meta.run_id}) — graded as trial {trial}")
            traj = traj.model_copy(update={"meta": traj.meta.model_copy(update={"trial": trial})})
        runs.setdefault(case.case_id, []).append((traj, ctx))
        results[(case.case_id, traj.meta.trial)] = grade_trial(traj, ctx)
        if judge is not None:
            from evalkit.evaluators.judges.geval_rubric import judge_checks  # noqa: PLC0415

            results[(case.case_id, traj.meta.trial)].checks.extend(judge_checks(judge, traj, ctx, rubrics or []))
    for cls in GROUP_EVALUATORS:
        try:
            for key, checks in cls().evaluate_group(runs).items():
                if key in results:
                    results[key].checks.extend(checks)
        except Exception as e:  # noqa: BLE001
            for r in results.values():
                r.checks.append(_error(cls.metric, e))
    ordered = list(results.values())
    for r in ordered:
        r.passed = trial_passed(r)
        r.checks = [redact(c, suite) for c in r.checks]
    end_states = {(t.meta.case_id, t.meta.trial): t.end_state for trials in runs.values() for t, _ in trials}
    case_checks, flaky = pass_hat_k(ordered, end_states)
    cards = agent_scorecards(ordered, list(suite.base.agents))
    graded_trajs = [t for trials in runs.values() for t, _ in trials]
    return Graded(ordered, case_checks, flaky, cards, notes, graded_trajs)


def summary(graded: Graded, suite: ProjectSuite) -> dict:
    return {
        "suite": suite_stats(graded.results),
        "agents": graded.scorecards,
        "patterns": by_pattern(graded.results, suite.cases),
        "cases": case_scores(graded.results),
        "pass_k": {cid: c.model_dump() for cid, c in graded.case_checks.items()},
        "flaky": graded.flaky,
        "notes": graded.notes,
    }
