"""The command line: every planned command is registered, and data rebuilds never damage the seed database."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3

import pytest

from evalkit import cli
from evalkit.config import repo_root

ROOT = repo_root()


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    for name in ["doctor", "data", "test", "smoke", "eval", "run", "gate", "grade", "report", "full", "calibrate", "lab", *cli.PLANNED]:
        assert name in out


def test_planned_commands_say_when_they_arrive(capsys, monkeypatch):
    monkeypatch.setitem(cli.PLANNED, "future", ("WP99", "1 Jan", "do something later"))
    assert cli.cmd_planned(cli.argparse.Namespace(command="future")) == 2
    out = capsys.readouterr().out
    assert "not built yet" in out and "WP99" in out


def test_unknown_project_is_a_readable_error(capsys):
    assert cli.main(["data", "--check-only", "--project", "nope"]) == 1
    assert "Project 'nope' not found" in capsys.readouterr().err


def test_data_check_only_passes_on_released_seed():
    assert cli.main(["data", "--check-only"]) == 0


@pytest.mark.slow
def test_data_rebuild_is_identical_and_keeps_seed_when_check_fails(tmp_path, monkeypatch):
    """Rebuild in a sandboxed copy of the project: the result equals the released seed, and a failing check leaves it untouched."""
    sandbox = tmp_path / "repo"
    (sandbox / "evalkit").mkdir(parents=True)
    shutil.copy2(ROOT / "pyproject.toml", sandbox / "pyproject.toml")
    for folder in ("data", "datasets"):
        shutil.copytree(ROOT / "projects" / "kyc_onboarding" / folder, sandbox / "projects" / "kyc_onboarding" / folder)
    shutil.copy2(ROOT / "projects" / "kyc_onboarding" / "project.yaml", sandbox / "projects" / "kyc_onboarding" / "project.yaml")
    monkeypatch.setattr(cli, "repo_root", lambda: sandbox)
    seed = sandbox / "projects" / "kyc_onboarding" / "data" / "kyc_synthetic.sqlite"

    def content(p):
        con = sqlite3.connect(p)
        tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY 1")]
        h = hashlib.sha256()
        for t in tabs:
            for row in sorted(map(repr, con.execute(f'SELECT * FROM "{t}"'))):
                h.update(row.encode())
        con.close()
        return h.hexdigest()

    before = content(seed)
    assert cli.main(["data"]) == 0
    assert content(seed) == before  # deterministic rebuild with --background-from

    # Corrupt a case's expectation (case YAML is the source since WP6): the rebuild must fail and leave the seed unchanged.
    case = sandbox / "projects" / "kyc_onboarding" / "datasets" / "edge" / "KYC-EDG-104.yaml"
    text = case.read_text(encoding="utf-8")
    assert "reason_codes: [DOC_EXPIRED]" in text, "KYC-EDG-104 changed; update this test's corruption"
    case.write_text(text.replace("DOC_EXPIRED", "DOC_MISSING"), encoding="utf-8")
    seed_bytes = seed.read_bytes()
    assert cli.main(["data"]) == 1
    assert seed.read_bytes() == seed_bytes
