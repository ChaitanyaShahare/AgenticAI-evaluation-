"""Claude access for the KYC agents, via the official Anthropic SDK.

Model IDs and effort come from configs/eval.yaml (never code). No sampling parameters are sent — the current API rejects
them. Determinism comes from the harness: deterministic mocks and contract builders, pinned effort, k trials.

Two interaction patterns:
  * run_tool_loop  — specialist ReAct loop. A manual loop (not the SDK tool runner) because every tool call must pass
                     through the KYC ToolRegistry (allow-list, schema check, fault hook, audit). It finishes when the
                     agent calls `submit_result`. Assistant content is sent back verbatim (keeps thinking blocks valid).
  * structured_call — Supervisor router: messages.parse() with a Pydantic schema (forced tool_choice is not available
                     on the current Sonnet, so structured outputs replace "force a tool call").
Refusals and truncation are checked before any tool runs and reported as a stop reason; there is no refusal fallback
to another model (eval.yaml refusal_fallback: false), so behaviour is always attributable to the configured model.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
FINISH_TOOL = "submit_result"


@dataclass(frozen=True)
class ModelSettings:
    model: str
    effort: str
    max_tokens: int = 16000
    prompt_caching: bool = True


def settings_for(cfg, role: str) -> ModelSettings:
    """role: 'supervisor' or 'specialist' (configs/eval.yaml models / effort)."""
    return ModelSettings(
        model=getattr(cfg.models, role), effort=getattr(cfg.effort, role), max_tokens=cfg.max_tokens, prompt_caching=cfg.prompt_caching
    )


def make_client():
    """The real client. Credentials resolve from the environment (ANTHROPIC_API_KEY loaded from .env by the caller)."""
    import anthropic  # noqa: PLC0415

    return anthropic.Anthropic()


_PROMPTS: dict[str, tuple[str, str]] = {}


def load_prompt(name: str) -> tuple[str, str]:
    """Return (text, sha256) of prompts/<name>.md. The hash goes into every run's metadata (RunMeta.prompt_hashes)."""
    if name not in _PROMPTS:
        text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        _PROMPTS[name] = (text, hashlib.sha256(text.encode("utf-8")).hexdigest())
    return _PROMPTS[name]


def _system(text: str, s: ModelSettings) -> list[dict[str, Any]]:
    block: dict[str, Any] = {"type": "text", "text": text}
    if s.prompt_caching:
        block["cache_control"] = {"type": "ephemeral"}  # tools + system are the stable prefix
    return [block]


def api_tool(spec: dict[str, Any]) -> dict[str, Any]:
    """Registry spec -> Messages API tool definition (schema body only, x-* metadata dropped)."""
    schema = {k: v for k, v in spec["input_schema"].items() if k != "$schema"}
    return {"name": spec["name"], "description": spec["description"], "input_schema": schema}


def _usage(resp) -> dict[str, int]:
    u = getattr(resp, "usage", None)
    return {
        k: int(getattr(u, k, 0) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    }


def llm_event(agent: str, s: ModelSettings, resp, purpose: str) -> dict[str, Any]:
    return {
        "kind": "llm",
        "agent": agent,
        "model": s.model,
        "effort": s.effort,
        "purpose": purpose,
        "stop_reason": getattr(resp, "stop_reason", None),
        "usage": _usage(resp),
    }


@dataclass
class LoopResult:
    finish_input: dict[str, Any] | None
    stop: str  # finished | refusal | max_tokens | no_finish | turn_limit | api_error
    events: list[dict[str, Any]] = field(default_factory=list)
    detail: str | None = None


def run_tool_loop(
    client,
    s: ModelSettings,
    agent: str,
    system: str,
    task: str,
    tool_specs: list[dict[str, Any]],
    finish_schema: dict[str, Any],
    execute: Callable[[str, dict[str, Any]], tuple[str, bool, dict[str, Any]]],
    max_turns: int = 12,
) -> LoopResult:
    """Specialist loop. execute(name, args) -> (content for the model, is_error, tool event)."""
    tools = [api_tool(t) for t in tool_specs] + [
        {
            "name": FINISH_TOOL,
            "description": "Submit your final result for the Supervisor. Call this exactly once, when your work is done.",
            "input_schema": finish_schema,
        }
    ]
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    events: list[dict[str, Any]] = []
    nudged = False
    for _ in range(max_turns):
        try:
            resp = client.messages.create(
                model=s.model,
                max_tokens=s.max_tokens,
                system=_system(system, s),
                tools=tools,
                messages=messages,
                output_config={"effort": s.effort},
            )
        except Exception as e:  # API errors end the agent's turn; the Supervisor sees an invalid / missing contract
            return LoopResult(None, "api_error", events, f"{type(e).__name__}: {str(e)[:300]}")
        events.append(llm_event(agent, s, resp, "react"))
        if resp.stop_reason == "refusal":
            return LoopResult(None, "refusal", events, str(getattr(resp, "stop_details", None)))
        if resp.stop_reason == "max_tokens":
            return LoopResult(None, "max_tokens", events)  # a truncated tool call is never executed
        calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        messages.append({"role": "assistant", "content": resp.content})
        if not calls:
            if nudged:
                return LoopResult(None, "no_finish", events)
            nudged = True
            messages.append({"role": "user", "content": f"Continue your task, then call {FINISH_TOOL} with your result."})
            continue
        results, finished = [], None
        for c in calls:
            if c.name == FINISH_TOOL:
                finished = dict(c.input)
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": "received"})
                continue
            content, is_error, ev = execute(c.name, dict(c.input))
            events.append(ev)
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})  # all results of one turn in a single message
        if finished is not None:
            return LoopResult(finished, "finished", events)
    return LoopResult(None, "turn_limit", events)


def structured_call(
    client, s: ModelSettings, agent: str, system: str, user: str, output_model
) -> tuple[Any | None, dict[str, Any], str | None]:
    """One structured decision. Returns (parsed model or None, llm event, error detail)."""
    try:
        resp = client.messages.parse(
            model=s.model,
            max_tokens=s.max_tokens,
            system=_system(system, s),
            messages=[{"role": "user", "content": user}],
            output_format=output_model,
            output_config={"effort": s.effort},
        )
    except Exception as e:
        return (
            None,
            {
                "kind": "llm",
                "agent": agent,
                "model": s.model,
                "purpose": "route",
                "stop_reason": "api_error",
                "error": f"{type(e).__name__}: {str(e)[:300]}",
            },
            f"{type(e).__name__}",
        )
    ev = llm_event(agent, s, resp, "route")
    if resp.stop_reason in ("refusal", "max_tokens"):
        return None, ev, resp.stop_reason
    return getattr(resp, "parsed_output", None), ev, None


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)  # sorted keys keep prompts byte-stable
