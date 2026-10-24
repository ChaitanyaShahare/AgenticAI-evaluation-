# M6 — Writing cases in YAML (2 h)

**You will be able to:** write a valid case file from a policy clause, pass `lint-cases`, and add it to coverage.

Reference: `projects/kyc_onboarding/datasets/README.md` (every field), `docs/tester_guide.md › Writing a case`.

## 1. Anatomy of a case (30 min)

Open `datasets/edge/KYC-EDG-014.yaml` side by side with this list.

| Group | Fields | Read by the harness? |
|---|---|---|
| Identity | `case_id`, `title`, `pattern`, `level`, `primary_agent`, `severity` | ID, pattern, level, severity: yes |
| Running | `trials`, `run_sets` | yes — S1: 3 trials, `[gate, full]` |
| Setup | `applicant`, `documents`, `customer_turns`, `mocks`, `fixtures`, `approver`, `form_updates` | IDs, fixtures, approver: yes; mocks text: no |
| Path | `expected_trajectory`, `reference`, `match_mode`, `required_tools`, `forbidden_tools` | all but the text |
| Outcome | `expected_outcome` (words), `expected` (structured) | `expected` only |
| Links | `rule_refs`, `checks`, `twin_pair` | twins: yes |

The words (`expected_outcome`, `expected_trajectory`) are for people; the structured fields are what checks compare.
They must agree — lint flags common contradictions.

## 2. Write one (45 min)

Follow the five steps (copy → edit setup → state the expectation → `evalkit data` + `evalkit lint-cases` → dry run).
Rules:
- Use applicants, documents and fixture profiles that exist. A new persona, document or fault profile is added by the
  QE Lead (fixtures are code, and the seed database is rebuilt from them).
- S1 expectations are drafted by you and **reviewed and accepted by the QE Lead**.
- Never paste a real identifier. Synthetic PANs are in the ZQ / ZX series.

## 3. Lint until clean (25 min)

`uv run --frozen evalkit lint-cases` explains every problem and its fix (`ERROR` must be fixed; `--all` adds notes a
reviewer checks by hand). Common first-timer errors: file name ≠ `case_id`; pattern ≠ folder; S1 with 1 trial; a tool
name misspelt; an applicant or document that does not exist; `twin_pair` naming a missing case.

Then `uv run --frozen evalkit coverage` — your case appears in the matrix.

## 4. Review checklist (20 min)

Swap cases with your partner and check:
- [ ] One behaviour per case; the title says situation → expected result.
- [ ] The expectation follows the decision table (D1–D10) and the reason codes exist.
- [ ] Required and forbidden tools match the expected path.
- [ ] The match mode fits (M3).
- [ ] Severity and trials fit (S1 → 3 trials, gate and full).
- [ ] Twins or pairs exist when the pattern needs them.
- [ ] `lint-cases` is clean.

Exercises **E3**, **E4** and **E5** each produce a case.

## Check yourself

1. Which fields does TR-1 read? Which does AG-1 read?
2. You need a document with a planted instruction that does not exist yet. Who adds it and how?
3. Lint says "trials: S1 cases run 3 trials". What do you change?
