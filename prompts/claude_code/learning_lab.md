# Learning lab — Agent Test Explorer (30 Oct 2026)

## Request

A learning artifact for .NET and traditional QA engineers, from the user:
- mock results for every test case, with data path, decision trail, trajectory, tool choices, expected vs actual,
  assertions, status, time and failure reason (`mock_test_results.json`);
- a self-contained `test_visualization.html` with a dashboard, category navigation, filters, expandable views,
  QA-equivalent callouts and a glossary;
- a README under 150 words.

The plan was approved first. The user chose:
- 110 agent cases plus about 15 framework unit tests;
- the golden and paraphrase cases as UAT;
- a realistic status mix of about 80 / 12 / 8;
- delivery as a repo folder plus a private page.

## How it was done

`UAT Mock results and visualisation/generate_mock_results.py` (first built in training/learning_lab/) derives every record from the real case YAML, the reference
trajectories, the tool specs and the synthetic seed database:
- **Statuses:** PASS cases follow the expected path. Each FAIL / WARN case gets exactly one named deviation, modelled
  on the seeded lab defects and known failure modes.
- **Consistency:** the data path, decision trail, tool choices, trajectory score and assertions are all computed from
  that one actual path, so they agree.
- **Reproducible:** the seed is fixed.
- **Labelled as mock:** the JSON metadata and the page banner say so, and confidence values are labelled
  illustrative.

## Boundaries kept

- No oracle was changed; the generator only reads the case suite.
- No live calls were made.
