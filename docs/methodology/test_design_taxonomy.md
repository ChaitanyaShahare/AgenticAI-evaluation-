# Test design taxonomy

Levels, patterns, the case ID scheme and coverage targets. Source: SOP-AIEVAL-001 §3.2 and §3.8, and the KYC suite as
it stands (110 cases, catalogue v0.12; counts from `evalkit coverage` on 24 Oct 2026).

## Evaluation levels

| Level | What is under test | How it is isolated | Primary metrics | KYC cases |
|---|---|---|---|---|
| L1 agent (unit) | one specialist, or the Supervisor alone | the agent node with a fixed task message and mocked tools; a Supervisor case starts from canned specialist state | AG-1 … AG-6 | 33 |
| L2 hand-off | Supervisor routing and state passing | full graph with stubbed specialists returning canned (also invalid, incomplete or out-of-slice) contracts | TR-5, AG-4, SLICE-1 | 6 |
| L3 end to end | the whole system from the customer's turn to the end state | full graph, mocked tools, scripted customer and mock approver | TR, TU, BF, and AG-1 … AG-6 on every agent's slice | 70 |
| L1+L3 | one specialist case also run end to end | both of the above | both | 1 |

Every L3 run yields five per-agent scorecards as well as the end-to-end verdict. Rules about the whole onboarding run
apply to L2 / L3 cases and to L1 Supervisor cases; a specialist alone (L1) is judged by its guardrails and its
expected output.

## Patterns

| Pattern | Folder | Purpose | Design rule | SOP target | KYC cases |
|---|---|---|---|---|---|
| Golden path | `golden/` | baseline correctness | one per main outcome (approve, info needed, EDD, reject) | 20% | 10 |
| Per-agent isolation | `agent_unit/` | each specialist alone | fixed task, mocked tools, agent-level expectations | 15% | 19 |
| Paraphrase / variant | `paraphrase/` | robustness to wording | phrasings of a golden case, same expectations | 10% | 10 |
| Boundary / policy edge | `edge/` | thresholds and borderline rules | value at, just below and just above each threshold | 10% | 14 |
| Missing / ambiguous info | `missing_info/` | clarify instead of guess | remove one required input; expect request_customer_info | 8% | 8 |
| Tool fault injection | `faults/` | resilience | one fault per tool type: timeout, 5xx, malformed, empty, slow | 12% | 13 |
| Adversarial / injection | `adversarial/` | goal-hijack resistance | clean twin + injected twin; tool calls identical | 8% | 10 |
| Policy-violating request | `policy/` | refuse unauthorised actions | social engineering, authority claims, "skip checks" | 5% | 6 |
| PII / PCI handling | `pii/` | masking and minimisation | full identifiers in the input; scan outputs and logs | 6% | 6 |
| Counterfactual fairness pair | `fairness_pairs/` | invariance to protected attributes | two cases differing in one attribute only | 4% | 6 (3 pairs) |
| Multi-turn state | `multi_turn/` | memory and corrections | customer corrects or adds something mid-conversation | 2% | 2 |
| Hand-off / routing (L2) | `handoff/` | routing and state passing | stubs return canned, invalid, incomplete and out-of-slice contracts | by agent count | 6 |

## Case ID scheme

`KYC-<PATTERN>-<NNN>`; NNN is unique across the whole catalogue. Per-agent cases carry the agent:
`KYC-AGT-<AGENT>-<NNN>` (SUP, DOC, IDV, SCR, RSK). Fairness pairs are `KYC-FAIR-<NNN>a / b`.

| Prefix | Pattern | | Prefix | Pattern |
|---|---|---|---|---|
| GLD | golden path | | POL | policy-violating request |
| AGT-<AGENT> | per-agent isolation | | HND | hand-off / routing |
| EDG | boundary / policy edge | | FAIR | fairness pair |
| FLT | tool fault injection | | MIS | missing information |
| ADV | adversarial / injection | | MTN | multi-turn state |
| PII | PII / PCI handling | | PAR | paraphrase |

## Severity and trials

| Severity | Use for | Trials | Run sets |
|---|---|---|---|
| S1 | compliance, privacy, security, unauthorised action | 3 (pass^k) | gate, full |
| S2 | wrong outcome or tool use without a compliance breach | 1 | full |
| S3 | efficiency or quality | 1 | full |

KYC: 70 S1 (26 L1, 1 L1+L3, 3 L2, 40 L3), 39 S2, 1 S3. Run sets: smoke 10 cases / 10 runs · gate 70 / 210 · full 110 /
250. The golden cases are in smoke with k = 1 for fast feedback; their S1 trials (k = 3) run in the gate.

## Coverage matrix (primary agent × pattern)

| Agent | Golden | Per-agent | Edge | Fault | Adversarial | PII | Policy | Hand-off | Fairness | Missing | Multi-turn | Paraphrase | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E2E | 10 | · | · | · | · | · | · | · | · | · | · | 5 | 15 |
| SUP | · | 3 | 1 | 2 | 6 | 4 | 3 | 6 | · | 4 | · | 5 | 34 |
| DOC | · | 6 | 3 | 2 | 3 | 2 | · | · | · | 1 | · | · | 17 |
| IDV | · | 2 | 2 | 4 | · | · | · | · | · | 1 | 2 | · | 11 |
| SCR | · | 4 | 4 | 3 | 1 | · | 2 | · | · | 1 | · | · | 15 |
| RSK | · | 4 | 4 | 2 | · | · | 1 | · | 6 | 1 | · | · | 18 |

Every agent has per-agent isolation and fault cases. `evalkit coverage` lists the gaps, and
`evalkit coverage --against-catalogue` compares the matrix with the workbook (equal on 24 Oct 2026).

## Oracle completeness (24 Oct 2026)

| Oracle | State |
|---|---|
| End state (`expected`) | all 110 cases |
| Reference trajectories RT-01 … RT-11 | written and reviewed by the QE Lead (23 Oct 2026) |
| Specialist outputs (`expected.agent_outputs`, AG-1) | 23 of the 24 S1 agent-level cases (KYC-PII-044 has no field to check) |
| Argument values (`expected.arguments`, TU-3) | none yet — TU-3 and the gate's TU-3 threshold are not measured |
| Conditional required / forbidden tools written in words | about 20 entries, checked by a reviewer, not by TU-1 |

## Choosing a match mode

Strict only where order is itself a control; unordered where independent reads may run in any order; superset for
exploratory or clarifying behaviour; subset where extra calls are a risk (write tools). Ordering that is a compliance
control is also enforced by precedence rules (TR-4), independent of the match mode. Decision table:
`docs/tester_guide.md › Choosing a match mode`.
