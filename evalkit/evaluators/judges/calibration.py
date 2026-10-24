"""Judge calibration (SOP §3.10): does the LLM judge agree with the testers well enough to gate?

Labels are a JSONL file, one row per (trace, metric, rater):
    {"trace_id": "KYC-GLD-001/t1", "metric": "TR-8.task", "rater": "T1", "score": 3}
The judge's own scores use rater "judge". For each metric the report gives, on the traces both raters scored:
  * exact agreement — share of traces with the same score;
  * Cohen's κ — agreement corrected for chance (unweighted), and quadratic-weighted κ for the ordinal 0–3 scale;
for the judge against each tester, tester against tester (the ceiling a judge can be expected to reach), and the
judge against the testers' consensus. The consensus is an adjudicated label (rater "consensus") where one exists,
otherwise the score all testers gave when they agree; traces where they disagree and nobody adjudicated are left out.
A metric's judge may gate only if, against the consensus on at least min_traces traces, κ ≥ min_kappa and agreement ≥
min_agreement (SOP §3.9; configs/gates.yaml › judges); otherwise it stays advisory — an accepted outcome.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

JUDGE = "judge"
CONSENSUS = "consensus"


@dataclass(frozen=True)
class Label:
    trace_id: str
    metric: str
    rater: str
    score: int


def load_labels(path: Path) -> list[Label]:
    """JSONL rows, or a YAML labelling sheet (`evalkit calibrate --template`) with an `items:` list."""
    if path.suffix in (".yaml", ".yml"):
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rater = data.get("rater")
        out = []
        for n, it in enumerate(data.get("items") or [], 1):
            if it.get("score") is None:
                continue  # not labelled yet
            try:
                out.append(Label(str(it["trace_id"]), str(it["metric"]), str(it.get("rater") or rater), int(it["score"])))
            except (ValueError, KeyError, TypeError) as e:
                raise ValueError(f"{path.name} item {n}: need trace_id, metric and a whole-number score 0–3 ({e})") from None
        if out and rater is None and any(lb.rater == "None" for lb in out):
            raise ValueError(f"{path.name}: say who labelled — add `rater: T1` at the top")
        return out
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            out.append(Label(str(d["trace_id"]), str(d["metric"]), str(d["rater"]), int(d["score"])))
        except (ValueError, KeyError, TypeError) as e:
            raise ValueError(f"{path.name} line {n}: need trace_id, metric, rater and a whole-number score ({e})") from None
    return out


def agreement(a: list[int], b: list[int]) -> float:
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a) if a else 0.0


def cohen_kappa(a: list[int], b: list[int], categories: list[int] | None = None, weights: str | None = None) -> float:
    """Cohen's κ for two raters over the same items. weights=None (unweighted) or 'quadratic' (ordinal scales).
    When chance agreement is total (both raters always gave one and the same score) κ is 1.0 if they agree, else 0.0."""
    if len(a) != len(b) or not a:
        raise ValueError("two equally long, non-empty score lists are needed")
    cats = sorted(set(categories or []) | set(a) | set(b))
    k, n = len(cats), len(a)
    idx = {c: i for i, c in enumerate(cats)}
    if k == 1:
        return 1.0

    def w(i: int, j: int) -> float:
        return ((i - j) / (k - 1)) ** 2 if weights == "quadratic" else float(i != j)

    obs = Counter((idx[x], idx[y]) for x, y in zip(a, b, strict=True))
    pa, pb = Counter(idx[x] for x in a), Counter(idx[y] for y in b)
    observed = sum(w(i, j) * c for (i, j), c in obs.items()) / n
    expected = sum(w(i, j) * pa[i] * pb[j] for i in range(k) for j in range(k)) / (n * n)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1 - observed / expected


@dataclass
class PairStats:
    raters: tuple[str, str]
    n: int
    agreement: float
    kappa: float
    weighted_kappa: float


@dataclass
class MetricCalibration:
    metric: str
    pairs: list[PairStats] = field(default_factory=list)
    gates: bool = False
    reason: str = ""


def with_consensus(labels: list[Label], metric: str, testers: list[str]) -> list[Label]:
    """Add derived consensus labels: adjudicated ones are kept; otherwise the shared score of agreeing testers."""
    mine = [lb for lb in labels if lb.metric == metric]
    given = {lb.trace_id for lb in mine if lb.rater == CONSENSUS}
    scores: dict[str, dict[str, int]] = {}
    for lb in mine:
        if lb.rater in testers:
            scores.setdefault(lb.trace_id, {})[lb.rater] = lb.score
    derived = [
        Label(t, metric, CONSENSUS, next(iter(s.values())))
        for t, s in scores.items()
        if t not in given and len(s) == len(testers) and len(set(s.values())) == 1
    ]
    return labels + derived


def pair_stats(labels: list[Label], metric: str, r1: str, r2: str, scale: list[int] | None = None) -> PairStats | None:
    s1 = {lb.trace_id: lb.score for lb in labels if lb.metric == metric and lb.rater == r1}
    s2 = {lb.trace_id: lb.score for lb in labels if lb.metric == metric and lb.rater == r2}
    common = sorted(set(s1) & set(s2))
    if not common:
        return None
    a, b = [s1[t] for t in common], [s2[t] for t in common]
    return PairStats((r1, r2), len(common), round(agreement(a, b), 3), round(cohen_kappa(a, b, scale), 3),
                     round(cohen_kappa(a, b, scale, "quadratic"), 3))  # fmt: skip


def calibrate(labels: list[Label], min_kappa: float = 0.6, min_agreement: float = 0.85, min_traces: int = 30,
              scale_max: int = 3) -> list[MetricCalibration]:  # fmt: skip
    scale = list(range(scale_max + 1))
    out = []
    for metric in sorted({lb.metric for lb in labels}):
        testers = sorted({lb.rater for lb in labels if lb.metric == metric and lb.rater not in (JUDGE, CONSENSUS)})
        rows = with_consensus(labels, metric, testers)
        mc = MetricCalibration(metric)
        for t in testers:
            if p := pair_stats(rows, metric, JUDGE, t, scale):
                mc.pairs.append(p)
        for t1, t2 in combinations(testers, 2):
            if p := pair_stats(rows, metric, t1, t2, scale):
                mc.pairs.append(p)
        vs_consensus = pair_stats(rows, metric, JUDGE, CONSENSUS, scale)
        if vs_consensus:
            mc.pairs.append(vs_consensus)
        if not testers:
            mc.reason = "no tester labels"
        elif vs_consensus is None:
            mc.reason = "no trace has both a judge score and a tester consensus"
        elif vs_consensus.n < min_traces:
            mc.reason = f"only {vs_consensus.n} traces with judge and consensus labels (need {min_traces})"
        elif vs_consensus.kappa < min_kappa or vs_consensus.agreement < min_agreement:
            mc.reason = f"vs consensus: κ {vs_consensus.kappa}, agreement {vs_consensus.agreement:.0%}"
        else:
            mc.gates = True
            mc.reason = f"κ ≥ {min_kappa} and agreement ≥ {min_agreement:.0%} against the testers' consensus"
        out.append(mc)
    return out


def render(results: list[MetricCalibration]) -> str:
    lines = ["Judge calibration (agreement · Cohen's κ · quadratic-weighted κ · traces)"]
    for mc in results:
        lines.append(f"\n{mc.metric}: {'GATES' if mc.gates else 'advisory'} — {mc.reason}")
        for p in mc.pairs:
            lines.append(
                f"  {p.raters[0]:>6} vs {p.raters[1]:<6} {p.agreement:6.0%}  κ {p.kappa:5.2f}  κw {p.weighted_kappa:5.2f}  n {p.n}"
            )
    return "\n".join(lines)


# ------------------------------------------------------------------ inputs for `evalkit calibrate`
def trace_id(case_id: str, trial: int) -> str:
    return f"{case_id}/t{trial}"


def judge_labels(results: Path, cfg) -> list[Label]:
    """The judge's scores from a run graded with --judges --yes (results.jsonl), as labels of rater 'judge'."""
    if not results.is_file():
        raise ValueError(f"{results}: not found — grade the run with `evalkit grade <run> --judges --yes` first")
    metrics = {m.id: m.scale_max for m in cfg.metrics}
    out = []
    for line in results.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("metric") in metrics and row.get("verdict") in ("pass", "fail") and row.get("score") is not None:
            pts = round(row["score"] * metrics[row["metric"]])
            out.append(Label(trace_id(row["case_id"], row["trial"]), row["metric"], JUDGE, pts))
    return out


