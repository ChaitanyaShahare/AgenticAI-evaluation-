"""Fixtures for the evaluator tests.

Good fixtures are the recorded runs (projects/kyc_onboarding/recorded_runs/). Each bad fixture is a recording with one
targeted defect applied by a helper below (drop a call, change an argument, leak a value), so a test states exactly
which defect each check must catch. All runs are offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from evalkit.config.registry import ProjectSuite
from evalkit.evaluators.base import EvalContext
from evalkit.evaluators.policy_engine import load_policy
from evalkit.schema import Step, ToolCall, Trajectory
from tests.recordings import RECORDINGS

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture(scope="session")
def suite() -> ProjectSuite:
    return ProjectSuite.load("kyc_onboarding")


@pytest.fixture(scope="session")
def engine_policy():
    return load_policy(FIXTURES / "policies" / "engine_rules.yaml")


def load(name: str) -> Trajectory:
    return Trajectory.load(RECORDINGS / f"{name}.json")


def ctx_for(suite: ProjectSuite, traj: Trajectory, **overrides: Any) -> EvalContext:
    ctx = suite.context(suite.cases[traj.meta.case_id])
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


def drop_tool(traj: Trajectory, tool: str) -> Trajectory:
    return traj.model_copy(update={"steps": [s for s in traj.steps if not (s.tool_call and s.tool_call.tool == tool)]})


def edit_call(traj: Trajectory, tool: str, args: dict | None = None, result: Any = ..., **fields: Any) -> Trajectory:
    """Change the first call to `tool`: merge args, replace result, set ToolCall fields (status, attempt, agent …)."""
    steps, done = [], False
    for s in traj.steps:
        if not done and s.tool_call and s.tool_call.tool == tool:
            upd: dict[str, Any] = dict(fields)
            if args:
                upd["args"] = {**s.tool_call.args, **args}
            if result is not ...:
                upd["result"] = result
            s = s.model_copy(update={"tool_call": s.tool_call.model_copy(update=upd), "agent": fields.get("agent", s.agent)})
            done = True
        steps.append(s)
    assert done, f"{tool} not in trajectory"
    return traj.model_copy(update={"steps": steps})


def add_call(
    traj: Trajectory, agent: str, tool: str, args: dict, result: Any = None, after: int | None = None, **fields: Any
) -> Trajectory:
    """Insert a tool call after step index `after` (end of run when None)."""
    steps = [s.model_copy(update={"index": s.index * 2}) for s in traj.steps]  # even indices leave room for the new step
    at = len(steps) if after is None else next(i for i, s in enumerate(traj.steps) if s.index == after) + 1
    call = ToolCall(call_id="cX", agent=agent, tool=tool, args=args, result=result, **fields)
    step = Step(index=steps[at - 1].index + 1 if at else 0, kind="tool", agent=agent, tool_call=call)
    return traj.model_copy(update={"steps": steps[:at] + [step] + steps[at:]})


def set_output(traj: Trajectory, agent: str, **fields: Any) -> Trajectory:
    """Change fields of the agent's (last) agent_result contract."""
    steps = []
    for s in traj.steps:
        if s.kind == "agent_result" and s.agent == agent:
            s = s.model_copy(update={"data": {**s.data, "contract": {**(s.data.get("contract") or {}), **fields}}})
        steps.append(s)
    return traj.model_copy(update={"steps": steps})


def with_reply(traj: Trajectory, text: str) -> Trajectory:
    steps = [s for s in traj.steps if s.kind != "message"] + [
        Step(index=10_000, kind="message", agent="supervisor", content=text, data={"final": True})
    ]
    return traj.model_copy(update={"steps": steps, "final_message": text})


def with_end_state(traj: Trajectory, **fields: Any) -> Trajectory:
    return traj.model_copy(update={"end_state": {**traj.end_state, **fields}})


def as_case(traj: Trajectory, case_id: str, trial: int = 1) -> Trajectory:
    return traj.model_copy(update={"meta": traj.meta.model_copy(update={"case_id": case_id, "trial": trial})})
