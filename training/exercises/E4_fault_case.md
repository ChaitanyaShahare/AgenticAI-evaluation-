# E4 — Add a fault-injection case for an untested tool (M3, M6 · 45 min)

The fault profiles FP-01 … FP-12 cover ten tools. Three tools have no fault case at all.

1. Find them: list the tools that appear in `projects/kyc_onboarding/tools/specs/` and the tools named by the fault
   profiles (catalogue sheet *Mocks & Faults*, or the `fixtures:` of the cases in `datasets/faults/`).
2. Choose the one whose failure would hurt onboarding most, and say why.
3. Design the case: which fault (timeout, HTTP 500, malformed, empty, slow), which attempt(s), which level, which
   applicant. A new fault profile (FP-13) is a fixture: write its definition for the QE Lead to add — do not edit the
   database.
4. Write the case YAML in `datasets/faults/` (new `KYC-FLT-<NNN>`), with the expected handling: retries allowed, what
   the agent's output must say, and the end state if it is an L3 case. Use the decision table: which D-rule applies?
5. Lint it. (Until the QE Lead adds FP-13, lint will report the unknown fixture — that is expected.)

Answers: `expected_answers.md › E4`.
