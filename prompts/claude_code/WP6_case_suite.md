# WP6 — test suite as YAML (23 Oct 2026)

## Request
> start WP6

Scope from EXECUTION_PLAN.md › WP6: catalogue import, loader, lint (plain-English errors), coverage, the 11 reference
trajectories, the tester README.

## Decisions
- The case YAML files are the source of truth for **both** the seed database's case tables and the harness, so a tester
  can add a runnable case with YAML alone (`evalkit data` rebuilds the tables). Proven by rebuilding the seed from the
  YAML: every table identical to the v0.12 seed.
- The import copies the catalogue; it does not interpret it. Structured fields follow fixed rules (run sets, documents
  with upload turn, fixture IDs, reference IDs, the end state read from the outcome text the same way the v0.12 builder
  did). Per-agent outputs and argument values are left empty for the QE Lead (S1 oracles are human-owned).
- The *Lab defect caught* column is never copied: it is the lab answer key and testers read the case files.
- Reference trajectories were expanded from the sheet's shorthand by a rule written into each file, and marked
  unreviewed.

## Produced
evalkit/datasets/{loader,catalogue_import,lint,coverage}.py, `evalkit cases` / `lint-cases` / `coverage`,
projects/kyc_onboarding/datasets/**/*.yaml (110), datasets/README.md, reference_trajectories/RT-01 … RT-11.json,
cases.py (YAML source + import hook), generate_kyc_db.py (case tables from YAML), project.yaml keys, docs, tests.
