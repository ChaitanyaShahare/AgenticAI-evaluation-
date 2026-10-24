"""Policy engine: executes a project's policy YAML (projects/<name>/policies/*.yaml) against a trajectory.

The policy file is written by a human (the QE Lead), never generated: it is the oracle for the S1 rules. This module
only executes it. Rule kinds and the condition language are documented in docs/config_reference.md › Policy files.

Rule kinds (default metric in brackets):
  required        [TR-3]  every `requires` call happened before the `before` call (or anywhere, without `before`)
  precedence      [TR-4]  same check, read as an ordering rule (P1–P3)
  forbidden       [BF-2]  the `call` never happens while `when` holds
  implies         [TR-3]  whenever `when` holds, `expect` holds (decision table, escalation, guardrails, disclosure)
  allow_list      [TU-7]  every call is made by the agent its tool spec names (x-agent)
  approval_token  [TU-7]  the `arg` of `call` is a token the approval step issued, never one from customer text
  slice_isolation [TR-3]  each agent's output stays inside its own contract; stray slices are reported, not kept
  limit           [TU-5]  attempts per identical call / delegations per agent / Supervisor steps stay within bounds

Conditions are mappings with one key (`all`, `any` and `not` combine them):
  called: tool | [tools]          succeeded: tool          failed: tool (called, never succeeded)     fault: tool
  result: {tool, path, <match>, every?}   args: {tool, path, <match>, every?}   output: {agent, path, <match>}
  end_state: {path, <match>}      reply: {<match>, scope: any|final}   user: {<match>}   guard: rule-id
  approval: APPROVE|DENY|NO_RESPONSE   case: {level|pattern|severity|primary_agent|case_id: value | [values]}
  inputs: {path, <match>}  (what the run was given, e.g. form.customer_type)
  equal: [ref, ref]  (two values are the same; a ref is {output: {agent, path}}, {result | args: {tool, path}} — the last
                      call —, {end_state: {path}} or {inputs: {path}})
Matchers: equals, not_equals, in, not_in, gt, gte, lt, lte, contains, matches (regex, case-insensitive),
exists (true/false), nonempty (true/false). With no matcher, the path must have a value.
Conditions on a call (`forbidden`, `required`) are evaluated on the steps before that call. `every: true` holds when the
tool was not called (combine with `called:` to require the call). A call in `requires` / `before` may add `ok: true`
(the call must have succeeded). A specialist replaced by an L2 stub, or whose output the run started from (canned
state of an L1 Supervisor case), counts as having made its own tool calls for `required` / `precedence`; the result
says so.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from evalkit.config.loader import ConfigError, is_blank, load_model
from evalkit.evaluators.base import EvalContext, Evaluator, get_path, is_failure, replies, run_inputs
from evalkit.schema import CheckResult, ToolCall, Trajectory

DEFAULT_METRIC = {
    "required": "TR-3",
    "precedence": "TR-4",
    "forbidden": "BF-2",
    "implies": "TR-3",
    "allow_list": "TU-7",
    "approval_token": "TU-7",
    "slice_isolation": "TR-3",
    "limit": "TU-5",
}
MATCHERS = ("equals", "not_equals", "in", "not_in", "gt", "gte", "lt", "lte", "contains", "matches", "exists", "nonempty")
CONDITION_KEYS = (
    "all", "any", "not", "called", "succeeded", "failed", "fault", "result", "args", "output",
    "end_state", "reply", "user", "guard", "approval", "case", "inputs", "equal",
)  # fmt: skip
REF_KEYS = ("output", "result", "args", "end_state", "inputs")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CallSpec(_Strict):
    """A tool call, optionally narrowed by its arguments or result: {tool, args: {path, <match>}, result: {...}}."""

    tool: str
    args: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    ok: bool | None = None  # true: the call must have succeeded; false: it must have failed


def _call_spec(v: Any) -> Any:
    return {"tool": v} if isinstance(v, str) else v


class Rule(_Strict):
    id: str
    kind: Literal["required", "precedence", "forbidden", "implies", "allow_list", "approval_token", "slice_isolation", "limit"]
    description: str = ""
    metric: str | None = None
    severity: Literal["S1", "S2", "S3"] = "S1"
    agent: str | None = None  # attribute the check to one agent (AG-5 guardrails)
    when: dict[str, Any] | None = None
    before: CallSpec | None = None  # required / precedence
    requires: list[CallSpec] = []  # required / precedence
    call: CallSpec | None = None  # forbidden / approval_token
    expect: dict[str, Any] | None = None  # implies
    arg: str | None = None  # approval_token
    max_attempts: int | None = Field(default=None, ge=1)  # limit
    max_delegations: int | None = Field(default=None, ge=1)  # limit
    max_steps: int | None = Field(default=None, ge=1)  # limit

    @field_validator("before", "call", mode="before")
    @classmethod
    def _one(cls, v):
        return _call_spec(v)

    @field_validator("requires", mode="before")
    @classmethod
    def _many(cls, v):
        return [_call_spec(x) for x in (v or [])]

    @field_validator("when", "expect")
    @classmethod
    def _condition(cls, v):
        if v is not None:
            check_condition(v)
        return v

    @property
    def metric_id(self) -> str:
        return self.metric or DEFAULT_METRIC[self.kind]


class Policy(_Strict):
    policy_id: str
    version: str
    owner: str  # the person who wrote and reviewed the rules
    source: str = ""  # where the rules come from (catalogue sheet, regulation clause)
    validated: bool = False  # True only after SME sign-off; MVP S1 rules are reported as unvalidated
    definitions: dict[str, Any] = {}  # shared conditions, referenced from rules with YAML anchors (&name / *name)
    rules: list[Rule]


def check_condition(cond: Any, where: str = "condition") -> None:
    """Fail early, with a readable message, on a condition the engine cannot evaluate."""
    if not isinstance(cond, dict) or len(cond) != 1:
        raise ValueError(f"{where}: a condition is a mapping with exactly one key ({', '.join(CONDITION_KEYS)})")
    (key, val), = cond.items()  # fmt: skip
    if key not in CONDITION_KEYS:
        raise ValueError(f"{where}: unknown condition '{key}' — use one of {', '.join(CONDITION_KEYS)}")
    if key in ("all", "any"):
        if not isinstance(val, list) or not val:
            raise ValueError(f"{where}.{key}: give a list of conditions")
        for i, c in enumerate(val):
            check_condition(c, f"{where}.{key}[{i}]")
    elif key == "not":
        check_condition(val, f"{where}.not")
    elif key == "equal":
        if not isinstance(val, list) or len(val) != 2:
            raise ValueError(f"{where}.equal: give two values to compare, e.g. [{{output: {{agent: risk, path: score}}}}, {{result: ...}}]")
        for i, ref in enumerate(val):
            if not isinstance(ref, dict) or len(ref) != 1 or next(iter(ref)) not in REF_KEYS:
                raise ValueError(f"{where}.equal[{i}]: a value is one of {', '.join(REF_KEYS)} with a path")
    elif key in ("result", "args", "output", "end_state", "reply", "user", "inputs") and isinstance(val, dict):
        unknown = set(val) - {"tool", "agent", "path", "every", "scope", *MATCHERS}
        if unknown:
            raise ValueError(f"{where}.{key}: unknown key(s) {', '.join(sorted(unknown))}")


def load_policy(path: Path) -> Policy | None:
    """None when the file is still blank (the QE Lead has not written it yet)."""
    if is_blank(path):
        return None
    return load_model(Policy, path)


# ------------------------------------------------------------------ condition evaluation
def _test(m: str, value: Any, want: Any) -> bool:
    if m == "equals":
        return value == want
    if m == "not_equals":
        return value != want
    if m == "in":
        return value in want
    if m == "not_in":
        return value not in want
    if value is None:
        return False
    if m == "gt":
        return value > want
    if m == "gte":
        return value >= want
    if m == "lt":
        return value < want
    if m == "lte":
        return value <= want
    if m == "contains":
        return want in value
    if m == "matches":
        return re.search(want, str(value), re.IGNORECASE) is not None
    raise ValueError(f"unknown matcher {m}")


def match(value: Any, spec: dict[str, Any]) -> bool:
    """Does one value satisfy every matcher in spec? (exists / nonempty are list-level, see values_match)"""
    for m in MATCHERS:
        if m not in spec or m in ("exists", "nonempty"):
            continue
        try:
            ok = _test(m, value, spec[m])
        except TypeError:  # comparing a string with a number, etc.
            ok = False
        if not ok:
            return False
    return True


def values_match(values: list[Any], spec: dict[str, Any]) -> bool:
    present = [v for v in values if v is not None]
    if "exists" in spec and bool(present) != bool(spec["exists"]):
        return False
    if "nonempty" in spec:
        full = any(v not in ([], {}, "") for v in present)
        if full != bool(spec["nonempty"]):
            return False
    if not any(m in spec for m in MATCHERS if m not in ("exists", "nonempty")):
        return bool(present) or spec.get("exists") is False or spec.get("nonempty") is False
    return any(match(v, spec) for v in values)


def _calls(traj: Trajectory, upto: int | None) -> list[tuple[int, ToolCall]]:
    return [(s.index, s.tool_call) for s in traj.steps if s.tool_call and (upto is None or s.index < upto)]


def call_matches(call: ToolCall, spec: CallSpec) -> bool:
    if call.tool != spec.tool:
        return False
    if spec.args is not None and not values_match(get_path(call.args, spec.args.get("path")), spec.args):
        return False
    if spec.result is not None and not values_match(get_path(call.result, spec.result.get("path")), spec.result):
        return False
    if spec.ok is not None and is_failure(call) == spec.ok:
        return False
    return True


def value_of(ref: dict[str, Any], traj: Trajectory, ctx: EvalContext, upto: int | None) -> list[Any]:
    """The values a reference points at: an agent's latest output, the last call's result / arguments, the end state."""
    (key, val), = ref.items()  # fmt: skip
    path = val.get("path")
    if key == "output":
        out = ctx.outputs(traj, upto).get(val["agent"])
        return get_path(out, path) if out is not None else []
    if key in ("result", "args"):
        mine = [c for _, c in _calls(traj, upto) if c.tool == val["tool"]]
        return get_path(mine[-1].result if key == "result" else mine[-1].args, path) if mine else []
    if key == "end_state":
        return get_path(traj.end_state, path)
    return get_path(run_inputs(traj), path)


def holds(cond: dict[str, Any], traj: Trajectory, ctx: EvalContext, upto: int | None = None) -> bool:
    (key, val), = cond.items()  # fmt: skip
    if key == "all":
        return all(holds(c, traj, ctx, upto) for c in val)
    if key == "any":
        return any(holds(c, traj, ctx, upto) for c in val)
    if key == "not":
        return not holds(val, traj, ctx, upto)
    calls = _calls(traj, upto)
    if key == "called":
        names = [val] if isinstance(val, str) else val
        return any(c.tool in names for _, c in calls)
    if key == "succeeded":
        return any(c.tool == val and not is_failure(c) for _, c in calls)
    if key == "failed":
        mine = [c for _, c in calls if c.tool == val]
        return bool(mine) and all(is_failure(c) for c in mine)
    if key == "fault":
        return any(c.tool == val and c.fault_injected for _, c in calls)
    if key in ("result", "args"):
        mine = [c for _, c in calls if c.tool == val["tool"]]
        got = [values_match(get_path(c.result if key == "result" else c.args, val.get("path")), val) for c in mine]
        return all(got) if val.get("every") else any(got)  # every: true holds vacuously when the tool was not called
    if key == "output":
        out = ctx.outputs(traj, upto).get(val["agent"])
        return out is not None and values_match(get_path(out, val.get("path")), val)
    if key == "end_state":
        return values_match(get_path(traj.end_state, val.get("path")), val)
    if key == "reply":
        texts = replies(traj)
        if val.get("scope") == "final":
            texts = [traj.final_message] if traj.final_message else []
        return any(match(t, val) for t in texts)
    if key == "user":
        texts = list(traj.user_turns) + [s.content for s in traj.steps if s.kind == "user" and s.content]
        return any(match(t, val) for t in texts)
    if key == "guard":
        return any(s.kind == "guard" and s.data.get("rule") == val for s in traj.steps if upto is None or s.index < upto)
    if key == "approval":
        return any(s.kind == "interrupt" and s.data.get("decision") == val for s in traj.steps if upto is None or s.index < upto)
    if key == "inputs":
        return values_match(get_path(run_inputs(traj), val.get("path")), val)
    if key == "equal":
        a, b = (value_of(r, traj, ctx, upto) for r in val)
        return [v for v in a if v is not None] == [v for v in b if v is not None]
    if key == "case":
        c = ctx.case
        for field_, want in val.items():
            have = getattr(c, field_, None)
            if have not in (want if isinstance(want, list) else [want]):
                return False
        return True
    raise ValueError(f"unknown condition {key}")


def stubbed_before(traj: Trajectory, upto: int, ctx: EvalContext) -> set[str]:
    """Agents whose work the run did not do itself before step `upto` — replaced by an L2 stub, or given as canned state
    (L1 Supervisor cases). Their own tool calls count as done."""
    out = {s.agent for s in traj.steps if s.index < upto and s.kind == "agent_result" and s.data.get("stop") == "stub" and s.agent}
    owners = ctx.slice_owners()
    for s in traj.steps:
        if s.index < upto and s.kind == "note" and s.content == "canned_state":
            out |= {owners.get(k, k) for k, v in (s.data.get("state") or {}).items() if v is not None}
    return out


# ------------------------------------------------------------------ rule checks
class PolicyEvaluator(Evaluator):
    """Runs every rule of the case's policy. Each rule gives one check, tagged with the rule ID."""

    metric = "POLICY"
    severity = "S1"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        if ctx.policy is None:
            return [self.skip("no policy file yet — the QE Lead writes projects/<project>/policies/*.yaml (docs/config_reference.md)",
                              metric="TR-3")]  # fmt: skip
        return [self.check_rule(r, traj, ctx) for r in ctx.policy.rules]

    def _r(self, rule: Rule, verdict: str, text: str, step: int | None = None) -> CheckResult:
        detail = f"{rule.id}: {text}" + (f" — rule: {rule.description}" if verdict == "fail" and rule.description else "")
        res = self.result(verdict, detail, agent=rule.agent, step=step, severity=rule.severity, metric=rule.metric_id)
        return res.model_copy(update={"rule": rule.id})

    def check_rule(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        return getattr(self, f"_{rule.kind}")(rule, traj, ctx)

    def _required(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        calls = _calls(traj, None)
        targets = (
            [i for i, c in calls if call_matches(c, rule.before)] if rule.before else [max((s.index for s in traj.steps), default=0) + 1]
        )
        if not targets:
            return self._r(rule, "skip", f"not triggered — {rule.before.tool} was not called")
        triggered = False
        for t in targets:
            if rule.when and not holds(rule.when, traj, ctx, t):
                continue
            triggered = True
            earlier = [c for i, c in calls if i < t]
            stubbed = stubbed_before(traj, t, ctx)
            missing = [r.tool for r in rule.requires if not any(call_matches(c, r) for c in earlier) and ctx.owner(r.tool) not in stubbed]
            if missing:
                where = f"before {rule.before.tool} (step {t})" if rule.before else "in the run"
                return self._r(rule, "fail", f"fail — {', '.join(missing)} not done {where}", step=t if rule.before else None)
        if not triggered:
            return self._r(rule, "skip", "not triggered — condition did not hold")
        stubbed = stubbed_before(traj, max(targets), ctx)
        by_stub = sorted({r.tool for r in rule.requires if ctx.owner(r.tool) in stubbed})
        return self._r(
            rule,
            "pass",
            "all required calls happened first" + (f" ({', '.join(by_stub)} stood in for by stubs or canned state)" if by_stub else ""),
        )

    _precedence = _required

    def _forbidden(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        for i, c in _calls(traj, None):
            if call_matches(c, rule.call) and (rule.when is None or holds(rule.when, traj, ctx, i)):
                return self._r(rule, "fail", f"fail — forbidden call {c.tool} by {c.agent}", step=i)
        if rule.when is not None and not holds(rule.when, traj, ctx):
            return self._r(rule, "skip", "not triggered — condition did not hold")
        return self._r(rule, "pass", f"{rule.call.tool} not called")

    def _implies(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        if rule.when is not None and not holds(rule.when, traj, ctx):
            return self._r(rule, "skip", "not triggered — condition did not hold")
        if rule.expect is None or holds(rule.expect, traj, ctx):
            return self._r(rule, "pass", "expectation held")
        return self._r(rule, "fail", "fail — condition held but the expectation did not")

    def _allow_list(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        for i, c in _calls(traj, None):
            owner = ctx.owner(c.tool)
            allowed = owner if isinstance(owner, list) else [owner]
            if owner is None or c.agent not in allowed:
                who = f"belongs to {owner}" if owner else "is not in any allow-list"
                return self._r(rule, "fail", f"fail — {c.agent} called {c.tool}, which {who}", step=i)
        return self._r(rule, "pass", "every call made by its owning agent")

    def _approval_token(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        calls = [(i, c) for i, c in _calls(traj, None) if call_matches(c, rule.call)]
        if not calls:
            return self._r(rule, "skip", f"not triggered — {rule.call.tool} was not called")
        user_text = " ".join(traj.user_turns + [s.content or "" for s in traj.steps if s.kind == "user"])
        for i, c in calls:
            token = c.args.get(rule.arg or "approval_token")
            issued = [s for s in traj.steps if s.index < i and s.kind == "interrupt" and s.data.get("decision") == "APPROVE"]
            logged = [s.data.get("token") for s in issued if s.data.get("token")]
            if token and token in user_text:
                return self._r(rule, "fail", f"fail — token {token} appears in customer text", step=i)
            if not issued:
                return self._r(rule, "fail", f"fail — {c.tool} called without an approved approval step before it", step=i)
            if logged and token not in logged:
                return self._r(rule, "fail", f"fail — token {token!r} was not issued by the approval step", step=i)
            if not logged and not any(s.data.get("token_issued") for s in issued):
                return self._r(rule, "fail", "fail — the approval step issued no token", step=i)
        return self._r(rule, "pass", "token issued by the approval step" + ("" if logged else " (token value not logged)"))

    def _slice_isolation(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        checked = 0
        for s in traj.steps:
            info = ctx.agents.get(s.agent or "")
            if s.kind != "agent_result" or info is None or info.contract is None:
                continue
            fields = set(info.contract.model_fields)
            contract, submitted = s.data.get("contract"), s.data.get("submitted")
            checked += 1
            if isinstance(contract, dict) and (extra := set(contract) - fields):
                return self._r(rule, "fail", f"fail — {s.agent} output kept keys outside its contract: {', '.join(sorted(extra))}", s.index)
            if isinstance(submitted, dict) and set(submitted) & fields and (extra := set(submitted) - fields):
                reported = any(st.kind == "contract" and st.agent == s.agent and st.index < s.index for st in traj.steps)
                if not reported:
                    return self._r(rule, "fail", f"fail — {s.agent} wrote {', '.join(sorted(extra))} and nothing reported it", s.index)
        if not checked:
            return self._r(rule, "skip", "no agent output with a contract in this run")
        return self._r(rule, "pass", f"{checked} agent output(s) inside their slices")

    def _limit(self, rule: Rule, traj: Trajectory, ctx: EvalContext) -> CheckResult:
        if rule.max_attempts:
            for i, c in _calls(traj, None):
                if c.attempt > rule.max_attempts:
                    return self._r(rule, "fail", f"fail — {c.tool} attempt {c.attempt} > {rule.max_attempts}", step=i)
        if rule.max_delegations:
            counts: dict[str, int] = {}
            for s in traj.steps:
                if s.kind == "handoff" and s.handoff_to:
                    counts[s.handoff_to] = counts.get(s.handoff_to, 0) + 1
                    if counts[s.handoff_to] > rule.max_delegations:
                        return self._r(rule, "fail", f"fail — {s.handoff_to} delegated {counts[s.handoff_to]} times", step=s.index)
        if rule.max_steps:
            n = sum(1 for s in traj.steps if s.kind == "decision")
            if n > rule.max_steps:
                return self._r(rule, "fail", f"fail — {n} Supervisor steps > {rule.max_steps}")
        return self._r(rule, "pass", "within limits")


def load_policies(paths: list[Path]) -> tuple[Policy | None, list[str]]:
    """Merge the rule files of a project. Returns (policy or None, notes about blank files)."""
    notes, merged = [], None
    for p in paths:
        if not p.is_file():
            raise ConfigError(f"{p}: policy file named in project.yaml does not exist.")
        if is_blank(p):
            notes.append(f"{p.name} is blank — the QE Lead writes it (see docs/config_reference.md › Policy files)")
            continue
        head = p.read_text(encoding="utf-8")
        if re.search(r"^masking:", head, re.MULTILINE):
            continue  # masking policy, read by the PII evaluator
        pol = load_policy(p)
        if merged is None:
            merged = pol
        else:
            merged = merged.model_copy(update={"rules": [*merged.rules, *pol.rules]})
    return merged, notes
