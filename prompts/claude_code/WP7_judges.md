# WP7 — LLM judges and calibration (23 Oct 2026)

## Requests
> start WP7 … complete what is possible within the session limit
> CONTINUE WP7 AND NO LIVE CALLS

## Decisions
- DeepEval 4.3.1's trajectory metrics need a trace captured by its own `@observe` tracing (private `_trace_dict`) and
  score 0–1; the judges therefore run on our own rubric judge with the SOP §3.9 0–3 anchors, quoted verbatim.
- Step efficiency is not judged: the SOP gives it no anchors and TR-6 / AG-6 measure it deterministically.
- Calibration gates against the testers' consensus (SOP §3.9), with per-tester and tester-vs-tester figures for context.
- Pricing left null: never guessed. No live judge call made; tests use a fake client.

## Produced
configs/judges.yaml, gates.yaml › judges, evalkit/evaluators/judges/{__init__,calibration,cache,geval_rubric,deepeval_metrics}.py,
`evalkit grade --judges`, `evalkit calibrate`, grader hook, tests/unit/evaluators/test_judges.py, docs.
