"""TU-2 argument schema validity and TU-3 argument value correctness.

TU-2: every call's arguments validate against the tool's input_schema (jsonschema, Draft 2020-12). Score = share valid.
TU-3: arguments equal the case's argument expectations — case.expected["arguments"] = {tool: {arg: value}} — after
name normalisation (case and spacing). Expectations come from the catalogue's "Argument expectations" column, which WP6
structures; until then TU-3 is skipped.
"""

from __future__ import annotations

from jsonschema import Draft202012Validator

from evalkit.evaluators.base import EvalContext, Evaluator, norm_text
from evalkit.schema import CheckResult, ToolCall, Trajectory


def schema_errors(call: ToolCall, ctx: EvalContext) -> list[str]:
    spec = ctx.tool_specs.get(call.tool)
    if spec is None or "input_schema" not in spec:
        return [f"{call.tool}: no tool spec"]
    v = Draft202012Validator(spec["input_schema"])
    return [f"{call.tool}.{'.'.join(map(str, e.path)) or '(args)'}: {e.message}" for e in v.iter_errors(call.args)]


def args_correct(call: ToolCall, expected: dict) -> list[str]:
    wrong = []
    for arg, want in expected.items():
        have = call.args.get(arg)
        if norm_text(have) != norm_text(want):
            wrong.append(f"{call.tool}.{arg} = {have!r}, expected {want!r}")
    return wrong


class SchemaValidityEvaluator(Evaluator):
    metric = "TU-2"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        calls = [(s.index, s.tool_call) for s in traj.steps if s.tool_call]
        if not calls:
            return [self.skip("no tool calls")]
        bad = [(i, e) for i, c in calls for e in schema_errors(c, ctx)[:1]]
        score = round(1 - len(bad) / len(calls), 3)
        if bad:
            return [self.result("fail", "; ".join(e for _, e in bad[:3]), score=score, step=bad[0][0])]
        return [self.result("pass", f"{len(calls)} call(s) schema-valid", score=1.0)]


class ArgumentCorrectnessEvaluator(Evaluator):
    metric = "TU-3"
    severity = "S2"

    def evaluate(self, traj: Trajectory, ctx: EvalContext) -> list[CheckResult]:
        expected = ctx.case.expected.get("arguments")
        if not expected:
            return [self.skip("no structured argument expectations yet (catalogue column, structured in WP6)")]
        checked, wrong = 0, []
        for s in traj.steps:
            if s.tool_call and s.tool_call.tool in expected:
                checked += 1
                wrong += [(s.index, w) for w in args_correct(s.tool_call, expected[s.tool_call.tool])]
        if not checked:
            return [self.result("fail", f"none of {', '.join(expected)} was called", score=0.0)]
        score = round(1 - len({i for i, _ in wrong}) / checked, 3)
        if wrong:
            return [self.result("fail", "; ".join(w for _, w in wrong[:3]), score=score, step=wrong[0][0])]
        return [self.result("pass", f"{checked} call(s) with expected values", score=1.0)]
