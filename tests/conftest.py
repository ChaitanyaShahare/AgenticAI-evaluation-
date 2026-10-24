"""Shared fixtures for the framework's own tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from evalkit.config import repo_root

ROOT = repo_root()
KYC = ROOT / "projects" / "kyc_onboarding"


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture
def seed_db_copy(tmp_path: Path) -> Path:
    """A private copy of the KYC seed database, so a test can never modify the released one."""
    dst = tmp_path / "kyc_synthetic.trial.sqlite"
    shutil.copy2(KYC / "data" / "kyc_synthetic.sqlite", dst)
    return dst


@pytest.fixture
def write_yaml(tmp_path: Path):
    """Write a YAML string to a temporary file and return its path."""

    def _write(text: str, name: str = "eval.yaml") -> Path:
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        return p

    return _write


@pytest.fixture(autouse=True, scope="session")
def _private_runs_dir(tmp_path_factory):
    """Keep test runs, judge caches and the cost ledger out of the real runs folder."""
    import os

    old = os.environ.get("EVALKIT_RUNS_DIR")
    os.environ["EVALKIT_RUNS_DIR"] = str(tmp_path_factory.mktemp("runs"))
    yield
    if old is None:
        os.environ.pop("EVALKIT_RUNS_DIR", None)
    else:
        os.environ["EVALKIT_RUNS_DIR"] = old
