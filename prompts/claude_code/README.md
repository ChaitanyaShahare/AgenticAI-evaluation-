# Claude Code prompts

Prompts used to generate code or fixtures are kept here, so a replication team can regenerate the same artefacts for its own domain.

| File | Work package | Produced |
|---|---|---|
| — | WP1 | Scaffold written interactively in the planning session of 23 Oct 2026: pyproject.toml, Makefile, configs/eval.yaml, evalkit/cli.py, evalkit/config/loader.py, tests for both, CI skeleton. No separate prompt file. |
| `WP5_evaluators.md` | WP5 | Evaluators, policy engine, scoring, gates, agents.yaml, PII recognisers, evaluator tests. Policy YAML, gates thresholds and S1 expectations deliberately not generated. |
| `WP6_case_suite.md` | WP6 | Case YAML import, loader, lint, coverage, reference trajectories, tester guide. Per-agent / argument oracles and the lab key deliberately not generated. |
| `WP7_judges.md` | WP7 | Rubric judges, cache, calibration, `grade --judges`, `calibrate`. Rubric anchors quoted from the SOP; pricing not guessed; no live calls. |
| — | WP8 | Reports, cost and CI written interactively ("start WP8"); no separate prompt file. |
| `WP9_docs.md` | WP9 | docs/setup, architecture, tester_guide, extension_guide, glossary, config_reference (completed), docs/methodology/*, projects/kyc_onboarding/README.md, docs/sop/SOP_v1.0_change_list.md. Regulatory mapping and the SOP .docx deliberately not written. |
| `WP10_lab.md` | WP10 | Seeded-defect switches, `evalkit lab`, seeded-defect and lab tests, training modules, exercises, assessment. The lab answer key was transcribed verbatim from the catalogue on the QE Lead's request; it was not generated. |
| `learning_lab.md` | — | Agent Test Explorer: mock results generator, interactive page and README, now in `UAT Mock results and visualisation/`. No oracle changed; mock data labelled as such. |

## Rules
- S1 expectations, policy YAML, gate thresholds and the lab answer key are **never** generated. They are written by the QE Lead from the Test Case Catalogue and the Agent Requirement sheet.
- Name each new file `WPn_<what>.md`, and record which files it produced in the table above.
