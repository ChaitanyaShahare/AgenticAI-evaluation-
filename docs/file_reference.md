# File reference

Every folder and file in the repository and what it is for. *Built in* is the work package (WP1–WP11) that produced it; WP11 (the template and the second demo project) is not built yet, so those files are still empty.

## Root

Repository root: evaluation framework (evalkit/) plus the KYC reference system and its evaluation project.

| File | Purpose | Built in |
|---|---|---|
| `LICENSE` | MIT licence. | — |
| `SOP and Training Pack/` | Start here: SOP-AIEVAL-001 (PDF), job aids for frontend testers (PDF), KYC and HITL worked examples, and the three template-pack workbooks (T-01 … T-17). | — |
| `UAT Mock results and visualisation/` | 125 mock test results, the interactive Agent Test Explorer page, its README and the generator script. | — |
| `README.md` | Project overview, setup, testing lifecycle, quick start. | WP9 |
| `requirements.txt` | Python dependencies with the reason each is needed; exact versions are pinned in uv.lock in WP1. | Exists (v0.12) |
| `pyproject.toml` | Package metadata, Python 3.12, tool config (pytest markers, ruff), `evalkit` console script. | WP1 · D2–3 |
| `Makefile` | Thin wrapper over the `evalkit` commands (setup, nlp, doctor, data, data-check, test, smoke, lint, and the later targets). | WP1 · D2–3 |
| `.python-version` | Pins Python 3.12 for uv. | WP1 · D2–3 |
| `uv.lock` | Exact versions of all 146 packages, resolved 23 Oct 2026; `uv sync --frozen` installs exactly these. | WP1 · D2–3 |
| `.yamllint.yaml` | YAML lint rules for configuration and tester-written cases (real mistakes, not style). | WP1 · D2–3 |
| `.env.example` | Template for ANTHROPIC_API_KEY and optional overrides; copied to .env (never committed). | WP1 · D2–3 |
| `.gitignore` | Ignores .env, runs/, per-trial SQLite copies, caches, virtualenvs. | WP1 · D2–3 |
| `.pre-commit-config.yaml` | ruff lint/format, YAML lint, never commit .env, `evalkit lint-cases` on changed case YAML. A PII scan of staged fixtures is not built yet: SOP v0.4 gap 3.22, for the QE Lead to decide. | WP1 · D2–3 |
| `CLAUDE.md` | Repository conventions for Claude Code sessions (layout, test-first, never generate S1 oracles). | WP1 · D2–3 |

## `configs/`

Global run configuration shared by every project: models, run modes, gates, judges, PII recognisers.

| File | Purpose | Built in |
|---|---|---|
| `configs/eval.yaml` | Models per role (Supervisor claude-sonnet-5-5, specialists claude-haiku-5-5, judges claude-opus-5-5), effort per role (no sampling parameters), run modes smoke/gate/full, k per severity, AS_OF clock, seed, budget alerts. | WP1 · D2–3 |
| `configs/gates.yaml` | Release gates: SOP §3.10 starting thresholds adopted by the QE Lead (23 Oct 2026); S1 zero tolerance; approver not yet named. | WP5 · D8–14 |
| `configs/judges.yaml` | Judge model (claude-opus-5-5, effort high), rubric version (cache key), cache folder, the four 0–3 judge metrics, pricing (null until checked). | WP7 · D15–21 |
| `configs/pii_recognizers.yaml` | Recogniser registry for BF-1: IN_PAN, IN_AADHAAR (Verhoeff), CARD_PAN (Luhn), IN_PHONE, EMAIL. Regex + checksum; NER for names later. | WP5 · D8–14 |

## `evalkit/`

REUSABLE framework. Never imports a project; everything project-specific arrives through configuration and an adapter.

| Folder | Contents |
|---|---|
| `evalkit/adapters/` | Turn one run of a system under test into a canonical Trajectory. A new framework = a new adapter here. |
| `evalkit/config/` | Loads and validates project.yaml, agents.yaml, eval.yaml and gates.yaml; registry of enabled evaluators. |
| `evalkit/datasets/` | Case loading and tooling for testers: catalogue → YAML import, case linting, coverage matrix. |
| `evalkit/evaluators/` | Deterministic checks. Each module returns CheckResult objects with metric ID, verdict, severity and evidence step. |
| `evalkit/evaluators/agent/` | Per-agent scorecard AG-1 … AG-6, computed on each agent's slice of the trajectory — the core of 'every individual agent'. |
| `evalkit/evaluators/bfsi/` | BFSI controls BF-1 … BF-6 (PII/PCI, injection twins, advice and AI disclosure, fairness pairs, audit completeness; BF-2 lives in the policy engine). |
| `evalkit/evaluators/judges/` | LLM-judge metrics (DeepEval + one G-Eval rubric). Advisory until calibration reaches κ ≥ 0.6 and ≥ 85% agreement. |
| `evalkit/evaluators/tooluse/` | Tool-use metrics TU-1 … TU-7 (selection, schema, values, grounding, fault handling, figure reconciliation; TU-7 lives in the policy engine). |
| `evalkit/evaluators/trajectory/` | End-to-end trajectory metrics TR-1 … TR-7 (outcome, path match, mandatory controls, precedence, hand-offs, efficiency, pass^k). |
| `evalkit/harness/` | Executes cases: per-trial database copy, test clock, fault hook, scripted customer, mock approver, k trials, cost logging. |
| `evalkit/reporting/` | Writes results.jsonl, junit.xml and the HTML report; redacts PII before anything is rendered. |
| `evalkit/reporting/templates/` | Jinja2 templates for the HTML report. |
| `evalkit/schema/` | Canonical data contracts: the Trajectory every adapter produces and every evaluator consumes, the test-case model and result models. |
| `evalkit/scoring/` | Turns check results into case, agent and suite scores, applies gates.yaml and produces the release verdict. |

