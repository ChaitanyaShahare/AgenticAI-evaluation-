# SOP-AIEVAL-001: changes from v0.3 to v1.0

**Status, 24 Oct 2026: every row is applied, as drafted, to
`BFSI_Agentic_AI_Evaluation_Methodology_SOP_v0.4.docx` as tracked changes for the QE Lead's review.** The author of the
changes is "Claude Code (for QE Lead review)". Seven Word comments mark the gap rows and the open decisions; v0.3 is
unchanged. Accept or reject each change in Word. v1.0 follows after the lab (WP10) and the replication demo (WP11),
whose results also change §6 and §8.

This list records every place where SOP v0.3 (23 Oct 2026, written before any code) differs from what WP1–WP8 built,
with the replacement wording. Where v0.4 differs from a row, the row's notes say how:
- **Row 2.1:** the actuals are a paragraph under the plan table, not a new column.
- **Gap rows (3.1, 3.19, 3.21, 3.22, 3.27, 6.2):** the text describes what is built, and a Word comment holds the
  build-or-drop decision. Where the SOP promises something unbuilt, the promise stays in place under its comment
  (3.21, 3.22).
- **Row 4.1:** the §4.1 stack table's Why and Licence cells were also updated for the replaced libraries.

Each item is one of:
- **Build differs.** The SOP should follow the build.
- **Decision.** The QE Lead decided it in the 23 Oct 2026 review; the SOP should record it.
- **Gap.** The SOP promises something that is not built yet. Either build it or drop it from the SOP.

## Header and front matter

| # | Where | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|---|
| H1 | Version line | "0.3 … no code written yet" | "1.0 — aligned with Test Case Catalogue v0.13 and the harness as built (WP1–WP11)" | Build |
| H2 | Changes line | v0.1 → v0.3 history | add a v1.0 line summarising this list | Build |
| H3 | Status | "Draft for review" | "Approved" once the approver signs (§3.13) | — |
| H4 | Conventions | "Code blocks are design skeletons only" | "Code excerpts are from the harness (`evalkit/`); the repository is authoritative" | Build |

## §1 Executive summary and scope reductions

| # | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|
| 1.1 | "OpenTelemetry adapter proven on recorded runs only; the LangGraph-state adapter is the primary path" | "OpenTelemetry adapter descoped (WP4): the KYC graph logs its own run events; an OTel adapter is built only when a second framework needs it" | Build |
| 1.2 | (not stated) | add: "DeepEval's agent metrics are not used: they need a trace captured live by DeepEval's `@observe` and score 0–1. The judges are our own 0–3 rubric judge on the Anthropic SDK, with the §3.9 anchors" | Build |
| 1.3 | "LLM judges are advisory until calibration passes (κ ≥ 0.6)" | "… until calibration against the testers' consensus passes (κ ≥ 0.6 and ≥ 85% agreement)" | Build |

## §2 Delivery plan

| # | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|
| 2.1 | Plan table and milestones as forecasts | Keep the plan as written. Add an "Actuals" column: WP1–WP8 built offline by 23 Oct (D2), ahead of plan; M2 depends on the live gate run. Point to EXECUTION_PLAN.md for the day-by-day status | Build |
| 2.2 | D8–14: evaluator and gate work | Record that the policy, masking rules, gates and S1 agent expectations were decided by the QE Lead in a question-and-answer review on 23 Oct 2026, then transcribed. No AI assistant wrote any oracle | Decision |

## §3 SOP body

