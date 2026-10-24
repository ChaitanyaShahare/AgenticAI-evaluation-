# M3 — Evaluation design (3 h)

**You will be able to:** choose the level and pattern for a test idea; read the coverage matrix; pick a reference
trajectory and match mode; turn one policy clause into a set of cases.

Reference: `docs/methodology/test_design_taxonomy.md`, `docs/tester_guide.md › Writing a case`.

## 1. Levels (30 min)

| Level | Isolates | Use it to test | Example |
|---|---|---|---|
| L1 | one agent with mocked tools (Supervisor cases start from canned specialist state) | that agent's job and guardrail | KYC-AGT-SCR-056: near-match reported, not cleared |
| L2 | the Supervisor with stubbed specialists | routing and what it does with a bad, incomplete or out-of-slice output | KYC-HND-109: a specialist writes outside its slice |
| L3 | the whole system | end-to-end controls, decisions, replies | KYC-EDG-014: domestic PEP → EDD, no account |

Test an agent alone first (L1): a failure there points straight at the agent. L3 tells you the system is compliant
and still yields per-agent scorecards for all five agents.

## 2. Patterns and coverage (40 min)

The 12 patterns (golden, per-agent, edge, fault, adversarial, policy-violating, PII, fairness, missing info,
multi-turn, hand-off, paraphrase) each have a design rule — `docs/methodology/test_design_taxonomy.md`.

Run `uv run evalkit coverage` and read:
- the **agent × pattern matrix** — where is an agent thin?
- **level × severity** — S1 cases run 3 trials and are in the gate;
- **oracle completeness** — which cases still lack structured expectations (agent outputs, arguments).

## 3. Reference trajectories and match modes (40 min)

`reference_trajectories/RT-01 … RT-11` are the expected tool sequences for each outcome family (approved, EDD on a
hit, EDD on high risk, pending info …). A case names one (`reference`) and a **match mode**:

| Mode | Passes when | Use when |
|---|---|---|
| strict | same calls, same order | order is itself a control |
| unordered | same calls, any order | independent reads |
| superset | every reference call appears; extras allowed | clarifying questions or retries are fine |
| subset | no call outside the reference | extra calls are a risk (write tools) |

Precedence rules (TR-4) enforce compliance-critical order regardless of the match mode, so do not make a case strict
just to protect an order that a rule already protects. Exercise **E2**.

## 4. From a policy clause to cases (50 min)

Take a clause, e.g. *"a sanctions near-match escalates like a hit"* (D1). Ask:

1. **Where can it break?** The screening agent (doesn't report the near-match), the Supervisor (doesn't escalate),
   the reply (discloses the list). → one L1 screening case, one L3 case, a reply check.
2. **Boundaries?** Scores at 0.75, 0.749, 0.85 → three edge cases (value at, below, above).
3. **What must happen and what must not?** Required: escalate_to_edd, finalize_application. Forbidden:
   create_customer_record.
4. **Oracle:** end state PENDING_EDD with SCREENING_HIT; for L1 the screening output (`any_hit: true`,
   `near_matches.0.score`). S1 → the QE Lead reviews it.
5. **Twin or pair?** None here; an injection case needs its clean twin, a fairness case its partner.

Exercise **E3** applies this to "any PEP hit requires EDD; no account opening".

## Check yourself

1. You suspect the identity agent mishandles a DOB mismatch. Which level first, and why?
2. Two reads may run in either order, and a clarifying question is acceptable. Which match mode?
3. Name the three boundary values for the document quality threshold 0.70.
