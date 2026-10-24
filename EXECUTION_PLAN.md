# Execution plan: working MVP evaluation harness

**Objective:** build a working MVP that applies the SOP-AIEVAL-001 methodology to **every individual agent** of a multi-agent BFSI system, plus its hand-offs and its end-to-end outcome. The system is the KYC-onboarding assistant: a Supervisor and four specialists running over 13 mocked tools and synthetic data. A second toy project then proves that the harness carries over to new projects through configuration alone.

**Window:** Day 1 = Thu 22 Oct 2026 → Day 30 = Fri 20 Nov 2026 · today = Day 2 (Fri 23 Oct).
**People:** the QE Lead is full time. Two testers are available in Weeks 3–4 (D15–D28) and work in YAML and on the command line only. There is no compliance SME, so S1 rules are reported as *unvalidated*.
**Rule:** S1 expectations, policy YAML, gate thresholds and the lab answer key are written by a human. Claude Code may scaffold, write mocks and evaluators, and write tests, but never the oracle that judges its own code.

## 1. Definition of done

| Deliverable | Accepted when |
|---|---|
| Methodology and SOP | SOP v1.0 (from v0.3) matches the built harness; a tester completes one full evaluation cycle from the SOP alone |
| Working implementation | `make smoke`, `make gate` and `make full` run from a clean clone; all S1 checks pass on the reference build across k = 3; every one of the 5 agents has a per-agent scorecard (AG-1 … AG-6) in `report.html`; each seeded defect LAB-1 … LAB-6 fails ≥ 1 S1 or S2 check |
| Reuse | `projects/demo_second/` is evaluated with a new adapter config, policy and 10 cases, with **zero** changes in `evalkit/` |
| Judges | Calibration report with agreement and κ on 30 traces; judges gate only if κ ≥ 0.6 and agreement ≥ 85%, otherwise they stay advisory (an accepted outcome) |
| Training | Both testers catch ≥ 5 of 6 seeded defects and write 10 cases each that pass `make lint-cases` |

## 2. Status at Day 2

| Done | Artefact |
|---|---|
| Requirements v0.3 (per-agent intake, decisions D1–D10, test clock, blank intake template) | `docs/requirements/Agent_Requirement_KYC_v0.3.xlsx` |
| 110 test cases with all fixtures, rules and lab answer key | `docs/requirements/KYC_Test_Case_Catalogue_v0.12.xlsx` |
| Synthetic data generator, seed DB and conformance checker (105 checked, 0 problems) | `projects/kyc_onboarding/data/` |
| SOP v0.3 (India-anchored, no-SME MVP) | `docs/sop/` |
| Repository skeleton, with every file named and described | this repository, `README.md` |
| **WP1 (23 Oct):** pinned environment (`uv.lock`, 146 packages), strict config loader, `evalkit` CLI (doctor, data, test, smoke), 23 framework tests, CI skeleton, Makefile, pre-commit | `pyproject.toml`, `configs/eval.yaml`, `evalkit/cli.py`, `evalkit/config/`, `tests/` |
| **WP2 (23 Oct, ahead of the 24–26 Oct slot):** 14 tool specs, SQLite-backed mocks for 13 tools and 5 hand-offs, generic fault hook, tool registry (allow-list, schema validation, audit, LangChain binding), 116 mock tests covering every fault, override and stub profile | `projects/kyc_onboarding/tools/`, `evalkit/harness/fault_hook.py`, `tests/unit/test_mocks.py` |

