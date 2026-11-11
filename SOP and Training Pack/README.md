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

- [Step 1 · The SOP and Training Pack](#step-1--the-sop-and-training-pack)
- [Step 2 · UAT mock results and visualisation](#step-2--uat-mock-results-and-visualisation)
- [Step 3 · Hands-on with the harness](#step-3--hands-on-with-the-harness)


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



# UAT mock results and visualisation: Agent Test Explorer

A self-contained page that shows how a multi-agent AI system is tested, for .NET and traditional QA engineers.

**Open it:** double-click `test_visualization.html`. It works offline; the 125 mock results are embedded. If the
built-in data is missing, use **Load a results file…** and pick `mock_test_results.json`.

**Use it:**
- The summary shows pass / fail / warn counts and the result mix per category.
- Filter by category tab, status or search text.
- Open a card for its data path, decision trail, expected vs actual trajectory, tool choices and assertions.
- The blue notes map each view to its .NET / QA equivalent; switch them off with **Show QA translations**.
- The glossary is at the bottom.

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
and **REJECTED**. Details: 
