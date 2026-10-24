"""Evaluator registry: which evaluator computes which metric, and the project inputs every evaluator receives.

ProjectSuite.load(project) reads everything grading needs from configuration alone — tool specs, agents.yaml, the policy
and masking files, the PII recognisers, the limits and pinned versions of eval.yaml, reference trajectories, cases — so
a new project is graded without changes here. Blank human-owned files (policy, masking) are reported in `notes`, and
the checks that need them are skipped with that reason.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from evalkit.adapters.base import import_ref
from evalkit.config.loader import (
    AgentsConfig,
    ConfigError,
    EvalConfig,
    ProjectConfig,
    load_eval_config,
    load_model,
    load_project_config,
    repo_root,
)
from evalkit.evaluators.agent.arguments import AgentArgumentsEvaluator
from evalkit.evaluators.agent.contract import AgentContractEvaluator
from evalkit.evaluators.agent.efficiency import AgentEfficiencyEvaluator
from evalkit.evaluators.agent.guardrails import GuardrailCoverageEvaluator
from evalkit.evaluators.agent.task_success import AgentTaskSuccessEvaluator
from evalkit.evaluators.agent.tool_selection import AgentToolSelectionEvaluator
from evalkit.evaluators.base import AgentInfo, EvalContext, Limits
from evalkit.evaluators.bfsi.audit_completeness import AuditCompletenessEvaluator
from evalkit.evaluators.bfsi.disclosure import DisclosureEvaluator
from evalkit.evaluators.bfsi.fairness import FairnessPairEvaluator
from evalkit.evaluators.bfsi.injection import InjectionTwinEvaluator
from evalkit.evaluators.bfsi.pii import PiiEvaluator, load_masking, load_recognizers
from evalkit.evaluators.policy_engine import PolicyEvaluator, load_policies
from evalkit.evaluators.tooluse.arguments import ArgumentCorrectnessEvaluator, SchemaValidityEvaluator
from evalkit.evaluators.tooluse.error_handling import ErrorHandlingEvaluator
from evalkit.evaluators.tooluse.grounding import GroundingEvaluator
from evalkit.evaluators.tooluse.reconciliation import ReconciliationEvaluator
from evalkit.evaluators.tooluse.selection import ToolSelectionEvaluator
from evalkit.evaluators.trajectory.efficiency import StepEfficiencyEvaluator
from evalkit.evaluators.trajectory.end_state import EndStateEvaluator
from evalkit.evaluators.trajectory.handoff import HandoffEvaluator
from evalkit.evaluators.trajectory.match import TrajectoryMatchEvaluator
from evalkit.schema import TestCase

# metric ID -> (what it measures, default severity). Policy rules choose their own metric among these.
METRICS = {
    "TR-1": ("Task success — end state equals expectation", "S2"),
    "TR-2": ("Trajectory match (mode per case)", "S2"),
    "TR-3": ("Mandatory-control coverage", "S1"),
    "TR-4": ("Precedence violations", "S1"),
    "TR-5": ("Hand-off accuracy; ≤ 2 bounces", "S2"),
    "TR-6": ("Step efficiency", "S3"),
    "TR-7": ("Reliability pass^k", "S2"),
    "TU-1": ("Tool selection F1", "S2"),
    "TU-2": ("Argument schema validity", "S2"),
    "TU-3": ("Argument value correctness", "S2"),
    "TU-4": ("Argument grounding", "S1"),
    "TU-5": ("Error handling under faults", "S2"),
    "TU-6": ("Figures reconcile to tool outputs", "S1"),
    "TU-7": ("Authorisation and allow-list compliance", "S1"),
    "BF-1": ("PII / PCI exposure", "S1"),
    "BF-2": ("AML / KYC escalation", "S1"),
    "BF-3": ("Prompt-injection resistance", "S1"),
    "BF-4": ("Advice and disclosure boundaries", "S2"),
    "BF-5": ("Counterfactual fairness", "S1"),
    "BF-6": ("Audit completeness", "S1"),
    "AG-1": ("Agent task success", "S2"),
    "AG-2": ("Agent tool selection F1", "S2"),
    "AG-3": ("Agent argument correctness", "S2"),
    "AG-4": ("Agent output-contract validity", "S2"),
    "AG-5": ("Agent-specific guardrails", "S1"),
    "AG-6": ("Agent efficiency", "S3"),
}

TRIAL_EVALUATORS = [
    PolicyEvaluator, EndStateEvaluator, TrajectoryMatchEvaluator, HandoffEvaluator, StepEfficiencyEvaluator,
    ToolSelectionEvaluator, SchemaValidityEvaluator, ArgumentCorrectnessEvaluator, GroundingEvaluator,
    ErrorHandlingEvaluator, ReconciliationEvaluator, PiiEvaluator, DisclosureEvaluator, AuditCompletenessEvaluator,
]  # fmt: skip
GROUP_EVALUATORS = [InjectionTwinEvaluator, FairnessPairEvaluator]
AGENT_EVALUATORS = {
    "AG-1": AgentTaskSuccessEvaluator,
    "AG-2": AgentToolSelectionEvaluator,
    "AG-3": AgentArgumentsEvaluator,
    "AG-4": AgentContractEvaluator,
    "AG-5": GuardrailCoverageEvaluator,
    "AG-6": AgentEfficiencyEvaluator,
}


def load_tool_specs(specs_dir: Path) -> dict[str, dict]:
    """Every tool spec in a folder: one tool per file, or a file with a `tools` list (hand-offs)."""
    out = {}
    for p in sorted(specs_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for spec in data.get("tools", [data]):
            out[spec["name"]] = spec
    return out


def load_references(folder: Path) -> tuple[dict[str, list[str]], set[str]]:
    """(RT-xx -> tool sequence, IDs not yet reviewed). A blank file is a reference not written yet."""
    out, unreviewed = {}, set()
    for p in sorted(folder.glob("RT-*.json")) if folder.is_dir() else []:
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            continue
        data = json.loads(text)
        out[p.stem] = list(data.get("tools") or [s["tool"] for s in data.get("steps", []) if s.get("tool")])
        if not data.get("reviewed_by"):
            unreviewed.add(p.stem)
    return out, unreviewed


@dataclass
class ProjectSuite:
    project: str
    project_dir: Path
    project_cfg: ProjectConfig
    cfg: EvalConfig
    cases: dict[str, TestCase]
    base: EvalContext  # everything but the case
    notes: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, project: str, cfg: EvalConfig | None = None, root: Path | None = None) -> ProjectSuite:
        root = root or repo_root()
        pdir = root / "projects" / project
        pcfg = load_project_config(pdir / "project.yaml")
        cfg = cfg or load_eval_config()
        notes: list[str] = []
        agents_cfg = load_model(AgentsConfig, pdir / pcfg.agents_file)
        agents = {}
        for name, a in agents_cfg.agents.items():
            prompt = (pdir / a.prompt).read_text(encoding="utf-8") if a.prompt and (pdir / a.prompt).is_file() else None
            try:
                contract = import_ref(a.contract) if a.contract else None
            except (ImportError, AttributeError) as e:
                raise ConfigError(f"{pdir / pcfg.agents_file}: agents.{name}.contract {a.contract!r} cannot be imported ({e}).") from None
            agents[name] = AgentInfo(name, a.role, a.slice, contract, a.output, prompt)
        policy, blank = load_policies([pdir / p for p in pcfg.policies])
        notes += blank
        masking = None
        for p in pcfg.policies:
            path = pdir / p
            if masking is None and re.search(r"^masking:", path.read_text(encoding="utf-8"), re.MULTILINE):
                masking = load_masking(path)
        recognizers = load_recognizers(root / "configs" / "pii_recognizers.yaml")
        references, unreviewed = load_references(pdir / "reference_trajectories")
        base = EvalContext(
            case=None,  # type: ignore[arg-type] — set per case by context()
            tool_specs=load_tool_specs(pdir / pcfg.tools_dir),
            agents=agents,
            policy=policy,
            masking=masking,
            recognizers=recognizers,
            limits=Limits(cfg.retry_limit, cfg.max_bounces_per_specialist, cfg.max_steps_per_run),
            pinned=cfg.determinism.model_dump(),
            protected_attributes=agents_cfg.protected_attributes,
            scorer_tools=agents_cfg.scorer_tools,
            references=references,
            unreviewed_references=unreviewed,
            pair_patterns=agents_cfg.pair_patterns.model_dump(),
        )
        if unreviewed:
            notes.append(f"reference trajectories not yet reviewed (reviewed_by is empty): {', '.join(sorted(unreviewed))}")
        if policy is not None and not policy.validated:
            notes.append(f"policy {policy.policy_id} {policy.version} is not SME-validated: S1 results are reported as unvalidated")
        cases = {c.case_id: c for c in import_ref(pcfg.case_source)()}
        return cls(project, pdir, pcfg, cfg, cases, base, notes)

    def context(self, case: TestCase) -> EvalContext:
        return replace(self.base, case=case)
