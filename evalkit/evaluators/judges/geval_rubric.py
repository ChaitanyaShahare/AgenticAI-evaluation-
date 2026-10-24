"""Rubric judges (G-Eval style): an LLM scores one aspect of a run on an anchored 0–3 scale and says why.

Each rubric names what it judges, the anchors (SOP §3.9, quoted), and which views of the trajectory the judge sees.
The judge reads a compact, masked rendering of the run — never the raw trajectory — so no unmasked identifier leaves
the harness. One structured-output call per (trace, rubric) on the Anthropic SDK (`messages.parse`, effort pinned, no
sampling parameters), cached by trace content, rubric version and model (judges/cache.py).

Results are CheckResults with the rubric ID as metric, severity S3 and score = points ÷ 3: advisory, report-only.
A judge contributes to gates only after calibration (judges/calibration.py) shows agreement with the testers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from evalkit.config.loader import JudgesConfig
from evalkit.evaluators.base import EvalContext, replies
from evalkit.evaluators.bfsi.pii import mask, scan
from evalkit.evaluators.judges.cache import JudgeCache
from evalkit.schema import CheckResult, Trajectory


@dataclass(frozen=True)
class Rubric:
    id: str  # metric ID, matches configs/judges.yaml › metrics
    name: str
    question: str  # what the judge decides
    anchors: dict[int, str]  # score -> anchor text (SOP §3.9)
    views: tuple[str, ...]  # task, steps, plan, replies, end_state


class Verdict(BaseModel):
    """The judge's answer (structured output)."""

    reason: str = Field(description="Two or three sentences citing the steps or reply text that justify the score")
    score: int = Field(ge=0, le=3, description="0–3 on the anchors given")


CUSTOMER_EXPLANATION = Rubric(
    id="BF-4.explanation",
    name="Customer explanation",
    question="How good is what the customer was told: accurate about the outcome, complete about next steps, giving reasons, "
    "with the required disclosures, and without advice or internal details?",
    anchors={
        3: "Accurate, complete, cites reasons, required disclosures present",
        2: "Accurate but incomplete or unclear in one point",
        1: "Vague, partly inaccurate, or missing a disclosure",
        0: "Wrong, misleading, or leaks restricted information",
    },
    views=("task", "end_state", "replies"),
)


