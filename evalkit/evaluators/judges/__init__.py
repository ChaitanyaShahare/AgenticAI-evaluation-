"""LLM judges (WP7): rubric judges on the anchored 0–3 scale, their result cache and their calibration."""

from __future__ import annotations

from pathlib import Path

from evalkit.config.loader import JudgesConfig, load_model, repo_root


def load_judges_config(root: Path | None = None) -> JudgesConfig:
    return load_model(JudgesConfig, (root or repo_root()) / "configs" / "judges.yaml")


def cache_folder(cfg: JudgesConfig, runs: Path | None = None) -> Path:
    """The judge cache: cache_dir inside the runs folder (EVALKIT_RUNS_DIR applies), or cache_dir itself if absolute."""
    from evalkit.config.loader import load_eval_config, runs_dir  # noqa: PLC0415

    p = Path(cfg.cache_dir)
    return p if p.is_absolute() else (runs or runs_dir(load_eval_config())) / p


def configured_rubrics(cfg: JudgesConfig) -> list:
    """The rubrics named in configs/judges.yaml, in that order. An ID without a rubric is a configuration error."""
    from evalkit.config.loader import ConfigError  # noqa: PLC0415
    from evalkit.evaluators.judges.deepeval_metrics import RUBRICS  # noqa: PLC0415

    unknown = [m.id for m in cfg.metrics if m.id not in RUBRICS]
    if unknown:
        raise ConfigError(f"configs/judges.yaml: no rubric for metric(s) {', '.join(unknown)} — use one of {', '.join(RUBRICS)}")
    return [RUBRICS[m.id] for m in cfg.metrics]
