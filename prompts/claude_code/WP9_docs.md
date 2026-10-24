# WP9 — framework documentation (24 Oct 2026)

## Request

"START WP9" — EXECUTION_PLAN.md › WP9: update the SOP from v0.3 to v1.0 wherever the build differs; write the
architecture, setup, config reference, extension guide, tester guide and glossary; the methodology extracts (metrics
catalogue, rubrics, taxonomy, defect taxonomy, audit pack); `regulatory_mapping.yaml` and the project README.

## How it was done

- Facts were taken from the code and configuration (CLI `--help`, `evalkit/config/loader.py`, the registry, schema,
  gates, policy and judge files, `evalkit coverage`), not from SOP v0.3's design sketches. Where they differ, the doc
  follows the code and the difference is listed in `docs/sop/SOP_v1.0_change_list.md`.
- Thresholds, severities, rubric anchors, root-cause codes and rule summaries are transcribed from SOP v0.3, the
  catalogue and the human-owned YAML; no oracle was written or changed.
- Costs: only measured or dry-run figures are quoted; nothing is estimated from prices.

## Boundaries kept

- `policies/regulatory_mapping.yaml` is in `policies/`, which CLAUDE.md reserves for the QE Lead, and maps rules to
  regulatory clauses that must be confirmed by compliance. Left empty for the QE Lead's decision.
- The SOP Word document is the QE Lead's controlled document. On request ("apply every row … as tracked changes, saved as
  v0.4"), every change-list row was applied to a copy of v0.3 as Word tracked changes (author "Claude Code (for QE Lead
  review)"), with comments on the gap rows; v0.3 is unchanged. The edit was scripted on document.xml (tracked
  insert / delete runs, inserted paragraphs and table rows) and checked with the docx skill's validator, including
  the check that every text change is tracked.

## Side fix

`Makefile`: `make eval` ignored `CASE` / `TRIALS`; `eval`, `gate` and `full` now accept `YES=1`, and `report` takes `RUN`.
