"""`evalkit lint-cases`: check every case YAML file and explain each problem in plain English, with the fix.

Errors stop the case from being used (exit code 1). Warnings are worth fixing but do not block. Notes (shown with
--all) list what a person still has to check by hand, such as conditional tool entries.

Mistake classes checked (each has a test in tests/unit/test_case_lint.py):
  file      not valid YAML · unknown or missing field · value not allowed (level, severity, run set …)
  identity  case ID scheme · file name ≠ case ID · duplicate case ID · pattern unknown · file in the wrong folder
  trials    trials ≠ k for the severity (eval.yaml) · run sets inconsistent with severity (gate = all S1; full = all)
  tools     unknown tool name · tool both required and forbidden
  links     unknown reference trajectory · unknown twin / pair case · unknown metric ID
  oracle    end state missing for L2 / L3 · structured end state disagrees with expected_outcome text ·
            contradictory end state · agent_outputs / arguments name an unknown agent, tool or argument
  setup     applicant, document or fixture profile not in the seed database · case not built into the seed database ·
            case files changed after the seed database was built
"""

from __future__ import annotations

import difflib
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from evalkit.config.loader import AgentsConfig, ConfigError, EvalConfig, ProjectConfig, load_model
from evalkit.datasets.catalogue_import import end_state_table, parse_end_state
from evalkit.datasets.loader import APPROVER, CASE_ID, LoadedCase, case_ids, load_case_files, metric_ids, read_case_file, split_tools

LEVELS = {"error": 0, "warning": 1, "note": 2}


@dataclass
class Finding:
    level: str  # error | warning | note
    file: Path
    message: str

    def render(self, root: Path) -> str:
        try:
            where = self.file.relative_to(root)
        except ValueError:
            where = self.file
        return f"{self.level.upper():7} {where.as_posix()}: {self.message}"


@dataclass
class LintContext:
    project_dir: Path
    pcfg: ProjectConfig
    cfg: EvalConfig
    tools: dict[str, dict]  # tool name -> spec
    agents: list[str]
    metrics: set[str]
    references: set[str]
    unreviewed: set[str]
    seed_db: Path


def _near(word: str, options) -> str:
    m = difflib.get_close_matches(word, list(options), n=1, cutoff=0.6)
    return f" — did you mean '{m[0]}'?" if m else ""


def build_context(project_dir: Path, pcfg: ProjectConfig, cfg: EvalConfig) -> LintContext:
    from evalkit.config.registry import METRICS, load_references, load_tool_specs  # noqa: PLC0415

    refs, unreviewed = load_references(project_dir / "reference_trajectories")
    agents = list(load_model(AgentsConfig, project_dir / pcfg.agents_file).agents)
    return LintContext(
        project_dir, pcfg, cfg, load_tool_specs(project_dir / pcfg.tools_dir), agents, set(METRICS), set(refs), unreviewed,
        project_dir / pcfg.data.seed_db,
    )  # fmt: skip