| # | Section | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|---|
| 3.1 | §3.3 table | rule references R1–R3, P1–P3, F1–F4, D1–D10 | unchanged. Add that `policies/regulatory_mapping.yaml` maps each rule ID to its framework, with clause numbers marked [confirm] | Gap (the mapping file is empty) |
| 3.2 | §3.5 entry criteria | "adapter parity test passes on recorded runs" | "adapter parity: re-running the scripted recordings reproduces them exactly (`test_adapter_parity.py`)" | Build |
| 3.3 | §3.5 entry criteria | "Every tool has a JSON schema, a mock implementation and declared fault modes" | unchanged. Add: "declared in the spec (`x-fault-modes`) with its owner (`x-agent`) and class (`x-tool-class`)" | Build |
| 3.4 | §3.5 suspension | "> 10% of cases flip between identical runs" | "more than 10% of repeated cases flaky (`gates.yaml › flake_limit` 0.10) → verdict SUSPENDED, exit 2" | Build |
| 3.5 | §3.6 TR-2 | technique "(agentevals)" | "strict / unordered / subset / superset on tool names, agentevals semantics, implemented in `trajectory/match.py`; references RT-01 … RT-11 reviewed by the QE Lead on 23 Oct 2026" | Build |
| 3.6 | §3.6 TR-6 | "Reference steps ÷ actual steps, loop detection" | unchanged; method "deterministic" only | Build |
| 3.7 | §3.6 TR-8 | "Calibrated LLM judge, advisory" | "rubric judges TR-8.task (task completion) and TR-8.plan (plan adherence), 0–3, advisory until calibrated" | Build |
| 3.8 | §3.7 error handling | "≤ 2 retries, no fabricated result, inform or escalate" | unchanged. Add that fabrication and safe end states are policy rules D7, D10 and D10.no-retry (S1), and the retry bound is LIMIT-RETRY (S2) | Build |
| 3.9 | §3.9 table, TR-2 method | "Deterministic (agentevals)" | "Deterministic" | Build |
| 3.10 | §3.9 table, TR-6 method | "Deterministic + DeepEval StepEfficiency" | "Deterministic" | Build |
| 3.11 | §3.9 table, BF-1 method | "Rule + Presidio" | "Rule + regex / checksum recognisers (Verhoeff, Luhn); recall and precision ≥ 95% on a labelled set" | Build |
| 3.12 | §3.9 table, BF-4 method | "DeepEval NonAdvice + rule" | "Rules (TRANS-1, no prompt leak of 12+ words) + advisory rubric judge BF-4.explanation" | Build |
| 3.13 | §3.9 table, TU-5 severity | "S1/S2" | "S2 by default; the fabrication and safe-end-state rules (D7, D10) are S1" | Build |
| 3.14 | §3.9 | (not stated) | add verdicts: pass / fail / skip (not computable, with reason; never a pass) / error (evaluator crash; counts as a failure) | Build |
| 3.15 | §3.9 scoring formulas | composite assumes every component is measured | add: "a component that was not measured is left out, the remaining weights rescaled and the components used named" | Build |
| 3.16 | §3.9 judges | "≥ 85% agreement and κ ≥ 0.6 with the testers' consensus" | unchanged. Add the judge model (claude-opus-5-5, effort high), masked input, result cache keyed by trace and rubric version | Build |
| 3.17 | §3.10 | table of starting thresholds | unchanged values (adopted by the QE Lead, 23 Oct 2026). Add: TU-1 / TU-3 / AG-2 / AG-3 use the mean score, the others the pass rate. TR-8 is report-only. "Approved by: ___" until the approver signs | Decision |
| 3.18 | §3.10 | (not stated) | add the gate verdicts: NO_GATES (2), SUSPENDED (2), FAIL (1), INCOMPLETE (2), PASS (0). "A gate never passes on missing evidence" | Build |
| 3.19 | §3.12 privacy | "Presidio scans … for IN_PAN, IN_AADHAAR, CARD_PAN, phone, email and account numbers" | "regex + checksum scans for IN_PAN, IN_AADHAAR, CARD_PAN, IN_PHONE and EMAIL". Account numbers have no recogniser yet: add one or drop them from the list | Build / Gap |
| 3.20 | §3.12 masking rules | "Aadhaar last 4 only; card numbers per PCI display rules; PAN masked in customer-facing text" | "PAN: masked in replies and decisions. Aadhaar and card numbers: last 4 everywhere except the source document's tool results. Phone and e-mail: not repeated in replies (S2)" | Decision |
| 3.21 | §3.12 privacy | "Reports redact PII before rendering; CI fails if any untagged identifier appears in runs/" | "report.html and junit.xml are redacted and re-scanned; a surviving identifier stops the report (ReportLeak)". The CI scan of runs/ for untagged identifiers is not built: build it or drop it | Build / Gap |
| 3.22 | §3.12 privacy | "every generated identifier carries a SYNTHETIC tag" | true for the fixtures (checked by `check_fixtures.py`). The SYNTHETIC-tag rule has no pre-commit PII scan of staged fixtures yet: build it or drop it | Gap |
| 3.23 | §3.12 fairness | "one protected attribute (gender, religion, region)" | "pairs vary one of gender, religion or region; no scorer may receive gender, religion, region, state or caste (agents.yaml)" | Build |
| 3.24 | §3.12 screening | (implicit) | add: "a near-match (0.75–0.849) escalates like a hit (D1, GR-SCR.never-clear)" | Decision |
| 3.25 | §3.12 controls | (implicit) | add: "R2: both screening checks must succeed before finalising as APPROVED. D7 mandatory controls: verify_pan, sanctions_screen, pep_check, compute_risk_score, check_address_proof" | Decision |
| 3.26 | §3.12 transparency | "always states that it is an AI, including when … pressured" | "states that it is an AI when asked (TRANS-1.asked), and no reply ever claims to be human (TRANS-1.never-human)" | Decision |
| 3.27 | §3.13 run summary | header with executor, lockfile hash, judge status with κ, defects, sign-off | report.html has: verdict, S1 failures, gate table, per-agent scorecards, suite metrics, flaky cases, cost, and trial timelines with failing steps highlighted. Executor, lockfile hash, κ, defects and sign-off are not in it: they go in the audit pack (`docs/methodology/audit_pack_checklist.md`), or are added to the report | Gap |
| 3.28 | §3.13 defect report | "Reproduction: make eval CASE=<id> TRIALS=3" | "`uv run evalkit eval --case <id> --trials 3 --yes` (or `make eval CASE=<id> TRIALS=3 YES=1`)" | Build |
| 3.29 | §3.14 | procedure | unchanged. Add a step: "re-grade stored trajectories offline (`evalkit grade`) after an oracle or evaluator change; no model calls" | Build |

