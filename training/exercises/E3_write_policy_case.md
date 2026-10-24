# E3 — Write a case from a policy clause (M3, M6 · 45 min)

**Clause:** "Any PEP hit requires enhanced due diligence; no account may be opened."

1. Decide the level, pattern, severity, trials and run sets.
2. Pick an applicant whose PEP check returns a hit (catalogue sheet *Watchlists*, or an existing case that uses one).
3. Write the case YAML in `datasets/edge/` with a new ID (`KYC-EDG-<NNN>`, unused), including:
   `rule_refs`, `reference` and `match_mode`, `required_tools`, `forbidden_tools`, `expected_outcome` in words and the
   structured `expected` (status, tier, record, reason codes).
4. Run `uv run --frozen evalkit data` and `uv run --frozen evalkit lint-cases` until there are no errors.
5. Dry-run it: `uv run --frozen evalkit eval --case <your ID>`.
6. List the checks you expect it to exercise.

Compare with your partner, then with `expected_answers.md › E3`. Your S1 expectation is a draft until the QE Lead
accepts it.