# ------------------------------------------------------------------ per-case checks
def check_case(lc: LoadedCase, ctx: LintContext, all_ids: set[str]) -> list[Finding]:
    c, f, out = lc.case, lc.path, []

    def err(msg: str) -> None:
        out.append(Finding("error", f, msg))

    def warn(msg: str) -> None:
        out.append(Finding("warning", f, msg))

    def note(msg: str) -> None:
        out.append(Finding("note", f, msg))

    # identity and placement
    if not CASE_ID.fullmatch(c.case_id):
        err(f"case_id {c.case_id!r} does not follow the ID scheme <PROJECT>-<PATTERN>-<NNN> (for example KYC-GLD-001)")
    if f.stem != c.case_id:
        err(f"the file name must be the case ID — rename {f.name} to {c.case_id}.yaml")
    if c.pattern not in ctx.pcfg.datasets:
        err(
            f"pattern {c.pattern!r} is not a catalogue pattern{_near(c.pattern, ctx.pcfg.datasets)} "
            f"(allowed: {', '.join(ctx.pcfg.datasets)})"
        )
    elif f.parent.name != Path(ctx.pcfg.datasets[c.pattern]).name:
        err(f"a {c.pattern!r} case belongs in {ctx.pcfg.datasets[c.pattern]}/ — move the file there")
    # trials and run sets
    k = ctx.cfg.trials.get(c.severity)
    if k is not None and c.trials != k:
        err(f"{c.severity} cases run k = {k} trial(s) (configs/eval.yaml › trials) — set trials: {k}")
    if c.severity == "S1" and "gate" not in c.run_sets:
        err("an S1 case must be in the gate run set — add gate to run_sets")
    if c.severity != "S1" and "gate" in c.run_sets:
        err("only S1 cases are in the gate run set — remove gate from run_sets, or raise the severity to S1 if that is intended")
    if "full" not in c.run_sets:
        err("every case is in the full run set — add full to run_sets")
    if "smoke" in c.run_sets and c.pattern != "Golden path":
        warn("the smoke run set is for golden-path cases — remove smoke unless the QE Lead asked for it")
    if not c.approver_response and not c.approver.strip().lower().startswith("n/a"):
        err(f"approver {c.approver!r} is not allowed — use {', '.join(APPROVER)} or n/a")
    if not c.match:
        err(f"match_mode {c.match_mode!r} must start with strict, unordered, subset or superset")
    # tools
    names = set(ctx.tools)
    req, req_notes = split_tools(c.required_tools, names)
    forb, forb_notes = split_tools(c.forbidden_tools, names)
    for entry in req_notes + forb_notes:
        if entry.replace("_", "").isalpha() and entry.islower():
            err(f"unknown tool {entry!r}{_near(entry, names)} (tool names come from tools/specs)")
        else:
            note(f"conditional tool entry {entry!r} is not checked automatically — a reviewer checks it")
    if both := sorted(set(req) & set(forb)):
        err(f"{', '.join(both)} is both required and forbidden — keep it in one list")
    # links
    for r in c.reference:
        if r not in ctx.references:
            err(
                f"reference trajectory {r} does not exist — use one of {', '.join(sorted(ctx.references))} or ask the QE Lead for a new one"
            )
        elif r in ctx.unreviewed:
            note(f"reference trajectory {r} is not reviewed yet (reviewed_by is empty in its JSON file)")
    for t in case_ids(c.twin_pair):
        if t not in all_ids:
            err(f"twin_pair names {t}, which is not a case — check the ID")
    for m in metric_ids(c.checks):
        if m not in ctx.metrics:
            err(f"checks names {m}, which is not a metric{_near(m, ctx.metrics)}")
    # oracle
    e = c.expected
    if c.level in ("L2", "L3", "L1+L3") and e.status is None:
        err(f"an {c.level} case needs expected.status (the end state the run must reach)")
    parsed = parse_end_state(c.expected_outcome, end_state_table(ctx.pcfg))
    for key in ("status", "risk_tier", "risk_score", "reason_codes", "record"):
        said, have = parsed[key], getattr(e, key)
        if (
            said is not None
            and have is not None
            and (sorted(said) if key == "reason_codes" else said) != (sorted(have) if key == "reason_codes" else have)
        ):
            err(f"expected.{key} is {have!r} but expected_outcome says {said!r} — make them agree")
        elif said is not None and have is None:
            err(f"expected_outcome states {key} = {said!r} but expected.{key} is empty — copy it into expected")
    if e.record is True and e.status not in (None, "APPROVED"):
        warn(f"expected.record is true but the status is {e.status} — only an approved application gets a record")
    if e.status == "APPROVED" and e.record is False:
        warn("expected.status is APPROVED but expected.record is false — an approved application gets a record")
    for agent in e.agent_outputs:
        if agent not in ctx.agents:
            err(f"expected.agent_outputs names agent {agent!r}{_near(agent, ctx.agents)} (agents: {', '.join(ctx.agents)})")
    for tool, args in e.arguments.items():
        if tool not in ctx.tools:
            err(f"expected.arguments names tool {tool!r}{_near(tool, names)}")
            continue
        props = (ctx.tools[tool].get("input_schema") or {}).get("properties", {})
        for a in args:
            if a not in props:
                err(f"expected.arguments.{tool} names argument {a!r}{_near(a, props)} (arguments: {', '.join(props)})")
    if c.severity == "S1" and c.level.startswith("L1") and c.primary_agent not in ("SUP", "E2E") and not e.agent_outputs:
        warn("S1 agent-level case without expected.agent_outputs — AG-1 is skipped until the QE Lead fills it from expected_outcome")
    return out


