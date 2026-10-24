"""TestCase: the harness's view of one catalogue case.

Built from the project's case YAML files (evalkit/datasets/loader.py: datasets/<pattern>/<case_id>.yaml).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["S1", "S2", "S3"]


class TestCase(BaseModel):
    __test__ = False  # not a pytest class
    model_config = ConfigDict(extra="forbid")

    case_id: str
    title: str = ""
    level: Literal["L1", "L2", "L3", "L1+L3"]
    primary_agent: str
    pattern: str
    severity: Severity
    trials: int = Field(ge=1)
    run_sets: list[Literal["smoke", "gate", "full"]]
    expected: dict[str, Any] = Field(default_factory=dict)  # end-state / agent-output expectations (TR-1, AG-1)
    # Oracle columns of the catalogue (human-authored). Empty means "not stated", and the check that needs it is skipped.
    match_mode: Literal["strict", "unordered", "subset", "superset"] | None = None  # TR-2
    reference: list[str] = Field(default_factory=list)  # reference trajectory IDs (RT-01 …), TR-2
    required_tools: list[str] = Field(default_factory=list)  # TU-1 / AG-2
    forbidden_tools: list[str] = Field(default_factory=list)  # TU-1 / AG-2 (unconditional ones only)
    tool_notes: list[str] = Field(default_factory=list)  # conditional required / forbidden entries, structured in WP6
    metrics: list[str] = Field(default_factory=list)  # "Checks (metric IDs)" column, for coverage
    twins: list[str] = Field(default_factory=list)  # related cases: clean twin (BF-3), fairness partner (BF-5), paraphrases

    def in_mode(self, mode: str) -> bool:
        return mode in self.run_sets
