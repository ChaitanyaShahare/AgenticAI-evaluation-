"""TR-7 reliability: pass^k across the trials of a case, and the flaky-case list.

A trial passes when none of its checks failed at S1 and its outcome check (TR-1, or AG-1 for agent-level cases) did not
fail. pass^k = 1 when every trial of the case passed. A case is flaky when its trials disagree (some pass, some fail,
or the end state differs between trials); SOP §3.5 suspends the cycle if more than 10% of cases are flaky.
"""

from __future__ import annotations

import json

from evalkit.schema import CaseResult, CheckResult

OUTCOME = ("TR-1", "AG-1")


def trial_passed(res: CaseResult) -> bool:
    return not any(c.verdict in ("fail", "error") and (c.severity == "S1" or c.metric in OUTCOME) for c in res.checks)


def pass_hat_k(results: list[CaseResult], end_states: dict[tuple[str, int], dict]) -> tuple[dict[str, CheckResult], list[str]]:
    """Returns (case_id -> TR-7 check, flaky case IDs). Cases run once get a skip."""
    by_case: dict[str, list[CaseResult]] = {}
    for r in results:
        by_case.setdefault(r.case_id, []).append(r)
    checks, flaky = {}, []
    for case_id, trials in sorted(by_case.items()):
        k = len(trials)
        if k < 2:
            checks[case_id] = CheckResult(metric="TR-7", verdict="skip", severity="S2", detail="run once — pass^k needs k ≥ 2")
            continue
        passed = [trial_passed(t) for t in trials]
        states = {json.dumps(end_states.get((case_id, t.trial), {}), sort_keys=True, default=str) for t in trials}
        if len(set(passed)) > 1 or len(states) > 1:
            flaky.append(case_id)
        ok = all(passed)
        checks[case_id] = CheckResult(
            metric="TR-7",
            verdict="pass" if ok else "fail",
            severity="S2",
            score=1.0 if ok else 0.0,
            detail=f"{sum(passed)}/{k} trials passed" + ("; end state differs between trials" if len(states) > 1 else ""),
        )
    return checks, flaky
