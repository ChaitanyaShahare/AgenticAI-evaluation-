"""KYC tool registry: specs + mocks + fault hook + allow-list + audit log, for one run (one trial of one case).

    reg = ToolRegistry.for_case(trial_db, "KYC-FLT-021", run_id="r1", trial=1)
    out = reg.call("identity", "verify_pan", {"pan": "ZQCPM1274R", "full_name": "ROHAN MEHTA", "dob": "1988-11-02"})
    out.status, out.fault_injected  # 'timeout', 'FP-01:TIMEOUT'

Order inside call(): allow-list → argument schema → fault hook (override / fault / pass) → mock → audit row.
Allow-list and schema failures are returned to the agent as errors (RBAC and input validation, as a real API would)
and are logged like any other call, so TU-2 / TU-7 evaluators see the attempt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from evalkit.harness.fault_hook import FaultHook, FaultPlan, FaultRule, Override, ToolOutcome
from projects.kyc_onboarding.tools.mocks import MOCKS
from projects.kyc_onboarding.tools.mocks.db import ToolContext
from projects.kyc_onboarding.tools.mocks.screening_tools import persist

SPECS_DIR = Path(__file__).resolve().parent / "specs"
PERSIST_OVERRIDES = {"sanctions_screen", "pep_check"}  # overrides of tools that write must still be stored (MO-02)


@lru_cache(maxsize=4)
def load_specs(specs_dir: Path = SPECS_DIR) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for f in sorted(specs_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for s in data.get("tools", [data]):
            if s["name"] in specs:
                raise ValueError(f"tool {s['name']} defined twice (second time in {f.name})")
            specs[s["name"]] = s
    return specs


def load_fault_plan(ctx: ToolContext) -> FaultPlan:
    """Fault rules and overrides for the case's profiles, read from the seed database."""
    timeout = int(ctx.config("client_timeout_ms"))
    if not ctx.profile_ids:
        return FaultPlan(client_timeout_ms=timeout)
    marks = ",".join("?" * len(ctx.profile_ids))
    rules = [
        FaultRule(r["profile_id"], r["tool_name"], r["attempt_no"], r["behaviour"], r["delay_ms"], r["error_code"], r["payload"])
        for r in ctx.all(
            f"SELECT * FROM tool_faults WHERE profile_id IN ({marks}) ORDER BY profile_id, tool_name, attempt_no", tuple(ctx.profile_ids)
        )
    ]
    overrides = [
        Override(r["profile_id"], r["tool_name"], json.loads(r["response_json"]))
        for r in ctx.all(f"SELECT * FROM tool_overrides WHERE profile_id IN ({marks}) ORDER BY profile_id", tuple(ctx.profile_ids))
    ]
    return FaultPlan(rules=rules, overrides=overrides, client_timeout_ms=timeout)


@dataclass
class ToolRegistry:
    ctx: ToolContext
    hook: FaultHook
    specs: dict[str, dict[str, Any]] = field(default_factory=load_specs)
    _step: int = 0

    @classmethod
    def for_case(cls, db_path: Path, case_id: str, run_id: str = "adhoc", trial: int = 1) -> ToolRegistry:
        ctx = ToolContext.for_case(db_path, case_id, run_id=run_id, trial=trial)
        return cls(ctx=ctx, hook=FaultHook(load_fault_plan(ctx)))

    @classmethod
    def adhoc(cls, db_path: Path) -> ToolRegistry:
        """No case: every document visible, no session restriction, no faults (for unit tests and exploration)."""
        ctx = ToolContext(db_path=Path(db_path))
        return cls(ctx=ctx, hook=FaultHook(load_fault_plan(ctx)))

    # ---------------------------------------------------------------- catalogue
    def tools_for(self, agent: str) -> list[str]:
        """Allow-list: the tools whose spec names this agent as owner (x-agent)."""
        return [n for n, s in self.specs.items() if s["x-agent"] == agent]

    def agents(self) -> list[str]:
        return sorted({s["x-agent"] for s in self.specs.values()})

    # ---------------------------------------------------------------- calls
    def call(self, agent: str, tool: str, args: dict[str, Any]) -> ToolOutcome:
        if tool not in self.specs:
            out = ToolOutcome(tool, args, 1, "error", {"error": "UNKNOWN_TOOL", "details": tool})
        elif self.specs[tool]["x-agent"] != agent:
            out = ToolOutcome(tool, args, 1, "error", {"error": "TOOL_NOT_ALLOWED", "details": f"{agent} may not call {tool}"})
        elif problems := self._invalid(tool, args):
            out = ToolOutcome(tool, args, 1, "error", {"error": "INVALID_ARGUMENT", "details": problems})
        else:
            fn = MOCKS[tool]
            on_override = (lambda resp: persist(self.ctx, tool, dict(args), resp)) if tool in PERSIST_OVERRIDES else None
            out = self.hook.call(tool, args, lambda a: fn(self.ctx, **a), on_override=on_override)
        self._audit(agent, out)
        return out

    def _invalid(self, tool: str, args: dict[str, Any]) -> list[str]:
        v = jsonschema.Draft202012Validator(self.specs[tool]["input_schema"])
        return [f"{'.'.join(map(str, e.absolute_path)) or '(arguments)'}: {e.message}" for e in sorted(v.iter_errors(args), key=str)]

    def _audit(self, agent: str, out: ToolOutcome) -> None:
        self._step += 1
        result = out.result if not isinstance(out.result, str) else {"raw": out.result}
        self.ctx.write(
            "INSERT INTO audit_events (run_id, case_id, trial, step, agent, tool, args_json, result_json, status, fault_injected, ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.ctx.run_id,
                self.ctx.case_id,
                self.ctx.trial,
                self._step,
                agent,
                out.tool,
                json.dumps(out.args, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                out.status,
                out.fault_injected,
                self.ctx.now(),
            ),
        )

    # ---------------------------------------------------------------- LangChain binding (used by the agents in WP3)
    def as_langchain_tools(self, agent: str, on_call=None) -> list:
        """StructuredTools for one agent. Each returns ToolOutcome.for_agent(); on_call(outcome) lets the adapter record it."""
        from langchain_core.tools import StructuredTool  # noqa: PLC0415 — only needed when agents run

        def make(name: str):
            def _run(**kwargs):
                out = self.call(agent, name, kwargs)
                if on_call:
                    on_call(out)
                return out.for_agent()

            schema = {k: v for k, v in self.specs[name]["input_schema"].items() if k != "$schema"}  # model APIs want the body only
            return StructuredTool.from_function(func=_run, name=name, description=self.specs[name]["description"], args_schema=schema)

        return [make(n) for n in self.tools_for(agent)]