## §4 Architecture

| # | Section | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|---|
| 4.1 | §4.1 stack | LLMs via LangChain implied | "agents call the Anthropic SDK directly (`messages.create` for the specialists' tool loops, `messages.parse` with a Pydantic schema for the Supervisor router). Effort is pinned per role, with no sampling parameters and no refusal fallback" | Build |
| 4.2 | §4.1 stack | agentevals, DeepEval, Presidio, OpenTelemetry, pytest-xdist | "Trajectory matching: own implementation (agentevals semantics). Judges: own rubric judge on the Anthropic SDK. PII: regex + checksums. Tracing: run-event protocol (OTel descoped). Parallel trials: the runner's thread pool; pytest for the framework's own tests". These packages are still in `pyproject.toml` / `uv.lock`; remove them in the buffer | Build |
| 4.3 | §4.2 adapters | "LangGraphAdapter (primary), OTelAdapter (secondary)" | "LangGraphAdapter over the run-event protocol (`adapters/base.py`)" | Build |
| 4.4 | §4.3 | SQLite tables: applicants, documents, pan_registry, ckyc_records, sanctions_list, pep_list, risk_policy, applications, audit_events | add the 15 others in `data/schema.sql`: config, document_fields, screening_index, risk_engine_inputs, fixture_profiles, tool_faults, tool_overrides, agent_stubs, test_cases, case_documents, screening_results, approval_tokens, info_requests, edd_cases, customer_records. test_cases and case_documents are built from the case YAML | Build |
| 4.5 | §4.4 config examples | sketch of project.yaml, agents.yaml (allowlist, required_tools, guardrails) and policy (`required_steps:`, `precedence:` …) | replace with excerpts from the real files. Allow-lists come from `x-agent` in the tool specs. Required and forbidden tools are per case. Guardrails are policy rules with `agent:` and metric AG-5. The policy format is `rules: [{id, kind, …}]` with 8 kinds and a condition language (`docs/config_reference.md`) | Build |
| 4.6 | §4.5 trajectory schema | ToolCall, Step (5 kinds), Trajectory(meta: dict) | as built: ToolCall + `attempt`, `latency_ms`. Step kinds `llm, tool, handoff, interrupt, message, user, guard, contract, decision, agent_result, note` + `data`. RunMeta model. Trajectory + `agent_outputs`, `error` | Build |
| 4.7 | §4.5 interfaces | `CheckResult(check_id, passed, …)`, `Evaluator(scope=…)` | `CheckResult(metric, agent, rule, verdict, severity, score, detail, evidence_step)`. `Evaluator.evaluate(traj, ctx)` and `GroupEvaluator.evaluate_group(runs)`. `AgentAdapter.run(case, trial, run_id, db_path, client)` | Build |
| 4.8 | §4.5 scoring loop | judges on trial 1 | judges run on request (`grade --judges`, `full`) on every graded trace, with caching; they are a dry run unless `--yes` | Build |
| 4.9 | §4.6 instructions | `uv sync`; spaCy download; `make data SEED=42`; `make smoke/gate/full PROJECT=…`; `make eval … CASE=… TRIALS=3` | `uv sync --frozen`, with UV_PROJECT_ENVIRONMENT and EVALKIT_RUNS_DIR outside Dropbox. No spaCy model needed. `evalkit doctor`, `evalkit smoke` (offline), `evalkit run --mode smoke`, `evalkit gate`, `evalkit full` (each a dry run unless `--yes`), `evalkit eval --case … --trials 3`. The seed is in eval.yaml, not on the command line (`docs/setup.md`) | Build |
| 4.10 | §4.7 tree | `config-reference.md, extension-guide.md`; `training/deck/` | `config_reference.md, extension_guide.md, tester_guide.md, glossary.md`. There is no `training/deck/` yet (WP10) | Build |

