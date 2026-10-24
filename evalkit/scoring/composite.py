"""Composite scores (SOP §5.3). Trend tracking only — release decisions use the gates (scoring/gates.py).

  End-to-end case score = G × (0.40·TR-1 + 0.20·TR-2 + 0.20·TU-3 + 0.10·TU-5 + 0.10·TR-6)
  Per-agent score (X)   = G_X × (0.40·AG-1 + 0.25·AG-2 + 0.20·AG-3 + 0.10·AG-4 + 0.05·AG-6)
G is 0 when any S1 check of the case failed (G_X: any S1 check attributed to agent X), else 1. A component that was not
measured (skipped) is left out and the remaining weights are rescaled, and the result says which components it used,
so a score built on 2 of 5 components is never mistaken for a full one. gates.yaml may override the weights.
"""

from __future__ import annotations

from dataclasses import dataclass

from evalkit.schema import CheckResult

E2E_WEIGHTS = {"TR-1": 0.40, "TR-2": 0.20, "TU-3": 0.20, "TU-5": 0.10, "TR-6": 0.10}
AGENT_WEIGHTS = {"AG-1": 0.40, "AG-2": 0.25, "AG-3": 0.20, "AG-4": 0.10, "AG-6": 0.05}


@dataclass
class Composite:
    score: float | None  # None when no component was measured
    gate: int  # G
    used: list[str]  # components that contributed
    s1_failures: int


def s1_failed(checks: list[CheckResult]) -> int:
    return sum(1 for c in checks if c.severity == "S1" and c.verdict in ("fail", "error"))


def composite(checks: list[CheckResult], weights: dict[str, float]) -> Composite:
    by_metric: dict[str, list[float]] = {}
    for c in checks:
        if c.metric in weights and c.verdict in ("pass", "fail") and c.score is not None:
            by_metric.setdefault(c.metric, []).append(c.score)
    fails = s1_failed(checks)
    gate = 0 if fails else 1
    used = [m for m in weights if m in by_metric]
    if not used:
        return Composite(None, gate, [], fails)
    total = sum(weights[m] for m in used)
    raw = sum(weights[m] * (sum(by_metric[m]) / len(by_metric[m])) for m in used) / total
    return Composite(round(gate * raw, 3), gate, used, fails)


def case_score(checks: list[CheckResult], weights: dict[str, float] | None = None) -> Composite:
    return composite(checks, weights or E2E_WEIGHTS)  # every S1 check of the case counts towards G, agent ones included


def agent_score(checks: list[CheckResult], agent: str, weights: dict[str, float] | None = None) -> Composite:
    return composite([c for c in checks if c.agent == agent], weights or AGENT_WEIGHTS)
