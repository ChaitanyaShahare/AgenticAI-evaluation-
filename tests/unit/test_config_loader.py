"""Configuration loading: the shipped files are valid, and mistakes produce readable messages."""

from __future__ import annotations

import pytest
import yaml

from evalkit.config import ConfigError, load_eval_config, load_project_config, runs_dir
from evalkit.config.loader import repo_root

ROOT = repo_root()
EVAL = ROOT / "configs" / "eval.yaml"


def _eval_text(**changes) -> str:
    data = yaml.safe_load(EVAL.read_text(encoding="utf-8"))
    for dotted, value in changes.items():
        node = data
        *path, last = dotted.split("__")
        for k in path:
            node = node[k]
        if value is None:
            node.pop(last)
        else:
            node[last] = value
    return yaml.safe_dump(data)


def test_shipped_eval_config_is_valid_and_matches_requirements():
    cfg = load_eval_config()
    assert cfg.models.supervisor == "claude-sonnet-5-5"
    assert cfg.models.specialist == "claude-haiku-5-5"
    assert (cfg.effort.supervisor, cfg.effort.specialist, cfg.effort.judge) == ("medium", "low", "high")
    assert cfg.refusal_fallback is False
    assert cfg.determinism.as_of == "2026-11-02" and cfg.determinism.seed == 42
    assert cfg.determinism.risk_policy_version == "v3"
    assert cfg.retry_limit == 2 and cfg.max_steps_per_run == 25


def test_trials_per_severity_and_mode():
    cfg = load_eval_config()
    assert cfg.trials_for("S1", "gate") == 3
    assert cfg.trials_for("S2", "gate") == 1
    assert cfg.trials_for("S1", "smoke") == 1  # smoke is fast feedback; k = 3 happens in gate


def test_shipped_project_config_is_valid():
    p = load_project_config(ROOT / "projects" / "kyc_onboarding" / "project.yaml")
    assert p.project == "kyc_onboarding"
    assert (ROOT / "projects" / "kyc_onboarding" / p.data.seed_db).is_file()
    assert (ROOT / "projects" / "kyc_onboarding" / p.data.checker).is_file()


def test_typo_key_is_named(write_yaml):
    data = yaml.safe_load(EVAL.read_text(encoding="utf-8"))
    data["max_tokns"] = data.pop("max_tokens")
    with pytest.raises(ConfigError) as e:
        load_eval_config(write_yaml(yaml.safe_dump(data)))
    msg = str(e.value)
    assert "max_tokns: unknown key — check the spelling" in msg
    assert "max_tokens: Field required" in msg


def test_sampling_parameters_are_rejected_with_the_reason(write_yaml):
    data = yaml.safe_load(EVAL.read_text(encoding="utf-8"))
    data["temperature"] = 0
    with pytest.raises(ConfigError) as e:
        load_eval_config(write_yaml(yaml.safe_dump(data)))
    assert "sampling parameters are rejected by the current Claude API" in str(e.value)


def test_bad_value_is_explained(write_yaml):
    with pytest.raises(ConfigError) as e:
        load_eval_config(write_yaml(_eval_text(budget__alert_at=[50, 80])))
    assert "fractions of the budget" in str(e.value)


def test_bad_date_is_rejected(write_yaml):
    with pytest.raises(ConfigError) as e:
        load_eval_config(write_yaml(_eval_text(determinism__as_of="02/11/2026")))
    assert "determinism.as_of" in str(e.value)


def test_broken_yaml_reports_line(write_yaml):
    with pytest.raises(ConfigError) as e:
        load_eval_config(write_yaml("version: 1\nmodels: [unclosed\n"))
    assert "not valid YAML" in str(e.value) and "line" in str(e.value)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="file not found"):
        load_eval_config(tmp_path / "nope.yaml")


def test_environment_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALKIT_RUNS_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("EVALKIT_MAX_WORKERS", "2")
    cfg = load_eval_config()
    assert cfg.execution.max_workers == 2
    assert runs_dir(cfg) == tmp_path / "out"


def test_bad_environment_override(monkeypatch):
    monkeypatch.setenv("EVALKIT_MAX_WORKERS", "four")
    with pytest.raises(ConfigError, match="whole number"):
        load_eval_config()