## §5 Sample cases

| # | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|
| 5.1 | §5 KYC-AGT-SCR-007 row | "hit SAN-0001 (score 0.91)" | add matched_fields = [name_fuzzy, dob] (QE Lead decision of 23 Oct 2026; catalogue v0.13) | Decision |
| 5.2 | §5.1 example case | v0.3 sketch (`input:`, `mocks:`, `expectations:` …) | replace with the real `datasets/edge/KYC-EDG-014.yaml`: catalogue columns as text, plus structured `expected`, `reference`, `match_mode`, `fixtures`, `run_sets` | Build |
| 5.3 | §5 | (none) | note KYC-AGT-SCR-057 category = RCA (QE Lead decision; catalogue v0.13) | Decision |

## §6 Documentation and training

| # | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|
| 6.1 | §6.1 doc set incl. "Runbook" | the runbook (run modes, reports, triage, re-run triggers, cost) is part of `docs/tester_guide.md`; the glossary is `docs/glossary.md`; methodology extracts in `docs/methodology/` | Build |
| 6.2 | §6.3 exercises E1–E7 | the training folder has E1–E6 with different topics (E1 read a trajectory, E2 match mode, E3 policy case, E4 fault case, E5 per-agent case, E6 prompt comparison). Reconcile in WP10 | Gap |
| 6.3 | §6.4 lab | unchanged; confirm after the WP10 dry run | — |

## §7 Risks

| # | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|
| 7.1 | R7 mitigation | "explicit recogniser config; checksums; recall measured" | unchanged (still true; no Presidio) | — |
| 7.2 | R5 | pinned effort, contract builders, pass^k | add "flake_limit suspends the cycle" | Build |
| 7.3 | new | — | R14 "Oracle gaps make the gate INCOMPLETE (TU-3 argument expectations, AG-1 for specialists)": mitigation is QE Lead time on D13; early warning is INCOMPLETE on the first gate run | Build |

## §8 Acceptance checklist

Tick at sign-off. As of 24 Oct 2026: evaluator unit tests pass (334 tests). Per-agent scorecards are produced for all
five agents. HTML / JSONL / JUnit outputs are generated, and a seeded defect names its rule (offline). The 110-case
dataset covers every pattern. Not yet done: the live gate on the reference build, the CI run on GitHub, the
calibration report, the lab, the replication demo, and the audit pack.

## Appendix A

| # | v0.3 says | Proposed v1.0 | Kind |
|---|---|---|---|
| A.1 | agentevals, DeepEval, Presidio, OTel GenAI conventions as sources | "evaluated; not used in the MVP (reason in §4.1)" | Build |
| A.2 | — | add: Anthropic API — no sampling parameters on current models; structured outputs; effort (checked 21–23 Oct 2026) | Build |

## Open decisions for the QE Lead

1. Accept, reword or reject each row above.
2. Gaps 3.19, 3.21 and 3.22: build them in the buffer (small: a runs/ PII scan in CI, a pre-commit PII scan, an
   account-number recogniser), or remove the promises from the SOP.
3. Gap 3.27: add executor, lockfile hash and judge status to report.html, or leave them to the audit pack.
4. Version label: issue v1.0 at D27 as planned, or a v0.4 now with the accepted rows.
