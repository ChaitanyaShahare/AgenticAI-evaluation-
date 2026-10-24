"""Harness runner: plan case × trial items, run them through the project's adapter, store trajectories.

    plan = make_plan("kyc_onboarding", mode="smoke")            # or case_ids=["KYC-GLD-001"], trials=3
    summary = execute(plan)                                       # live model calls

Layout of runs/<run_id>/:
    manifest.json                 plan, models, effort, determinism, package versions
    trajectories/<case>/t<k>.json one canonical Trajectory per trial
    trials.jsonl                  one TrialRecord per trial (end state, counts, usage, error)
    db/<case>/t<k>.sqlite         the per-trial database after the run (evidence for audit and debugging)
Grading (evaluators, gates, reports) reads these files in WP5 / WP8.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evalkit.adapters.base import import_ref
from evalkit.adapters.langgraph_adapter import package_versions
from evalkit.config import ConfigError, load_env, load_eval_config, load_project_config, repo_root, runs_dir
from evalkit.harness.clock import check_clock
from evalkit.harness.sandbox import trial_db
from evalkit.schema import TestCase, Trajectory, TrialRecord

LAB_ENV = "EVALKIT_LAB_SWITCHES"  # seeded-defect switches; set only by `evalkit lab` for the length of one run

# rough per-trial cost for the cost guard (measured on KYC-GLD-001: ~$0.03 for a full L3 run)
EST_COST_USD = {"L1": 0.005, "L2": 0.02, "L3": 0.03, "L1+L3": 0.03}


@dataclass
class RunPlan:
    run_id: str
    project: str
    mode: str | None
    items: list[tuple[TestCase, int]]
    project_dir: Path
    seed: Path
    cfg: Any
    project_cfg: Any
    lab_variant: str | None = None  # bug-hunt lab: the seeded-defect variant this run uses

    @property
    def est_cost_usd(self) -> float:
        return round(sum(EST_COST_USD.get(c.level, 0.03) for c, _ in self.items), 2)

    def describe(self) -> str:
        cases = sorted({c.case_id for c, _ in self.items})
        return (
            f"run {self.run_id}: {len(cases)} case(s), {len(self.items)} trial(s), est. ~${self.est_cost_usd:.2f} "
            f"(supervisor {self.cfg.models.supervisor}, specialists {self.cfg.models.specialist})"
        )


@dataclass
class RunSummary:
    run_id: str
    run_dir: Path
    records: list[TrialRecord] = field(default_factory=list)

    @property
    def errors(self) -> list[TrialRecord]:
        return [r for r in self.records if r.error]


def new_run_id(mode: str | None) -> str:
    return f"{mode or 'adhoc'}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def make_plan(
    project: str, mode: str | None = None, case_ids: list[str] | None = None, trials: int | None = None, run_id: str | None = None, cfg=None
) -> RunPlan:
    root = repo_root()
    pdir = root / "projects" / project
    pcfg = load_project_config(pdir / "project.yaml")
    cfg = cfg or load_eval_config()
    cases: list[TestCase] = import_ref(pcfg.case_source)()
    by_id = {c.case_id: c for c in cases}
    if case_ids:
        unknown = [c for c in case_ids if c not in by_id]
        if unknown:
            raise KeyError(f"unknown case id(s): {', '.join(unknown)}")
        selected = [by_id[c] for c in case_ids]
    elif mode:
        selected = [c for c in cases if c.in_mode(mode)]
    else:
        raise ValueError("give a run mode or case ids")
    items = []
    for c in selected:
        k = trials if trials is not None else (cfg.trials_for(c.severity, mode) if mode else c.trials)
        items += [(c, t) for t in range(1, k + 1)]
    return RunPlan(run_id or new_run_id(mode), project, mode, items, pdir, pdir / pcfg.data.seed_db, cfg, pcfg)


def _record(plan: RunPlan, case: TestCase, trial: int, traj: Trajectory, path: Path) -> TrialRecord:
    calls = traj.tool_calls()
    return TrialRecord(
        run_id=plan.run_id,
        case_id=case.case_id,
        trial=trial,
        level=case.level,
        severity=case.severity,
        trajectory_path=str(path.relative_to(path.parents[2])),
        end_state=traj.end_state,
        steps=len(traj.steps),
        tool_calls=len(calls),
        faults_injected=sum(1 for c in calls if c.fault_injected),
        duration_s=traj.meta.duration_s or 0.0,
        usage=traj.meta.usage,
        error=traj.error,
    )


def execute(
    plan: RunPlan,
    client_factory: Callable[[TestCase, int], Any] | None = None,
    max_workers: int | None = None,
    progress: Callable[[str], None] = print,
) -> RunSummary:
    """Run every planned trial. client_factory(case, trial) supplies the model client (default: one shared real client)."""
    load_env()
    if os.environ.get(LAB_ENV) and not plan.lab_variant:
        raise ConfigError(
            f"{LAB_ENV} is set ({os.environ[LAB_ENV]}), which switches seeded lab defects on. Only `evalkit lab` may set it: "
            "remove it from your shell or .env and run again."
        )
    check_clock(plan.seed, plan.cfg.determinism.as_of)
    run_dir = runs_dir(plan.cfg) / plan.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter_cls = import_ref(plan.project_cfg.adapter)
    adapter = adapter_cls(plan.project_cfg, plan.project_dir, plan.cfg)
    shared = None
    if client_factory is None:
        from anthropic import Anthropic  # noqa: PLC0415 — only for live runs

        shared = Anthropic()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": plan.run_id,
                "project": plan.project,
                "mode": plan.mode,
                "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "items": [{"case_id": c.case_id, "trial": t, "level": c.level, "severity": c.severity} for c, t in plan.items],
                "models": plan.cfg.models.model_dump(),
                "effort": plan.cfg.effort.model_dump(),
                "determinism": plan.cfg.determinism.model_dump(),
                "package_versions": package_versions(),
                "client": "live" if shared else "injected",
                "lab_variant": plan.lab_variant,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def one(case: TestCase, trial: int) -> TrialRecord:
        db = trial_db(plan.seed, run_dir, case.case_id, trial)
        client = client_factory(case, trial) if client_factory else shared
        traj = adapter.run(case, trial, plan.run_id, db, client=client)
        path = traj.save(run_dir / "trajectories" / case.case_id / f"t{trial}.json")
        return _record(plan, case, trial, traj, path)

    summary = RunSummary(plan.run_id, run_dir)
    workers = max(1, min(max_workers or plan.cfg.execution.max_workers, len(plan.items) or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, c, t): (c, t) for c, t in plan.items}
        for f in as_completed(futures):
            c, t = futures[f]
            rec = f.result()
            summary.records.append(rec)
            status = rec.end_state.get("status") or ("ERROR" if rec.error else "—")
            progress(
                f"  {c.case_id} t{t}: {status}  ({rec.tool_calls} tool calls, {rec.faults_injected} faults, {rec.duration_s:.0f}s)"
                + ("  ERROR: " + rec.error.splitlines()[0] if rec.error else "")
            )
    summary.records.sort(key=lambda r: (r.case_id, r.trial))
    with (run_dir / "trials.jsonl").open("w", encoding="utf-8") as fh:
        for r in summary.records:
            fh.write(r.model_dump_json() + "\n")
    return summary
