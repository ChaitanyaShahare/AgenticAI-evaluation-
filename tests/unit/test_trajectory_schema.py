"""Canonical Trajectory: round trip, strictness, and the per-agent views evaluators use."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evalkit.config import repo_root
from evalkit.schema import RunMeta, Step, ToolCall, Trajectory

REC = repo_root() / "projects" / "kyc_onboarding" / "recorded_runs"


def _traj() -> Trajectory:
    meta = RunMeta(run_id="r", case_id="C", trial=1, project="p", adapter="a", models={"supervisor": "m"})
    steps = [
        Step(index=0, kind="handoff", agent="supervisor", handoff_to="identity"),
        Step(
            index=1, kind="tool", agent="identity", tool_call=ToolCall(call_id="c1", agent="identity", tool="verify_pan", args={"pan": "X"})
        ),
        Step(
            index=2,
            kind="tool",
            agent="supervisor",
            tool_call=ToolCall(call_id="c2", agent="supervisor", tool="finalize_application", args={}),
        ),
        Step(index=3, kind="message", agent="supervisor", content="done"),
    ]
    return Trajectory(meta=meta, steps=steps, final_message="done", end_state={"status": "APPROVED"})


def test_round_trip(tmp_path):
    t = _traj()
    assert Trajectory.load(t.save(tmp_path / "t.json")) == t


def test_views():
    t = _traj()
    assert t.tool_sequence() == ["verify_pan", "finalize_application"]
    assert t.tool_sequence("identity") == ["verify_pan"]
    assert t.handoffs() == ["identity"]
    assert [s.index for s in t.agent_slice("supervisor")] == [0, 2, 3]
    assert t.agents() == ["identity", "supervisor"] and t.messages() == ["done"]


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ToolCall(call_id="c", agent="a", tool="t", args={}, retries=3)
    with pytest.raises(ValidationError):
        Step(index=0, kind="dance")


@pytest.mark.parametrize("name", ["KYC-GLD-001", "KYC-FLT-021", "KYC-HND-109"])
def test_recordings_load_as_trajectories(name):
    t = Trajectory.load(REC / f"{name}.json")
    assert t.meta.case_id == name and t.steps and t.error is None
    assert all(s.index == i for i, s in enumerate(t.steps))