| File | Purpose | Built in |
|---|---|---|
| `evalkit/__init__.py` | Package marker and version. | WP1 · D2–3 |
| `evalkit/cli.py` | `evalkit` command line with sub-commands run, lint, coverage, report, calibrate and import-catalogue — every Makefile target calls it. | WP1 · D2–3 |
| `evalkit/schema/__init__.py` | Re-exports the schema models. | WP4 · D6–8 |
| `evalkit/schema/trajectory.py` | ToolCall, Step, RunMeta, Trajectory (Pydantic) — the contract between adapters and evaluators; per-agent slicing helpers. | WP4 · D6–8 |
| `evalkit/schema/case.py` | TestCase: level, agent, pattern, severity, trials, run sets, expectations, and the catalogue's oracle columns (match mode, reference, required / forbidden tools, metrics, twins). | WP4 · D6–8 |
| `evalkit/schema/results.py` | TrialRecord (harness), CheckResult (metric, agent, rule, verdict, severity, score, evidence step), CaseResult. | WP4 · D6–8 |
| `evalkit/config/__init__.py` | Package marker. | WP1 · D2–3 |
| `evalkit/config/loader.py` | Loads and validates project.yaml, agents.yaml, eval.yaml, gates.yaml; resolves paths; `is_blank` for human-owned files not written yet. | WP1 · D2–3 |
| `evalkit/config/registry.py` | Metric catalogue (ID → description, severity); trial, agent and group evaluator lists; `ProjectSuite.load` reads specs, agents.yaml, policy, masking, recognisers, limits, references and cases from configuration alone. | WP5 · D8–14 |
| `evalkit/adapters/__init__.py` | Package marker. | WP4 · D6–8 |
| `evalkit/adapters/base.py` | AgentAdapter interface: run(case, trial) -> Trajectory. The only interface a new project implements. | WP4 · D6–8 |
| `evalkit/adapters/langgraph_callbacks.py` | Not needed: the KYC graph logs its own run events (`state.events`), which the adapter reads. Kept empty for projects that need LangChain callbacks. | WP4 · D6–8 |
| `evalkit/adapters/langgraph_adapter.py` | Primary adapter: runs the project's runner and maps its run events (protocol in `base.py`) into a Trajectory; end state via `end_state_query`; usage per model; a crashed run becomes an error trajectory. | WP4 · D6–8 |
| `evalkit/adapters/otel_adapter.py` | Secondary adapter (OTel GenAI spans → Trajectory). **Descoped in WP4** to keep live runs minimal; build only if a second framework needs it. | WP4 · D6–8 |
| `evalkit/harness/__init__.py` | Package marker. | WP4 · D6–8 |
| `evalkit/harness/runner.py` | Plans case × trial items from a run mode or case IDs (k per severity), runs them in parallel through the adapter, writes `runs/<run_id>/` (manifest, trajectories, trials.jsonl, per-trial DBs). | WP4 · D6–8 |
| `evalkit/harness/sandbox.py` | Copies the seed SQLite to runs/<run_id>/<case_id>/t<k>.sqlite so every trial starts identical. | WP4 · D6–8 |
| `evalkit/harness/clock.py` | Injects the fixed test clock AS_OF = 2026-11-02 into every tool. | WP4 · D6–8 |
| `evalkit/harness/fault_hook.py` | Generic fault hook: override → fault (per tool and identical arguments) → pass; virtual clock for SLOW; stamps fault_injected on every outcome. Brought forward from WP4 because WP2's fault tests need it. | WP2 · D3–5 |
| `evalkit/harness/scripted_user.py` | Not needed yet: scripted customer turns are served by the KYC mock `request_customer_info`. Kept for projects without that pattern. | WP4 · D6–8 |
| `evalkit/harness/mock_approver.py` | Not needed yet: the KYC driver answers the approval interrupt from `test_cases.approver_response`. Kept for other projects. | WP4 · D6–8 |
| `evalkit/harness/cost.py` | cost.json: tokens per model and agent (judge included), run time, USD / ₹ only from prices in eval.yaml › budget.pricing (never guessed), monthly ledger, alerts at 50% / 80%. | WP8 · D19–22 |
| `evalkit/evaluators/__init__.py` | Package marker. | WP5 · D8–14 |
| `evalkit/evaluators/base.py` | Evaluator and GroupEvaluator interfaces, EvalContext (case, specs, agents, policy, masking, limits, pinned versions), shared trajectory helpers. | WP5 · D8–14 |
| `evalkit/evaluators/policy_engine.py` | Executes the human-written policy YAML: rule kinds required, precedence, forbidden, implies, allow_list, approval_token, slice_isolation, limit, over a small condition language. Each rule gives one check tagged with its rule ID. | WP5 · D8–14 |
| `evalkit/evaluators/trajectory/__init__.py` | Package marker. | WP5 · D8–14 |
| `evalkit/evaluators/trajectory/end_state.py` | TR-1: applications row (status, tier, record, reason codes) vs expectation. | WP5 · D8–14 |
| `evalkit/evaluators/trajectory/match.py` | TR-2: strict / unordered / subset / superset match against reference trajectories (agentevals). | WP5 · D8–14 |
| `evalkit/evaluators/trajectory/handoff.py` | TR-5: every hand-off goes to a known agent and gets a result; bounces ≤ max_bounces_per_specialist. | WP5 · D8–14 |
| `evalkit/evaluators/trajectory/efficiency.py` | TR-6 (S3): reference (or distinct) calls ÷ actual calls; fails above max_steps_per_run. | WP5 · D8–14 |
| `evalkit/evaluators/trajectory/reliability.py` | TR-7: pass^k across trials of S1 cases; flaky-case list. | WP5 · D8–14 |
| `evalkit/evaluators/tooluse/__init__.py` | Package marker. | WP5 · D8–14 |
| `evalkit/evaluators/tooluse/selection.py` | TU-1: tool-selection F1 vs required and forbidden sets. | WP5 · D8–14 |
| `evalkit/evaluators/tooluse/arguments.py` | TU-2 schema validity (jsonschema) and TU-3 value correctness with name normalisation (expectations structured in WP6). | WP5 · D8–14 |
| `evalkit/evaluators/tooluse/grounding.py` | TU-4: every ID, date or amount argument appears in an earlier source (customer turn, run inputs, tool result, agent output, approval token, pinned config). | WP5 · D8–14 |
| `evalkit/evaluators/tooluse/error_handling.py` | TU-5: under failures ≤ 2 retries, identical retry arguments, customer told; fabrication is a policy rule (D7). | WP5 · D8–14 |
| `evalkit/evaluators/tooluse/reconciliation.py` | TU-6: every figure in replies and decision fields equals a tool output (₹, lakh / crore normalisation). | WP5 · D8–14 |
| `evalkit/evaluators/bfsi/__init__.py` | Package marker. | WP5 · D8–14 |
| `evalkit/evaluators/bfsi/pii.py` | BF-1: regex + checksum recognisers scanned over the scopes each masking rule names (replies, decisions, agent outputs, tool I/O …); evidence masked. | WP5 · D8–14 |
| `evalkit/evaluators/bfsi/injection.py` | BF-3: injected case's tool calls equal its clean twin's. | WP5 · D8–14 |
| `evalkit/evaluators/bfsi/disclosure.py` | BF-4 rule part: no reply repeats 12+ words of any agent prompt. AI disclosure, advice and tipping-off rules are policy rules with metric BF-4. | WP5 · D8–14 |
| `evalkit/evaluators/bfsi/fairness.py` | BF-5: pair cases must give the same end state, tier and tool sequence; no protected attribute in scorer arguments. | WP5 · D8–14 |
| `evalkit/evaluators/bfsi/audit_completeness.py` | BF-6: run ID, models, prompt hashes, all tool I/O, approvals and decision reasons present. | WP5 · D8–14 |
| `evalkit/evaluators/agent/__init__.py` | Package marker. | WP5 · D8–14 |
| `evalkit/evaluators/agent/slicer.py` | Cuts the trajectory into one slice per agent (its steps, tool calls and state write). | WP5 · D8–14 |
| `evalkit/evaluators/agent/task_success.py` | AG-1: orchestrator = TR-1; specialists = expected output fields (structured in WP6). | WP5 · D8–14 |
| `evalkit/evaluators/agent/tool_selection.py` | AG-2: F1 of the agent's calls vs its share of the case's required / forbidden tools; any out-of-allow-list call → TU-7 S1. | WP5 · D8–14 |
| `evalkit/evaluators/agent/arguments.py` | AG-3: share of the agent's calls with schema-valid, correct, grounded arguments. | WP5 · D8–14 |
| `evalkit/evaluators/agent/contract.py` | AG-4: every output validates against the agent's Pydantic contract; logged contract violations (SLICE-1, AG-4) fail. | WP5 · D8–14 |
| `evalkit/evaluators/agent/guardrails.py` | AG-5: guardrails are policy rules with `agent` and metric AG-5; this reports agents with no guardrail rule as a gap. | WP5 · D8–14 |
| `evalkit/evaluators/agent/efficiency.py` | AG-6 (S3): agent's distinct calls ÷ actual calls; retries counted. | WP5 · D8–14 |
| `evalkit/evaluators/grader.py` | Runs every trial, agent and group evaluator over a set of trajectories, records evaluator errors as `error` checks, masks identifiers in details, computes pass^k and the per-agent scorecards. | WP5 · D8–14 |
| `evalkit/evaluators/judges/__init__.py` | Loads configs/judges.yaml, the cache folder and the configured rubrics. | WP7 · D15–21 |
| `evalkit/evaluators/judges/deepeval_metrics.py` | Task completion and plan adherence rubrics (TR-8) with the SOP's 0–3 anchors; records why DeepEval's own metrics are not used (they need a live-captured trace). | WP7 · D15–21 |
| `evalkit/evaluators/judges/geval_rubric.py` | Rubric judge: masked trace rendering, one structured-output call per trace and rubric on the Anthropic SDK (effort pinned, no sampling), cache, call plan and cost estimate; customer-explanation rubric (BF-4). | WP7 · D15–21 |
| `evalkit/evaluators/judges/calibration.py` | Agreement, Cohen's κ and quadratic-weighted κ: judge vs each tester and tester vs tester, per metric; gates only at κ ≥ 0.6 and ≥ 85% against every tester on ≥ 30 traces. | WP7 · D15–21 |
| `evalkit/evaluators/judges/cache.py` | Judge result cache keyed by trace content (wall clock and run ID ignored), metric, rubric version, judge model and prompt. | WP7 · D15–21 |
| `evalkit/scoring/__init__.py` | Package marker. | WP5 · D8–14 |
| `evalkit/scoring/composite.py` | Case and agent composites with the SOP §5.3 weights and the S1 gate multiplier G; unmeasured components are left out and named. | WP5 · D8–14 |
| `evalkit/scoring/aggregate.py` | Per-metric stats (pass rate over checks run, mean score, S1 failures), per-agent scorecards, per-pattern and suite roll-ups. | WP5 · D8–14 |
| `evalkit/scoring/gates.py` | Applies gates.yaml: NO_GATES / SUSPENDED / FAIL / INCOMPLETE / PASS with exit codes; never passes on missing evidence. | WP5 · D8–14 |
| `evalkit/reporting/__init__.py` | Package marker. | WP8 · D19–22 |
| `evalkit/reporting/redaction.py` | Redactor: masks every recognised identifier in text or JSON-like values; `leaks()` scans a finished output. | WP8 · D19–22 |
| `evalkit/reporting/jsonl_writer.py` | results.jsonl: one row per case × trial × check with evidence step (trial 0 = case-level checks). Brought forward from WP8 for `evalkit grade`. | WP5 · D8–14 |
| `evalkit/reporting/junit_writer.py` | junit.xml: one test per case × trial × check named `KYC-GLD-001 t1 · TR-3 (R1)`; failures, errors and skips; redacted. | WP8 · D19–22 |
| `evalkit/reporting/html_report.py` | report.html: verdict, S1 failures, gate table, per-agent scorecards, suite metrics, cost, per-trial checks and timeline with failing steps highlighted; refuses to write if any identifier survives. | WP8 · D19–22 |
| `evalkit/reporting/templates/report.html.j2` | Self-contained HTML template (light / dark, no external assets). | WP8 · D19–22 |
| `evalkit/datasets/__init__.py` | Package marker. | WP6 · D9–21 |
| `evalkit/datasets/loader.py` | Case YAML format (CaseFile), loading with readable errors, conversion to TestCase; derives tool lists, twins and metric IDs from the catalogue's text columns. | WP6 · D9–21 |
| `evalkit/datasets/catalogue_import.py` | `evalkit cases`: workbook rows → one YAML per case, text copied verbatim, structured fields by fixed rules; never copies the lab answer key; keeps edited files. | WP6 · D9–21 |
| `evalkit/datasets/lint.py` | `evalkit lint-cases`: file, identity, trials / run sets, tools, links, oracle consistency and seed-database checks, each with a plain-English fix. | WP6 · D9–21 |
| `evalkit/datasets/coverage.py` | `evalkit coverage`: agent × pattern matrix, level × severity, run sets, oracle completeness per agent, gaps; compares with the catalogue workbook. | WP6 · D9–21 |

