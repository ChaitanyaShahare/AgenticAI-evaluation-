"""results.jsonl: one row per case × trial × check, with the evidence step (trial 0 = case-level checks such as TR-7).

Rows hold only check verdicts and details, which name identifiers masked (evaluators never quote a full PAN, Aadhaar or
card number). The HTML and JUnit reports (WP8) read this file.
"""

from __future__ import annotations

import json
from pathlib import Path

from evalkit.schema import CaseResult, CheckResult


def write_results(path: Path, results: list[CaseResult], case_checks: dict[str, CheckResult], run_id: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in results:
            for c in r.checks:
                fh.write(
                    json.dumps({"run_id": run_id, "case_id": r.case_id, "trial": r.trial, **c.model_dump()}, ensure_ascii=False) + "\n"
                )
        for case_id, c in case_checks.items():
            fh.write(json.dumps({"run_id": run_id, "case_id": case_id, "trial": 0, **c.model_dump()}, ensure_ascii=False) + "\n")
    return path
