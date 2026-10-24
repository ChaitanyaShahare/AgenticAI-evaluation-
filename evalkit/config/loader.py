"""Load and validate the harness configuration files.

Every model forbids unknown keys, so a typo in YAML fails loudly with the file, the key path and the reason
instead of being silently ignored. Testers edit YAML only, so these messages are written for them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

Severity = Literal["S1", "S2", "S3"]


class ConfigError(Exception):
    """A configuration file is missing or invalid. str(err) is safe to show to a tester."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------- configs/eval.yaml
class Models(_Strict):
    supervisor: str
    specialist: str
    judge: str


class Determinism(_Strict):
    as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    seed: int
    lists_version: str
    risk_policy_version: str


class RunSelect(_Strict):
    run_set: Literal["smoke", "gate", "full"]


class RunMode(_Strict):
    select: RunSelect
    trials: int | Literal["per_severity"]
    judges: bool
    target_minutes: int | None = None


class Execution(_Strict):
    max_workers: int = Field(ge=1, le=32)
    runs_dir: str


class ModelPrice(_Strict):
    """USD per million tokens. Null until checked against the current price list."""

    input: float | None = None
    output: float | None = None
    cache_read: float | None = None
    cache_write: float | None = None


class Budget(_Strict):
    monthly_limit_inr: float | None = None
    alert_at: list[float]
    usd_to_inr: float | None = None  # exchange rate used for the monthly budget (null: alerts cannot be evaluated)
    pricing: dict[str, ModelPrice] = {}  # model ID -> prices (cost.json); a model without prices makes the cost unknown

    @field_validator("alert_at")
    @classmethod
    def _fractions(cls, v: list[float]) -> list[float]:
        if any(not 0 < x <= 1 for x in v):
            raise ValueError("alert_at values are fractions of the budget, between 0 and 1 (for example 0.5)")
        return v


EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]
SAMPLING_KEYS = ("temperature", "top_p", "top_k")


class Effort(_Strict):
    supervisor: EffortLevel
    specialist: EffortLevel
    judge: EffortLevel


class EvalConfig(_Strict):
    version: int
    models: Models
    effort: Effort
    max_tokens: int = Field(ge=1024, le=128_000)
    refusal_fallback: bool
    prompt_caching: bool

    @model_validator(mode="before")
    @classmethod
    def _no_sampling(cls, data: Any) -> Any:
        if isinstance(data, dict) and (bad := [k for k in SAMPLING_KEYS if k in data]):
            raise ValueError(
                f"{', '.join(bad)}: sampling parameters are rejected by the current Claude API; "
                "pin determinism with 'effort', the fixed test clock and k trials instead"
            )
        return data

    max_steps_per_run: int = Field(ge=1)
    retry_limit: int = Field(ge=0)
    max_bounces_per_specialist: int = Field(ge=0)
    determinism: Determinism
    trials: dict[Severity, int]
    run_modes: dict[Literal["smoke", "gate", "full"], RunMode]
    execution: Execution
    budget: Budget

    def trials_for(self, severity: Severity, mode: str) -> int:
        """Number of trials for a case of this severity in this run mode."""
        t = self.run_modes[mode].trials
        return self.trials[severity] if t == "per_severity" else t


# ---------------------------------------------------------------- projects/<name>/project.yaml
class DataConfig(_Strict):
    """How to rebuild and check the project's synthetic data. Paths are relative to the project folder."""

    seed_db: str
    generator: str
    generator_args: list[str] = []
    checker: str


class CaseLookups(_Strict):
    """SQL run against the seed database by `evalkit lint-cases` (parameter :value). A query that returns a row means
    the referenced item exists. Leave a key out to skip that check."""

    applicant: str | None = None
    document: str | None = None
    fixture: str | None = None
    case_in_seed: str | None = None  # the case's setup has been built into the seed database (`evalkit data`)