def check_setup(loaded: list[LoadedCase], ctx: LintContext) -> list[Finding]:
    q = ctx.pcfg.case_lookups
    if not ctx.seed_db.is_file():
        return [Finding("error", ctx.seed_db, "seed database not found — run `evalkit data`")]
    out: list[Finding] = []
    seed_time = ctx.seed_db.stat().st_mtime
    con = sqlite3.connect(f"file:{ctx.seed_db}?mode=ro", uri=True)
    try:

        def exists(sql: str | None, value: str) -> bool:
            return sql is None or con.execute(sql, {"value": value}).fetchone() is not None

        for lc in loaded:
            c, f = lc.case, lc.path
            if not exists(q.applicant, c.applicant):
                out.append(Finding("error", f, f"applicant {c.applicant} is not in the seed database — use an existing applicant "
                                               "(catalogue › Synthetic Applicants) or ask the QE Lead to add one"))  # fmt: skip
            for d in c.documents:
                if not exists(q.document, d.doc):
                    out.append(
                        Finding(
                            "error", f, f"document {d.doc} is not in the seed database — check the ID (catalogue › Synthetic Documents)"
                        )
                    )
            for p in c.fixtures:
                if not exists(q.fixture, p):
                    out.append(Finding("error", f, f"fixture profile {p} does not exist — check the ID (catalogue › Mocks & Faults)"))
            if not exists(q.case_in_seed, c.case_id):
                out.append(Finding("error", f, "this case is not built into the seed database yet — run `evalkit data`, then lint again"))
    finally:
        con.close()
    newer = [lc.path for lc in loaded if lc.path.stat().st_mtime > seed_time]
    if newer:
        names = ", ".join(p.stem for p in newer[:5]) + (f" and {len(newer) - 5} more" if len(newer) > 5 else "")
        msg = f"{len(newer)} case file(s) changed after the seed database was built ({names}) — run `evalkit data` so runs use them"
        out.append(Finding("warning", ctx.seed_db, msg))
    return out


def _file_errors(path: Path, message: str) -> list[Finding]:
    """One finding per line of a loader message ('<file name>: <field>: <problem>'), without the repeated file name."""
    prefix = f"{path.name}"
    return [Finding("error", path, line[len(prefix) :].lstrip(": ") if line.startswith(prefix) else line) for line in message.splitlines()]


def prepare(project_dir: Path, pcfg: ProjectConfig, cfg: EvalConfig) -> tuple[LintContext, list[LoadedCase], list]:
    """Load the project once; pass the result to lint(prepared=…) to lint several drafts against it."""
    loaded, problems = load_case_files(project_dir, pcfg)
    return build_context(project_dir, pcfg, cfg), loaded, problems


def lint(
    project_dir: Path, pcfg: ProjectConfig, cfg: EvalConfig, extra_files: list[Path] | None = None, prepared: tuple | None = None
) -> list[Finding]:
    """Lint every case file of the project, plus extra_files (used by tests and for a draft outside the datasets)."""
    ctx, loaded, problems = prepared or prepare(project_dir, pcfg, cfg)
    loaded = list(loaded)
    findings = [f for p in problems for f in _file_errors(p.path, p.message)]
    for x in extra_files or []:
        try:
            loaded.append(LoadedCase(x, read_case_file(x)))
        except ConfigError as e:
            findings += _file_errors(x, str(e))
    by_id: dict[str, list[Path]] = defaultdict(list)
    for lc in loaded:
        by_id[lc.case.case_id].append(lc.path)
    for cid, paths in by_id.items():
        if len(paths) > 1:
            for p in paths:
                others = ", ".join(o.name if o.parent == p.parent else o.as_posix() for o in paths if o != p)
                findings.append(Finding("error", p, f"case ID {cid} is also used by {others} — give each case its own ID"))
    for lc in loaded:
        findings += check_case(lc, ctx, set(by_id))
    findings += check_setup(loaded, ctx)
    return sorted(findings, key=lambda x: (LEVELS[x.level], str(x.file), x.message))
