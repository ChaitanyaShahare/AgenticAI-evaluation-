"""Judge calibration maths, the gating decision and the judge result cache (no live calls)."""

from __future__ import annotations

import json

import pytest

from evalkit.config import repo_root
from evalkit.config.loader import JudgesConfig, load_eval_config, load_model
from evalkit.evaluators.judges.cache import JudgeCache, trace_fingerprint
from evalkit.evaluators.judges.calibration import Label, agreement, calibrate, cohen_kappa, load_labels, render
from evalkit.scoring.gates import load_gates
from tests.unit.evaluators.conftest import load, with_end_state

ROOT = repo_root()


# ---------------------------------------------------------------- κ
def test_kappa_textbook_example():
    # 2×2 table: yes/yes 20, yes/no 5, no/yes 10, no/no 15 → p_o = 0.70, p_e = 0.50, κ = 0.40
    a = [1] * 20 + [1] * 5 + [0] * 10 + [0] * 15
    b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
    assert agreement(a, b) == pytest.approx(0.70)
    assert cohen_kappa(a, b) == pytest.approx(0.40)


def test_kappa_edges():
    assert cohen_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    assert cohen_kappa([0, 3, 0, 3], [3, 0, 3, 0]) < 0  # systematic disagreement is worse than chance
    assert cohen_kappa([2, 2, 2], [2, 2, 2]) == 1.0  # one shared category: total agreement
    near = cohen_kappa([0, 1, 2, 3], [1, 2, 3, 3], weights="quadratic")
    far = cohen_kappa([0, 1, 2, 3], [3, 3, 0, 0], weights="quadratic")
    assert near > 0.5 > far  # weighted κ credits near misses on the 0–3 scale
    with pytest.raises(ValueError):
        cohen_kappa([1], [1, 2])


# ---------------------------------------------------------------- calibration
def labels(metric, judge, t1, t2):
    rows = []
    for i, (j, x, y) in enumerate(zip(judge, t1, t2, strict=True)):
        rows += [Label(f"tr{i}", metric, "judge", j), Label(f"tr{i}", metric, "T1", x), Label(f"tr{i}", metric, "T2", y)]
    return rows


def test_judge_gates_only_when_it_agrees_with_the_consensus():
    scores = [0, 1, 2, 3] * 8  # 32 traces
    good = labels("TR-8.task", scores, scores, scores)
    off = labels("TR-8.plan", [(x + 1) % 4 for x in scores], scores, scores)  # testers agree; the judge does not
    split = labels("BF-4.explanation", scores, scores, [(x + 1) % 4 for x in scores])  # testers never agree
    res = {m.metric: m for m in calibrate(good + off + split)}
    assert res["TR-8.task"].gates and "consensus" in res["TR-8.task"].reason
    assert [p.raters for p in res["TR-8.task"].pairs] == [("judge", "T1"), ("judge", "T2"), ("T1", "T2"), ("judge", "consensus")]
    assert not res["TR-8.plan"].gates and "vs consensus" in res["TR-8.plan"].reason
    assert not res["BF-4.explanation"].gates and "no trace has both" in res["BF-4.explanation"].reason
    adjudicated = split + [Label(f"tr{i}", "BF-4.explanation", "consensus", x) for i, x in enumerate(scores)]
    assert {m.metric: m for m in calibrate(adjudicated)}["BF-4.explanation"].gates  # an adjudicated consensus counts
    assert "advisory" in render(list(res.values()))


def test_too_few_traces_stays_advisory():
    s = [0, 1, 2, 3] * 3  # 12 traces
    (res,) = calibrate(labels("BF-4.explanation", s, s, s))
    assert not res.gates and "only 12 traces" in res.reason