def labelling_sheet(source: Path, cfg, rater: str, out: Path) -> int:
    """A YAML sheet listing every judged (trace, metric) of a run, with the anchors, for one tester to score 0–3."""
    import yaml  # noqa: PLC0415

    from evalkit.evaluators.base import replies  # noqa: PLC0415
    from evalkit.evaluators.judges.deepeval_metrics import RUBRICS  # noqa: PLC0415
    from evalkit.schema import Trajectory  # noqa: PLC0415

    folder = source / "trajectories" if (source / "trajectories").is_dir() else source
    items = []
    for f in sorted(folder.rglob("*.json")):
        try:
            t = Trajectory.load(f)
        except (ValueError, KeyError):
            continue
        if not replies(t):
            continue  # judges score conversations with a customer only
        for m in cfg.metrics:
            items.append({"trace_id": trace_id(t.meta.case_id, t.meta.trial), "metric": m.id, "score": None, "note": "",
                          "trajectory": f.as_posix()})  # fmt: skip
    head = [f"# Labelling sheet for {rater}: score each item 0–3 on the anchors below, without looking at the judge's scores.",
            "# Leave score empty for an item you cannot judge. Then: evalkit calibrate <this file> --judged <run>"]  # fmt: skip
    for m in cfg.metrics:
        r = RUBRICS.get(m.id)
        if r:
            head.append(f"# {m.id} — {r.name}: " + " · ".join(f"{k} {v}" for k, v in sorted(r.anchors.items(), reverse=True)))
    body = yaml.safe_dump({"rater": rater, "rubric_version": cfg.rubric_version, "items": items}, allow_unicode=True, sort_keys=False)
    out.write_text("\n".join(head) + "\n" + body, encoding="utf-8", newline="\n")
    return len(items)
