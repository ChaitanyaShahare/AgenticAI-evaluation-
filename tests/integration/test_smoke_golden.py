"""M1 exit check: the 10 golden cases run end to end on the real models and reach the catalogue's end state.

Live API calls (marker `api`): run with `uv run evalkit test --with-api`. Skipped when no ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3

import pytest

from evalkit.config import load_env, repo_root
from projects.kyc_onboarding.sut.run import run_case

ROOT = repo_root()
SEED = ROOT / "projects" / "kyc_onboarding" / "data" / "kyc_synthetic.sqlite"
load_env(ROOT)
GOLDEN = [
    r
    for r in sqlite3.connect(SEED).execute(
        "SELECT case_id, expected_status, expected_tier, expected_reasons_json, expected_record FROM test_cases "
        "WHERE run_sets LIKE '%smoke%' ORDER BY case_id"
    )
]

pytestmark = [pytest.mark.api, pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")]


@pytest.mark.parametrize("case_id,status,tier,reasons,record", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_golden_case_end_state(tmp_path, case_id, status, tier, reasons, record):
    db = tmp_path / "trial.sqlite"
    shutil.copy2(SEED, db)
    run = run_case(db, case_id, run_id="m1", trial=1)
    row = run.registry.ctx.one(
        "SELECT status, risk_tier, reason_codes_json, record_id FROM applications WHERE application_id = ?",
        (run.registry.ctx.application_id,),
    )
    assert row["status"] == status, run.state.get("decision")
    if tier:
        assert row["risk_tier"] == tier
    assert sorted(json.loads(row["reason_codes_json"])) == sorted(json.loads(reasons or "[]"))
    assert (row["record_id"] is not None) == bool(record)
