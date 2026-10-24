# WP5 — deterministic evaluators, per-agent scorecards and gates (23 Oct 2026)

## Request
> start WP5

Scope from EXECUTION_PLAN.md › WP5: the policy engine, the S1 / S2 / S3 deterministic checks (TR, TU, BF), the agent
slicer and AG-1 … AG-6, scoring with the SOP §5.3 weights and the gate multiplier G, gates, and tests on good / bad
fixtures, offline on the recordings (no live runs).

## Boundary kept (CLAUDE.md › Rules that protect the evaluation)
Generated: the evaluators, the policy engine and its condition language, scoring, gates logic, the case-source merge of
the catalogue's oracle columns (read verbatim, nothing inferred), agents.yaml (system description only), the PII
recogniser registry, the labelled PII test set, the engine's test policy (rule IDs T-…), all unit tests, and the
schema documentation in docs/config_reference.md.

Not generated, left for the QE Lead:
- `projects/kyc_onboarding/policies/kyc_individual_v1.yaml` (R1–R3, P1–P3, F1–F4, A1, D1–D10, TRANS-1, SLICE-1, VER-1, AG-5 guardrails)
- `projects/kyc_onboarding/policies/pii_masking.yaml` (MASK-*)
- `configs/gates.yaml` thresholds (SOP §3.10)
- structured per-agent output and argument expectations (WP6 catalogue import, human-reviewed)

While these are blank the checks that need them report `skip` with the reason and the gate verdict is `NO_GATES`.

## Produced
evalkit/evaluators/** (except judges), evalkit/evaluators/grader.py, evalkit/config/registry.py, evalkit/scoring/*,
evalkit/reporting/jsonl_writer.py, `evalkit grade` / `evalkit gate`, configs/pii_recognizers.yaml,
projects/kyc_onboarding/agents.yaml, projects/kyc_onboarding/cases.py (catalogue columns), run-event additions
(run inputs, approval token, canned state), tests/unit/evaluators/*, tests/unit/test_gates.py,
tests/fixtures/pii_labelled.jsonl, tests/fixtures/policies/engine_rules.yaml, docs/config_reference.md.