class ProjectConfig(_Strict):
    project: str
    data: DataConfig
    adapter: str  # "module.path:ClassName"
    entrypoint: str  # "module.path:build_graph"
    runner: str  # "module.path:run_case" — runs one case × trial and returns its run record (see evalkit/adapters/base.py)
    case_source: str  # "module.path:list_cases" — returns the project's TestCase list
    end_state_query: str
    agents_file: str
    tools_dir: str
    policies: list[str]
    datasets: dict[str, str]  # catalogue pattern -> folder of case YAML files (relative to the project folder)
    gates: str
    catalogue: str | None = None  # test-case workbook imported by `evalkit cases` (relative to the project folder)
    case_import_extras: str | None = None  # "module:function" — extra setup fields per case the workbook does not hold
    case_lookups: CaseLookups = CaseLookups()  # seed-database lookups used by `evalkit lint-cases`
    lab_variants: str | None = None  # folder of bug-hunt lab variant files (`evalkit lab`), relative to the project folder


class LabVariant(_Strict):
    """training/lab/variants/<id>.yaml — one seeded-defect variant of the system under test (`evalkit lab`)."""

    variant: str = Field(pattern=r"^LAB-\d+$")
    project: str
    switches: list[str] = Field(min_length=1)  # names the project's runner reads from EVALKIT_LAB_SWITCHES
    brief: str  # what the tester is told; never names the defect


# ---------------------------------------------------------------- projects/<name>/agents.yaml
class AgentEntry(_Strict):
    """One agent of the system under test, as the evaluators need to know it (requirement sheet, per-agent intake)."""

    role: Literal["orchestrator", "specialist"]
    description: str = ""
    slice: str | None = None  # state key the agent alone writes (SLICE-1)
    contract: str | None = None  # "module.path:Model" — Pydantic model its output must validate against (AG-4)
    output: Literal["agent_result", "decision"] = "agent_result"  # where its output appears in the trajectory
    prompt: str | None = None  # system prompt file, relative to the project folder (prompt-leak check, BF-4)


class PairPatterns(_Strict):
    """Case patterns (catalogue › Pattern) whose Twin / pair column the group checks read."""

    injection: list[str] = ["Adversarial / injection"]  # BF-3: compared with the clean twin
    fairness: list[str] = ["Fairness pair"]  # BF-5: compared with the pair partner


class AgentsConfig(_Strict):
    version: int
    agents: dict[str, AgentEntry] = Field(min_length=1)
    protected_attributes: list[str] = []  # BF-5: attributes no scorer may receive
    scorer_tools: list[str] = []  # BF-5: tools that compute a score or decision
    pair_patterns: PairPatterns = PairPatterns()


# ---------------------------------------------------------------- configs/gates.yaml
class Threshold(_Strict):
    metric: str  # TR-1, AG-2 …
    scope: Literal["suite", "agent", "pattern"] = "suite"
    patterns: list[str] = []  # only cases of these patterns (catalogue › Pattern)
    stat: Literal["pass_rate", "mean_score"] = "pass_rate"
    min: float = Field(ge=0, le=1)
    note: str = ""


class JudgeGate(_Strict):
    """When LLM judges may gate (SOP §3.9): agreement and Cohen's κ against the testers' consensus, per metric."""

    min_kappa: float = Field(default=0.6, ge=-1, le=1)
    min_agreement: float = Field(default=0.85, ge=0, le=1)


class GatesConfig(_Strict):
    """Release gates (SOP §3.10). Thresholds are human-owned and approved by the release approver."""

    version: int
    owner: str
    approved_by: str | None = None
    s1_zero_tolerance: bool = True
    thresholds: list[Threshold] = []
    report_only: list[str] = []  # metrics tracked for trend, never gating (S3)
    flake_limit: float = Field(default=0.10, ge=0, le=1)  # share of flaky cases that suspends the cycle (SOP §3.5)
    judges: JudgeGate = JudgeGate()  # calibration bar; below it the judges stay advisory
    weights_e2e: dict[str, float] | None = None  # override the SOP §5.3 composite weights
    weights_agent: dict[str, float] | None = None


