"""Generic fault hook, independent of any project: precedence, attempt counting, behaviours, virtual clock."""

from __future__ import annotations

import json

from evalkit.harness.fault_hook import FaultHook, FaultPlan, FaultRule, Override

OK = {"status": "VALID"}


def fn(args):
    return dict(OK)


def test_no_plan_passes_through():
    out = FaultHook().call("t", {"a": 1}, fn)
    assert (out.status, out.result, out.fault_injected, out.attempt) == ("ok", OK, None, 1)


def test_exact_attempt_beats_default_and_unlisted_attempts_pass():
    plan = FaultPlan(rules=[FaultRule("P", "t", 1, "TIMEOUT"), FaultRule("P", "t", 3, "HTTP_500")])
    h = FaultHook(plan)
    assert [h.call("t", {}, fn).status for _ in range(4)] == ["timeout", "ok", "error", "ok"]


def test_attempt_zero_covers_every_other_attempt():
    h = FaultHook(FaultPlan(rules=[FaultRule("P", "t", 1, "TIMEOUT"), FaultRule("P", "t", 0, "HTTP_500")]))
    assert [h.call("t", {}, fn).fault_injected for _ in range(3)] == ["P:TIMEOUT", "P:HTTP_500", "P:HTTP_500"]


def test_attempts_are_per_identical_arguments():
    h = FaultHook(FaultPlan(rules=[FaultRule("P", "t", 1, "TIMEOUT")]))
    assert h.call("t", {"x": 1}, fn).status == "timeout"
    assert h.call("t", {"x": 2}, fn).status == "timeout"
    assert h.call("t", {"x": 1}, fn).status == "ok"
    assert h.attempts("t", {"x": 1}) == 2


def test_override_wins_and_can_be_post_processed():
    h = FaultHook(FaultPlan(rules=[FaultRule("F", "t", 0, "TIMEOUT")], overrides=[Override("O", "t", {"v": 1})]))
    out = h.call("t", {}, fn, on_override=lambda r: {**r, "persisted": True})
    assert out.result == {"v": 1, "persisted": True} and out.fault_injected == "O:OVERRIDE"


def test_slow_uses_a_virtual_clock():
    h = FaultHook(
        FaultPlan(
            rules=[FaultRule("P", "t", 1, "SLOW", delay_ms=12_000), FaultRule("P", "t", 2, "SLOW", delay_ms=500)], client_timeout_ms=10_000
        )
    )
    late, fast = h.call("t", {}, fn), h.call("t", {}, fn)
    assert (late.status, late.latency_ms) == ("timeout", 10_000)
    assert (fast.status, fast.result, fast.latency_ms) == ("ok", OK, 500)


def test_error_malformed_empty_and_replace_fields():
    plan = FaultPlan(
        rules=[
            FaultRule("E", "e", 0, "ERROR", error_code="VERSION_NOT_FOUND", payload='{"version": "v3"}'),
            FaultRule("M", "m", 0, "MALFORMED_JSON", payload='{"x": tru'),
            FaultRule("Y", "y", 0, "EMPTY"),
            FaultRule("R", "r", 0, "REPLACE_FIELDS", payload='{"name": null}'),
        ]
    )
    h = FaultHook(plan)
    assert h.call("e", {}, fn).result == {"error": "VERSION_NOT_FOUND", "version": "v3"}
    m = h.call("m", {}, fn)
    assert m.status == "error" and m.for_agent() == '{"x": tru'
    assert h.call("y", {}, fn).result == {}
    r = h.call("r", {}, lambda a: {"fields": {"name": {"value": "A", "confidence": 0.9}, "dob": {"value": "D", "confidence": 0.9}}})
    assert r.result["fields"]["name"] == {"value": None, "confidence": 0.0} and r.result["fields"]["dob"]["value"] == "D"


def test_timeout_text_for_the_agent():
    out = FaultHook(FaultPlan(rules=[FaultRule("P", "t", 0, "TIMEOUT")])).call("t", {}, fn)
    assert json.loads(out.for_agent())["error"] == "TIMEOUT"


def test_business_errors_are_errors_without_fault_tag():
    out = FaultHook().call("t", {}, lambda a: {"error": "UNAUTHORISED"})
    assert (out.status, out.fault_injected) == ("error", None)
