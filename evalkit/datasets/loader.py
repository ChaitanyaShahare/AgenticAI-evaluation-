"""Test cases as YAML: the file format, loading, and conversion into the harness's TestCase.

One file per case: projects/<name>/<datasets folder of its pattern>/<case_id>.yaml. The fields mirror the catalogue's
columns (SOP §4.6), so a tester can copy a row of the workbook or a neighbouring file. Descriptive columns stay as text
(the catalogue's own words); fields a machine must read exactly are structured: run sets, documents, fixture profiles,
the expected end state, and the per-agent / argument expectations.

The expected outcome is human-owned (S1 cases are QE-Lead-authored, "unvalidated" without an SME). `expected` holds the
end state in structured form; `expected.agent_outputs` and `expected.arguments` are filled by the QE Lead from the
`expected_outcome` and `argument_expectations` text — the import never guesses them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from evalkit.config.loader import ConfigError, ProjectConfig
from evalkit.schema import TestCase

CASE_ID = re.compile(r"\b[A-Z][A-Z0-9]+(?:-[A-Z][A-Z0-9]*)+-\d+[a-z]?\b")  # KYC-GLD-001, KYC-AGT-DOC-046, KYC-FAIR-071a
CASE_RANGE = re.compile(r"([A-Z][A-Z0-9]*-[A-Z][A-Z0-9-]*-)(\d+)…(\d+)")
METRIC = re.compile(r"\b(?:TR|TU|BF|AG)-\d\b")
MATCH_MODES = ("strict", "unordered", "subset", "superset")
APPROVER = {"approve": "APPROVE", "deny": "DENY", "no response": "NO_RESPONSE"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Document(_Strict):
    doc: str
    turn: int = Field(default=1, ge=1)  # the customer turn in which the document is uploaded


class Expected(_Strict):
    """Structured expectation. Unstated (null) fields are not checked."""

    status: str | None = None  # end state (L2 / L3, and L1 Supervisor cases)
    risk_tier: str | None = None
    risk_score: int | None = None
    reason_codes: list[str] | None = None
    record: bool | None = None  # a customer record is (true) / is not (false) created
    agent_outputs: dict[str, dict[str, Any]] = {}  # agent -> {field path: value} (AG-1) — written by the QE Lead
    arguments: dict[str, dict[str, Any]] = {}  # tool -> {argument: value} (TU-3) — written by the QE Lead


class CaseFile(_Strict):
    """One test case. Text fields hold the catalogue's words; see projects/<name>/datasets/README.md."""

    case_id: str
    title: str
    level: Literal["L1", "L2", "L3", "L1+L3"]
    primary_agent: str  # E2E, SUP, DOC, IDV, SCR, RSK …
    agents_exercised: str
    pattern: str
    severity: Literal["S1", "S2", "S3"]
    trials: int = Field(ge=1)
    run_sets: list[Literal["smoke", "gate", "full"]] = Field(min_length=1)
    rule_refs: str = "—"
    applicant: str
    documents: list[Document] = []
    customer_turns: str
    mocks: str = "—"  # fault / mock / stub description, catalogue words
    fixtures: list[str] = []  # fixture profile IDs applied to the run (FP-01, MO-02, STUB-07 …)
    approver: str = "n/a"  # approve | deny | no response | n/a
    form_updates: dict[str, Any] | None = None  # fields the scripted customer supplies when asked
    expected_trajectory: str = "—"
    reference: list[str] = []  # reference trajectory IDs (RT-01 …)
    match_mode: str  # strict | unordered | subset | superset, optionally with a note: "unordered (vs twin)"
    required_tools: str = "—"  # comma-separated tool names; other entries are conditions, checked by a person
    forbidden_tools: str = "—"
    argument_expectations: str = "—"
    expected_outcome: str
    expected: Expected = Expected()
    checks: str = "—"  # metric IDs this case exercises
    twin_pair: str = "—"  # related cases: clean twin, fairness partner, paraphrases
    oracle_owner: str
    case_status: str = "Draft"
    notes: str = ""

    @field_validator("documents", mode="before")
    @classmethod
    def _docs(cls, v):
        return [{"doc": d} if isinstance(d, str) else d for d in (v or [])]

    @property
    def match(self) -> str | None:
        mode = self.match_mode.split(" ")[0]
        return mode if mode in MATCH_MODES else None

    @property
    def approver_response(self) -> str | None:
        return next((code for word, code in APPROVER.items() if self.approver.strip().lower().startswith(word)), None)


# ------------------------------------------------------------------ text-column helpers
def split_tools(cell: str, tools: set[str]) -> tuple[list[str], list[str]]:
    """Plain tool names and conditional entries of a tools cell."""
    if not cell or cell.strip() in ("—", "-"):
        return [], []
    plain, notes = [], []
    for part in (p.strip() for p in cell.split(",")):
        if part:
            (plain if part in tools else notes).append(part)
    return plain, notes