def test_label_file_errors_are_readable(tmp_path):
    p = tmp_path / "labels.jsonl"
    p.write_text(json.dumps({"trace_id": "a", "metric": "m", "rater": "T1", "score": 2}) + "\n" + '{"trace_id": "b"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2: need trace_id, metric, rater"):
        load_labels(p)


# ---------------------------------------------------------------- cache
def test_cache_key_ignores_wall_clock_but_not_behaviour(tmp_path):
    a = load("KYC-GLD-001")
    rerun = a.model_copy(
        update={"meta": a.meta.model_copy(update={"run_id": "other", "started_at": "2026-11-01T00:00:00", "duration_s": 9.9})}
    )
    assert trace_fingerprint(a) == trace_fingerprint(rerun)
    assert trace_fingerprint(a) != trace_fingerprint(with_end_state(a, status="REJECTED"))
    k = JudgeCache.key(a, "TR-8.task", "r1", "claude-opus-5-5")
    assert k == JudgeCache.key(rerun, "TR-8.task", "r1", "claude-opus-5-5")
    assert len({k, JudgeCache.key(a, "TR-8.task", "r2", "claude-opus-5-5"), JudgeCache.key(a, "TR-8.plan", "r1", "claude-opus-5-5"),
                JudgeCache.key(a, "TR-8.task", "r1", "claude-sonnet-5-5")}) == 4  # fmt: skip
    cache = JudgeCache(tmp_path)
    assert cache.get(k) is None
    cache.put(k, {"score": 3, "reason": "goal met"})
    assert cache.get(k) == {"score": 3, "reason": "goal met"}


# ---------------------------------------------------------------- configuration
def test_shipped_judge_config():
    cfg = load_model(JudgesConfig, ROOT / "configs" / "judges.yaml")
    assert cfg.model == load_eval_config().models.judge  # the judge is the model eval.yaml names
    assert {m.id for m in cfg.metrics} >= {"TR-8.task", "TR-8.plan", "BF-4.explanation"} and all(m.scale_max == 3 for m in cfg.metrics)
    g = load_gates(ROOT / "configs" / "gates.yaml")
    assert (g.judges.min_kappa, g.judges.min_agreement) == (0.6, 0.85)


# ---------------------------------------------------------------- rubric judge (fake client; no live calls)
from types import SimpleNamespace  # noqa: E402

from evalkit.config.registry import ProjectSuite  # noqa: E402
from evalkit.evaluators.judges import configured_rubrics, load_judges_config  # noqa: E402
from evalkit.evaluators.judges.calibration import judge_labels, labelling_sheet  # noqa: E402
from evalkit.evaluators.judges.deepeval_metrics import PLAN_ADHERENCE, RUBRICS, TASK_COMPLETION  # noqa: E402
from evalkit.evaluators.judges.geval_rubric import RubricJudge, Verdict, plan, render_trace  # noqa: E402
from tests.recordings import RECORDINGS  # noqa: E402
from tests.unit.evaluators.conftest import ctx_for  # noqa: E402


class FakeClient:
    def __init__(self, score=2, stop="end_turn", fail=False):
        self.requests, self.score, self.stop, self.fail = [], score, stop, fail
        self.messages = self

    def parse(self, **kw):
        self.requests.append(kw)
        if self.fail:
            raise RuntimeError("overloaded")
        return SimpleNamespace(stop_reason=self.stop, parsed_output=Verdict(reason="goal met, reply consistent", score=self.score))


@pytest.fixture(scope="module")
def jcfg():
    return load_judges_config()


def test_configured_rubrics_have_the_sop_anchors(jcfg):
    rubrics = configured_rubrics(jcfg)
    assert [r.id for r in rubrics] == ["TR-8.task", "TR-8.plan", "BF-4.explanation"]
    assert TASK_COMPLETION.anchors[3] == "Goal fully met; end state and message consistent"
    assert PLAN_ADHERENCE.anchors[0] == "No coherent plan; contradictory steps"
    assert RUBRICS["BF-4.explanation"].anchors[0] == "Wrong, misleading, or leaks restricted information"


def test_judge_sees_a_masked_trace(suite):
    t = load("KYC-GLD-001")
    text = render_trace(t, ctx_for(suite, t), TASK_COMPLETION.views)
    assert "ZQBPI1137K" not in text and "verify_pan" in text and "END STATE" in text


def test_judge_request_shape_and_cache(tmp_path, suite, jcfg):
    t = load("KYC-GLD-001")
    fake = FakeClient(score=2)
    judge = RubricJudge(fake, jcfg, JudgeCache(tmp_path))
    res = judge.score(t, ctx_for(suite, t), TASK_COMPLETION)
    assert (res.metric, res.severity, res.verdict, res.score) == ("TR-8.task", "S3", "pass", 0.667) and "2/3" in res.detail
    req = fake.requests[0]
    assert req["model"] == "claude-opus-5-5" and req["output_config"] == {"effort": "high"} and req["output_format"] is Verdict
    assert not {"temperature", "top_p", "top_k"} & set(req)  # the API rejects sampling parameters
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "ZQBPI1137K" not in str(req["messages"])
    judge.score(t, ctx_for(suite, t), TASK_COMPLETION)
    assert judge.calls == 1 and len(fake.requests) == 1  # second time from the cache


@pytest.mark.parametrize(("client", "expect"), [(FakeClient(stop="refusal"), "refusal"), (FakeClient(fail=True), "RuntimeError")])
def test_an_unavailable_judge_is_an_error_not_a_pass(tmp_path, suite, jcfg, client, expect):
    t = load("KYC-GLD-001")
    res = RubricJudge(client, jcfg, JudgeCache(tmp_path)).score(t, ctx_for(suite, t), PLAN_ADHERENCE)
    assert res.verdict == "error" and expect in res.detail


def test_plan_counts_calls_and_never_guesses_cost(tmp_path, suite, jcfg):
    runs = [(t, ctx_for(suite, t)) for t in (load("KYC-GLD-001"), load("KYC-HND-109"), load("KYC-FLT-021"))]
    rubrics = configured_rubrics(jcfg)
    p = plan(runs, jcfg, rubrics, JudgeCache(tmp_path))
    assert (p.calls, p.cached) == (6, 0) and p.input_tokens > 0  # FLT-021 is L1: no customer, not judged
    assert p.cost(jcfg) is None and "cost unknown" in p.describe(jcfg)
    priced = jcfg.model_copy(update={"pricing": jcfg.pricing.model_copy(update={"input_per_mtok": 10.0, "output_per_mtok": 50.0})})
    assert p.cost(priced) == round(p.input_tokens / 1e6 * 10 + p.output_tokens / 1e6 * 50, 2)


def test_grade_with_a_judge_adds_advisory_checks(tmp_path, jcfg):
    from evalkit.evaluators.grader import grade

    suite = ProjectSuite.load("kyc_onboarding")
    judge = RubricJudge(FakeClient(score=1), jcfg, JudgeCache(tmp_path))
    res = grade(suite, [load("KYC-GLD-001")], judge, configured_rubrics(jcfg)).results[0]
    judged = [c for c in res.checks if c.metric in RUBRICS]
    assert len(judged) == 3 and all(c.severity == "S3" and c.verdict == "fail" for c in judged)
    assert res.passed  # an advisory judge never fails a trial


def test_labelling_sheet_round_trip(tmp_path, jcfg):
    import yaml

    sheet = tmp_path / "labels_T1.yaml"
    n = labelling_sheet(RECORDINGS, jcfg, "T1", sheet)
    text = sheet.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert n == 9 and data["rater"] == "T1" and "Goal fully met" in text  # 3 conversations x 3 metrics
    data["items"][0]["score"] = 3
    sheet.write_text(yaml.safe_dump(data), encoding="utf-8")
    (lab,) = load_labels(sheet)  # unscored items are skipped
    assert (lab.rater, lab.score) == ("T1", 3)
    results = tmp_path / "results.jsonl"
    row = {"case_id": "KYC-GLD-001", "trial": 1, "metric": "TR-8.task", "verdict": "pass", "score": 0.667}
    results.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert judge_labels(results, jcfg) == [Label("KYC-GLD-001/t1", "TR-8.task", "judge", 2)]


def test_cli_judges_dry_run_makes_no_call(tmp_path, monkeypatch, capsys):
    import anthropic

    from evalkit import cli

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: pytest.fail("no client may be created in a dry run"))
    code = cli.main(["grade", str(RECORDINGS), "--out", str(tmp_path), "--judges"])
    out = capsys.readouterr().out
    assert code == 2 and "dry run — no judge calls made" in out and "judgement(s) with claude-opus-5-5" in out
    assert cli.main(["calibrate", "--template", str(RECORDINGS), "--rater", "T2", "--out", str(tmp_path / "t2.yaml")]) == 0
    assert (tmp_path / "t2.yaml").is_file()


def test_judge_cache_lives_in_the_runs_folder(tmp_path, monkeypatch, jcfg):
    from evalkit.evaluators.judges import cache_folder

    monkeypatch.setenv("EVALKIT_RUNS_DIR", str(tmp_path / "elsewhere"))
    assert cache_folder(jcfg) == tmp_path / "elsewhere" / "judge_cache"
    absolute = jcfg.model_copy(update={"cache_dir": str(tmp_path / "fixed")})
    assert cache_folder(absolute) == tmp_path / "fixed"
