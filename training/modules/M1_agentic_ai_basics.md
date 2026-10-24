# M1 — Agentic AI basics (2 h)

**You will be able to:** explain what an agent, a tool and a trajectory are; name the five KYC agents and what each
owns; say why checking only the final answer misses compliance failures.

## 1. Agents and tools (30 min)

An **agent** is a language model in a loop: it reads a task, decides on an action, calls a **tool** (a function with a
JSON schema), reads the result and decides again, until it submits a result. A **multi-agent system** splits the work:
a **Supervisor** plans and talks to the customer; **specialists** each do one job with their own tools.

| Agent | Job | Its tools | It writes |
|---|---|---|---|
| Supervisor | plans, delegates, applies the decision table D1–D10, talks to the customer | request_customer_info, escalate_to_edd, create_customer_record, finalize_application, hand-offs | decisions, replies |
| Document extraction | reads the uploaded documents | classify_document, extract_document | `profile` |
| Identity verification | checks PAN, CKYC and address proof | verify_pan, ckyc_lookup, check_address_proof | `identity` |
| Sanctions / PEP screening | screens against watch lists | sanctions_screen, pep_check | `screening` |
| Risk rating | scores onboarding risk with the pinned policy | fetch_risk_policy, compute_risk_score | `risk` |

Every tool belongs to exactly one agent (`x-agent` in its spec); a call by any other agent is an S1 failure (F4, TU-7).
Tools are mocks over synthetic data: nothing here touches a real registry or a real customer.

Two design facts that matter for testing:
- **The model chooses tools and arguments; code builds the agent's output from what the tools returned.** So a
  specialist cannot "decide" a match — but it can fail to call a tool, call it wrongly, or call it too often.
- **Creating the customer record needs a human approval.** The graph stops, the (mock) approver answers, and only
  an approval token issued at that step lets `create_customer_record` succeed.

## 2. What a trajectory contains (30 min)

A **trajectory** is the ordered record of one run. Every step has an index, a kind and the agent that produced it:

| Kind | What it is |
|---|---|
| `llm` | a model call (model, effort, tokens) |
| `decision` | the Supervisor's chosen action, with its reason |
| `tool` | a tool call: arguments, status (`ok` / `error` / `timeout`), result, attempt number, injected fault |
| `handoff` | the Supervisor passing control to a specialist |
| `agent_result` | a specialist's validated output |
| `interrupt` | the approval step (decision, token) |
| `message` | what the customer was told |
| `guard` / `contract` | a hard limit fired in code / an output that broke its contract |

The **end state** is what the system of record says afterwards: `applications.status` (APPROVED, PENDING_INFO,
PENDING_EDD, REJECTED), risk tier and score, record ID, reason codes.

## 3. Why outcome-only testing fails (20 min)

Two runs can end in the same correct state while only one is compliant:
- the account is approved, but the risk score was computed before screening returned → precedence rule P3 broken;
- the application ends `PENDING_EDD` as expected, but the Supervisor tried to create a record after a PEP hit and was
  only stopped because the approver said no → forbidden rule F1 broken (SOP §5.2, worked example).

That is why every run is graded on its path (TR, TU), its BFSI controls (BF) and **every agent's own slice** (AG),
not just its end state.

## 4. Hands-on: walk one real run (40 min)

Open `projects/kyc_onboarding/recorded_runs/live/KYC-GLD-001.json` (a real model run of the golden case, 51 steps),
or build its report: `uv run evalkit report projects/kyc_onboarding/recorded_runs/live --out <a folder>`. Then do
exercise **E1** (`training/exercises/E1_read_a_trajectory.md`).

## Check yourself

1. Which agent may call `compute_risk_score`? What happens if the Supervisor calls it?
2. Where in a trajectory do you find the approval token, and why does its origin matter?
3. Give one failure that a correct end state would hide.
