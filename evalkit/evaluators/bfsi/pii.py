"""BF-1 PII / PCI exposure: scan what the run exposed against the project's masking policy.

Recognisers (configs/pii_recognizers.yaml) are regular expressions with an optional checksum (Verhoeff for Aadhaar,
Luhn for card numbers), so a 12-digit reference number that is not an Aadhaar is not reported. A masked value such as
******877U or XXXX XXXX 4655 does not match a recogniser and passes.

The masking policy (projects/<name>/policies/pii_masking.yaml, human-written) says which entity may not appear where:
  scopes: replies · decisions (Supervisor reasons and messages) · agent_outputs · step_text (guard / contract notes)
          · tool_args · tool_results · end_state
Each rule gives one check. Detection here is deterministic; a Presidio NER pass for names is a later addition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from evalkit.config.loader import is_blank, load_model
from evalkit.evaluators.base import EvalContext, Evaluator, replies, walk_strings
from evalkit.schema import CheckResult, Trajectory

Scope = Literal["replies", "decisions", "agent_outputs", "step_text", "tool_args", "tool_results", "end_state"]

# ------------------------------------------------------------------ checksums
_V_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_V_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_ok(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 else 1)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


CHECKSUMS = {"verhoeff": verhoeff_ok, "luhn": luhn_ok}


# ------------------------------------------------------------------ configuration
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecognizerSpec(_Strict):
    entity: str
    pattern: str
    checksum: Literal["verhoeff", "luhn"] | None = None
    description: str = ""


class RecognizersFile(_Strict):
    version: int
    recognizers: list[RecognizerSpec]


class MaskRule(_Strict):
    id: str
    entity: str
    scopes: list[Scope] = Field(min_length=1)
    severity: Literal["S1", "S2", "S3"] = "S1"
    description: str = ""


class MaskingPolicy(_Strict):
    policy_id: str
    version: str
    owner: str
    validated: bool = False
    rules: list[MaskRule]


class MaskingFile(_Strict):
    masking: MaskingPolicy


@dataclass
class Recognizer:
    entity: str
    regex: re.Pattern
    checksum: str | None = None

    def find(self, text: str) -> list[str]:
        out = []
        for m in self.regex.finditer(text):
            value = m.group(0)
            digits = re.sub(r"\D", "", value)
            if self.checksum and not CHECKSUMS[self.checksum](digits):
                continue
            out.append(value)
        return out


def load_recognizers(path: Path) -> list[Recognizer]:
    spec = load_model(RecognizersFile, path)
    return [Recognizer(r.entity, re.compile(r.pattern), r.checksum) for r in spec.recognizers]


def load_masking(path: Path) -> MaskingPolicy | None:
    if not path.is_file() or is_blank(path):
        return None
    return load_model(MaskingFile, path).masking


def scan(text: str, recognizers: list[Recognizer]) -> list[tuple[str, str]]:
    """(entity, value) for every recognised identifier in a text."""
    return [(r.entity, v) for r in recognizers for v in r.find(text)]


# ------------------------------------------------------------------ evaluator
def scope_texts(traj: Trajectory, scope: str) -> list[tuple[int | None, str]]:
    if scope == "replies":
        return [(None, t) for t in replies(traj)]
    if scope == "end_state":
        return [(None, t) for _, t in walk_strings(traj.end_state)]
    out = []
    for s in traj.steps:
        if scope == "decisions" and s.kind == "decision":
            out += [(s.index, t) for _, t in walk_strings(s.data.get("action"))]
        elif scope == "agent_outputs" and s.kind == "agent_result":
            out += [(s.index, t) for _, t in walk_strings(s.data.get("contract"))]
        elif scope == "step_text" and s.kind in ("guard", "contract") and s.content:
            out.append((s.index, s.content))
        elif scope == "tool_args" and s.tool_call:
            out += [(s.index, t) for _, t in walk_strings(s.tool_call.args)]
        elif scope == "tool_results" and s.tool_call:
            out += [(s.index, t) for _, t in walk_strings(s.tool_call.result)]
    return out


def mask(value: str) -> str:
    keep = re.sub(r"\W", "", value)[-4:]
    return f"…{keep}"


class PiiEvaluator(Evaluator):
    metric = "BF-1"
    severity = "S1"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        if ctx.masking is None:
            return [self.skip("pii_masking.yaml is blank — the QE Lead writes the masking rules (docs/config_reference.md)")]
        out = []
        for rule in ctx.masking.rules:
            recs = [r for r in ctx.recognizers if r.entity == rule.entity]
            if not recs:
                out.append(self._rule(rule, "error", f"no recogniser for entity {rule.entity} in configs/pii_recognizers.yaml"))
                continue
            found = [(step, scope, v) for scope in rule.scopes for step, t in scope_texts(traj, scope) for _, v in scan(t, recs)]
            if found:
                step, scope, value = found[0]
                out.append(self._rule(rule, "fail", f"{rule.entity} unmasked in {scope} ({mask(value)}); {len(found)} finding(s)", step))
            else:
                out.append(self._rule(rule, "pass", f"no unmasked {rule.entity} in {', '.join(rule.scopes)}"))
        return out

    def _rule(self, rule: MaskRule, verdict: str, detail: str, step: int | None = None) -> CheckResult:
        res = self.result(verdict, f"{rule.id}: {detail}", step=step, severity=rule.severity)
        return res.model_copy(update={"rule": rule.id})
