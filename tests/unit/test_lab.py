"""Bug-hunt lab plumbing (WP10): switches are off by default, cannot leak into a normal run, and the variant files given
to testers do not give the defect away. That each variant is caught is tests/lab/test_seeded_defects.py."""

from __future__ import annotations

import re

import pytest
import yaml

from evalkit import cli
from evalkit.config import ConfigError, repo_root
from evalkit.harness.runner import LAB_ENV, execute, make_plan
from projects.kyc_onboarding.sut.lab import defects

VARIANTS = repo_root() / "training" / "lab" / "variants"


def test_switches_are_off_by_default(monkeypatch):
    monkeypatch.delenv(LAB_ENV, raising=False)
    assert defects.active() == frozenset()


def test_unknown_switch_stops_the_run(monkeypatch):
    monkeypatch.setenv(LAB_ENV, "LAB-1, LAB-9")
    with pytest.raises(ValueError, match="LAB-9"):
        defects.active()
    monkeypatch.setenv(LAB_ENV, "LAB-1, LAB-4")
    assert defects.active() == {"LAB-1", "LAB-4"}


def test_a_normal_run_refuses_while_a_switch_is_set(monkeypatch):
    monkeypatch.setenv(LAB_ENV, "LAB-3")
    plan = make_plan("kyc_onboarding", case_ids=["KYC-GLD-001"], trials=1, run_id="guard-test")
    with pytest.raises(ConfigError, match="Only `evalkit lab` may set it"):
        execute(plan, client_factory=lambda c, t: pytest.fail("must not run"), progress=lambda _m: None)


def test_lab_dry_run_names_the_variant_and_clears_the_switch(capsys, monkeypatch):
    monkeypatch.delenv(LAB_ENV, raising=False)
    assert cli.main(["lab", "--variant", "LAB-3", "--case", "KYC-PII-042"]) == 0
    out = capsys.readouterr().out
    assert "variant LAB-3" in out and "run lab-LAB-3-" in out and "dry run — no model calls made" in out
    assert LAB_ENV not in __import__("os").environ


def test_lab_needs_cases_and_a_known_variant(capsys):
    assert cli.main(["lab", "--variant", "LAB-3"]) == 2
    assert "--case" in capsys.readouterr().out
    assert cli.main(["lab", "--variant", "LAB-9", "--case", "KYC-GLD-001"]) == 1
    assert "No lab variant 'LAB-9'" in capsys.readouterr().err


@pytest.mark.parametrize("path", sorted(VARIANTS.glob("LAB-*.yaml")), ids=lambda p: p.stem)
def test_variant_files_do_not_give_the_defect_away(path):
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert data["variant"] == path.stem and data["switches"] == [path.stem] and data["project"] == "kyc_onboarding"
    giveaways = r"pep|sanction|aadhaar|retr|score|injection|instruction|corporate|screening|identity|document agent|risk|mask"
    assert not re.search(giveaways, text, re.IGNORECASE), f"{path.name} hints at its defect"