# ---------------------------------------------------------------- configs/judges.yaml
class JudgeMetric(_Strict):
    id: str  # TR-8.plan, BF-4.advice …
    name: str
    scale_max: int = Field(default=3, ge=1)  # anchored 0 … scale_max
    description: str = ""


class JudgePricing(_Strict):
    """USD per million tokens. Left null until checked against the current price list (never guessed)."""

    input_per_mtok: float | None = None
    output_per_mtok: float | None = None
    checked_on: str | None = None


class JudgesConfig(_Strict):
    version: int
    model: str  # must equal configs/eval.yaml › models.judge
    effort: Literal["low", "medium", "high", "xhigh", "max"]
    max_tokens: int = Field(ge=256, le=64_000)
    rubric_version: str  # part of the cache key: changing a rubric re-judges
    cache_dir: str  # relative to the runs folder (eval.yaml › execution.runs_dir / EVALKIT_RUNS_DIR), or absolute
    metrics: list[JudgeMetric] = Field(min_length=1)
    pricing: JudgePricing = JudgePricing()


# ---------------------------------------------------------------- helpers
def repo_root(start: Path | None = None) -> Path:
    """The folder that holds pyproject.toml, searching upwards from start (default: this file)."""
    here = (start or Path(__file__)).resolve()
    for p in [here, *here.parents]:
        if (p / "pyproject.toml").is_file() and (p / "evalkit").is_dir():
            return p
    raise ConfigError("Could not find the repository root (a folder containing pyproject.toml and evalkit/).")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"{path}: file not found.")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        raise ConfigError(f"{path}{where}: not valid YAML — {getattr(e, 'problem', e)}.") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping of keys at the top level.")
    return data


def _explain(path: Path, err: ValidationError) -> ConfigError:
    lines = [f"{path}: {err.error_count()} problem(s)"]
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"]) or "(top level)"
        msg = "unknown key — check the spelling" if e["type"] == "extra_forbidden" else e["msg"]
        lines.append(f"  • {loc}: {msg}")
    return ConfigError("\n".join(lines))


def _validate(model: type[BaseModel], path: Path, data: dict[str, Any]):
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise _explain(path, e) from None


def load_env(root: Path | None = None) -> None:
    """Load .env from the repository root if present. Never prints values."""
    env = (root or repo_root()) / ".env"
    if env.is_file():
        load_dotenv(env, override=False)


def load_eval_config(path: Path | None = None) -> EvalConfig:
    """Load configs/eval.yaml, then apply EVALKIT_RUNS_DIR / EVALKIT_MAX_WORKERS overrides from the environment."""
    root = repo_root()
    path = path or root / "configs" / "eval.yaml"
    data = _read_yaml(path)
    ex = dict(data.get("execution") or {})
    if os.environ.get("EVALKIT_RUNS_DIR"):
        ex["runs_dir"] = os.environ["EVALKIT_RUNS_DIR"]
    if os.environ.get("EVALKIT_MAX_WORKERS"):
        try:
            ex["max_workers"] = int(os.environ["EVALKIT_MAX_WORKERS"])
        except ValueError:
            raise ConfigError("EVALKIT_MAX_WORKERS must be a whole number, for example 4.") from None
    if ex:
        data["execution"] = ex
    return _validate(EvalConfig, path, data)


def is_blank(path: Path) -> bool:
    """True when a YAML file holds nothing but comments: a human-owned file that has not been written yet."""
    return path.is_file() and yaml.safe_load(path.read_text(encoding="utf-8")) is None


def load_model(model: type[BaseModel], path: Path):
    """Read a YAML file and validate it against a strict model, with tester-readable errors."""
    return _validate(model, path, _read_yaml(path))


def load_project_config(path: Path) -> ProjectConfig:
    return _validate(ProjectConfig, path, _read_yaml(path))


def runs_dir(cfg: EvalConfig, root: Path | None = None) -> Path:
    p = Path(cfg.execution.runs_dir)
    return p if p.is_absolute() else (root or repo_root()) / p
