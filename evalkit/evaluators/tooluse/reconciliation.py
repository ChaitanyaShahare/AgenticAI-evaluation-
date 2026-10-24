"""TU-6 output fidelity (S1): every figure the system states equals a figure some tool returned.

Figures are read from customer replies, the Supervisor's customer messages and the string fields of agent outputs
(explanations, addresses …). Dates, times and numbers inside identifiers (REC-001, v3, SCR-0001) are not figures.
Indian notation is normalised: "₹1,240.00", "Rs 1240", "5 lakh" (= 500000), "2 crore", "91%" (= 0.91).
A figure reconciles when it equals a number found anywhere in a tool result or in the run inputs.
"""

from __future__ import annotations

import re
from typing import Any

from evalkit.evaluators.base import EvalContext, Evaluator, replies, walk_scalars, walk_strings
from evalkit.schema import CheckResult, Trajectory

DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:\d{2}|Z)?)?|\b\d{2}:\d{2}(?::\d{2})?\b|\b\d{2}/\d{2}/\d{4}\b"
)
FIGURE = re.compile(
    r"(?<![A-Za-z0-9\-_./])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![A-Za-z0-9\-_/]|\.\d)\s*(lakh|lac|crore|cr|%)?",
    re.IGNORECASE,
)
SCALE = {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "cr": 1e7}


def figures(text: str) -> list[tuple[str, set[float]]]:
    """(as written, candidate values) for each figure in a text."""
    text = DATETIME.sub(" ", text)
    out = []
    for m in FIGURE.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "").lower()
        v = float(raw.replace(",", ""))
        cands = {v}
        if unit in SCALE:
            cands.add(v * SCALE[unit])
        if unit == "%":
            cands.add(v / 100)
        out.append((m.group(0).strip(), cands))
    return out


def source_numbers(values: list[Any]) -> set[float]:
    nums: set[float] = set()
    for root in values:
        for v in walk_scalars(root):
            if isinstance(v, bool):
                continue
            if isinstance(v, int | float):
                nums.add(float(v))
            elif isinstance(v, str):
                for _, cands in figures(v):
                    nums |= cands
    return nums


def stated_texts(traj: Trajectory) -> list[tuple[int | None, str, str]]:
    """(step, where, text) for everything the system states as output."""
    out: list[tuple[int | None, str, str]] = [(None, "reply", r) for r in replies(traj)]
    for s in traj.steps:
        if s.kind == "agent_result":
            out += [(s.index, f"{s.agent}.{p}", t) for p, t in walk_strings(s.data.get("contract"))]
        elif s.kind == "decision":
            msg = (s.data.get("action") or {}).get("message_to_customer")
            if msg:
                out.append((s.index, "supervisor.message_to_customer", msg))
    return out


class ReconciliationEvaluator(Evaluator):
    metric = "TU-6"
    severity = "S1"

    def unreconciled(self, traj: Trajectory, agent: str | None = None) -> tuple[int, list[tuple[int | None, str]]]:
        sources = [c.result for c in traj.tool_calls()]
        sources += [s.data.get("inputs") for s in traj.steps if s.kind == "note"] + [
            s.data.get("state") for s in traj.steps if s.kind == "note"
        ]
        nums = source_numbers(sources)
        checked, bad = 0, []
        for step, where, text in stated_texts(traj):
            if agent and not where.startswith(f"{agent}."):
                continue
            for raw, cands in figures(text):
                checked += 1
                if not any(abs(c - n) < 1e-6 for c in cands for n in nums):
                    bad.append((step, f"{where}: {raw}"))
        return checked, bad

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        checked, bad = self.unreconciled(traj)
        if not checked:
            return [self.skip("no figures stated")]
        score = round(1 - len(bad) / checked, 3)
        if bad:
            step = next((i for i, _ in bad if i is not None), None)
            return [self.result("fail", "figures not from any tool output: " + "; ".join(b for _, b in bad[:4]), score=score, step=step)]
        return [self.result("pass", f"{checked} figure(s) reconcile to tool outputs", score=1.0)]
