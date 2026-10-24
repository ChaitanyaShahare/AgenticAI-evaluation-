# Assessment (M4, D27 · Tue 17 Nov)

Each tester, working alone, on the six lab variants and the case suite. Pass bar (SOP §6.4, milestone M4):
**at least 5 of the 6 seeded defects caught, and 10 valid new cases written.**

## Part A — Bug hunt (6 variants)

For each variant LAB-1 … LAB-6, submit the per-variant report described in `training/lab/README.md`.

A variant counts as **caught** when all three hold:
1. a submitted case fails at least one S1 or S2 check in a run of that variant, and the same case passes those checks
   on the normal system;
2. the failing checks are named as in the report (metric and rule), with the evidence step;
3. the agent is named correctly, and the explanation describes the defect's behaviour (the exact wording does not
   matter).

A correct agent and behaviour with a check failure on a different case still counts. A failure caused by a bad case
(RC-TST) does not.

## Part B — 10 new cases

Ten new case files, written by you, in `projects/kyc_onboarding/datasets/`. A case is **valid** when:
- `uv run --frozen evalkit lint-cases` shows no error for it;
- it tests one behaviour, and its title says situation → expected result;
- its expectation follows the decision table and the policy rules (the QE Lead checks the S1 ones);
- it is not a copy of an existing case with only the ID changed;
- across the ten, at least four patterns and at least three agents are covered, including at least one L1 case and one
  case that would catch one of the lab defects.

Cases found invalid may be fixed once, within the assessment day.

## Part C — Triage question (formative, not part of the pass bar)

The QE Lead gives you one failing run from the normal system. Classify each failure as agent, mock, case or evaluator
defect, with the RC code.

## Time and budget

One working day. API budget per tester: set by the QE Lead before the day (for example 40 trials). Dry-run first.

## Marking

The QE Lead marks with `scoring_sheet.md` and the restricted answer key, and returns the result with feedback. A
tester below the bar repeats the missed variants after a review session in the buffer (D28–D30).