def case_ids(text: str) -> list[str]:
    """Case IDs named in a text, with ranges (KYC-PAR-090…094) expanded."""
    out = []
    for prefix, a, b in CASE_RANGE.findall(text or ""):
        out += [f"{prefix}{n:0{len(a)}d}" for n in range(int(a), int(b) + 1)]
    rest = CASE_RANGE.sub("", text or "")
    return out + [c for c in CASE_ID.findall(rest) if c not in out]


def metric_ids(text: str) -> list[str]:
    return sorted(set(METRIC.findall(text or "")))


# ------------------------------------------------------------------ loading
@dataclass
class LoadedCase:
    path: Path
    case: CaseFile


@dataclass
class LoadProblem:
    path: Path
    message: str


def read_case_file(path: Path) -> CaseFile:
    """Parse and validate one case file. Raises ConfigError with a tester-readable message."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        raise ConfigError(f"{path.name}{where}: not valid YAML — {getattr(e, 'problem', e)}. Check indentation and quotes.") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: expected the case's fields (key: value) at the top level.")
    try:
        return CaseFile.model_validate(data)
    except ValidationError as e:
        raise ConfigError(explain(path, e, data)) from None


def explain(path: Path, err: ValidationError, data: dict) -> str:
    import difflib  # noqa: PLC0415

    lines = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"]) or "(top level)"
        if e["type"] == "extra_forbidden":
            key = str(e["loc"][-1])
            model = Expected if len(e["loc"]) > 1 and e["loc"][0] == "expected" else CaseFile
            near = difflib.get_close_matches(key, list(model.model_fields), n=1)
            hint = f" — did you mean '{near[0]}'?" if near else " — remove it or check the spelling"
            lines.append(f"{path.name}: {loc}: unknown field{hint}")
        elif e["type"] == "missing":
            lines.append(f"{path.name}: {loc}: required field is missing — add it (copy it from a case of the same pattern)")
        elif e["type"] in ("literal_error", "enum"):
            lines.append(f"{path.name}: {loc}: {e['input']!r} is not allowed — {e['msg'].replace('Input should be ', 'use ')}")
        else:
            lines.append(f"{path.name}: {loc}: {e['msg']} (got {e.get('input')!r})")
    return "\n".join(lines)


def case_files(project_dir: Path, pcfg: ProjectConfig) -> list[Path]:
    files = []
    for folder in dict.fromkeys(pcfg.datasets.values()):
        d = project_dir / folder
        files += sorted(d.glob("*.yaml")) if d.is_dir() else []
    return files


def load_case_files(project_dir: Path, pcfg: ProjectConfig) -> tuple[list[LoadedCase], list[LoadProblem]]:
    """Every case file of the project. Problems are returned, not raised, so lint can report them all at once."""
    loaded, problems = [], []
    for p in case_files(project_dir, pcfg):
        try:
            loaded.append(LoadedCase(p, read_case_file(p)))
        except ConfigError as e:
            problems.append(LoadProblem(p, str(e)))
    return loaded, problems


def to_test_case(c: CaseFile, tools: set[str]) -> TestCase:
    req, req_notes = split_tools(c.required_tools, tools)
    forb, forb_notes = split_tools(c.forbidden_tools, tools)
    e = c.expected
    expected = {
        "status": e.status,
        "risk_tier": e.risk_tier,
        "risk_score": e.risk_score,
        "reason_codes": e.reason_codes,
        "record": e.record,
        "output": c.expected_outcome,
        "agent_outputs": e.agent_outputs,
        "arguments": e.arguments,
    }
    return TestCase(
        case_id=c.case_id,
        title=c.title,
        level=c.level,
        primary_agent=c.primary_agent,
        pattern=c.pattern,
        severity=c.severity,
        trials=c.trials,
        run_sets=c.run_sets,
        expected=expected,
        match_mode=c.match,
        reference=c.reference,
        required_tools=req,
        forbidden_tools=forb,
        tool_notes=[f"required: {n}" for n in req_notes] + [f"forbidden: {n}" for n in forb_notes],
        metrics=metric_ids(c.checks),
        twins=case_ids(c.twin_pair),
    )


def tool_names(project_dir: Path, pcfg: ProjectConfig) -> set[str]:
    import json  # noqa: PLC0415

    names = set()
    for p in (project_dir / pcfg.tools_dir).glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        names |= {t["name"] for t in data.get("tools", [data])}
    return names


def load_cases(project_dir: Path, pcfg: ProjectConfig) -> list[TestCase]:
    """The project's cases as TestCase objects. Any invalid file stops the run with every problem listed."""
    loaded, problems = load_case_files(project_dir, pcfg)
    if problems:
        raise ConfigError("case files with problems (run `evalkit lint-cases` for details):\n" + "\n".join(p.message for p in problems))
    tools = tool_names(project_dir, pcfg)
    return sorted((to_test_case(lc.case, tools) for lc in loaded), key=lambda t: t.case_id)
