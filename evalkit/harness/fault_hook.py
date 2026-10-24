"""Generic fault hook: wraps every tool call of a run and applies the case's override / fault plan.

Protocol (projects/kyc_onboarding/data/README.md › Fault hook protocol):
  1. Override: a response configured for (profile, tool) replaces the tool's own lookup on every attempt.
  2. Fault: the rule for the exact attempt number wins; attempt_no = 0 covers every other attempt; no rule = PASS.
  3. Stubs (L2 / canned state) are handled by the project's hand-off tools, not here.
  4. Every outcome carries fault_injected = "<profile_id>:<behaviour>" when the harness interfered. Agents never set it.

The attempt counter is per (tool, identical arguments), so a retry with the same arguments sees attempt 2, 3, …
SLOW responses use a virtual clock: a delay above client_timeout_ms surfaces as a timeout without sleeping,
which keeps runs fast and deterministic.

This module knows nothing about any project: a project builds a FaultPlan from wherever it stores profiles.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

Behaviour = Literal["PASS", "TIMEOUT", "HTTP_500", "MALFORMED_JSON", "EMPTY", "SLOW", "ERROR", "REPLACE_FIELDS"]
Status = Literal["ok", "error", "timeout"]


@dataclass(frozen=True)
class FaultRule:
    profile_id: str
    tool: str
    attempt_no: int  # 0 = every attempt without its own rule
    behaviour: Behaviour
    delay_ms: int | None = None
    error_code: str | None = None
    payload: str | None = None  # raw body for MALFORMED_JSON / EMPTY / REPLACE_FIELDS; JSON error body for ERROR


@dataclass(frozen=True)
class Override:
    profile_id: str
    tool: str
    response: Any


@dataclass
class FaultPlan:
    rules: list[FaultRule] = field(default_factory=list)
    overrides: list[Override] = field(default_factory=list)
    client_timeout_ms: int = 10_000

    def rule_for(self, tool: str, attempt: int) -> FaultRule | None:
        exact = [r for r in self.rules if r.tool == tool and r.attempt_no == attempt]
        if exact:
            return exact[0]
        default = [r for r in self.rules if r.tool == tool and r.attempt_no == 0]
        return default[0] if default else None

    def override_for(self, tool: str) -> Override | None:
        return next((o for o in self.overrides if o.tool == tool), None)


@dataclass(frozen=True)
class ToolOutcome:
    """What one tool call produced. `result` is what the agent sees (a dict, or a raw string for malformed JSON)."""

    tool: str
    args: dict[str, Any]
    attempt: int
    status: Status
    result: Any
    fault_injected: str | None = None
    latency_ms: int = 0

    def for_agent(self) -> str:
        """The text handed back to the model: JSON for structured results, the raw body for malformed ones."""
        if self.status == "timeout":
            return json.dumps({"error": "TIMEOUT", "detail": f"{self.tool} did not respond in time"})
        if isinstance(self.result, str):
            return self.result
        return json.dumps(self.result, ensure_ascii=False)


def _args_key(tool: str, args: dict[str, Any]) -> str:
    return tool + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)


def _merge_fields(result: Any, payload: dict[str, Any]) -> Any:
    """REPLACE_FIELDS: merge into result['fields'] when the tool returns IDP-style fields, else into the top level."""
    if not isinstance(result, dict):
        return result
    merged = dict(result)
    if isinstance(merged.get("fields"), dict):
        fields = dict(merged["fields"])
        for k, v in payload.items():
            fields[k] = {"value": v, "confidence": 0.0 if v is None else 1.0}
        merged["fields"] = fields
    else:
        merged.update(payload)
    return merged


def is_error_result(result: Any) -> bool:
    return isinstance(result, dict) and "error" in result


class FaultHook:
    """Applies a FaultPlan to tool calls. One instance per run (trial)."""

    def __init__(self, plan: FaultPlan | None = None, *, real_sleep: bool = False):
        self.plan = plan or FaultPlan()
        self.real_sleep = real_sleep
        self._attempts: Counter[str] = Counter()

    def attempts(self, tool: str, args: dict[str, Any]) -> int:
        return self._attempts[_args_key(tool, args)]

    def call(
        self, tool: str, args: dict[str, Any], fn: Callable[[dict[str, Any]], Any], on_override: Callable[[Any], Any] | None = None
    ) -> ToolOutcome:
        """Run `fn(args)` under the plan. `on_override` lets a tool post-process an override (for example persist it)."""
        key = _args_key(tool, args)
        self._attempts[key] += 1
        attempt = self._attempts[key]
        start = time.perf_counter()

        def done(status: Status, result: Any, fault: str | None, latency: int | None = None) -> ToolOutcome:
            ms = latency if latency is not None else int((time.perf_counter() - start) * 1000)
            return ToolOutcome(tool, args, attempt, status, result, fault, ms)

        ov = self.plan.override_for(tool)
        if ov is not None:
            result = on_override(ov.response) if on_override else ov.response
            return done("error" if is_error_result(result) else "ok", result, f"{ov.profile_id}:OVERRIDE")

        rule = self.plan.rule_for(tool, attempt)
        if rule is None or rule.behaviour == "PASS":
            result = fn(args)
            return done("error" if is_error_result(result) else "ok", result, None)

        tag = f"{rule.profile_id}:{rule.behaviour}"
        b = rule.behaviour
        if b == "TIMEOUT":
            return done("timeout", None, tag, self.plan.client_timeout_ms)
        if b == "SLOW":
            delay = rule.delay_ms or 0
            if delay > self.plan.client_timeout_ms:
                return done("timeout", None, tag, self.plan.client_timeout_ms)
            if self.real_sleep:
                time.sleep(delay / 1000)
            result = fn(args)
            return done("error" if is_error_result(result) else "ok", result, tag, delay)
        if b in ("HTTP_500", "ERROR"):
            body: dict[str, Any] = {"error": rule.error_code or "INTERNAL_ERROR"}
            if rule.payload:
                try:
                    body.update(json.loads(rule.payload))
                except json.JSONDecodeError:
                    body["detail"] = rule.payload
            if b == "HTTP_500":
                body["http_status"] = 500
            return done("error", body, tag)
        if b == "MALFORMED_JSON":
            return done("error", rule.payload or "{", tag)
        if b == "EMPTY":
            return done("ok", {}, tag)
        if b == "REPLACE_FIELDS":
            result = _merge_fields(fn(args), json.loads(rule.payload or "{}"))
            return done("error" if is_error_result(result) else "ok", result, tag)
        raise ValueError(f"unknown fault behaviour {b!r} in profile {rule.profile_id}")
