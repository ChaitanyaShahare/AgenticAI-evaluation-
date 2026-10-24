"""Evaluator interface and the context every evaluator receives.

An evaluator reads one canonical Trajectory (never the framework that produced it) plus an EvalContext, and returns
CheckResults. Group evaluators (TR-7 pass^k, BF-3 injection twins, BF-5 fairness pairs) read several trajectories at
once. Every check names its metric, severity and verdict; a check that cannot be computed returns `skip` with the reason,
so the report shows what was not covered instead of silently passing it.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from evalkit.schema import CheckResult, TestCase, ToolCall, Trajectory

if TYPE_CHECKING:
    from evalkit.evaluators.bfsi.pii import MaskingPolicy, Recognizer
    from evalkit.evaluators.policy_engine import Policy

SEVERITY_ORDER = {"S1": 1, "S2": 2, "S3": 3}


@dataclass
class Limits:
    retry_limit: int = 2  # retries per (tool, identical arguments): at most retry_limit + 1 attempts
    max_bounces: int = 2  # re-delegations to the same specialist
    max_steps: int = 25  # Supervisor steps per run


@dataclass
class AgentInfo:
    name: str
    role: str = "specialist"
    slice: str | None = None  # state key the agent owns
    contract: Any = None  # Pydantic model class for its output (None: not validated)
    output: str = "agent_result"  # where its output appears: agent_result steps or decision steps
    prompt_text: str | None = None  # BF-4 prompt-leak check


@dataclass
class EvalContext:
    case: TestCase
    tool_specs: dict[str, dict[str, Any]] = field(default_factory=dict)  # tool name -> spec (x-agent, input_schema …)
    agents: dict[str, AgentInfo] = field(default_factory=dict)
    policy: Policy | None = None
    masking: MaskingPolicy | None = None
    recognizers: list[Recognizer] = field(default_factory=list)
    limits: Limits = field(default_factory=Limits)
    pinned: dict[str, Any] = field(default_factory=dict)  # determinism block of eval.yaml (policy_version, lists_version …)
    protected_attributes: list[str] = field(default_factory=list)
    scorer_tools: list[str] = field(default_factory=list)
    references: dict[str, list[str]] = field(default_factory=dict)  # RT-xx -> reference tool sequence
    unreviewed_references: set[str] = field(default_factory=set)  # RT IDs whose reviewed_by is empty
    pair_patterns: dict[str, list[str]] = field(default_factory=dict)  # injection / fairness -> case patterns

    def owner(self, tool: str) -> str | None:
        """The agent a tool belongs to (x-agent in its spec)."""
        spec = self.tool_specs.get(tool)
        return spec.get("x-agent") if spec else None

    def slice_owners(self) -> dict[str, str]:
        return {a.slice: name for name, a in self.agents.items() if a.slice}

    def outputs(self, traj: Trajectory, upto: int | None = None) -> dict[str, Any]:
        return agent_outputs_upto(traj, upto, self.slice_owners())


class Evaluator:
    """One metric over one trajectory."""

    metric: ClassVar[str]
    severity: ClassVar[str] = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        raise NotImplementedError

    # -------------------------------------------------------------- result helpers
    def result(self, verdict: str, detail: str = "", *, score: float | None = None, agent: str | None = None, step: int | None = None,
               severity: str | None = None, metric: str | None = None) -> CheckResult:  # fmt: skip
        if score is None and verdict in ("pass", "fail"):
            score = 1.0 if verdict == "pass" else 0.0
        return CheckResult(
            metric=metric or self.metric,
            agent=agent,
            verdict=verdict,
            severity=severity or self.severity,
            score=score,
            detail=detail,
            evidence_step=step,
        )

    def skip(self, reason: str, *, agent: str | None = None, metric: str | None = None) -> CheckResult:
        return self.result("skip", reason, agent=agent, metric=metric)


class GroupEvaluator:
    """One metric over several trajectories: all trials of a case, or a case and its twin."""

    metric: ClassVar[str]
    severity: ClassVar[str] = "S1"

    def evaluate_group(self, runs: dict[str, list[tuple[Trajectory, EvalContext]]]) -> dict[tuple[str, int], list[CheckResult]]:
        """runs: case_id -> [(trajectory, context) per trial]. Returns (case_id, trial) -> checks."""
        raise NotImplementedError


# ------------------------------------------------------------------ trajectory helpers shared by evaluators
def is_failure(call: ToolCall) -> bool:
    """A call that did not give the agent a usable answer: transport failure or a business error body."""
    if call.status != "ok":
        return True
    return isinstance(call.result, dict) and "error" in call.result


def agent_outputs_upto(traj: Trajectory, upto: int | None = None, slices: dict[str, str] | None = None) -> dict[str, Any]:
    """Each agent's latest output before step `upto` (all steps when None): canned state first, then agent results.

    slices maps a state key to the agent that owns it (from agents.yaml), so canned state lands under the agent's name."""
    out: dict[str, Any] = {}
    slices = slices or {}
    for s in traj.steps:
        if upto is not None and s.index >= upto:
            break
        if s.kind == "note" and s.content == "canned_state":
            for key, value in (s.data.get("state") or {}).items():
                if value is not None:
                    out[slices.get(key, key)] = value
        elif s.kind == "agent_result" and s.agent:
            out[s.agent] = s.data.get("contract")
    return out


def replies(traj: Trajectory) -> list[str]:
    """Everything the system said to the customer."""
    out = traj.messages()
    if traj.final_message and traj.final_message not in out:
        out.append(traj.final_message)
    return out


def run_inputs(traj: Trajectory) -> dict[str, Any]:
    for s in traj.steps:
        if s.kind == "note" and s.content == "run_start":
            return s.data.get("inputs") or {}
    return {}


def get_path(obj: Any, path: str | None) -> list[Any]:
    """Values at a dot path; `*` expands a list or dict. Missing keys give no values (not None)."""
    if path in (None, "", "."):
        return [obj]
    vals = [obj]
    for part in path.split("."):
        nxt = []
        for v in vals:
            if part == "*":
                if isinstance(v, list):
                    nxt += v
                elif isinstance(v, dict):
                    nxt += list(v.values())
            elif isinstance(v, dict) and part in v:
                nxt.append(v[part])
            elif isinstance(v, list) and part.isdigit() and int(part) < len(v):
                nxt.append(v[int(part)])
        vals = nxt
    return vals


def walk_strings(obj: Any, prefix: str = "") -> Iterator[tuple[str, str]]:
    """(path, text) for every string inside a JSON-like value."""
    if isinstance(obj, str):
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{prefix}.{i}" if prefix else str(i))


def walk_scalars(obj: Any) -> Iterator[Any]:
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_scalars(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_scalars(v)
    elif obj is not None:
        yield obj


def norm_text(value: Any) -> str:
    """Case- and spacing-insensitive form used when comparing names and IDs."""
    return re.sub(r"\s+", " ", str(value)).strip().upper()
