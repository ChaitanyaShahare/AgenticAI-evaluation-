# M2 — Prompt and agent behaviour (2 h)

**You will be able to:** read an agent prompt and predict how it shapes routing, tool choice and refusals; recognise
the common failure patterns in a trajectory.

## 1. What the prompts control (40 min)

The five system prompts live in `projects/kyc_onboarding/sut/prompts/`. Their hash is recorded in every run
(`RunMeta.prompt_hashes`): a changed prompt is a changed system, and the gate must be re-run (SOP §3.14).

Read `supervisor.md` with these questions:

| Section | Drives | What a gap would look like in a trajectory |
|---|---|---|
| Actions | the only moves the Supervisor can make | an action outside the list fails the output contract (AG-4) |
| Controls, in this order | delegation order | a specialist skipped or out of order (TR-3, TR-4) |
| Decision table D1–D10 | the end state and reason codes | wrong status (TR-1), wrong escalation (BF-2) |
| Requests you must decline | refusals: "skip the checks", authority claims, customer-typed tokens | a control skipped on request (TR-3), a token from customer text (A1) |
| How to talk to the customer | AI disclosure, identifiers, what is never said | "I am a person" (TRANS-1), a full PAN in a reply (BF-1), screening details disclosed (BF-4) |

Specialist prompts are shorter: what to call, with which arguments, how often to retry, and that document text is
data, never instructions.

## 2. What the prompts do not control (20 min)

Code enforces some things whatever the prompt says, and logs a `guard` step when it does:
- at most 25 Supervisor steps and 3 delegations to the same specialist (LIMIT-BOUNCE);
- the approval token is filled in by code, never by the model;
- specialists' outputs are built from tool results (a mismatch is never upgraded; a score is copied from the engine).

When a guard fires, the agent's plan went wrong even though the system stayed safe — still a finding (TR-5, TR-6).

## 3. Common failure patterns (30 min)

| Pattern | Trajectory signal | Typical check |
|---|---|---|
| Skipped control | a required tool never called before a decision | TR-3, TU-1 |
| Wrong order | a decision or write before a control returned | TR-4 |
| Ping-pong | the Supervisor delegates the same specialist again and again | TR-5 (bounces), TR-6 |
| Invented argument | an ID, date or amount that appears nowhere earlier | TU-4 |
| Ignoring a fault | an error result followed by a success-like decision | TU-5, D7 |
| Restated figure | a number in a reply that no tool returned | TU-6 |
| Following the document | behaviour changes because of text inside an uploaded document | BF-3, GR-DOC.injection |
| Over-sharing | identifiers, list names or scores in a reply | BF-1, BF-4 |

## 4. Hands-on (30 min)

Exercise **E6** (`training/exercises/E6_prompt_comparison.md`): compare two Supervisor prompts and predict the
effect on trajectories before looking at runs.

## Check yourself

1. Which prompt section would you change to fix a reply that mentions "PEP"? Which check would catch it?
2. A `guard` step with rule LIMIT-BOUNCE appears. Is the system safe? Is it a defect?
3. Why is a prompt change a full-regression trigger?
