"""Adapter interface: turn one run of a system under test into a canonical Trajectory.

A project implements (or reuses) an adapter and names it in project.yaml. Adapters are the only framework-aware code.

Run-event protocol (what LangGraphAdapter reads). A project's runner returns an object with:
  * .state["events"]  — ordered list of dicts, each with a `kind`:
        run_start   {case_id, run_id, trial, models, effort, prompt_hashes, as_of, seed, inputs}
                    — inputs: what the system was given (IDs, form, documents); a grounding source for TU-4
        llm         {agent, model, effort, purpose, stop_reason, usage{input_tokens, output_tokens, cache_*}}
        tool        {agent, tool, args, status, result, fault_injected, attempt, latency_ms}
        handoff     {agent, to, status}
        interrupt   {agent, name, decision, token_issued, token}  — token: the approval token issued (A1 provenance)
        message     {agent, content, final?}          — text the system said to the user
        user        {content, new_documents?}         — a later user turn
        decision    {agent, action}                   — a routing decision
        guard       {agent, rule, detail}             — a hard limit fired in code
        contract    {agent, violations}               — output-contract or slice violations
        agent_result{agent, stop, contract, submitted}— an agent's final (validated) output
        canned_state{state}                           — L1 supervisor cases: the agent outputs the run starts from
        anything else is kept as a `note` step (canned_state and l1_task included)
  * .state["customer_messages"] (initial user turns) and .state["replies"]
  * .end_state_params — parameters for project.yaml end_state_query
"""

from __future__ import annotations

import importlib
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from evalkit.config import ProjectConfig, repo_root
from evalkit.schema import TestCase, Trajectory


def import_ref(ref: str) -> Any:
    """Import 'package.module:attribute'. The repository root is put on sys.path so projects/ is importable."""
    root = str(repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    module, _, attr = ref.partition(":")
    if not attr:
        raise ValueError(f"{ref!r} must look like 'package.module:attribute'")
    return getattr(importlib.import_module(module), attr)


class AgentAdapter(ABC):
    name = "base"

    def __init__(self, project: ProjectConfig, project_dir: Path, eval_cfg):
        self.project = project
        self.project_dir = project_dir
        self.eval_cfg = eval_cfg

    @abstractmethod
    def run(self, case: TestCase, trial: int, run_id: str, db_path: Path, client=None) -> Trajectory:
        """Run one case × trial against the per-trial database copy and return its trajectory. Must not raise for agent
        failures: a crashed run is returned as a Trajectory with `error` set, so it is graded rather than lost."""
