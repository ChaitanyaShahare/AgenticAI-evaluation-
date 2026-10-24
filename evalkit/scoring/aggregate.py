"""Roll check results up per metric, per agent (the scorecards), per pattern and per suite.

pass_rate is over checks that were run (pass + fail + error); skips are counted separately and never help a rate.
mean_score is over the scores of run checks. A per-agent scorecard has one row per AG metric plus the agent's S1
checks (TU-7 allow-list, AG-5 guardrails), and the mean per-agent composite across trials.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from evalkit.schema import CaseResult, CheckResult, TestCase
from evalkit.scoring.composite import AGENT_WEIGHTS, E2E_WEIGHTS, agent_score, case_score

AG_METRICS = ("AG-1", "AG-2", "AG-3", "AG-4", "AG-5", "AG-6")


@dataclass
class MetricStats:
    metric: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    scores: list[float] = field(default_factory=list, repr=False)
    s1_failures: int = 0
    first_failure: str = ""

    def add(self, c: CheckResult, where: str) -> None:
        if c.verdict == "skip":
            self.skipped += 1
            return
        self.passed += c.verdict == "pass"
        self.failed += c.verdict == "fail"
        self.errors += c.verdict == "error"
        if c.score is not None:
            self.scores.append(c.score)
        if c.verdict in ("fail", "error"):
            self.s1_failures += c.severity == "S1"
            self.first_failure = self.first_failure or f"{where}: {c.detail}"

    @property
    def run(self) -> int:
        return self.passed + self.failed + self.errors

    @property
    def pass_rate(self) -> float | None:
        return round(self.passed / self.run, 3) if self.run else None

    @property
    def mean_score(self) -> float | None:
        return round(sum(self.scores) / len(self.scores), 3) if self.scores else None

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("scores")
        return {**d, "run": self.run, "pass_rate": self.pass_rate, "mean_score": self.mean_score}


def stats(results: list[CaseResult], keep=lambda r, c: True) -> dict[str, MetricStats]:
    out: dict[str, MetricStats] = {}
    for r in results:
        for c in r.checks:
            if keep(r, c):
                out.setdefault(c.metric, MetricStats(c.metric)).add(c, f"{r.case_id} t{r.trial}")
    return dict(sorted(out.items()))


def agent_scorecards(results: list[CaseResult], agents: list[str], weights: dict | None = None) -> dict[str, dict]:
    cards = {}
    for a in agents:
        rows = stats(results, lambda r, c, a=a: c.agent == a)
        if not rows:
            continue
        comps = [agent_score(r.checks, a, weights) for r in results if any(c.agent == a for c in r.checks)]
        scored = [x.score for x in comps if x.score is not None]
        cards[a] = {
            "trials": len(comps),
            "composite": round(sum(scored) / len(scored), 3) if scored else None,
            "gate": 0 if any(x.gate == 0 for x in comps) else 1,
            "s1_failures": sum(x.s1_failures for x in comps),
            "components": sorted({m for x in comps for m in x.used}, key=list(weights or AGENT_WEIGHTS).index),
            "metrics": {m: s.as_dict() for m, s in rows.items()},
        }
    return cards


def by_pattern(results: list[CaseResult], cases: dict[str, TestCase]) -> dict[str, dict[str, dict]]:
    patterns = sorted({cases[r.case_id].pattern for r in results if r.case_id in cases})
    return {
        p: {m: s.as_dict() for m, s in stats(results, lambda r, c, p=p: r.case_id in cases and cases[r.case_id].pattern == p).items()}
        for p in patterns
    }


def case_scores(results: list[CaseResult], weights: dict | None = None) -> dict[str, dict]:
    out = {}
    for r in results:
        comp = case_score(r.checks, weights or E2E_WEIGHTS)
        out[f"{r.case_id} t{r.trial}"] = {"score": comp.score, "gate": comp.gate, "used": comp.used, "s1_failures": comp.s1_failures}
    return out


def suite_stats(results: list[CaseResult]) -> dict[str, dict]:
    return {m: s.as_dict() for m, s in stats(results).items()}