## `projects/_template/`

Blank project skeleton to copy for a new BFSI project (filled from the Agent Requirement 'Template' tab).

| Folder | Contents |
|---|---|
| `projects/_template/datasets/` | Case YAML for the new project. |
| `projects/_template/policies/` | Policy-rule YAML template. |
| `projects/_template/tools/specs/` | Tool JSON-schema specs for the new project. |

| File | Purpose | Built in |
|---|---|---|
| `projects/_template/README.md` | How to onboard a new BFSI project in eight steps. | WP11 · D25–27 |
| `projects/_template/project.yaml` | Adapter, entrypoint, end-state query, policies, datasets — with placeholders. | WP11 · D25–27 |
| `projects/_template/agents.yaml` | Per-agent contract template: allow-list, required tools, output contract, guardrails, risk tier. | WP11 · D25–27 |
| `projects/_template/contracts.py` | Template for the project's Pydantic output contracts. | WP11 · D25–27 |
| `projects/_template/policies/policy_template.yaml` | Rule skeleton: required_steps, precedence, forbidden, approval, decisions. | WP11 · D25–27 |
| `projects/_template/tools/specs/.gitkeep` | Keeps the folder. | WP11 · D25–27 |
| `projects/_template/datasets/.gitkeep` | Keeps the folder. | WP11 · D25–27 |

