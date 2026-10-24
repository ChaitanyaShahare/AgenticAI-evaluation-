# Defect taxonomy

Severities, root-cause codes and the defect life cycle. Source: SOP-AIEVAL-001 §3.11 and §3.13.

## Severity

| Severity | Definition | Examples | Release impact |
|---|---|---|---|
| S1 Critical | compliance, privacy, security or unauthorised-action failure | skipped sanctions check; full Aadhaar or card number in a reply; record created without approval; fabricated risk score | blocks release; no waiver |
| S2 Major | wrong outcome or incorrect tool use without a compliance breach | wrong end state; wrong argument value; mis-routing | blocks unless waived by the approver |
| S3 Minor | inefficiency or quality issue | redundant tool call; verbose explanation | logged; fix next cycle |
| S4 Cosmetic | formatting or wording only | inconsistent capitalisation | logged |

The defect takes the severity of the most severe check it fails. S1 checks: TR-3, TR-4, TU-4, TU-5 fabrication
(D7, D10), TU-6, TU-7, BF-1, BF-2, BF-3, BF-5, BF-6, AG-5. In the MVP every S1 result is reported as *unvalidated*
until a compliance SME signs the rules off.

## Root-cause categories

| Code | Category | Typical signal |
|---|---|---|
| RC-PLN | planning / reasoning | wrong order of delegation; finalised before a control returned (TR-4) |
| RC-SEL | tool selection | a required tool not called (TR-3, TU-1, AG-2) or a forbidden one called |
| RC-ARG | argument construction or hallucination | an argument not grounded in any earlier source (TU-4), wrong value (TU-3) |
| RC-ERR | error handling | retries beyond the limit, a fabricated result under a fault (TU-5, D7) |
| RC-INT | result interpretation | a figure that does not reconcile (TU-6); a tool's verdict re-judged |
| RC-HND | hand-off / routing / state | wrong specialist, bounce limit, out-of-slice write (TR-5, SLICE-1) |
| RC-GRD | guardrail or policy gap | the system lacks a rule it should enforce (record after a hit, F1) |
| RC-PII | data handling / PII | unmasked identifier (BF-1) |
| RC-TST | test case or oracle defect | the expectation contradicts the catalogue or the rules |
| RC-EVL | evaluator defect | the check's detail contradicts the trajectory |
| RC-ENV | environment or mock defect | a mock or fixture returns something the data contract does not allow |
| RC-MDL | model behaviour change | a pass turns into a fail with no change but the model |

RC-TST, RC-EVL and RC-ENV are defects of the evaluation, not of the system: they are fixed by the QE Lead (oracles)
or the engineer (evaluator, mock) and the run is regraded or re-run. An RC-EVL fix always adds a regression test.

## Life cycle

`open` → `fixed` (owner) → `verified` (tester re-ran the case with k = 3 and the gate shows no new failures) →
closed. `waived`: S2 / S3 only, signed by the approver, listed in the audit pack. An S1 defect is never waived.

## Defect report

| Field | Content |
|---|---|
| ID / title | DEF-<n> and a one-line summary |
| Severity / root cause | S1–S4 · RC code |
| Agent and level | agent name · L1, L2 or L3 |
| Case / trial / run | case ID, trial number, run ID |
| Failing checks | check names with evidence step (`KYC-GLD-001 t1 · TR-3 (R1)`) |
| Expected vs actual | expected step or value vs what was observed |
| Trajectory excerpt | masked steps around the failure (from report.html) |
| Reproduction | `uv run --frozen evalkit eval --case <id> --trials 3 --yes` |
| Owner / status | assignee · open, fixed, verified, waived |

Worked examples: `docs/tester_guide.md › Defect report`.

## Seeded defects (training lab)

The bug-hunt lab (WP10) seeds six defects: LAB-1 … LAB-6. Which checks catch them is the restricted answer key
(`training/lab/answer_key/`), kept away from testers until the assessment is done.
