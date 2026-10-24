"""Catalogue workbook → one case YAML file per row (`evalkit cases`).

The workbook's "Test Cases" sheet (SOP §4.6 columns) is copied, not interpreted: text columns keep the catalogue's
words; only fields a machine must read exactly are given structure, by fixed rules:
  run sets → list · documents → list with the upload turn ("(turn 2)") · fixture profile IDs → list (from the mocks
  column) · reference trajectory IDs → list (from the expected trajectory) · expected end state → structured, read from
  the "<end-state table>.<field> = value" statements of the expected outcome (the same rule the seed builder used).
Per-agent outputs (AG-1) and argument values (TU-3) are left empty for the QE Lead to fill from the text.

Not copied: the "Lab defect caught" column. It is part of the bug-hunt lab's answer key, and testers read the case files.

A file that already exists and differs from what the import would write was edited by someone, so it is kept unless
--force is given. Case files with no row in the workbook (added by testers) are left alone and listed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evalkit.adapters.base import import_ref
from evalkit.config.loader import ConfigError, ProjectConfig
from evalkit.datasets.loader import CaseFile, case_files

COLUMNS = {  # YAML field -> catalogue column
    "case_id": "Case ID",
    "title": "Title",
    "level": "Level",
    "primary_agent": "Primary agent",
    "agents_exercised": "Agents exercised",
    "pattern": "Pattern",
    "severity": "Severity",
    "trials": "Trials (k)",
    "run_sets": "Run sets",
    "rule_refs": "Rule / control refs",
    "applicant": "Applicant",
    "documents": "Documents",
    "customer_turns": "Customer turns (scripted)",
    "mocks": "Mocks / faults / stubs",
    "approver": "Approver",
    "expected_trajectory": "Expected trajectory",
    "match_mode": "Match mode",
    "required_tools": "Required tools",
    "forbidden_tools": "Forbidden tools",
    "argument_expectations": "Argument expectations",
    "expected_outcome": "Expected outcome (end state / agent output)",
    "checks": "Checks (metric IDs)",
    "twin_pair": "Twin / pair",
    "oracle_owner": "Oracle owner",
    "case_status": "Status",
    "notes": "Notes",
}
EXCLUDED = ("Lab defect caught",)  # answer key — never in tester-visible files
DOC_ID = re.compile(r"\bDOC-[0-9A-Za-z]+-[A-Z0-9-]*[A-Z0-9]\b")
PROFILE_ID = re.compile(r"\b[A-Z]{2,5}-\d{2}\b")
RT_ID = re.compile(r"\bRT-\d+\b")
HEADER = """\
# {case_id} — imported from {source} (row {row}). Fields mirror the catalogue columns; see datasets/README.md.
# The expected outcome is owned by the QE Lead{s1}.
# expected.agent_outputs (AG-1) and expected.arguments (TU-3) are filled by the QE Lead from expected_outcome and
# argument_expectations; the import never guesses them.
"""


# ------------------------------------------------------------------ cell → field rules
def parse_documents(cell: str) -> list[Any]:
    """'DOC-1-PAN, DOC-1-UB; DOC-1-UB2 (turn 2)' → [DOC-1-PAN, DOC-1-UB, {doc: DOC-1-UB2, turn: 2}]."""
    out: list[Any] = []
    for seg in re.split(r"[;,]", cell or ""):
        m = DOC_ID.search(seg)
        if m:
            turn = re.search(r"turn (\d+)", seg)
            out.append({"doc": m.group(0), "turn": int(turn.group(1))} if turn and turn.group(1) != "1" else m.group(0))
    return out


def parse_end_state(outcome: str, table: str) -> dict[str, Any]:
    """Structured end state from the outcome text: '<table>.status = X; record_id NULL; risk_tier = T (n); reason_codes = [..]'."""
    st = re.search(rf"{re.escape(table)}\.status = (\w+)", outcome)
    tier = re.search(r"risk_tier = (\w+)(?: \((\d+)\))?", outcome)
    rc = re.search(r"reason_codes = (\[[^\]]*\])", outcome)
    rec = re.search(r"record_id (NOT NULL|NULL)", outcome)
    return {
        "status": st.group(1) if st else None,
        "risk_tier": tier.group(1) if tier else None,
        "risk_score": int(tier.group(2)) if tier and tier.group(2) else None,
        "reason_codes": [x.strip() for x in rc.group(1)[1:-1].split(",") if x.strip()] if rc else None,
        "record": (rec.group(1) == "NOT NULL") if rec else None,
        "agent_outputs": {},
        "arguments": {},
    }


def end_state_table(pcfg: ProjectConfig) -> str:
    m = re.search(r"\bFROM\s+(\w+)", pcfg.end_state_query, re.IGNORECASE)
    return m.group(1) if m else "applications"


def row_to_case(row: dict[str, Any], pcfg: ProjectConfig, extras: dict[str, Any]) -> dict[str, Any]:
    text = {k: ("" if row.get(col) is None else str(row[col]).strip()) for k, col in COLUMNS.items()}
    case: dict[str, Any] = {}
    for k in COLUMNS:
        case[k] = text[k]
    case["trials"] = int(row["Trials (k)"])
    case["run_sets"] = [s.strip() for s in text["run_sets"].split(",") if s.strip()]
    case["documents"] = parse_documents(text["documents"])
    case["fixtures"] = PROFILE_ID.findall(text["mocks"])
    case["reference"] = list(dict.fromkeys(RT_ID.findall(text["expected_trajectory"])))
    case["form_updates"] = (extras.get(text["case_id"]) or {}).get("form_updates")
    case["expected"] = parse_end_state(text["expected_outcome"], end_state_table(pcfg))
    order = [
        "case_id", "title", "level", "primary_agent", "agents_exercised", "pattern", "severity", "trials", "run_sets",
        "rule_refs", "applicant", "documents", "customer_turns", "mocks", "fixtures", "approver", "form_updates",
        "expected_trajectory", "reference", "match_mode", "required_tools", "forbidden_tools", "argument_expectations",
        "expected_outcome", "expected", "checks", "twin_pair", "oracle_owner", "case_status", "notes",
    ]  # fmt: skip
    out = {k: case[k] for k in order}
    if out["form_updates"] is None:
        out.pop("form_updates")
    CaseFile.model_validate(out)  # the import never writes a file the loader would reject
    return out


# ------------------------------------------------------------------ YAML text
class _Dumper(yaml.SafeDumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):  # indent list items under their key
        return super().increase_indent(flow, False)


def _list(dumper: yaml.SafeDumper, data: list):
    flow = all(isinstance(x, str | int | float) and len(str(x)) < 40 for x in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_Dumper.add_representer(list, _list)


def to_yaml(case: dict[str, Any], source: str, row: int) -> str:
    s1 = " — S1: human-authored, unvalidated without an SME" if case["severity"] == "S1" else ""
    body = yaml.dump(case, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=118, default_flow_style=False)
    return HEADER.format(case_id=case["case_id"], source=source, row=row, s1=s1) + body


# ------------------------------------------------------------------ workbook
def read_rows(workbook: Path, sheet: str = "Test Cases") -> list[tuple[int, dict[str, Any]]]:
    import openpyxl  # noqa: PLC0415

    if not workbook.is_file():
        raise ConfigError(f"{workbook}: catalogue workbook not found (project.yaml › catalogue).")
    wb = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    head = next((i for i, r in enumerate(rows) if r and r[0] == "Case ID"), None)
    if head is None:
        raise ConfigError(f"{workbook} › {sheet}: no header row starting with 'Case ID'.")
    names = [str(h) if h is not None else "" for h in rows[head]]
    missing = [c for c in COLUMNS.values() if c not in names]
    if missing:
        raise ConfigError(f"{workbook} › {sheet}: missing column(s) {', '.join(missing)}.")
    return [(head + 1 + i + 1, dict(zip(names, r, strict=False))) for i, r in enumerate(rows[head + 1 :]) if r and r[0]]


@dataclass
class ImportReport:
    written: list[Path] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    kept_edits: list[Path] = field(default_factory=list)
    not_in_catalogue: list[Path] = field(default_factory=list)


def import_catalogue(
    project_dir: Path, pcfg: ProjectConfig, workbook: Path | None = None, force: bool = False, extras: Callable | None = None
) -> ImportReport:
    if workbook is None:
        if not pcfg.catalogue:
            raise ConfigError("project.yaml has no `catalogue:` workbook to import from.")
        workbook = (project_dir / pcfg.catalogue).resolve()
    rows = read_rows(workbook)
    ids = [r["Case ID"] for _, r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ConfigError(f"{workbook.name}: duplicate case IDs {', '.join(dup)} — fix the workbook first.")
    hook = extras or (import_ref(pcfg.case_import_extras) if pcfg.case_import_extras else None)
    extra = hook(ids) if hook else {}
    report = ImportReport()
    for row_no, row in rows:
        pattern = str(row["Pattern"]).strip()
        if pattern not in pcfg.datasets:
            raise ConfigError(f"{row['Case ID']}: pattern {pattern!r} has no folder in project.yaml › datasets.")
        path = project_dir / pcfg.datasets[pattern] / f"{row['Case ID']}.yaml"
        text = to_yaml(row_to_case(row, pcfg, extra), workbook.name, row_no)
        if path.is_file():
            old = path.read_text(encoding="utf-8")
            if old == text:
                report.unchanged.append(path)
                continue
            if not force:
                report.kept_edits.append(path)
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")  # LF on every platform (yamllint, diffs)
        report.written.append(path)
    known = set(ids)
    report.not_in_catalogue = [p for p in case_files(project_dir, pcfg) if p.stem not in known]
    return report
