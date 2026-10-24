"""KYC case source: the case YAML files under datasets/ (one per catalogue row, plus any a tester adds).

The YAML files are the source of truth for the cases. `evalkit data` builds the seed database's case tables from them,
so the runner and the evaluators read the same definition.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from evalkit.config.loader import load_project_config
from evalkit.datasets.loader import load_cases
from evalkit.schema import TestCase

HERE = Path(__file__).resolve().parent
SEED = HERE / "data" / "kyc_synthetic.sqlite"


def list_cases() -> list[TestCase]:
    return load_cases(HERE, load_project_config(HERE / "project.yaml"))


def import_extras(case_ids: list[str], seed_db: Path = SEED) -> dict[str, dict]:
    """`evalkit cases` hook: setup the workbook does not hold — the form fields the scripted customer supplies on request
    (kept in the seed database since v0.12)."""
    if not seed_db.is_file():
        return {}
    con = sqlite3.connect(f"file:{seed_db}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT case_id, form_updates_json FROM test_cases WHERE form_updates_json IS NOT NULL").fetchall()
    finally:
        con.close()
    return {cid: {"form_updates": json.loads(fu)} for cid, fu in rows if cid in set(case_ids)}