def _clip(value: Any, n: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= n else text[: n - 1] + "…"


def render_trace(traj: Trajectory, ctx: EvalContext, views: tuple[str, ...]) -> str:
    """The run as the judge sees it, with every recognised identifier masked."""
    parts: list[str] = []
    if "task" in views:
        parts.append(f"TASK: {ctx.case.title or ctx.case.case_id}")
        parts += [f"CUSTOMER: {t}" for t in traj.user_turns]
    if "plan" in views and ctx.case.reference:
        plan = [t for r in ctx.case.reference for t in ctx.references.get(r, [])]
        parts.append(f"EXPECTED PLAN ({ctx.case.match_mode or 'superset'}): " + " → ".join(plan))
    if "steps" in views:
        parts.append("STEPS:")
        for s in traj.steps:
            if s.tool_call:
                c = s.tool_call
                parts.append(f"  [{s.index}] {c.agent} → {c.tool}({_clip(c.args, 120)}) = {c.status}: {_clip(c.result)}")
            elif s.kind == "handoff":
                parts.append(f"  [{s.index}] {s.agent} hands off to {s.handoff_to}")
            elif s.kind == "decision":
                a = s.data.get("action") or {}
                parts.append(f"  [{s.index}] supervisor decides {a.get('action')} {a.get('target') or ''}: {_clip(a.get('reason'), 200)}")
            elif s.kind in ("guard", "contract", "interrupt"):
                parts.append(f"  [{s.index}] {s.kind} {s.agent or ''}: {_clip(s.content or s.data)}")
            elif s.kind == "user":
                parts.append(f"  [{s.index}] customer: {_clip(s.content, 200)}")
    if "replies" in views:
        parts += [f"REPLY: {r}" for r in replies(traj)] or ["REPLY: (none)"]
    if "end_state" in views:
        parts.append(f"END STATE: {json.dumps(traj.end_state, ensure_ascii=False, default=str)}")
    text = "\n".join(parts)
    for _, value in scan(text, ctx.recognizers):
        text = text.replace(value, mask(value))
    return text


def system_prompt(rubric: Rubric) -> str:
    anchors = "\n".join(f"{k} — {v}" for k, v in sorted(rubric.anchors.items(), reverse=True))
    return (
        "You evaluate one run of a multi-agent financial-services assistant for a quality-engineering team. "
        "Judge only what the run shows; do not assume steps that are not listed. "
        f"Criterion: {rubric.name}. {rubric.question}\n\nScore on this anchored scale:\n{anchors}\n\n"
        "Identifiers are masked on purpose; masking is not a defect. Give the reason first, then the score."
    )


def prompt_hash(rubric: Rubric) -> str:
    return hashlib.sha256(system_prompt(rubric).encode()).hexdigest()[:16]


class RubricJudge:
    """Scores trajectories on rubrics. `client` is an Anthropic client (or a test double with messages.parse)."""

    def __init__(self, client: Any, cfg: JudgesConfig, cache: JudgeCache | None = None):
        self.client, self.cfg, self.cache = client, cfg, cache
        self.calls = 0  # live judge calls made (cache hits excluded)
        self.usage = {"model": cfg.model, "calls": 0, "input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}  # fmt: skip

    def _ask(self, rubric: Rubric, trace_text: str) -> tuple[Verdict | None, str | None]:
        try:
            resp = self.client.messages.parse(
                model=self.cfg.model,
                max_tokens=self.cfg.max_tokens,
                system=[{"type": "text", "text": system_prompt(rubric), "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": f"The run:\n\n{trace_text}"}],
                output_format=Verdict,
                output_config={"effort": self.cfg.effort},
            )
        except Exception as e:  # noqa: BLE001 — an unavailable judge is an error result, never a pass
            return None, f"{type(e).__name__}: {str(e)[:200]}"
        self.calls += 1
        self.usage["calls"] += 1
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            self.usage[k] += int(getattr(getattr(resp, "usage", None), k, 0) or 0)
        if resp.stop_reason in ("refusal", "max_tokens"):
            return None, f"judge stopped: {resp.stop_reason}"
        return getattr(resp, "parsed_output", None), None

    def score(self, traj: Trajectory, ctx: EvalContext, rubric: Rubric) -> CheckResult:
        key = JudgeCache.key(traj, rubric.id, self.cfg.rubric_version, self.cfg.model, prompt_hash(rubric))
        hit = self.cache.get(key) if self.cache else None
        if hit is None:
            verdict, err = self._ask(rubric, render_trace(traj, ctx, rubric.views))
            if verdict is None:
                return CheckResult(metric=rubric.id, verdict="error", severity="S3", detail=f"judge unavailable — {err}")
            hit = {"score": verdict.score, "reason": verdict.reason, "model": self.cfg.model, "rubric_version": self.cfg.rubric_version}
            if self.cache:
                self.cache.put(key, hit)
        pts = int(hit["score"])
        return CheckResult(
            metric=rubric.id,
            verdict="pass" if pts >= 2 else "fail",
            severity="S3",
            score=round(pts / 3, 3),
            detail=f"{pts}/3 (advisory judge) — {hit['reason']}",
        )


# ------------------------------------------------------------------ planning and wiring
def applies(rubric: Rubric, traj: Trajectory) -> bool:
    """Judges score conversations with a customer (L2 / L3); a specialist run alone (L1) has no task to judge."""
    return bool(replies(traj))


def judge_checks(judge: RubricJudge, traj: Trajectory, ctx: EvalContext, rubrics: list[Rubric]) -> list[CheckResult]:
    return [judge.score(traj, ctx, r) for r in rubrics if applies(r, traj)]


@dataclass
class JudgePlan:
    calls: int  # judgements needed
    cached: int  # of which already in the cache
    input_tokens: int  # rough estimate for the uncached calls (characters ÷ 4)
    output_tokens: int

    def cost(self, cfg: JudgesConfig) -> float | None:
        p = cfg.pricing
        if p.input_per_mtok is None or p.output_per_mtok is None:
            return None
        return round(self.input_tokens / 1e6 * p.input_per_mtok + self.output_tokens / 1e6 * p.output_per_mtok, 2)

    def describe(self, cfg: JudgesConfig) -> str:
        cost = self.cost(cfg)
        money = f"about ${cost:.2f}" if cost is not None else "cost unknown — set pricing in configs/judges.yaml"
        return (f"{self.calls} judgement(s) with {cfg.model}: {self.cached} cached, {self.calls - self.cached} new "
                f"(~{self.input_tokens:,} input / ~{self.output_tokens:,} output tokens; {money})")  # fmt: skip


def plan(runs: list[tuple[Trajectory, EvalContext]], cfg: JudgesConfig, rubrics: list[Rubric], cache: JudgeCache | None) -> JudgePlan:
    calls = cached = tin = 0
    for traj, ctx in runs:
        for r in rubrics:
            if not applies(r, traj):
                continue
            calls += 1
            if cache and cache.get(JudgeCache.key(traj, r.id, cfg.rubric_version, cfg.model, prompt_hash(r))):
                cached += 1
            else:
                tin += (len(system_prompt(r)) + len(render_trace(traj, ctx, r.views))) // 4
    return JudgePlan(calls, cached, tin, (calls - cached) * 400)
