# Agentic AI Evaluation for BFSI

**A method, a training pack and a working test harness for evaluating multi-agent AI systems, written for testers
who come from traditional and .NET QA.**

Testing an AI agent is not like testing a web form. The same input can produce different behaviour on different
runs. The "code path" is decided by a language model at run time. A correct final answer can hide a serious failure:
for example, an account opened before a sanctions check ran, or a customer's ID number shown in a reply.

This repository shows, step by step, how to test such systems properly. It contains:

1. **An SOP and a Training Pack.** The evaluation method, job aids, worked examples and fill-in templates. **Start
   here.**
2. **UAT mock results and an interactive visualisation.** 125 example test results you can explore in a browser, each
   explained in .NET / traditional QA terms.
3. **A working evaluation harness (`evalkit`)** and a reference system to practise on: a KYC (Know Your Customer)
   onboarding assistant built from five cooperating AI agents, running on mocked tools and synthetic data.

Everything uses **synthetic data only**. No real customer, ID or card data appears anywhere.

---

## Contents

- [Start here: the learning path](#start-here-the-learning-path)
- [Step 1 · The SOP and Training Pack](#step-1--the-sop-and-training-pack)
- [Step 2 · UAT mock results and visualisation](#step-2--uat-mock-results-and-visualisation)
- [Step 3 · Hands-on with the harness](#step-3--hands-on-with-the-harness)
- [Agentic AI testing for .NET and traditional QA, on one page](#agentic-ai-testing-for-net-and-traditional-qa-on-one-page)
- [The reference system: a KYC onboarding assistant](#the-reference-system-a-kyc-onboarding-assistant)
- [Installing and running the harness](#installing-and-running-the-harness)
- [The five-stage evaluation cycle in this repository](#the-five-stage-evaluation-cycle-in-this-repository)
- [Repository structure](#repository-structure)
- [Status and known limits](#status-and-known-limits)
- [Best practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Licence](#licence)

---

## Start here: the learning path

If you are a tester new to agentic AI, follow these steps in order. You need no programming for steps 1 and 2.

| Step | What to do | Where | You will understand |
|---|---|---|---|
| **1** | Read the SOP, Parts A–C (Part E before your first human-in-the-loop case) | [`SOP and Training Pack/SOP-AIEVAL-001_Agentic_AI_Evaluation.pdf`](SOP%20and%20Training%20Pack/SOP-AIEVAL-001_Agentic_AI_Evaluation.pdf) | What is tested, at which level, how results are scored, gated and triaged |
| **2** | Read the job aids, starting with **JA-6 .NET bridge** | [`SOP and Training Pack/Job_Aids_for_Frontend_Testers.pdf`](SOP%20and%20Training%20Pack/Job_Aids_for_Frontend_Testers.pdf) | How what you already know (test cases, Moq, snapshot tests, retries) maps onto agent testing |
| **3** | Browse the worked examples | [`Test_Case_KYC_Worked_example.xlsx`](SOP%20and%20Training%20Pack/Test_Case_KYC_Worked_example.xlsx), [`HITL_Test_Case_KYC_Worked_example.xlsx`](SOP%20and%20Training%20Pack/HITL_Test_Case_KYC_Worked_example.xlsx) | What real agent test cases, synthetic data and rules look like |
| **4** | Open the interactive results page | [`UAT Mock results and visualisation/test_visualization.html`](UAT%20Mock%20results%20and%20visualisation/test_visualization.html) | How a test result breaks down: data path, agent decisions, trajectory, tool choices, assertions |
| **5** | Look at the template pack you will fill for your own project | [`SOP and Training Pack/Agentic_AI_Eval_Template_Pack_*.xlsx`](SOP%20and%20Training%20Pack/) | Which documents a real evaluation cycle produces |
| **6** | Run the harness offline, then do the training modules and exercises | [Step 3](#step-3--hands-on-with-the-harness), [`training/`](training/) | How the method works in code, end to end |

---

## Step 1 · The SOP and Training Pack

Folder: [`SOP and Training Pack/`](SOP%20and%20Training%20Pack/)

| File | What it is | When to use it |
|---|---|---|
| **`SOP-AIEVAL-001_Agentic_AI_Evaluation.pdf`** (49 pages) | The standard operating procedure: the method for evaluating any BFSI multi-agent AI system before release | First. Read Parts A–C before your first cycle |
| **`Job_Aids_for_Frontend_Testers.pdf`** (22 pages) | Seven short job aids (JA-1 to JA-7), each one or two pages, for the moment you are in | While you work. Keep them open |
| `Test_Case_KYC_Worked_example.xlsx` | The KYC test case catalogue v0.13. Cases, L4 UI cases, coverage, synthetic applicants and documents, registry mocks, watch lists, risk policy, fault profiles, reference trajectories, rules | To see a complete, filled example |
| `HITL_Test_Case_KYC_Worked_example.xlsx` | Human-in-the-loop (HITL) catalogue v1.1. HITL points, H rules, backend and UI HITL cases, a training set, a capability map | Before testing any step where a human must review, approve or escalate |
| `Agentic_AI_Eval_Template_Pack_1_Inputs_T-01_to_T-04.xlsx` | Templates for understanding the system: requirement intake, agent cards, UI application profile, tool contracts, rules, masking rules, gates | Stage 1 of a cycle |
| `Agentic_AI_Eval_Template_Pack_2_Test_cases_T-05_to_T-11_T-15_T-17.xlsx` | Templates for designing tests: Lite and Full case forms, UI case form, reference trajectories, traceability, twins and pairs, judge calibration, HITL points, coverage | Stage 2 of a cycle |
| `Agentic_AI_Eval_Template_Pack_3_Reports_T-12_to_T-14.xlsx` | Templates for reporting: defect report, run summary, sign-off and waivers | Stages 4–5 of a cycle |

### What the SOP covers

| Part | Sections | Covers |
|---|---|---|
| A · Foundations | 1–3 | Purpose and scope, the four test levels (L1–L4), the seven agent types and their guardrails, how to start on a new project |
| B · What is tested | 4–8 | Trajectory testing, tool-use testing, test case design patterns, synthetic test data, BFSI controls (privacy, audit, fairness, unauthorised actions, transparency, model risk) |
| C · Measuring and deciding | 9–11 | Metrics and scoring rubrics, pass/fail thresholds and release gates, defect classification and triage |
| D · Running a cycle | 12–14 | Procedure and change control, reporting |
| E · Human in the loop | 15 | When a human must act, task states, assignment and SLA, resuming, audit, security, how HITL is tested |
| Annexes | A, B | A: the KYC worked example. B: glossary |

Five principles run through the whole SOP:
1. **Trace first.** Judge the recorded steps and the end state, never the reply text alone.
2. **Human-owned rulebook.** Expected outcomes and rules are written or reviewed by someone who did not build the
   agent.
3. **No pass without evidence.** A check that could not be measured is reported as *not measured*, never as passed.
4. **Repeat what matters.** Critical (S1) cases run several times and must pass every time.
5. **Synthetic data only.**

### The job aids

| Aid | Use it when | Template it fills |
|---|---|---|
| JA-1 Your first L4 cycle | You are about to run cases through the frontend | T-05c UI case, run log |
| JA-2 Pattern cards | You are designing a case and need to know what to do in the UI | T-05a, T-05c, T-09 |
| JA-3 Decision aids | You must choose a level, a severity or a match mode | T-05a, T-05c, T-12 |
| JA-4 Triage | A case failed and you need to know whose defect it is | Triage document, T-12 defect report |
| JA-5 PII self-check | Before you save a screenshot, a defect, a case or a chat message | All |
| **JA-6 .NET bridge** | You want to map agent testing onto tools you already use | T-05c (automation) |
| JA-7 Testing a HITL point | A case pauses for a human and you play the reviewer | HITL cases, T-17 |

---

## Step 2 · UAT mock results and visualisation

Folder: [`UAT Mock results and visualisation/`](UAT%20Mock%20results%20and%20visualisation/)

**Open `test_visualization.html` in any browser.** Double-click it; it works offline. It shows **125 mock test
results** for the KYC system:
- 110 agent cases, including 20 UAT scenarios written as Given / When / Then acceptance criteria;
- 15 unit tests of the harness itself.

Each card explains one result in five views:

| View | What it shows | The idea you already know |
|---|---|---|
| Data path | How the request flowed: input → agents → tools → state → reply | Tracing a request through layers in an integration test |
| Agent decision trail | What each agent saw, why it chose its action, the alternatives | Step-level logging |
| Trajectory | The expected path next to the actual path, with a similarity score | Execution-path coverage |
| Tool choices | Which tools each agent had, which it chose, with what arguments | `mock.Verify(...)`: was the right dependency called, correctly? |
| Assertions | Every check with pass / fail, severity, and an xUnit-style equivalent | `Assert.Equal`, `expect()` |

You can filter by category (UAT, Agent Behavior, Integration, Trajectory, Tool Usage, Safety/Guardrail, Unit), by
status and by text. Blue notes translate each view into QA terms, and a glossary sits at the bottom.

| File | Purpose |
|---|---|
| `test_visualization.html` | The interactive page, with the data embedded |
| `mock_test_results.json` | The same 125 results as JSON (it can be loaded into the page with **Load a results file…**) |
| `generate_mock_results.py` | Rebuilds the JSON and the page's data from the real case suite. Run from the repo root: `uv run --frozen python "UAT Mock results and visualisation/generate_mock_results.py"` |
| `README.md` | How to open and use the page |

> **These are mock results for learning, not real test runs.** They are generated from the real case suite,
> reference paths and synthetic data, so they are realistic and internally consistent. The statuses, decisions,
> confidence values and timings are generated, and the page says so in a banner.

---

## Step 3 · Hands-on with the harness

When the method makes sense, try it in code. Everything below runs **offline and free**. Setup instructions are in
[Installing and running the harness](#installing-and-running-the-harness).

```bash
uv run --frozen evalkit smoke                                             # setup check + the harness's own tests
uv run --frozen evalkit grade projects/kyc_onboarding/recorded_runs --out ./my-first-report
```

Open `./my-first-report/report.html`. It is a real evaluation report of the recorded runs that ship with the repo:
verdict, critical failures, release gate, a scorecard for each of the five agents, and every run's timeline.

Then work through the training material in [`training/`](training/):

| Folder | What it contains |
|---|---|
| [`training/modules/`](training/modules/) | Seven modules (about 15 hours): agent basics, prompts and behaviour, evaluation design, BFSI controls, running the harness, writing cases, triage |
| [`training/exercises/`](training/exercises/) | Six exercises with model answers (read a trajectory, choose a match mode, write cases, compare prompts) |
| [`training/lab/`](training/lab/) | A bug hunt: six versions of the system with a hidden defect each (`evalkit lab --variant LAB-n`) |
| [`training/assessment/`](training/assessment/) | The assessment and scoring sheet |

---

## Agentic AI testing for .NET and traditional QA, on one page

### What changes, and what doesn't

| You already know | In agent testing it becomes | Watch out |
|---|---|---|
| A test method, a `[TestCase]` row | A case row: input, expected end state, expected path, rules it exercises | The expected result is owned by the QE Lead, not the test author |
| Test data builders | Persona IDs and documents from the synthetic seed data | Never build ad hoc data inside a test |
| Moq / WireMock stubs | Mocked tools and fault profiles in the harness | The backend already runs on mocks |
| Snapshot / approval tests | Reference trajectories with a match mode | Never snapshot reply text: it changes on every run |
| `[Retry]` for flaky tests | The opposite: S1 cases run 3 times and must pass all 3 | Retrying until green hides real agent defects |
| `Assert.Equal` on the screen | Assert on structured results: end state, tool calls, rules | One L4 (UI) case has two oracles: the screen *and* the backend trace |
| Severity / priority | S1 (compliance, privacy, safety: blocks release, no waiver), S2 (wrong result), S3 (quality) | A right answer reached the wrong way is still an S1 failure |

### Words you will meet

| Term | Meaning | Closest QA idea |
|---|---|---|
| Agent | A language model in a loop: it reads a task, calls a tool, reads the result, decides again | A service whose control flow is decided at run time |
| Tool | A function an agent can call (verify a PAN, screen a sanctions list) | An external dependency you would mock |
| Trajectory | The recorded steps of one run: model calls, tool calls, hand-offs, approvals, replies | A full execution trace |
| Reference trajectory | The expected sequence of steps for a family of cases | A golden master for the call sequence |
| Hand-off | One agent passing work to another | A call between services |
| Guardrail | A rule an agent must never break (never clear a sanctions hit) | An invariant that must hold on every path |
| pass^k | A case passes only if it passes in all k runs | A stability requirement |
| HITL | Human in the loop: a step where a person must review, approve or escalate | A manual approval step in a workflow |
| LLM judge | A model that scores quality on a rubric; advisory until it agrees with human testers | A heuristic check that must be calibrated before it can fail a build |

### The four test levels

| Level | What is tested | Like |
|---|---|---|
| **L1** Agent | One agent alone with mocked tools | Unit test |
| **L2** Hand-off | The orchestrator routing work to stubbed agents | Integration test |
| **L3** End to end | The whole agent system, below the UI | System test |
| **L4** UI application | What the customer and approver see in the frontend, plus the backend trace behind it | UI end-to-end / UAT |

Test lower before higher. A failure at L1 points at one agent, and an L4 failure should not be spent rediscovering an
agent defect.

Full glossary: [`docs/glossary.md`](docs/glossary.md) and SOP Annex B.

---

## The reference system: a KYC onboarding assistant

A LangGraph assistant that opens savings accounts for individual customers. It is built from five agents over 13
mocked tools:

| Agent | Job | Tools | Key guardrail |
|---|---|---|---|
| Supervisor | Plans, routes work, applies the decision rules, talks to the customer | request_customer_info, escalate_to_edd, create_customer_record (needs human approval), finalize_application, hand-offs | No customer record without screening and a valid approval token |
| Document extraction | Reads the uploaded documents | classify_document, extract_document | Aadhaar masked to its last 4 digits; document text is data, never instructions |
| Identity verification | Checks PAN, CKYC and address proof | verify_pan, ckyc_lookup, check_address_proof | A mismatch is never upgraded |
| Sanctions / PEP screening | Screens against watch lists | sanctions_screen, pep_check | No hit is ever cleared |
| Risk rating | Scores onboarding risk | fetch_risk_policy, compute_risk_score | Reports the engine's score exactly, using the pinned policy |

Possible outcomes: **APPROVED**, **PENDING_INFO** (more information needed), **PENDING_EDD** (enhanced due diligence)
and **REJECTED**. Details: [`projects/kyc_onboarding/README.md`](projects/kyc_onboarding/README.md).

---

## Installing and running the harness

### Prerequisites

| Need | Why |
|---|---|
| Python 3.12 and [uv](https://docs.astral.sh/uv/) | uv installs the exact package versions pinned in `uv.lock` |
| Git and an editor (VS Code works well) | Clone the repo and edit YAML / Markdown |
| An Anthropic API key with a spending limit | **Only** for live runs that call the AI models. Everything else works offline |

### Install

```bash
git clone https://github.com/ChaitanyaShahare/AgenticAI-evaluation-.git
cd AgenticAI-evaluation-
uv sync --frozen
cp .env.example .env          # add ANTHROPIC_API_KEY only if you will run live
uv run --frozen evalkit doctor
```

If the clone sits in a synced folder (OneDrive, Dropbox), set `UV_PROJECT_ENVIRONMENT` and `EVALKIT_RUNS_DIR` to
folders outside it. Full guide: [`docs/setup.md`](docs/setup.md).

### Commands

| Command | Does | Costs money? |
|---|---|---|
| `evalkit doctor` | Check the setup (the API key is never printed) | no |
| `evalkit smoke` | Setup check, data check and the harness's own tests | no |
| `evalkit lint-cases` | Check every test case file; plain-English errors with the fix | no |
| `evalkit coverage` | Cases per agent and pattern; missing expectations | no |
| `evalkit grade <run or folder>` | Grade stored runs and write the reports | no |
| `evalkit report <run>` | Rebuild report.html, junit.xml, results.jsonl, cost.json | no |
| `evalkit data` | Rebuild the synthetic database and check it against every case | no |
| `evalkit eval --case <id> [--trials N] [--yes]` | Run named cases against the AI system | with `--yes` |
| `evalkit gate [--yes]` | The release gate: all 70 critical cases × 3 runs | with `--yes` |
| `evalkit full [--yes]` | All cases, with the advisory LLM judges | with `--yes` |
| `evalkit lab --variant LAB-n --case <id> [--yes]` | Training bug hunt against a seeded defect | with `--yes` |

Every command that calls a model is a **dry run** until you add `--yes`. The dry run shows how many runs and what they
will cost. One live golden case costs about $0.04.

Prefix every command with `uv run --frozen`. `make` targets exist too.

---

## The five-stage evaluation cycle in this repository

The SOP (section 3.1) defines five stages. Here is where each one lives in this repository, using the KYC example.

| Stage | What you do | In this repository |
|---|---|---|
| **1. Understand the requirements** | Describe each agent, its tools, rules and expected outcomes | Templates T-01–T-04 · [`projects/kyc_onboarding/agents.yaml`](projects/kyc_onboarding/agents.yaml), `tools/specs/`, `policies/` |
| **2. Design scenarios and cases** | Pick the level, write cases per pattern, pair injection and fairness cases, choose a reference path | Templates T-05–T-09 · 110 case files in [`projects/kyc_onboarding/datasets/`](projects/kyc_onboarding/datasets/) · [case guide](projects/kyc_onboarding/datasets/README.md) |
| **3. Generate synthetic data** | Add personas, documents and fault profiles, rebuild, check | [`projects/kyc_onboarding/data/`](projects/kyc_onboarding/data/) · `evalkit data` |
| **4. Execute and evaluate** | Dry-run, run with k trials, grade every trajectory | `evalkit eval / gate / full`, reports in the run folder |
| **5. Analyse and improve** | Start at the verdict, compare expected vs actual, triage, one defect per root cause | `report.html` · Template T-12, T-13, T-14 · [`docs/tester_guide.md`](docs/tester_guide.md) |

What the harness checks on every run:
- **End state and path:** right outcome, right steps, right order (TR family).
- **Tool use:** right tools, valid and grounded arguments, safe fault handling, figures that match tool output (TU
  family).
- **BFSI controls:** PII masking, AML escalation, injection resistance, AI disclosure, fairness, audit trail (BF
  family).
- **Each agent's own scorecard** (AG-1 to AG-6).

Metric definitions: [`docs/methodology/metrics_catalogue.md`](docs/methodology/metrics_catalogue.md).

---

## Repository structure

```
AgenticAI-evaluation-/
├── SOP and Training Pack/                SOP, job aids, worked examples, template pack   ← start here
├── UAT Mock results and visualisation/   125 mock results and the interactive page        ← then here
├── training/                             modules, exercises, bug-hunt lab, assessment
├── docs/                                 setup, architecture, tester guide, configuration, glossary, methodology
├── projects/
│   ├── kyc_onboarding/                   the reference KYC system, its cases, rules, synthetic data
│   ├── _template/                        starting point for a new project (in progress)
│   └── demo_second/                      replication demo (in progress)
├── evalkit/                              the reusable evaluation harness (Python)
├── configs/                              models, run modes, release gates, judges, PII recognisers
├── tests/                                the harness's own tests
├── prompts/claude_code/                  notes on how parts of the code were generated
├── .github/workflows/                    CI: checks on push, the release gate on pull requests, nightly full run
└── runs/                                 run output (not committed)
```

Every file explained: [`docs/file_reference.md`](docs/file_reference.md). Architecture:
[`docs/architecture.md`](docs/architecture.md). Evaluating your own agents: [`docs/extension_guide.md`](docs/extension_guide.md).

---

## Status and known limits

- **The harness covers levels L1–L3.** The L4 UI-application level, run through a .NET frontend, is defined in the SOP
  and job aids. The worked example includes 20 L4 cases, but this repository has no frontend to run them against.
- **Two catalogue versions.** The harness runs the 110 cases of catalogue v0.12. The worked-example workbook is
  catalogue v0.13 (119 backend cases plus the L4 cases).
- **Human in the loop.** The reference system implements the approval step only. Of the 54 HITL cases in the HITL
  worked example, 10 run on it today; the rest are marked *Proposed* with the capability they need.
- **Unvalidated S1 results.** The policy rules and critical expectations were reviewed by the QE Lead but not yet
  validated by a compliance expert, so critical results are reported as *unvalidated*.
- **Templates in progress.** `projects/_template/` and `projects/demo_second/` are placeholders for the next work
  package.

---

## Best practices

- **Read the SOP before writing cases.** The rules for levels, severities and match modes are there.
- **Test lower before higher:** L1 → L2 → L3 → L4.
- **Never judge on reply text alone.** Check the end state and the path.
- **Run critical cases three times.** One pass proves little for a system that is not deterministic.
- **Rule out the test before blaming the agent.** Check the expectation, the data and the evaluator first.
- **Keep the rulebook human.** The person who built the agent does not write its expected results.
- **Dry-run before every paid run,** and agree a budget.
- **Synthetic data only,** including in screenshots and defect reports (JA-5).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| The visualisation page shows no tests | Use **Load a results file…** and pick `mock_test_results.json` from the same folder |
| `ANTHROPIC_API_KEY is not set` | Only live runs need it; add it to `.env` |
| A `.venv` folder appears in a synced folder | Set `UV_PROJECT_ENVIRONMENT` outside it and open a new terminal |
| Files locked or slow during runs | Set `EVALKIT_RUNS_DIR` to a local folder |
| Gate says `INCOMPLETE` | A threshold had nothing to measure, usually a missing expectation. See the gate table in report.html |
| `lint-cases` errors | Each line says what is wrong and how to fix it |

More: [`docs/setup.md`](docs/setup.md#troubleshooting).

---

## Contributing

Contributions are welcome: new evaluators, adapters for other agent frameworks, new BFSI controls, test cases,
training material.

1. Open an issue first for anything larger than a fix.
2. Tests first: every evaluator needs a test that passes on a good run and fails on a bad one.
3. Keep `evalkit/` independent of any project.
4. Do not change the human-owned rulebook (policy files, gate thresholds, critical expectations, the lab answer key)
   without the owner's review.
5. Synthetic data only.
6. Before a pull request, run:
   ```bash
   uv run --frozen ruff check .
   uv run --frozen evalkit test
   uv run --frozen evalkit lint-cases
   ```

## Licence

[MIT](LICENSE) © 2026 ChaitanyaShahare.
