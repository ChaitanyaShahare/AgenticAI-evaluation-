"""Results of running and checking cases.

TrialRecord is written by the harness for every case × trial (WP4). CheckResult and CaseResult are filled by the
evaluators and the gate layer (WP5); they are defined here so the runner's output format is stable from the start.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["pass", "fail", "skip", "error"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrialRecord(_Model):
    run_id: str
    case_id: str
    trial: int
    level: str
    severity: str
    trajectory_path: str | None
    end_state: dict[str, Any] = Field(default_factory=dict)
    steps: int = 0
    tool_calls: int = 0
    faults_injected: int = 0
    duration_s: float = 0.0
    usage: dict[str, dict[str, int]] = Field(default_factory=dict)
    error: str | None = None


class CheckResult(_Model):
    metric: str  # TR-1, TU-4, BF-1, AG-5 …
    agent: str | None = None  # set for per-agent checks
    rule: str | None = None  # policy rule ID (R1, D7, MASK-IN_PAN …) when the check comes from a policy file
    verdict: Verdict
    severity: Literal["S1", "S2", "S3"]
    score: float | None = None
    detail: str = ""
    evidence_step: int | None = None


class CaseResult(_Model):
    case_id: str
    trial: int
    checks: list[CheckResult] = Field(default_factory=list)
    passed: bool | None = None
