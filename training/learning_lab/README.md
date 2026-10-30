# Learning lab: Agent Test Explorer

A self-contained page that shows how a multi-agent AI system is tested, for .NET and traditional QA engineers.

**Open it:** double-click `test_visualization.html`. It works offline; the 125 mock results are embedded. If the
built-in data is missing, use **Load a results file…** and pick `mock_test_results.json`.

**Use it:**
- The summary shows pass / fail / warn counts and the result mix per category.
- Filter by category tab, status or search text.
- Open a card for its data path, decision trail, expected vs actual trajectory, tool choices and assertions.
- The blue notes map each view to its .NET / QA equivalent; switch them off with **Show QA translations**.
- The glossary is at the bottom.

**Mock data.** The results are generated from the real case suite, not measured. Regenerate them with
`uv run --frozen python training/learning_lab/generate_mock_results.py`.