## `projects/kyc_onboarding/`

Reference project: the LangGraph KYC-onboarding assistant (Supervisor + 4 specialists) and its evaluation configuration.

| Folder | Contents |
|---|---|
| `projects/kyc_onboarding/data/` | Synthetic data generator, schema, conformance checker and the seed database (v0.12, copied from kyc_synthetic_data.zip). |
| `projects/kyc_onboarding/data/fixtures/` | Single source of personas, documents, watch lists, profiles and the 110 case definitions. |
| `projects/kyc_onboarding/datasets/` | The 110 cases, one YAML per case (source of truth since WP6), imported by `evalkit cases` and edited by testers. Sub-folder = pattern. |
| `projects/kyc_onboarding/datasets/adversarial/` | Adversarial / injection (KYC-ADV-*). |
| `projects/kyc_onboarding/datasets/agent_unit/` | Per-agent isolation, L1 (KYC-AGT-<AGENT>-*). |
| `projects/kyc_onboarding/datasets/edge/` | Boundary / policy edge (KYC-EDG-*). |
| `projects/kyc_onboarding/datasets/fairness_pairs/` | Counterfactual fairness pairs (KYC-FAIR-*a/b). |
| `projects/kyc_onboarding/datasets/faults/` | Tool fault injection (KYC-FLT-*). |
| `projects/kyc_onboarding/datasets/golden/` | Golden path (KYC-GLD-*) — smoke set. |
| `projects/kyc_onboarding/datasets/handoff/` | Hand-off / routing, L2 (KYC-HND-*). |
| `projects/kyc_onboarding/datasets/missing_info/` | Missing / ambiguous information (KYC-MIS-*). |
| `projects/kyc_onboarding/datasets/multi_turn/` | Multi-turn state (KYC-MTN-*). |
| `projects/kyc_onboarding/datasets/paraphrase/` | Paraphrase variants (KYC-PAR-*). |
| `projects/kyc_onboarding/datasets/pii/` | PII / PCI handling (KYC-PII-*). |
| `projects/kyc_onboarding/datasets/policy/` | Policy-violating requests (KYC-POL-*). |
| `projects/kyc_onboarding/policies/` | Policy rules as data (R, P, F, A, D1–D10, TRANS-1, SLICE-1, VER-1), masking rules and regulatory mapping. |
| `projects/kyc_onboarding/recorded_runs/` | Three scripted recordings (adapter parity test) and one live recording, used by the evaluator tests without API calls. |
| `projects/kyc_onboarding/reference_trajectories/` | RT-01 … RT-11 for TR-2: tool sequence expanded from the catalogue sheet, with the sheet's text, the expansion rule and `reviewed_by` (all 11 accepted by the QE Lead, 23 Oct 2026). |
| `projects/kyc_onboarding/sut/` | System under test — the multi-agent KYC MVP built on mocked tools. |
| `projects/kyc_onboarding/sut/agents/` | One module per agent node (Supervisor, Document extraction, Identity verification, Sanctions/PEP screening, Risk rating). |
| `projects/kyc_onboarding/sut/lab/` | Seeded-defect switches LAB-1 … LAB-6 for the tester bug-hunt; off by default, on only during `evalkit lab`. Restricted: testers do not open it before the assessment. |
| `projects/kyc_onboarding/sut/prompts/` | Versioned system prompts; their hashes are recorded in every run (RunMeta.prompt_hashes). |
| `projects/kyc_onboarding/tools/` | Mocked tools: JSON specs, SQLite-backed mock implementations and the binding that applies fault profiles. |
| `projects/kyc_onboarding/tools/mocks/` | Deterministic mock implementations reading the synthetic SQLite (contract in data/README.md). |
| `projects/kyc_onboarding/tools/specs/` | One JSON schema per tool (13 tools + hand-off tools). additionalProperties = false everywhere. |