Found in WP1:
- `make` is not installed on this machine, so the `evalkit` CLI is the primary interface.
- The repository has no git remote, so CI has not run on GitHub yet; its exact steps pass locally.
- The Claude desktop app redirects `AppData\Local`, so the virtual environment lives in `C:\Users\<you>\.venvs\`.

| **WP3 (23 Oct):** KYC multi-agent system on the official Anthropic SDK inside LangGraph — Supervisor (structured-output router, decision table D1–D10, guards), 4 specialists (model drives tools; deterministic contract builders), approval interrupt, corporate stub, 5 versioned prompts, case driver; 27 offline graph tests with a scripted client | `projects/kyc_onboarding/sut/`, `contracts.py`, `tests/unit/test_kyc_graph.py` |

**M1 status:** KYC-GLD-001 passed live (APPROVED, LOW 22, REC-001, reference order, 7 Supervisor steps, about 60 s, about $0.03). The other 9 golden cases were deliberately not run live yet, to save cost; run `uv run evalkit test --with-api` to complete M1.

Changed in WP3: no sampling parameters (the API rejects temperature), effort pinned per role; agents call the Anthropic SDK directly (LangChain's structured output forces a tool call, which Sonnet 5.5 rejects); no refusal fallback. KYC-MIS-087 fixture fixed (form nationality blank, supplied on request).

| **WP4 (23 Oct):** canonical Trajectory / TestCase / result schemas; LangGraph adapter over the run-event protocol; harness runner (per-trial DB sandbox, k trials per severity, run modes, parallel trials, run folder layout); clock check; L1 specialist cases in the KYC driver; `evalkit eval` / `evalkit run` with dry-run cost guard; 4 recordings (3 scripted, 1 live) | `evalkit/schema/`, `evalkit/adapters/`, `evalkit/harness/`, `projects/kyc_onboarding/cases.py`, `recorded_runs/` |

**WP4 live check:** `evalkit eval --case KYC-GLD-001 --trials 1 --yes` → APPROVED, LOW 22, REC-001, reference order, 17 tool calls, 37 s, about $0.04. Descoped: the OTel adapter (and its parity test); LangChain callbacks are not needed because the graph logs its own events. Fixed while recording: L1 cases could not see the applicant's documents; L2 risk stubs did not record the tier.

| **WP5 (23 Oct, ahead of the 29 Oct–4 Nov slot):** policy engine (8 rule kinds over a condition language); TR-1, TR-2, TR-5, TR-6, TR-7; TU-1 … TU-6; BF-1 (regex + Verhoeff / Luhn, no spaCy needed), BF-3, BF-4, BF-5, BF-6; agent slicer and AG-1 … AG-6 with TU-7 per agent; SOP §5.3 composites with G; per-agent / pattern / suite roll-ups; gate verdicts and exit codes; `evalkit grade` and `evalkit gate`; agents.yaml; catalogue oracle columns in the case source; 68 evaluator and gate tests on the recordings (offline, no live runs); 263 framework tests in total | `evalkit/evaluators/`, `evalkit/scoring/`, `evalkit/config/registry.py`, `tests/unit/evaluators/`, `tests/unit/test_gates.py` |

**WP5 state — waiting on the QE Lead.** The engine runs, but the oracles it executes are human-owned and still blank: `policies/kyc_individual_v1.yaml`, `policies/pii_masking.yaml` and `configs/gates.yaml` (schemas and a catalogue-kind mapping in `docs/config_reference.md`). Until they are written, the policy checks (TR-3, TR-4, BF-2, A1, D1–D10, AG-5) and BF-1 report `skip`, and the gate reports `NO_GATES` (exit 2). M2 (`evalkit gate --yes`, 210 trials, about $4.26) is not run yet. Still skipped for lack of structured oracles until WP6: TR-2 (reference trajectories RT-01 … RT-11), TU-3 and AG-3's correctness part (argument expectations), AG-1 for specialists (expected agent outputs).

Changed in WP5: the run log now records the run inputs (application and applicant IDs, form, documents), the approval token and the canned state of L1 Supervisor cases, so TU-4 grounding and A1 token provenance can be checked. The three scripted recordings were refreshed, and the live KYC-GLD-001 recording was re-recorded once (23 Oct, `adhoc-20261023T124533Z`: APPROVED, LOW 22, REC-001, reference order, 17 tool calls, 38 s, about $0.04); every check that can run passes on it, TU-4 and A1 token provenance included. In L2 cases a stubbed specialist counts as having made its own tool calls for `required` / `precedence` rules.

| **WP6 (23 Oct, ahead of the 30 Oct–11 Nov slot):** the 110 cases as YAML (`datasets/<pattern>/<case_id>.yaml`), the source of truth for both the seed database's case tables and the harness; `evalkit cases` (workbook import, keeps edited files), `evalkit lint-cases` (30 mistake classes, plain-English fixes), `evalkit coverage` (matrix, run sets, oracle completeness, catalogue comparison); RT-01 … RT-11 as JSON; tester guide `datasets/README.md` | `evalkit/datasets/`, `projects/kyc_onboarding/datasets/`, `reference_trajectories/`, `tests/unit/test_case_lint.py` |

**WP6 exit check:** every catalogue row is reproduced column by column (re-import is a no-op); the seed database rebuilt from the YAML is identical, table by table, to the v0.12 seed and passes the conformance check; the coverage matrix equals the catalogue's (E2E 15 · SUP 34 · DOC 17 · IDV 11 · SCR 15 · RSK 18; smoke 10 · gate 210 · full 250 runs); `lint-cases` reports 0 errors on the shipped cases and each mistake class in its test.

**WP6 — waiting on the QE Lead.** (1) Review RT-01 … RT-11: the sheet's "…" and "×n" were expanded by a stated rule (RT-05 and RT-08 are deliberately lax), and each file says how; set `reviewed_by` when accepted. (2) Fill `expected.agent_outputs` for the 24 S1 agent-level cases (lint warns on each) and `expected.arguments` where TU-3 matters — the import copies the text and never guesses these oracles. Until then AG-1 (specialists) and TU-3 stay skipped. The catalogue's *Lab defect caught* column is deliberately not in the YAML (lab answer key). `fixtures/kyc_cases.py` is retired and kept for provenance.

**QE Lead decisions, 23 Oct 2026 (question-and-answer review).** The human-owned inputs are now in place, each transcribed from the QE Lead's answers: `policies/kyc_individual_v1.yaml` (37 rules: R1–R3, P1–P3, F1–F4, A1, D1–D10, limits, TRANS-1, SLICE-1, VER-1, guardrails for all five agents), `policies/pii_masking.yaml` (5 rules), `configs/gates.yaml` (SOP §3.10 values; approver not named), RT-01 … RT-11 marked reviewed, and `expected.agent_outputs` for 23 of the 24 S1 agent-level cases (KYC-PII-044 has no field to check; masking and the contract cover it). Decisions that changed the catalogue: KYC-AGT-SCR-007 matched_fields = [name_fuzzy, dob] and KYC-AGT-SCR-057 category = RCA (aligned with the fixtures) — carry these into catalogue v0.13. The policy fires on every seeded defect tried and on none of the four recordings (`test_kyc_policy_catches_seeded_defects`). Gate on the recordings: INCOMPLETE — TU-3 (no argument expectations yet) and the edge / adversarial TR-1 threshold are not measured until a gate run.

| **WP7, part 1 (23 Oct):** `configs/judges.yaml` (Opus judge, effort high, 4 metrics on 0–3, rubric version, cache, pricing left null until checked); judge-gating bar in `configs/gates.yaml` (SOP §3.10: κ ≥ 0.6, ≥ 85%); calibration maths (agreement, Cohen's κ, quadratic-weighted κ, per-metric gating decision); judge result cache; 8 offline tests | `evalkit/evaluators/judges/calibration.py`, `cache.py`, `tests/unit/evaluators/test_judges.py` |

**WP7, part 2 (23 Oct, offline):** DeepEval checked (deepeval 4.3.1): its TaskCompletion / StepEfficiency / PlanAdherence need a trace captured live by DeepEval's `@observe` and score 0–1, so the judges run on our own rubric judge with the SOP §3.9 anchors (task completion, plan adherence, customer explanation); step efficiency stays deterministic (TR-6, the SOP gives no anchors). Rubric judge on the Anthropic SDK (masked trace, structured 0–3 verdict, effort high, cached); `evalkit grade --judges` (dry run with call count and cost unless `--yes`); `evalkit calibrate` (labelling sheet per tester; agreement and κ; gating against the testers' consensus, as SOP §3.9 says). 16 judge tests, fake client only.

**WP7 still to do (needs people or spend):** (1) judge pricing in `configs/judges.yaml` from the current price list; (2) one judged run (`evalkit grade <run> --judges --yes`, after approving its cost); (3) testers T1 and T2 label 30 traces each (D16–D20) on sheets from `evalkit calibrate --template`; (4) `evalkit calibrate` writes the calibration report (M3). No live judge call has been made.

| **WP8 (23 Oct, offline):** `junit.xml` (one test per case × trial × check, named after the rule), `report.html` (verdict, gate, per-agent scorecards, suite metrics, cost, timelines with failing steps highlighted; refuses to write if an identifier survives redaction), `cost.json` with a monthly ledger and 50% / 80% alerts (money only from configured prices), `evalkit report`, `evalkit full`, CI workflow (smoke on push, gate on PR, full nightly, JUnit annotations); 11 tests | `evalkit/reporting/`, `evalkit/harness/cost.py`, `.github/workflows/eval.yml`, `tests/unit/test_reporting.py` |

**WP8 exit check:** a seeded defect (pep_check skipped) gives exit 1 and names `KYC-GLD-001 t1 · TR-3 (R1)` in the console and in junit.xml; report.html and junit.xml contain no unmasked identifier even when a reply leaks one (tested offline). **Not yet proven on GitHub:** the repository has no remote, so the workflow has only been validated with yamllint; it needs the `ANTHROPIC_API_KEY` secret for its live steps. **Still to set:** prices and the USD→INR rate in `configs/eval.yaml › budget` (and judge prices), and the monthly budget — until then cost.json reports tokens with cost "unknown" and alerts off.

| **WP9, first draft (24 Oct, offline):** `docs/setup.md`, `architecture.md`, `tester_guide.md` (includes the SOP's runbook), `extension_guide.md`, `glossary.md`; `config_reference.md` completed (eval.yaml, project.yaml, tool specs, environment); the five methodology extracts; `projects/kyc_onboarding/README.md`; `docs/sop/SOP_v1.0_change_list.md` (every v0.3 statement the build changed, with proposed wording) applied as tracked changes in `docs/sop/BFSI_Agentic_AI_Evaluation_Methodology_SOP_v0.4.docx`, with 7 comments on the gaps. Also fixed: `make eval` now passes `CASE` / `TRIALS`, and `YES=1` / `RUN=` were added | `docs/`, `docs/methodology/`, `projects/kyc_onboarding/README.md`, `Makefile` |

**WP9 — waiting on the QE Lead.** (1) Accept or reject the tracked changes in SOP v0.4 and answer its 7 comments (v1.0 at D27, after WP10 / WP11 change §6 and §8). The change list flags three SOP promises that are not built: a CI PII scan of runs/, a pre-commit PII scan, and an account-number recogniser. (2) `policies/regulatory_mapping.yaml` is human-owned (policies/) and needs compliance-confirmed clauses; it is still empty. (3) Exit check: a tester runs one full cycle from the SOP and `docs/tester_guide.md` without help.

| **WP10 (24 Oct, offline):** LAB-1 … LAB-6 as code switches in the agents, read from `EVALKIT_LAB_SWITCHES`, which only `evalkit lab --variant LAB-n --case …` sets (a normal run refuses while it is set; the variant is recorded in manifest.json); neutral variant files; seven modules, six exercises with model answers, lab README, assessment and scoring sheet; `make lab VARIANT= CASE=` | `projects/kyc_onboarding/sut/lab/`, `training/**`, `evalkit/cli.py` (lab), `tests/lab/test_seeded_defects.py`, `tests/unit/test_lab.py` |

**WP10 exit check (engineering half, offline):** each variant, run with a scripted model on a case listed in catalogue › Lab Mapping, fails an S1 / S2 check that the same run without the switch passes (KYC-GLD-001, KYC-FLT-028, KYC-PII-042, KYC-FLT-021, KYC-ADV-032, KYC-HND-067). **Waiting on the QE Lead:** (1) `training/lab/answer_key/answer_key.md`: transcribed verbatim at the QE Lead's request from catalogue › Lab Mapping and `sut/lab/defects.py`. Review it and sign the header; its reviewer note lists where the offline test's failing checks differ from the sheet's. (2) Review the model answers in `training/exercises/expected_answers.md`. They are drafts, and E4 and E5 surface two gaps: there is no decision rule for a failed finalize_application, and no persona has a registry DOB mismatch. (3) SOP §6.4 lists every seeded defect with the checks that catch it, which is the answer key; withhold that section from the testers or move it to the answer key. (4) The D22 dry run and the M4 assessment with T1 and T2 (live runs, budget to be set). The modules follow the README's M1–M7, which fold SOP §6.2's LLM-as-judge module into M5 and split running from triage (M5, M7).

Not started: WP11 onwards (WP7 waits on pricing, one judged run and tester labels).

## 3. Calendar overview

| Week | Days | Dates | Focus | Milestone |
|---|---|---|---|---|
| 1 | D2–D7 | 23–28 Oct | Scaffold, mocks, KYC multi-agent system, trajectory schema | **M1 (D7, Wed 28 Oct):** the 10 golden cases run end to end with trajectories captured |
| 2 | D8–D14 | 29 Oct–4 Nov | Adapters, all deterministic evaluators, per-agent scorecards, gates; case YAML import | **M2 (D14, Wed 4 Nov):** S1 suite green on the reference build; evaluator unit tests pass |
| 3 | D15–D21 | 5–11 Nov | Judges and calibration (testers label traces), remaining cases, reports and CI | **M3 (D21, Wed 11 Nov):** calibration report; CI red on a failing named rule |
| 4 | D22–D28 | 12–18 Nov | Training and bug-hunt lab, replication demo, documentation | **M4 (D27, Tue 17 Nov):** both testers catch ≥ 5 of 6 seeded defects |
| 5 | D28–D30 | 18–20 Nov | Buffer: fixes, full regression, audit pack, handover | **M5 (D30, Fri 20 Nov):** sign-off |

Diwali falls on D18 (Sun 8 Nov). Nothing is planned for D18, and no tester work is planned for D17–D18.

## 4. Critical path

```
WP1 scaffold ─► WP2 tool specs + mocks ─► WP3 KYC system ─► M1 ─► WP4 adapters ─► WP5 evaluators + gates ─► M2
                                                                       │                    │
                                                    WP6 case YAML ─────┘                    ├─► WP7 judges ─► M3
                                                                                            ├─► WP8 reports + CI
                                                                                            └─► WP10 lab ─► M4 ─► M5
WP9 docs runs alongside everything · WP11 replication needs WP4 + WP5 only
```

The KYC system (WP3) feeding the evaluators (WP5) is the critical path. If M1 slips past D8, apply the de-scope ladder (§10) immediately.

## 5. Work packages

Each work package lists the files it codes (paths match `README.md`), how it is proved, and who owns it.

### WP1: Scaffold and environment · D2–D3 (23–24 Oct) · QE Lead

- **Tasks:**
  1. Install uv and run `uv lock` from `requirements.txt`; pin exact versions; download the spaCy model.
  2. Write `pyproject.toml`, the `Makefile` targets, `.env.example`, `.gitignore`, pre-commit, `CLAUDE.md` and `prompts/claude_code/README.md`.
  3. Write `configs/eval.yaml`: models per role, temperature 0, run modes, k = 3 for S1 cases, AS_OF = 2026-11-02, seed 42, budget alerts at 50% and 80%.
  4. Write `evalkit/cli.py` and `evalkit/config/loader.py`.
  5. Add a CI skeleton with a dummy test.
  6. Make `make data` rebuild the DB with `--background-from` and run `check_fixtures.py`.
- **Files:** `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml`, `CLAUDE.md`, `configs/eval.yaml`, `evalkit/__init__.py`, `evalkit/cli.py`, `evalkit/config/*`, `tests/conftest.py`, `tests/unit/test_config_loader.py`, `runs/.gitkeep`.
- **Exit check:** `make data` prints "✓ fixture data is consistent"; `make smoke` runs the dummy test in CI.
- **Blocked by:** an Anthropic API key with a spending limit, written approval to send synthetic-only data to the API, and a CI host with a secret store (§11).

### WP2: Tool specs and mocks · D3–D5 (24–26 Oct) · QE Lead (Claude Code drafts, QE Lead reviews)

- **Tasks:**
  1. Write 14 JSON specs: 13 tools plus the hand-offs, with `additionalProperties: false`. The `compute_risk_score` spec has no protected-attribute fields.
  2. Write the mocks exactly per `data/README.md`, the mock tool data contract.
  3. Wrap each tool in `tools/registry.py` with audit logging into `audit_events`; the fault hook is added in WP4.
- **Files:** `projects/kyc_onboarding/tools/specs/*.json`, `tools/mocks/*.py`, `tools/registry.py`, `tests/unit/test_mocks.py`.
- **Exit check:** every mock returns the documented result for its fixture rows, and every fault mode FP-01 … FP-12 and override MO-02 / 04 / 05 is reproduced in `test_mocks.py`.

### WP3: KYC multi-agent system · D4–D7 (25–28 Oct) · QE Lead

- **Tasks:**
  1. Define the state model with one slice per agent.
  2. Write the output contracts.
  3. Build the Supervisor router as a structured output.
  4. Build the 4 ReAct specialists.
  5. Add the approval interrupt, the corporate stub and the model factory.
  6. Write the 5 prompts, which are versioned and hashed.
  7. Freeze the agent scope on D7.
- **Files:** `projects/kyc_onboarding/contracts.py`, `sut/state.py`, `sut/llm.py`, `sut/router.py`, `sut/graph.py`, `sut/approval.py`, `sut/corporate_stub.py`, `sut/agents/*.py`, `sut/prompts/*.md`, `tests/integration/test_smoke_golden.py`.
- **Order:**
  1. Build the graph with stubbed nodes.
  2. Add the Supervisor with all specialists stubbed, so it can be tested at L2 from day one.
  3. Add the specialists one at a time: DOC → IDV → SCR → RSK. Each is tried alone (L1) before it is wired in.
  4. Add the approval interrupt.
- **Exit check (M1):** the 10 golden cases (KYC-GLD-001 … 011) complete end to end, and the end states match the catalogue on a manual check.

### WP4: Trajectory schema, adapters and harness · D6–D9 (27–30 Oct) · QE Lead

- **Tasks:**
  1. Write the canonical Pydantic Trajectory, with per-agent slicing helpers.
  2. Write the LangGraph adapter: callbacks plus the end state read from SQLite.
  3. Write the OTel adapter.
  4. Build the harness: per-trial DB sandbox, clock, fault hook, scripted user, mock approver, runner (k trials, run modes, xdist).
  5. Record 3 runs for the parity test.
  6. Write `project.yaml` and `agents.yaml` for KYC.
- **Files:** `evalkit/schema/*`, `evalkit/adapters/*`, `evalkit/harness/runner.py, sandbox.py, clock.py, fault_hook.py, scripted_user.py, mock_approver.py`, `projects/kyc_onboarding/project.yaml`, `agents.yaml`, `recorded_runs/`, plus the tests `test_trajectory_schema.py`, `test_fault_hook.py` and `test_adapter_parity.py`.
- **Exit check:** both adapters give identical trajectories on the 3 recordings, apart from timestamps; `make eval CASE=KYC-FLT-021` shows `fault_injected` on every faulted call.

### WP5: Deterministic evaluators, per-agent scorecards and gates · D8–D14 (29 Oct–4 Nov) · QE Lead

- **Tasks, in priority order** (S1 evaluators first, so M2 is safe even if S2 / S3 slip):
  1. Write `policies/kyc_individual_v1.yaml` and `pii_masking.yaml` by hand from catalogue › Rules & Decisions. Every rule ID in the catalogue must appear.
  2. Build the policy engine: TR-3, TR-4, BF-2, TU-7, SLICE-1, VER-1.
  3. Build the S1 checks:
     - **Trajectory and tool use:** TR-1 end state, TU-4 grounding, TU-5 fault handling, TU-6 reconciliation.
     - **BFSI:** BF-1 PII, BF-3 injection twins, BF-5 fairness, BF-6 audit.
     - **Per agent:** AG-5 guardrails per agent.
  4. Build the S2 / S3 checks:
     - **Trajectory:** TR-2 match modes, TR-5 hand-offs, TR-6 efficiency, TR-7 pass^k.
     - **Tool use:** TU-1 selection, TU-2 / TU-3 arguments.
     - **BFSI:** BF-4 disclosure.
     - **Per agent:** the AG-1, AG-2, AG-3, AG-4 and AG-6 checks.
  5. Build the agent slicer, so that every L3 run yields 5 agent scorecards.
  6. Build scoring: the composite with the §5.3 weights and the gate multiplier G, the aggregation per agent / pattern / suite, and `configs/gates.yaml`.
  7. For each check, hand-make one good and one bad trajectory fixture.
- **Files:** `evalkit/evaluators/**` (except judges), `evalkit/config/registry.py`, `evalkit/scoring/*`, `configs/gates.yaml`, `configs/pii_recognizers.yaml`, `projects/kyc_onboarding/policies/*.yaml`, `tests/unit/evaluators/*`, `tests/unit/test_gates.py`, `tests/fixtures/**`.
- **Exit check (M2):** every evaluator passes its good fixture and fails its bad one; PII recall ≥ 95% on `pii_labelled.jsonl`; `make gate` (70 S1 cases × 3 trials) is green on the reference build, or every failure is triaged into an agent defect and fixed.

### WP6: Test suite as YAML · D9–D21 (30 Oct–11 Nov) · QE Lead, then the testers from D15

- **Tasks:**
  1. Build `catalogue_import.py` (workbook → 110 YAML files), `loader.py`, `lint.py` (plain-English errors) and `coverage.py`.
  2. Write the 11 reference trajectories RT-01 … RT-11 as JSON.
  3. Write the dataset README for testers.
  4. From D15, testers add cases only through YAML plus `make lint-cases`.
- **Files:** `evalkit/datasets/*`, `projects/kyc_onboarding/datasets/**`, `reference_trajectories/RT-*.json`, `tests/unit/test_case_lint.py`.
- **Exit check:** `make cases` reproduces all 110 catalogue rows; the coverage matrix equals the catalogue's (E2E 15 · SUP 34 · DOC 17 · IDV 11 · SCR 15 · RSK 18); lint catches every mistake class in its test.

### WP7: LLM judges and calibration · D15–D21 (5–11 Nov) · QE Lead with T1 and T2 (~3 h each)

- **Tasks:**
  1. Wire up DeepEval TaskCompletion, StepEfficiency and PlanAdherence over the Trajectory; Week 1 must first check that DeepEval accepts a pre-built trace.
  2. Add one G-Eval rubric (0–3 anchors) for customer explanations.
  3. Use claude-opus-5-5 as the judge model, with pricing metadata in `configs/judges.yaml`.
  4. Add a result cache.
  5. The testers label 30 traces each on D16, D17, D19 and D20 (Diwali-safe).
  6. The calibration script reports agreement and Cohen's κ.
- **Files:** `evalkit/evaluators/judges/*`, `configs/judges.yaml`, `tests/unit/evaluators/test_judges.py`.
- **Exit check (M3):** a calibration report exists. Judges either gate (κ ≥ 0.6, agreement ≥ 85%) or are documented as advisory.

### WP8: Reports, cost and CI · D19–D22 (9–12 Nov) · QE Lead

- **Tasks:**
  1. Write `results.jsonl` (one row per case × trial × check, with the evidence step) and `junit.xml` (one test per case and check).
  2. Build `report.html`: verdict, gate table, **per-agent scorecards**, and a trajectory timeline with the failing step highlighted. PII is redacted first.
  3. Write `cost.json` with budget alerts.
  4. Set up CI: smoke on push, gate on PR, full nightly.
- **Files:** `evalkit/reporting/**`, `evalkit/harness/cost.py`, `.github/workflows/eval.yml`, `tests/unit/test_reporting.py`.
- **Exit check:** on a seeded defect, CI turns red and names the failing rule (for example `KYC-GLD-001 · TR-3 (R1)`), and the HTML report contains no unmasked identifier.

### WP9: SOP v1.0 and framework docs · D5–D27, written alongside the build · QE Lead

- **Tasks:**
  1. Update the SOP from v0.3 to v1.0 wherever the build differs.
  2. Write the architecture, setup, config reference, extension guide, tester guide and glossary.
  3. Write the methodology extracts (metrics catalogue, rubrics, taxonomy, defect taxonomy, audit pack).
  4. Write `regulatory_mapping.yaml` and the project README.
- **Files:** `docs/*.md`, `docs/methodology/*.md`, `projects/kyc_onboarding/README.md`, `projects/kyc_onboarding/policies/regulatory_mapping.yaml`.
- **Exit check:** a tester runs one full cycle (lint → gate → triage → defect report) from the SOP and `docs/tester_guide.md` without help.

### WP10: Training and bug-hunt lab · D22–D27 (12–17 Nov) · QE Lead with T1 and T2 (~15 h each)

- **Tasks:**
  1. Write the LAB-1 … LAB-6 switches, enabled by `training/lab/variants/*.yaml`.
  2. Write 7 modules and 6 exercises with expected answers.
  3. Write the answer key (restricted), the assessment and the scoring sheet.
  4. Do a dry run on D22.
- **Files:** `projects/kyc_onboarding/sut/lab/*`, `training/**`, `tests/lab/test_seeded_defects.py`.
- **Exit check (M4):** `test_seeded_defects.py` proves that every variant fails ≥ 1 S1 or S2 check in its listed cases (catalogue › Lab Mapping), and both testers catch ≥ 5 of 6 and write 10 valid cases each.

### WP11: Replication demo · D25–D27 (15–17 Nov) · QE Lead

- **Tasks:**
  1. Build a two-tool account-statement bot.
  2. Write its `project.yaml`, `agents.yaml`, policy (a consent gate on `send_statement`) and 10 cases.
  3. Fill in `projects/_template/` from the experience.
- **Files:** `projects/demo_second/**`, `projects/_template/**`.
- **Exit check:** `make gate PROJECT=demo_second` runs; `git diff --stat evalkit/` is empty across the whole package.

### Buffer · D28–D30 (18–20 Nov)

1. Fix the remaining defects and run a full regression with judges on.
2. Build the audit pack: configuration, versions, results, reports, waivers, and the 'unvalidated' statement for S1.
3. Hand over and get sign-off (M5).

## 6. Per-agent evaluation build-up

Every agent goes through the same three steps.

1. **L1 alone:** fixed task, mocked tools, AG-1 … AG-6.
2. **Integration:**
   - For the four specialists, the agent is wired into the graph and the L2 hand-off cases are run. This is the **L2 in context** step.
   - For the Supervisor, its L2 hand-off cases with stubbed specialists are its *main* integration test, and they run first (from D7).
3. **L3:** the agent's slice of every end-to-end run is scored again, so a regression is pinned to the agent that caused it.

| Agent | L1 cases (examples) | Guardrail checked (AG-5) | Evaluators that must exist first | L1 green by |
|---|---|---|---|---|
| DOC | AGT-DOC-046 … 049, 106, 107; EDG-017; FLT-100, 102; ADV-033; PII-042, 044 | Aadhaar masked; no instruction followed; nothing guessed | `agent/*`, `bfsi/pii.py`, `bfsi/injection.py`, `tooluse/grounding.py` | D11 |
| IDV | AGT-IDV-050, 051; FLT-021, 023, 024 | Mismatch never upgraded; ≤ 2 retries; never VALID under faults | `agent/*`, `tooluse/error_handling.py`, `tooluse/grounding.py` | D11 |
| SCR | AGT-SCR-007, 055, 056, 057; EDG-019; FLT-025, 027 | No hit cleared; near-matches reported; UNSCREENED on failure | `agent/*`, `tooluse/error_handling.py` | D12 |
| RSK | AGT-RSK-052 … 054, 105; FLT-028, 029 | Score and tier equal the engine; pinned v3 (VER-1); no protected attribute in arguments | `agent/*`, `tooluse/reconciliation.py`, `bfsi/fairness.py` | D12 |
| SUP | AGT-SUP-058, 059, 110; L2 HND-066 … 070, 109 | No record without a token; any hit → EDD; fail closed when screening is unavailable | `policy_engine.py`, `trajectory/handoff.py`, `agent/contract.py` | D13 |

`report.html` shows one scorecard per agent (AG-1 … AG-6 plus its S1 checks), so the release decision can name which agent blocks it.

## 7. Day-by-day schedule

| Day | Date | QE Lead | Testers |
|---|---|---|---|
| D2 | Fri 23 Oct | WP1: uv lock, pyproject, Makefile, eval.yaml; request API key, data-sending approval, CI secrets | — |
| D3 | Sat 24 Oct | WP1 done (CI dummy green); WP2: 14 tool specs | — |
| D4 | Sun 25 Oct | WP2 mocks (document, identity, screening); WP3: state, contracts, graph with stubbed nodes | — |
| D5 | Mon 26 Oct | WP2 mocks (risk, supervisor, hand-off) and `test_mocks.py`; WP3 Supervisor router; WP9 starts | — |
| D6 | Tue 27 Oct | WP3 specialists DOC, IDV with prompts; WP4 schema; QE-Lead review of policy rules | — |
| D7 | Wed 28 Oct | WP3 SCR, RSK, approval interrupt, corporate stub; **M1** golden run; agent scope frozen | — |
| D8 | Thu 29 Oct | WP4 LangGraph adapter, sandbox, clock, fault hook; WP5 policy YAML (human-written) | — |
| D9 | Fri 30 Oct | WP4 scripted user, approver, runner, OTel adapter, parity test; WP6 catalogue import | — |
| D10 | Sat 31 Oct | WP5 policy engine, TR-1, TU-4, TU-5 with fixtures | — |
| D11 | Sun 1 Nov | WP5 TU-6, BF-1 (Presidio), agent slicer, AG-1 … AG-6 → DOC and IDV L1 green | — |
| D12 | Mon 2 Nov | WP5 BF-3, BF-5, BF-6 → SCR and RSK L1 green | — |
| D13 | Tue 3 Nov | WP5 TR-2, TR-5, TR-6, TR-7, TU-1 … TU-3, BF-4, scoring, gates → SUP L1 and L2 green; QE-Lead review of S1 expectations | — |
| D14 | Wed 4 Nov | **M2** `make gate` green; triage; WP6 lint and coverage | — |
| D15 | Thu 5 Nov | WP7 DeepEval wiring; WP6 RT-01 … RT-11; onboarding for testers | Setup, M1 module, first `make smoke` |
| D16 | Fri 6 Nov | WP7 rubric and cache | Label 15 traces each |
| D17 | Sat 7 Nov | WP7 calibration script; WP6 remaining fixes | — |
| D18 | Sun 8 Nov | **Diwali — no work planned** | — |
| D19 | Mon 9 Nov | WP8 JSONL, JUnit, cost | Label 15 traces each |
| D20 | Tue 10 Nov | WP8 HTML report with per-agent scorecards | Write 5 cases each in YAML |
| D21 | Wed 11 Nov | **M3** calibration report; WP8 CI workflow red/green demo | Write 5 more cases each |
| D22 | Thu 12 Nov | WP10 lab switches, modules M2–M4; dry run | Modules M2–M3, E1–E2 |
| D23 | Fri 13 Nov | WP10 exercises, answer key | Modules M4–M5, E3–E4 |
| D24 | Sat 14 Nov | WP9 docs (setup, config reference, tester guide) | — |
| D25 | Sun 15 Nov | WP11 demo bot and config | — |
| D26 | Mon 16 Nov | WP11 demo cases; `_template` | Modules M6–M7, E5–E6 |
| D27 | Tue 17 Nov | **M4** bug-hunt assessment; WP9 SOP v1.0 draft | Bug hunt (LAB-1 … LAB-6) and assessment |
| D28 | Wed 18 Nov | Buffer: defect fixes, full regression | Re-run of failed lab items if needed |
| D29 | Thu 19 Nov | Buffer: audit pack, final docs | — |
| D30 | Fri 20 Nov | **M5** sign-off and handover | — |

The QE Lead works weekends in this plan, since the window is 30 calendar days. If weekends are not worked, apply de-scope steps 1–3 now.

## 8. Run budget and determinism

- Temperature is 0 and models are pinned per role. Prompt hashes, package versions, seed 42, AS_OF 2026-11-02, lists version SYN-2026-10 and policy v3 are recorded in every RunMeta.
- **Run volume:**
  - smoke: 10 runs
  - gate: 70 S1 cases × 3 = 210 runs
  - full: 110 cases with k = 3 for S1 cases = 250 runs, plus judges
- Specialists use claude-haiku-5-5 and prompt caching is on. Judges are off in smoke and gate runs, and their results are cached by trajectory hash.
- `cost.json` from the first real run (D7) sets the actual budget, and the alerts fire at 50% and 80%. Check current per-token prices before fixing the budget figure in `eval.yaml`.
- A flake report is produced for every run. If more than 10% of cases flip between identical runs, the evaluation cycle is suspended (SOP §3.5).

## 9. Ownership

| Work | Owner | Never delegated to Claude Code |
|---|---|---|
| Policy YAML, S1 expectations, gate thresholds, lab answer key | QE Lead | ✔ |
| Scaffolding, mocks, evaluators, reports, unit tests | QE Lead with Claude Code (test-first; every diff reviewed) | — |
| Case YAML from D15, trace labels, lab | Testers (YAML and command line) | — |
| Release sign-off | Named approver (to be confirmed) | ✔ |

## 10. De-scope ladder

If the plan slips, apply these steps in order. S1 gates are never cut.

1. Use scripted users only (already the default) and drop the LLM-simulated customer idea.
2. Prove the OTel adapter on recordings only (already the default).
3. Cut the dataset from 110 to ~80 cases. Keep all 70 S1 cases and drop paraphrases and S2 / S3 extras first.
4. Leave the judges advisory and skip their calibration if WP5 slips past D16.
5. Reduce the replication demo to configuration plus 5 cases.
6. Shorten training to modules M3, M5, M6 and the lab.

Early warnings: M1 not met by D8 · more than 50% of the budget used by D14 · 429 rate-limit errors · exercise E1 taking more than twice its planned time.

## 11. Needed before coding starts (D2–D3)

| Item | Needed by | If late |
|---|---|---|
| Anthropic API key with a spending limit; rate-limit tier known | D3 | Only deterministic unit tests progress |
| Written approval that synthetic-only fixtures may be sent to the API | D3 | All LLM runs blocked |
| CI host with a secret store and nightly jobs allowed | D19 | Gate runs locally, reports attached by hand |
| Named release approver | D28 | Handover without formal sign-off |
| Testers' calendars confirmed for D15–D28 (~18 h each) | D14 | Calibration and training move into the buffer |

## 12. Scope reductions carried from requirements v0.3

The MVP does not cover:

- Applicants under 18.
- DPDP consent withdrawal or erasure.
- Corporate onboarding beyond a routing stub.
- Non-English documents or OCR model training.
- Performance and load testing.
- Production monitoring.
- Real vendors, documents or customer data.

There is no compliance SME, so every S1 rule and result is reported as *unvalidated*.
