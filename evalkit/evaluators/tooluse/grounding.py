"""TU-4 argument grounding (S1): no invented IDs, dates or amounts.

Every identifier-like, date or numeric argument value must appear in a source the system legitimately had before the
call: the customer's turns, the run inputs (run_start), an L1 task's inputs, canned state, an earlier tool result, an
earlier agent output, an approval token, or a pinned environment value (eval.yaml › determinism). The model's own
decisions and reasoning are not sources. Names and free text are TU-3's concern, not this check's.
"""

from __future__ import annotations

import json
import re
from typing import Any

from evalkit.evaluators.base import EvalContext, Evaluator
from evalkit.schema import CheckResult, Trajectory

IDENTIFIER = re.compile(r"^(?=.*\d)[A-Za-z0-9][A-Za-z0-9\-/_.]{2,}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def checked_values(args: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    for key, val in args.items():
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, int | float):
                out.append((key, str(v)))
            elif isinstance(v, str) and (IDENTIFIER.match(v.strip()) or DATE.match(v.strip())):
                out.append((key, v.strip()))
    return out


def source_text(traj: Trajectory, upto: int, ctx: EvalContext) -> str:
    parts: list[Any] = [traj.user_turns, ctx.pinned]
    for s in traj.steps:
        if s.index >= upto:
            break
        if s.kind == "tool" and s.tool_call:
            parts.append(s.tool_call.result)
        elif s.kind == "agent_result":
            parts.append(s.data.get("contract"))
        elif s.kind == "user":
            parts.append(s.content)
        elif s.kind == "interrupt":
            parts.append(s.data.get("token"))
        elif s.kind == "note" and s.content in ("run_start", "l1_task", "canned_state"):
            parts.append({k: s.data.get(k) for k in ("inputs", "state")})
    return json.dumps(parts, ensure_ascii=False, default=str)


def grounded(value: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


class GroundingEvaluator(Evaluator):
    metric = "TU-4"
    severity = "S1"

    def ungrounded(self, traj: Trajectory, ctx: EvalContext, agent: str | None = None) -> tuple[int, list[tuple[int, str]]]:
        checked, bad = 0, []
        for s in traj.steps:
            c = s.tool_call
            if not c or (agent and c.agent != agent):
                continue
            vals = checked_values(c.args)
            if not vals:
                continue
            checked += 1
            text = source_text(traj, s.index, ctx)
            bad += [(s.index, f"{c.agent} → {c.tool}.{k} = {v!r}") for k, v in vals if not grounded(v, text)]
        return checked, bad

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        checked, bad = self.ungrounded(traj, ctx)
        if not checked:
            return [self.skip("no ID, date or amount arguments")]
        score = round(1 - len({i for i, _ in bad}) / checked, 3)
        if bad:
            return [
                self.result("fail", "not found in any earlier source: " + "; ".join(b for _, b in bad[:3]), score=score, step=bad[0][0])
            ]
        return [self.result("pass", f"{checked} call(s) with grounded arguments", score=1.0)]
