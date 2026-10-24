"""`evalkit coverage`: what the case suite covers, per agent and pattern, and what its oracles still lack.

Tables (computed from the case YAML files, like the catalogue's Coverage sheet):
  primary agent × pattern        blanks in the per-agent isolation and fault columns are gaps (SOP §3.8)
  level × severity, run sets     cases and agent runs (cases × k) per run set
  oracle completeness            per agent: structured agent outputs (AG-1), argument expectations (TU-3),
                                 reference trajectories, and how many of those references are reviewed
`--against-catalogue` recomputes the agent × pattern matrix from the workbook rows and reports any difference, so the
YAML suite can be shown to equal the catalogue it came from.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from evalkit.config.loader import ProjectConfig
from evalkit.datasets.catalogue_import import read_rows
from evalkit.datasets.loader import CaseFile

REQUIRED_PATTERNS = ("Per-agent isolation", "Tool fault injection")  # every agent needs ≥ 1 case in each (SOP §3.8)


@dataclass
class Coverage:
    patterns: list[str]
    agents: list[str]
    matrix: Counter = field(default_factory=Counter)  # (agent, pattern) -> cases
    level_severity: Counter = field(default_factory=Counter)
    run_sets: dict[str, tuple[int, int]] = field(default_factory=dict)  # run set -> (cases, cases × k)
    oracles: dict[str, dict[str, int]] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    def total(self, agent: str | None = None, pattern: str | None = None) -> int:
        return sum(n for (a, p), n in self.matrix.items() if agent in (None, a) and pattern in (None, p))


def agent_order(agents: set[str]) -> list[str]:
    return (["E2E"] if "E2E" in agents else []) + sorted(agents - {"E2E"})


def coverage(cases: list[CaseFile], pcfg: ProjectConfig, unreviewed: set[str] = frozenset(), trials_for=None) -> Coverage:
    """trials_for(severity, mode) gives k per run mode (EvalConfig.trials_for); without it, each case's own trials."""
    patterns = list(pcfg.datasets)
    cov = Coverage(patterns, agent_order({c.primary_agent for c in cases}))
    for c in cases:
        cov.matrix[(c.primary_agent, c.pattern)] += 1
        cov.level_severity[(c.level, c.severity)] += 1
    for rs in ("smoke", "gate", "full"):
        sel = [c for c in cases if rs in c.run_sets]
        cov.run_sets[rs] = (len(sel), sum(trials_for(c.severity, rs) if trials_for else c.trials for c in sel))
    for a in cov.agents:
        mine = [c for c in cases if c.primary_agent == a]
        refs = [r for c in mine for r in c.reference]
        cov.oracles[a] = {
            "cases": len(mine),
            "S1": sum(c.severity == "S1" for c in mine),
            "agent_outputs": sum(bool(c.expected.agent_outputs) for c in mine),
            "arguments": sum(bool(c.expected.arguments) for c in mine),
            "with_reference": sum(bool(c.reference) for c in mine),
            "reference_reviewed": sum(r not in unreviewed for r in refs),
            "references": len(refs),
        }
    for a in cov.agents:
        if a == "E2E":
            continue
        for p in REQUIRED_PATTERNS:
            if p in patterns and not cov.matrix[(a, p)]:
                cov.gaps.append(f"{a} has no {p!r} case")
    return cov


def catalogue_matrix(workbook: Path) -> Counter:
    return Counter((str(r["Primary agent"]).strip(), str(r["Pattern"]).strip()) for _, r in read_rows(workbook))


def compare(cov: Coverage, catalogue: Counter) -> list[str]:
    diffs = []
    for key in sorted(set(cov.matrix) | set(catalogue)):
        if cov.matrix[key] != catalogue[key]:
            diffs.append(f"{key[0]} × {key[1]}: YAML {cov.matrix[key]}, catalogue {catalogue[key]}")
    return diffs


def render(cov: Coverage) -> str:
    short = {p: p.split(" (")[0].split(" / ")[0][:11] for p in cov.patterns}
    lines = ["Primary agent × pattern (cases)", "  " + f"{'agent':6}" + "".join(f"{short[p]:>12}" for p in cov.patterns) + f"{'total':>8}"]
    for a in cov.agents:
        cells = "".join(f"{(cov.matrix[(a, p)] or '·'):>12}" for p in cov.patterns)
        lines.append(f"  {a:6}{cells}{cov.total(a):>8}")
    lines.append(f"  {'total':6}" + "".join(f"{cov.total(pattern=p):>12}" for p in cov.patterns) + f"{cov.total():>8}")
    lines.append("\nLevel × severity")
    for lvl in sorted({lv for lv, _ in cov.level_severity}):
        row = "  ".join(f"{s} {cov.level_severity[(lvl, s)]:>3}" for s in ("S1", "S2", "S3"))
        lines.append(f"  {lvl:6} {row}")
    lines.append("\nRun sets (cases · agent runs = cases × k)")
    for rs, (n, runs) in cov.run_sets.items():
        lines.append(f"  {rs:6} {n:>4} · {runs:>4}")
    lines.append("\nOracle completeness per primary agent (structured expectations the evaluators can read)")
    lines.append(f"  {'agent':6}{'cases':>7}{'S1':>5}{'AG-1 outputs':>14}{'TU-3 args':>11}{'with RT':>9}{'RT reviewed':>13}")
    for a, o in cov.oracles.items():
        lines.append(
            f"  {a:6}{o['cases']:>7}{o['S1']:>5}{o['agent_outputs']:>14}{o['arguments']:>11}{o['with_reference']:>9}"
            f"{o['reference_reviewed']:>7} of {o['references']:<3}"
        )
    if cov.gaps:
        lines.append("\nGaps (SOP §3.8: every agent needs isolation and fault cases)")
        lines += [f"  ! {g}" for g in cov.gaps]
    return "\n".join(lines)