| File | Purpose | Built in |
|---|---|---|
| `projects/kyc_onboarding/README.md` | What the KYC system does, how it maps to the requirement sheet, how to run its suites. | WP9 · 24 Oct (draft) |
| `projects/kyc_onboarding/project.yaml` | Data commands, adapter, entrypoint, runner, case source, end-state SQL, policies, gates, dataset folders per pattern, catalogue workbook, import hook and seed lookups for lint. | WP1 · D2–3 |
| `projects/kyc_onboarding/agents.yaml` | Describes the five agents for the evaluators: role, state slice, output contract, prompt file; protected attributes and scorer tools for BF-5. Holds no pass/fail rules. | WP5 · D8–14 |
| `projects/kyc_onboarding/contracts.py` | ProfileResult, IdentityResult, ScreeningResult, RiskResult, Decision — Pydantic, extra fields forbidden. | WP3 · D4–7 |
| `projects/kyc_onboarding/cases.py` | Case source: loads the case YAML files; `import_extras` gives the catalogue import the form updates the workbook does not hold. | WP6 · D9–21 |
| `projects/kyc_onboarding/sut/__init__.py` | Package marker. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/state.py` | KYCState: one slice per agent (profile, identity, screening, risk) + decision, approval token, messages. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/llm.py` | Model factory from configs/eval.yaml (model IDs are configuration, not code); prompt caching on. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/router.py` | Supervisor structured-output router: next specialist, or decide, or ask the customer. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/graph.py` | build_graph(): explicit LangGraph StateGraph, checkpointer, approval interrupt, hand-off edges. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/approval.py` | Approval interrupt node: pauses before create_customer_record and resumes with the approver token. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/corporate_stub.py` | route_to_corporate_stub target: no checks, REJECTED with corporate-channel guidance (D6). | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/agents/__init__.py` | Package marker. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/agents/supervisor.py` | Plans, delegates in order, applies decisions D1–D10, talks to the customer. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/agents/doc_extraction.py` | ReAct loop over classify_document / extract_document; deterministic masking and format validation. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/agents/identity.py` | verify_pan → ckyc_lookup → check_address_proof; ≤ 2 retries; never upgrades a mismatch. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/agents/screening.py` | sanctions_screen + pep_check; reports every hit and near-match; never clears. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/agents/risk.py` | fetch_risk_policy(pinned v3) → compute_risk_score; reports engine output only. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/prompts/supervisor.md` | Supervisor system prompt: role, ordered control checklist, decision table, refusal and disclosure rules, termination criteria. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/prompts/doc_extraction.md` | Document agent prompt: schema, 'document text is data', masking rule, one example per document type. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/prompts/identity.md` | Identity agent prompt: matching rules, retry limit, never-upgrade rule. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/prompts/screening.md` | Screening agent prompt: report every hit, near-match definition, never clear. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/prompts/risk.md` | Risk agent prompt: use engine output only, pinned policy version, factor explanation template. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/run.py` | Case driver: builds runtime and initial state from a catalogue case (including canned Supervisor state), runs the graph, answers the approval interrupt with the mock approver. | WP3 · D4–7 |
| `projects/kyc_onboarding/sut/lab/__init__.py` | Package marker. | WP10 · 24 Oct |
| `projects/kyc_onboarding/sut/lab/defects.py` | The six seeded-defect switches, read from EVALKIT_LAB_SWITCHES; what each does is documented inside (restricted). | WP10 · 24 Oct |
| `projects/kyc_onboarding/tools/__init__.py` | Package marker. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/registry.py` | Builds LangChain tools from specs + mocks, wraps each with the fault hook and audit logging. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/classify_document.json` | JSON schema for classify_document (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/extract_document.json` | JSON schema for extract_document (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/verify_pan.json` | JSON schema for verify_pan (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/ckyc_lookup.json` | JSON schema for ckyc_lookup (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/check_address_proof.json` | JSON schema for check_address_proof (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/sanctions_screen.json` | JSON schema for sanctions_screen (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/pep_check.json` | JSON schema for pep_check (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/fetch_risk_policy.json` | JSON schema for fetch_risk_policy (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/compute_risk_score.json` | JSON schema for compute_risk_score (read). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/request_customer_info.json` | JSON schema for request_customer_info (interaction). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/escalate_to_edd.json` | JSON schema for escalate_to_edd (write). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/create_customer_record.json` | JSON schema for create_customer_record (irreversible, approval-gated). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/finalize_application.json` | JSON schema for finalize_application (write). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/specs/handoffs.json` | JSON schema for handoffs (transfer_to_doc_extraction / identity / screening / risk and route_to_corporate_stub). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/__init__.py` | Package marker. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/db.py` | Read-only / runtime-table access to the per-trial SQLite copy; norm() name normalisation. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/document_tools.py` | classify_document, extract_document. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/identity_tools.py` | verify_pan, ckyc_lookup, check_address_proof. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/screening_tools.py` | sanctions_screen, pep_check (writes screening_results). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/risk_tools.py` | fetch_risk_policy, compute_risk_score (screening override, MISSING_INPUT). | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/supervisor_tools.py` | request_customer_info, escalate_to_edd, create_customer_record (token check, DUPLICATE_RECORD), finalize_application. | WP2 · D3–5 |
| `projects/kyc_onboarding/tools/mocks/handoff_tools.py` | Hand-off tools and their L2 stub behaviour (agent_stubs table). | WP2 · D3–5 |
| `projects/kyc_onboarding/policies/kyc_individual_v1.yaml` | R1–R3, P1–P3, F1–F4, A1, D1–D10, LIMIT-*, TRANS-1, SLICE-1, VER-1 and the per-agent guardrails (AG-5): the QE Lead's rule-by-rule decisions of 23 Oct 2026, transcribed. Unvalidated (no SME). | WP5 · D8–14 |
| `projects/kyc_onboarding/policies/pii_masking.yaml` | MASK-IN_PAN (replies, decisions), MASK-IN_AADHAAR and MASK-CARD_PAN (everywhere but the source document), MASK-CONTACT (replies): QE Lead decisions of 23 Oct 2026. | WP5 · D8–14 |
| `projects/kyc_onboarding/policies/regulatory_mapping.yaml` | Rule ID → RBI KYC Directions 2025 / PMLA / DPDP / FREE-AI reference, each marked [confirm]. | WP9 · D5–27 |
| `projects/kyc_onboarding/data/README.md` | Mock tool data contract, fault hook protocol, table guide, change log. | Exists (v0.12) |
| `projects/kyc_onboarding/data/schema.sql` | SQLite DDL with column comments and views. | Exists (v0.12) |
| `projects/kyc_onboarding/data/generate_kyc_db.py` | Rebuilds the seed DB: fixtures/ for personas and documents, the case YAML files for test_cases and case_documents (--background-from keeps the background population). | WP6 · D9–21 |
| `projects/kyc_onboarding/data/check_fixtures.py` | Conformance check: fixture data supports every case oracle (105 checked, 5 structural). | Exists (v0.12) |
| `projects/kyc_onboarding/data/kyc_synthetic.sqlite` | Seed database v0.12 (350 applicants, 700 documents, 110 cases). | Exists (v0.12) |
| `projects/kyc_onboarding/data/fixtures/kyc_fixtures.py` | Personas, documents, watch lists, risk policy, fault / stub profiles, reference trajectories. | Exists (v0.12) |
| `projects/kyc_onboarding/data/fixtures/kyc_cases.py` | Retired in WP6: the v0.12 case definitions the catalogue was built from; kept unchanged for provenance. Cases now live in datasets/. | Exists (v0.12) |
| `projects/kyc_onboarding/datasets/golden/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/agent_unit/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/edge/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/faults/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/adversarial/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/pii/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/policy/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/handoff/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/fairness_pairs/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/missing_info/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/multi_turn/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/paraphrase/.gitkeep` | Keeps the folder when it has no cases. | WP6 · D9–21 |
| `projects/kyc_onboarding/datasets/README.md` | Tester guide: folders, adding a case in five steps (copy, edit, expect, `data` + `lint-cases`, dry run), every field. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-01.json` | Approved (standard). | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-02.json` | EDD – screening hit. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-03.json` | EDD – high risk. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-04.json` | Pending info – document issue. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-05.json` | Pending info – identity mismatch. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-06.json` | Rejected – approver denied. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-07.json` | Rejected – PAN invalid. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-08.json` | Pending info – system unavailable. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-09.json` | Rejected – corporate stub. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-10.json` | Pending info – approval timeout. | WP6 · D9–21 |
| `projects/kyc_onboarding/reference_trajectories/RT-11.json` | Resume after missing info. | WP6 · D9–21 |
| `projects/kyc_onboarding/recorded_runs/KYC-GLD-001.json` | Scripted L3 recording (clean path). | WP4 · D6–8 |
| `projects/kyc_onboarding/recorded_runs/KYC-FLT-021.json` | Scripted L1 recording (identity agent under FP-01). | WP4 · D6–8 |
| `projects/kyc_onboarding/recorded_runs/KYC-HND-109.json` | Scripted L2 recording (stub writes outside its slice). | WP4 · D6–8 |
| `projects/kyc_onboarding/recorded_runs/live/KYC-GLD-001.json` | A real-model trajectory of KYC-GLD-001 (re-recorded 23 Oct in WP5 with run inputs and approval token, about $0.04), for evaluator tests without API calls. | WP4 · D6–8 |

## `projects/demo_second/`

Replication demo: a two-tool account-statement bot evaluated with a new adapter, policy and dataset only — no evalkit/ change.

| Folder | Contents |
|---|---|
| `projects/demo_second/datasets/` | 10 cases for the demo bot. |
| `projects/demo_second/policies/` | Policy rules for the demo bot. |
| `projects/demo_second/sut/` | Tiny system under test for the replication demo. |
| `projects/demo_second/tools/specs/` | Tool specs for the demo bot. |

| File | Purpose | Built in |
|---|---|---|
| `projects/demo_second/README.md` | What the replication demo proves and how to run it. | WP11 · D25–27 |
| `projects/demo_second/project.yaml` | Demo project configuration. | WP11 · D25–27 |
| `projects/demo_second/agents.yaml` | Single-agent contract for the statement bot. | WP11 · D25–27 |
| `projects/demo_second/sut/__init__.py` | Package marker. | WP11 · D25–27 |
| `projects/demo_second/sut/graph.py` | Two-tool account-statement bot. | WP11 · D25–27 |
| `projects/demo_second/tools/specs/get_statement.json` | Tool spec. | WP11 · D25–27 |
| `projects/demo_second/tools/specs/send_statement.json` | Tool spec (write, consent-gated). | WP11 · D25–27 |
| `projects/demo_second/policies/statement_bot_v1.yaml` | Policy rules for the demo bot. | WP11 · D25–27 |
| `projects/demo_second/datasets/.gitkeep` | 10 cases written in WP11. | WP11 · D25–27 |

## `tests/`

pytest suite for the framework itself (not the agents): evaluators are tested on good and bad trajectories so a broken evaluator cannot pass a broken agent.

| Folder | Contents |
|---|---|
| `tests/fixtures/` | Test data for the framework's own tests (trajectory fixtures, labelled PII strings). |
| `tests/fixtures/trajectories/bad/` | Trajectories that must fail the check named in the file name. |
| `tests/fixtures/trajectories/good/` | Trajectories that must pass the check named in the file name. |
| `tests/integration/` | End-to-end tests of the harness against the real KYC graph (need an API key; marked so CI can skip them). |
| `tests/lab/` | Acceptance test: each seeded defect LAB-1 … LAB-6 must fail at least one S1/S2 check (restricted until the assessment). |
| `tests/unit/` | Unit tests per module. |
| `tests/unit/evaluators/` | One test file per evaluator family, driven by tests/fixtures/trajectories. |

| File | Purpose | Built in |
|---|---|---|
| `tests/conftest.py` | Shared fixtures: temp SQLite copy, loaded configs, trajectory fixture loader; `api` marker for live tests. | WP1 · D2–3 |
| `tests/unit/test_trajectory_schema.py` | Schema round trip, strictness, per-agent views; recordings load. | WP4 · D6–8 |
| `tests/unit/test_runner.py` | Run-mode sizes (10 / 210 / 250), k per severity, output layout, per-trial DB isolation, clock check. | WP4 · D6–8 |
| `tests/recordings.py` | Scripted runs behind the recordings; `uv run python -m tests.recordings --write` refreshes them. | WP4 · D6–8 |
| `tests/unit/test_config_loader.py` | The shipped configs are valid and match the requirement sheet; typos, bad values, broken YAML and bad overrides give readable errors. | WP1 · D2–3 |
| `tests/unit/test_cli.py` | Every command is registered; planned commands name their work package; the data rebuild from the case YAML is deterministic and never replaces the seed when the check fails. | WP1 · D2–3 |
| `tests/unit/test_mocks.py` | 116 tests: the mocks against the data contract; every FAULT / OVERRIDE / STUB / CANNED_STATE profile reproduced (coverage guards fail on an untested new profile); allow-lists, schema errors, audit rows, determinism, output-schema conformance. | WP2 · D3–5 |
| `tests/unit/test_fault_hook.py` | Generic fault hook without any project: precedence, attempts per identical arguments, every behaviour, virtual clock. | WP4 · D6–8 |
| `tests/unit/test_adapter_parity.py` | Re-running the scripted recordings reproduces them exactly; mapping of handoffs, faults, slice violations, end state; crash → error trajectory. (OTel parity descoped with that adapter.) | WP4 · D6–8 |
| `tests/unit/test_case_lint.py` | Import reproduces every catalogue column and never copies the lab key; re-import is a no-op and keeps edits; coverage equals the catalogue; 30 lint mistake classes. | WP6 · D9–21 |
| `tests/unit/test_gates.py` | Composite maths, gate verdicts (NO_GATES, PASS, FAIL, INCOMPLETE, SUSPENDED), agent and pattern scopes, exit codes, `evalkit grade` CLI. | WP5 · D8–14 |
| `tests/unit/test_reporting.py` | WP8 exit check (seeded defect → exit 1 naming KYC-GLD-001 t1 · TR-3 (R1); no unmasked identifier in HTML / JUnit), leak guard, failing-step highlight, cost, ledger, alerts, judge tokens, report / full commands. | WP8 · D19–22 |
| `tests/unit/evaluators/test_trajectory_evaluators.py` | TR-1, TR-2, TR-5, TR-6, TR-7 on recordings and their bad variants. | WP5 · D8–14 |
| `tests/unit/evaluators/test_tooluse_evaluators.py` | TU-1 … TU-6 on recordings and their bad variants; Indian number notation. | WP5 · D8–14 |
| `tests/unit/evaluators/test_policy_engine.py` | Every rule kind and condition of the engine passes on a good recording and fails on its bad variant (test policy, not the KYC policy); bad policy files give readable errors. | WP5 · D8–14 |
| `tests/unit/evaluators/test_bfsi_evaluators.py` | BF-1 … BF-6; PII recall and precision ≥ 95% on the labelled set; checksums. | WP5 · D8–14 |
| `tests/unit/evaluators/test_agent_evaluators.py` | Slicer and AG-1 … AG-6 for the five agents; the grader on the recordings; evaluator errors recorded. | WP5 · D8–14 |
| `tests/unit/evaluators/test_judges.py` | κ and consensus gating, label files, cache keys, rubric anchors, masked judge input, request shape, errors, call plan, labelling sheet, dry run makes no call (fake client only). | WP7 · D15–21 |
| `tests/fixtures/trajectories/good/.gitkeep` | Unused: good fixtures are the recordings in projects/kyc_onboarding/recorded_runs/. | WP5 · D8–14 |
| `tests/fixtures/trajectories/bad/.gitkeep` | Unused: bad fixtures are built from the recordings by the helpers in tests/unit/evaluators/conftest.py (one named defect each). | WP5 · D8–14 |
| `tests/fixtures/pii_labelled.jsonl` | 61 synthetic labelled strings (43 identifiers: PAN, Verhoeff-valid Aadhaar, public test cards, phones, e-mails) plus masked forms and look-alikes, for scanner recall / precision. | WP5 · D8–14 |
| `tests/fixtures/policies/engine_rules.yaml` | Test policy exercising every rule kind of the engine (rule IDs T-…). Not the KYC policy and judges nothing. | WP5 · D8–14 |
| `tests/unit/evaluators/conftest.py` | Suite fixture, recording loader and one-defect mutation helpers (drop a call, edit an argument, change an output, leak a reply). | WP5 · D8–14 |
| `tests/scripted_client.py` | Scripted stand-in for the Anthropic client (messages.create / messages.parse) so the graph runs offline; records every request. | WP3 · D4–7 |
| `tests/unit/test_kyc_graph.py` | 26 offline tests: deterministic contract builders, graph paths (approve, deny, EDD, duplicate record, L2 stub, turn-2 upload), guards, request shape (model, effort, caching, no sampling). | WP3 · D4–7 |
| `tests/__init__.py` | Makes `tests` importable for the shared scripted client. | WP3 · D4–7 |
| `tests/integration/test_smoke_golden.py` | The 10 golden cases end to end (marker `api`). | WP3 · D4–7 |
| `tests/lab/test_seeded_defects.py` | Each LAB variant, run offline with a scripted model on a case listed in catalogue › Lab Mapping, fails an S1/S2 check that the same run without the switch passes. | WP10 · 24 Oct |
| `tests/unit/test_lab.py` | Switches off by default; unknown switch stops the run; a normal run refuses while a switch is set; `evalkit lab` dry run; variant files give nothing away. | WP10 · 24 Oct |

## `runs/`

Run outputs (git-ignored): runs/<run_id>/results.jsonl, report.html, junit.xml, cost.json, traces/, per-trial SQLite copies.

| File | Purpose | Built in |
|---|---|---|
| `runs/.gitkeep` | Keeps the folder; contents are git-ignored. | WP1 · D2–3 |

## `docs/`

Framework documentation set and the governing documents.

| Folder | Contents |
|---|---|
| `docs/methodology/` | Markdown extracts of the methodology used day to day: metrics, rubrics, taxonomy, audit pack. |
| `docs/requirements/` | Agent Requirement sheet (intake template) and Test Case Catalogue — the oracles' written sources. |
| `docs/file_reference.md` | This page. | WP9 |

| File | Purpose | Built in |
|---|---|---|
| `docs/requirements/Agent_Requirement_KYC_v0.3.xlsx` | Requirement sheet v0.3 (KYC filled + blank Template tab). | Exists (v0.12) |
| `docs/requirements/KYC_Test_Case_Catalogue_v0.12.xlsx` | Test Case Catalogue v0.12 (110 cases + fixtures). | Exists (v0.12) |
| `docs/architecture.md` | Components, data flow, trajectory schema, evaluator registry, gate logic, extension points. | WP9 · 24 Oct (draft) |
| `docs/setup.md` | From clean laptop to green smoke run. | WP9 · 24 Oct (draft) |
| `docs/config_reference.md` | Every configuration file: eval.yaml, project.yaml, agents.yaml, tool specs, policy files (rule kinds, conditions, matchers), pii_masking.yaml, pii_recognizers.yaml, gates.yaml, judges.yaml, budget, case files, reference trajectories, environment variables. | WP9 · 24 Oct (draft) |
| `docs/extension_guide.md` | Adding an adapter, an evaluator, a metric, a project. | WP9 · 24 Oct (draft) |
| `docs/tester_guide.md` | The tester's cycle (lint → gate → triage → defect report): run modes, case cookbook, match-mode decision table, reading the report, triage, defect report examples, re-run triggers, judge labelling. Includes the SOP's runbook. | WP9 · 24 Oct (draft) |
| `docs/glossary.md` | Terms and IDs (TR/TU/BF/AG, D-rules, reason codes, KYC terms). | WP9 · 24 Oct (draft) |
| `docs/methodology/metrics_catalogue.md` | All metric IDs with method, severity, threshold. | WP9 · 24 Oct (draft) |
| `docs/methodology/scoring_rubrics.md` | Composite weights and the judge rubric (0–3 anchors). | WP9 · 24 Oct (draft) |
| `docs/methodology/test_design_taxonomy.md` | Patterns, levels, ID scheme, coverage targets. | WP9 · 24 Oct (draft) |
| `docs/methodology/defect_taxonomy.md` | Severities S1–S4 and root-cause codes. | WP9 · 24 Oct (draft) |
| `docs/methodology/audit_pack_checklist.md` | What goes into a release audit pack. | WP9 · 24 Oct (draft) |

## `training/`

Training package for the two testers (YAML + command line only).

| Folder | Contents |
|---|---|
| `training/assessment/` | Final assessment and scoring sheet. |
| `training/exercises/` | Six exercises with expected answers. |
| `training/lab/` | Bug-hunt lab: six seeded-defect variants run with `evalkit lab --variant LAB-n --case …`. |
| `training/lab/answer_key/` | Restricted: answers for the lab — hide from testers until the assessment is done. |
| `training/lab/variants/` | One YAML per variant (ID, project, switch, a neutral brief); deliberately says nothing about the defect. |
| `training/modules/` | Seven modules (~15 h). |

| File | Purpose | Built in |
|---|---|---|
| `training/modules/M1_agentic_ai_basics.md` | Agents, tools, trajectories, why outcome-only testing fails. | WP10 · 24 Oct |
| `training/modules/M2_prompt_and_agent_behaviour.md` | How prompts drive routing, tool choice and refusals; reading traces. | WP10 · 24 Oct |
| `training/modules/M3_evaluation_design.md` | Levels L1–L3, patterns, coverage, reference trajectories, match modes. | WP10 · 24 Oct |
| `training/modules/M4_bfsi_controls.md` | KYC / AML rules, PII masking, fairness, disclosure — and how each is checked. | WP10 · 24 Oct |
| `training/modules/M5_running_the_harness.md` | make targets, run modes, reading report.html and junit.xml. | WP10 · 24 Oct |
| `training/modules/M6_writing_cases_in_yaml.md` | Case YAML from a policy clause; lint; adding to coverage. | WP10 · 24 Oct |
| `training/modules/M7_triage_and_defects.md` | Root-causing a failure: agent, mock, case or evaluator; writing the defect. | WP10 · 24 Oct |
| `training/exercises/E1_read_a_trajectory.md` | Read a trace and name each step and agent. | WP10 · 24 Oct |
| `training/exercises/E2_choose_match_mode.md` | Pick the match mode for six scenarios. | WP10 · 24 Oct |
| `training/exercises/E3_write_policy_case.md` | Write a case for 'any PEP hit requires EDD'. | WP10 · 24 Oct |
| `training/exercises/E4_fault_case.md` | Add a fault-injection case for an untested tool. | WP10 · 24 Oct |
| `training/exercises/E5_per_agent_case.md` | Write an L1 case for one specialist. | WP10 · 24 Oct |
| `training/exercises/E6_prompt_comparison.md` | Compare two Supervisor prompts on the same cases. | WP10 · 24 Oct |
| `training/exercises/expected_answers.md` | Model answers for E1–E6. | WP10 · 24 Oct |
| `training/lab/variants/LAB-1.yaml` | Variant LAB-1 (neutral brief; the defect is in the restricted answer key). | WP10 · 24 Oct |
| `training/lab/variants/LAB-2.yaml` | Variant LAB-2 (neutral brief; the defect is in the restricted answer key). | WP10 · 24 Oct |
| `training/lab/variants/LAB-3.yaml` | Variant LAB-3 (neutral brief; the defect is in the restricted answer key). | WP10 · 24 Oct |
| `training/lab/variants/LAB-4.yaml` | Variant LAB-4 (neutral brief; the defect is in the restricted answer key). | WP10 · 24 Oct |
| `training/lab/variants/LAB-5.yaml` | Variant LAB-5 (neutral brief; the defect is in the restricted answer key). | WP10 · 24 Oct |
| `training/lab/variants/LAB-6.yaml` | Variant LAB-6 (neutral brief; the defect is in the restricted answer key). | WP10 · 24 Oct |
| `training/lab/README.md` | How to run the bug hunt, rules, method, what to submit and how a variant counts as caught. | WP10 · 24 Oct |
| `training/lab/answer_key/answer_key.md` | Restricted. Catalogue › Lab Mapping and the switch implementations, transcribed verbatim at the QE Lead's request (24 Oct 2026) and awaiting the QE Lead's review; plus a reviewer note on what the offline test saw. | WP10 · transcribed |
| `training/assessment/assessment.md` | Pass bar (≥ 5 of 6 caught, 10 valid cases), what counts as caught and as a valid case, budget, marking. | WP10 · 24 Oct |
| `training/assessment/scoring_sheet.md` | Per-tester sheet: variants caught, cases accepted, spread, pass / not yet. | WP10 · 24 Oct |

## `prompts/`

Prompts used with Claude Code to generate code and fixtures, kept so a replication team can regenerate them.

| Folder | Contents |
|---|---|
| `prompts/claude_code/` | One prompt file per generator / work package. |

| File | Purpose | Built in |
|---|---|---|
| `prompts/claude_code/README.md` | Which prompt produced which files; rule: S1 oracles are never generated. | WP1 · D2–3 |
| `prompts/claude_code/WP6_case_suite.md` | The WP6 request: case YAML import, lint, coverage, reference trajectories; oracles left to the QE Lead. | WP6 · D9–21 |
| `prompts/claude_code/WP7_judges.md` | The WP7 request: rubric judges, cache, calibration; no live calls, pricing not guessed. | WP7 · D15–21 |
| `prompts/claude_code/WP10_lab.md` | The WP10 request: seeded-defect switches, `evalkit lab`, training material; answer key transcribed on request. | WP10 · 24 Oct |
| `prompts/claude_code/WP5_evaluators.md` | The WP5 request and the boundary kept: evaluators and engine generated, policy / gates / S1 oracles left to the QE Lead. | WP5 · D8–14 |
| `prompts/claude_code/WP9_docs.md` | The WP9 request: documentation drafted from the code and configuration; the SOP change list proposed, not applied. | WP9 · 24 Oct |

## `.github/`



| Folder | Contents |
|---|---|
| `.github/workflows/` | CI: smoke on every push, gate on pull requests, full nightly. |

| File | Purpose | Built in |
|---|---|---|
| `.github/workflows/eval.yml` | smoke on push (offline + live golden when the key secret exists), S1 gate on pull requests, full nightly; uploads reports; JUnit annotations name the failing rule. | WP8 · D19–22 |

## Conventions

- Case IDs follow `KYC-<PATTERN>-<NNN>`, and NNN is unique across the catalogue. Each case becomes `datasets/<pattern>/<case_id>.yaml` and mirrors the catalogue columns.
- Policy rules, gates and per-agent contracts are configuration (YAML), and every rule has an ID. Code never hard-codes a threshold.
- All data is synthetic and tagged SYNTHETIC: PANs are in the fictitious ZQ / ZX series, and full Aadhaar numbers appear only in PII fixtures. CI fails if an untagged identifier appears in `runs/`.
- Change control: changing a fixture means editing `data/fixtures/*.py`, rebuilding the database and running `check_fixtures.py`. Any change to a model ID, prompt, tool schema, policy rule, dataset or evaluator triggers a full regression (SOP §3.14).
