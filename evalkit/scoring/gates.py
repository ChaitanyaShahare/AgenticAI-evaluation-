"""Release gates (SOP §3.10): apply configs/gates.yaml to graded results and return a verdict and exit code.

Verdicts, in order of precedence:
  NO_GATES    gates.yaml is blank — thresholds are human-owned and not written yet        exit 2
  SUSPENDED   more than flake_limit of repeated cases are flaky (SOP §3.5)                 exit 2
  FAIL        an S1 check failed (zero tolerance) or a measured threshold was missed       exit 1
  INCOMPLETE  a threshold could not be measured (no checks ran for it)                     exit 2
  PASS        every S1 check passed and every threshold was measured and met               exit 0
A gate never passes on missing evidence: an unmeasured threshold makes the verdict INCOMPLETE, not PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from evalkit.config.loader import GatesConfig, is_blank, load_model
from evalkit.schema import CaseResult, CheckResult, TestCase
from evalkit.scoring.aggregate import stats

EXIT = {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2, "SUSPENDED": 2, "NO_GATES": 2}


@dataclass
class GateLine:
    name: str
    value: float | None
    minimum: float
    ok: bool | None  # None: not measured
    detail: str = ""


@dataclass
class GateVerdict:
    verdict: str
    lines: list[GateLine] = field(default_factory=list)
    s1_failures: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return EXIT[self.verdict]


def load_gates(path: Path) -> GatesConfig | None:
    if not path.is_file() or is_blank(path):
        return None
    return load_model(GatesConfig, path)


def _s1_failures(results: list[CaseResult]) -> list[str]:
    out = []
    for r in results:
        for c in r.checks:
            if c.severity == "S1" and c.verdict in ("fail", "error"):
                rule = f" ({c.rule})" if c.rule else ""
                who = f" [{c.agent}]" if c.agent else ""
                out.append(f"{r.case_id} t{r.trial} · {c.metric}{rule}{who}: {c.detail}")
    return out


def evaluate_gates(
    gates: GatesConfig | None,
    results: list[CaseResult],
    cases: dict[str, TestCase],
    case_checks: dict[str, CheckResult] | None = None,
    flaky: list[str] | None = None,
) -> GateVerdict:
    if gates is None:
        return GateVerdict("NO_GATES", reasons=["configs/gates.yaml is blank — the QE Lead writes the thresholds (SOP §3.10)"])
    rows = results + [CaseResult(case_id=cid, trial=0, checks=[c]) for cid, c in (case_checks or {}).items()]
    v = GateVerdict("PASS", s1_failures=_s1_failures(rows))
    repeated = {r.case_id for r in results if r.trial > 1}
    if repeated and len(flaky or []) / len(repeated) > gates.flake_limit:
        v.verdict = "SUSPENDED"
        v.reasons.append(
            f"{len(flaky or [])} of {len(repeated)} repeated cases are flaky (limit {gates.flake_limit:.0%}): {', '.join(flaky or [])}"
        )
        return v
    if gates.s1_zero_tolerance and v.s1_failures:
        v.verdict = "FAIL"
        v.reasons.append(f"{len(v.s1_failures)} S1 check failure(s) — zero tolerance")
    for t in gates.thresholds:
        if t.metric in gates.report_only:
            continue

        def in_scope(r: CaseResult, t=t) -> bool:
            return not t.patterns or (r.case_id in cases and cases[r.case_id].pattern in t.patterns)

        if t.scope == "suite":
            groups = {"suite": stats(rows, lambda r, c, t=t, f=in_scope: c.metric == t.metric and f(r))}
        elif t.scope == "agent":
            agents = sorted({c.agent for r in rows for c in r.checks if c.metric == t.metric and c.agent})
            groups = {a: stats(rows, lambda r, c, a=a, t=t, f=in_scope: c.metric == t.metric and c.agent == a and f(r)) for a in agents}
            groups = groups or {"agents": {}}
        else:
            pats = t.patterns or sorted({cases[r.case_id].pattern for r in rows if r.case_id in cases})
            groups = {
                p: stats(rows, lambda r, c, p=p, t=t: c.metric == t.metric and r.case_id in cases and cases[r.case_id].pattern == p)
                for p in pats
            }
        for name, st in groups.items():
            s = st.get(t.metric)
            value = None if s is None else (s.pass_rate if t.stat == "pass_rate" else s.mean_score)
            label = (
                f"{t.metric} {t.stat} ({t.scope}{'' if name == 'suite' else ': ' + name}"
                + (f", {', '.join(t.patterns)}" if t.patterns and t.scope != "pattern" else "")
                + ")"
            )
            ok = None if value is None else value >= t.min
            v.lines.append(GateLine(label, value, t.min, ok, s.first_failure if s else "no checks ran"))
    if any(line.ok is False for line in v.lines):
        v.verdict = "FAIL"
        v.reasons.append("threshold(s) missed: " + "; ".join(line.name for line in v.lines if line.ok is False))
    if v.verdict == "PASS" and (unmeasured := [line.name for line in v.lines if line.ok is None]):
        v.verdict = "INCOMPLETE"
        v.reasons.append("not measured: " + "; ".join(unmeasured))
    if v.verdict == "PASS" and not results:
        v.verdict = "INCOMPLETE"
        v.reasons.append("no results to gate")
    return v
