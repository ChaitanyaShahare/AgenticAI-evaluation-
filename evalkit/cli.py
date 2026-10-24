"""`evalkit` command line. Every Makefile target calls one of these sub-commands, so Windows users without make
run the same thing with `uv run evalkit <command>`.

Commands: doctor, data, test, smoke (WP1) · eval, run (WP4) · grade, gate (WP5) · cases, lint-cases, coverage (WP6)
· grade --judges, calibrate (WP7) · report, full, junit.xml / report.html / cost.json (WP8) · lab (WP10).
A command registered in PLANNED before it is built says which work package delivers it (none are pending now).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from evalkit.config import ConfigError, load_env, load_eval_config, load_project_config, repo_root, runs_dir

# command -> (work package, planned date, what it will do)
PLANNED: dict[str, tuple[str, str, str]] = {}


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _warn(msg: str) -> None:
    print(f"  ! {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def _project_dir(root: Path, name: str) -> Path:
    d = root / "projects" / name
    if not (d / "project.yaml").is_file():
        raise ConfigError(f"Project '{name}' not found: expected {d / 'project.yaml'}.")
    return d


# ---------------------------------------------------------------- doctor
def cmd_doctor(args: argparse.Namespace) -> int:
    root = repo_root()
    problems = 0
    print("evalkit doctor")
    load_env(root)  # before reading eval.yaml, so EVALKIT_* overrides in .env apply
    if sys.version_info[:2] == (3, 12):
        _ok(f"Python {sys.version.split()[0]}")
    else:
        _fail(f"Python {sys.version.split()[0]} — this project needs 3.12 (see .python-version)")
        problems += 1
    try:
        cfg = load_eval_config()
    except ConfigError as e:
        _fail(str(e))
        return 1
    m = cfg.models
    _ok(f"configs/eval.yaml valid · supervisor {m.supervisor} · specialists {m.specialist} · judge {m.judge}")
    proj = load_project_config(_project_dir(root, args.project) / "project.yaml")
    _ok(f"projects/{args.project}/project.yaml valid")
    db = root / "projects" / args.project / proj.data.seed_db
    (_ok if db.is_file() else _fail)(f"seed database {'found' if db.is_file() else 'missing'}: {db.relative_to(root)}")
    problems += not db.is_file()
    if os.environ.get("ANTHROPIC_API_KEY"):
        _ok("ANTHROPIC_API_KEY is set (value not shown)")
    else:
        _warn("ANTHROPIC_API_KEY not set — fine for data and framework tests; needed from the first agent run (WP3)")
    out = runs_dir(cfg, root)
    if "dropbox" in str(out).lower():
        _warn(f"run output folder is inside Dropbox ({out}); set EVALKIT_RUNS_DIR in .env to a local folder to avoid sync churn")
    else:
        _ok(f"run output folder: {out}")
    try:
        import spacy.util  # noqa: PLC0415

        has_model = spacy.util.is_package("en_core_web_lg")
    except Exception:  # spaCy itself missing or broken
        has_model = False
    if has_model:
        _ok("spaCy model en_core_web_lg installed")
    else:
        _warn("spaCy model en_core_web_lg not installed — optional: BF-1 uses regex + checksum recognisers; NER for names comes later")
    print("result:", "OK" if not problems else f"{problems} problem(s)")
    return 1 if problems else 0


# ---------------------------------------------------------------- data
def _run(cmd: list[str], cwd: Path) -> int:
    shown = ["python"] + [Path(c).name if Path(c).is_absolute() else c for c in cmd[1:]]
    print("  $", " ".join(shown), flush=True)  # flush so our lines and the child's output stay in order
    return subprocess.run(cmd, cwd=cwd, env={**os.environ, "PYTHONIOENCODING": "utf-8"}).returncode


def cmd_data(args: argparse.Namespace) -> int:
    """Rebuild the seed database into a temporary file, check it, and only then replace the seed."""
    root = repo_root()
    pdir = _project_dir(root, args.project)
    d = load_project_config(pdir / "project.yaml").data
    seed, generator, checker = pdir / d.seed_db, pdir / d.generator, pdir / d.checker
    if args.check_only:
        print(f"Checking {seed.relative_to(root)}")
        return _run([sys.executable, str(checker), str(seed)], checker.parent)
    new = seed.with_suffix(".new.sqlite")
    gen_args = [a.replace("{seed_db}", str(seed)) for a in d.generator_args]
    print(f"Rebuilding {seed.relative_to(root)}")
    if _run([sys.executable, str(generator), "--out", str(new), *gen_args], generator.parent) != 0:
        new.unlink(missing_ok=True)
        _fail("generator failed; seed database left unchanged")
        return 1
    if _run([sys.executable, str(checker), str(new)], checker.parent) != 0:
        _fail(f"fixture check failed; seed database left unchanged, failed build kept at {new.name} for inspection")
        return 1
    shutil.move(new, seed)
    _ok(f"seed database replaced: {seed.relative_to(root)}")
    return 0


# ---------------------------------------------------------------- test / smoke
def cmd_test(args: argparse.Namespace) -> int:
    root = repo_root()
    marker = [] if args.with_api else ["-m", "not api"]
    sys.stdout.flush()
    return subprocess.run([sys.executable, "-m", "pytest", *marker, *args.pytest_args], cwd=root).returncode


def cmd_smoke(args: argparse.Namespace) -> int:
    print("smoke (offline): setup check, fixture check, framework tests. Live golden cases: evalkit run --mode smoke.\n")
    steps = [
        ("doctor", lambda: cmd_doctor(args)),
        ("data check", lambda: cmd_data(argparse.Namespace(project=args.project, check_only=True))),
        ("framework tests", lambda: cmd_test(argparse.Namespace(with_api=False, pytest_args=["-q"]))),
    ]
    failed = []
    for name, fn in steps:
        print(f"── {name}", flush=True)
        if fn() != 0:
            failed.append(name)
        print()
    print("smoke:", "PASS" if not failed else "FAIL (" + ", ".join(failed) + ")")
    return 1 if failed else 0


def _run_plan(plan, yes: bool, max_workers: int | None, gate: bool = False) -> int:
    from evalkit.harness.runner import execute  # noqa: PLC0415 — keeps `evalkit --help` fast

    print(plan.describe())
    for c, t in plan.items[:20]:
        print(f"  {c.case_id} t{t}  [{c.level} {c.primary_agent} {c.severity}]")
    if len(plan.items) > 20:
        print(f"  … and {len(plan.items) - 20} more")
    if not yes:
        print("dry run — no model calls made. Add --yes to run (this calls the Claude API and costs money).")
        return 0
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _fail("ANTHROPIC_API_KEY is not set (see .env.example)")
        return 1
    summary = execute(plan, max_workers=max_workers)
    print(f"run folder: {summary.run_dir}")
    print(f"{len(summary.records)} trial(s), {len(summary.errors)} harness error(s).\n")
    code = _grade_and_report(plan.project, summary.run_dir, summary.run_dir, gate=gate)
    return 1 if summary.errors and not code else code


def cmd_eval(args: argparse.Namespace) -> int:
    from evalkit.harness.runner import make_plan  # noqa: PLC0415

    plan = make_plan(args.project, case_ids=args.case, trials=args.trials)
    return _run_plan(plan, args.yes, args.max_workers)


def cmd_run(args: argparse.Namespace) -> int:
    from evalkit.harness.runner import make_plan  # noqa: PLC0415

    plan = make_plan(args.project, mode=args.mode, trials=args.trials)
    return _run_plan(plan, args.yes, args.max_workers)


def cmd_gate(args: argparse.Namespace) -> int:
    from evalkit.harness.runner import make_plan  # noqa: PLC0415

    plan = make_plan(args.project, mode="gate")
    return _run_plan(plan, args.yes, args.max_workers, gate=True)


def cmd_lab(args: argparse.Namespace) -> int:
    """Run cases against one seeded-defect variant of the system (bug-hunt lab). The switches are on only for this run."""
    from evalkit.config.loader import LabVariant, load_model  # noqa: PLC0415
    from evalkit.harness.runner import LAB_ENV, make_plan, new_run_id  # noqa: PLC0415

    root = repo_root()
    pdir = _project_dir(root, args.project)
    pcfg = load_project_config(pdir / "project.yaml")
    if not pcfg.lab_variants:
        raise ConfigError(f"projects/{args.project}/project.yaml has no lab_variants folder, so this project has no bug-hunt lab.")
    folder = (pdir / pcfg.lab_variants).resolve()
    path = folder / f"{args.variant}.yaml"
    if not path.is_file():
        known = ", ".join(sorted(p.stem for p in folder.glob("LAB-*.yaml"))) or "none"
        raise ConfigError(f"No lab variant {args.variant!r} in {folder} (known: {known}).")
    variant = load_model(LabVariant, path)
    if variant.project != args.project:
        raise ConfigError(
            f"{path.name} is a variant of project {variant.project!r}, not {args.project!r}; add --project {variant.project}."
        )
    if not args.case and not args.mode:
        _fail("say which cases to run against the variant: --case <id> (repeatable) or --mode smoke|gate|full")
        return 2
    run_id = new_run_id(f"lab-{variant.variant}")
    plan = make_plan(args.project, mode=args.mode, case_ids=args.case, trials=args.trials, run_id=run_id)
    plan.lab_variant = variant.variant
    print(f"bug-hunt lab · variant {variant.variant}: {variant.brief}\n")
    os.environ[LAB_ENV] = ",".join(variant.switches)
    try:
        return _run_plan(plan, args.yes, args.max_workers)
    finally:
        os.environ.pop(LAB_ENV, None)


# ---------------------------------------------------------------- grade
def _cell(m: dict | None, stat: str = "pass_rate") -> str:
    if not m or not m["run"]:
        return "  —  "
    v = m[stat] if m[stat] is not None else m["pass_rate"]
    return f"{v:5.2f}" + ("!" if m["s1_failures"] else " ")


def _print_report(graded, suite, verdict) -> None:
    from evalkit.evaluators.grader import summary  # noqa: PLC0415

    s = summary(graded, suite)
    print(f"Graded {len(graded.results)} trial(s) of {len({r.case_id for r in graded.results})} case(s).")
    for n in s["notes"]:
        _warn(n)
    cols = ["AG-1", "AG-2", "AG-3", "AG-4", "AG-5", "TU-7", "AG-6"]
    print("\nPer-agent scorecards (pass rate; AG-6 mean score; ! = S1 failure; — = not measured)")
    print(f"  {'agent':15}" + "".join(f"{c:>7}" for c in cols) + f"{'score':>8}{'S1 fails':>10}")
    for agent, card in s["agents"].items():
        cells = "".join(f"{_cell(card['metrics'].get(c), 'mean_score' if c == 'AG-6' else 'pass_rate'):>7}" for c in cols)
        comp = "  —  " if card["composite"] is None else f"{card['composite']:.2f}"
        print(f"  {agent:15}{cells}{comp:>8}{card['s1_failures']:>10}")
    print("\nSuite metrics (pass rate · checks run · skipped)")
    for metric, m in s["suite"].items():
        rate = "  —  " if m["pass_rate"] is None else f"{m['pass_rate']:.2f}"
        flag = f"   first failure: {m['first_failure'][:110]}" if m["failed"] or m["errors"] else ""
        print(f"  {metric:5} {rate:>5}  run {m['run']:>3}  skipped {m['skipped']:>3}{flag}")
    if graded.flaky:
        _warn(f"flaky cases: {', '.join(graded.flaky)}")
    print(f"\nGate: {verdict.verdict}")
    for r in verdict.reasons:
        print(f"  {r}")
    for line in verdict.lines:
        mark = {True: "✓", False: "✗", None: "?"}[line.ok]
        val = "not measured" if line.value is None else f"{line.value:.2f}"
        print(f"  {mark} {line.name}: {val} (min {line.minimum:.2f})")
    for f in verdict.s1_failures[:15]:
        _fail(f[:180])
    if len(verdict.s1_failures) > 15:
        print(f"  … {len(verdict.s1_failures) - 15} more S1 failure(s) in results.jsonl")


def _judge_for(suite, trajs, yes: bool):
    """(judge, rubrics) for `--judges`, or (None, None) after a dry run. Never calls the judge without --yes."""
    from evalkit.evaluators.judges import cache_folder, configured_rubrics, load_judges_config  # noqa: PLC0415
    from evalkit.evaluators.judges.cache import JudgeCache  # noqa: PLC0415
    from evalkit.evaluators.judges.geval_rubric import RubricJudge, plan  # noqa: PLC0415

    jcfg = load_judges_config()
    rubrics = configured_rubrics(jcfg)
    cache = JudgeCache(cache_folder(jcfg))
    runs = [(t, suite.context(suite.cases[t.meta.case_id])) for t in trajs if t.meta.case_id in suite.cases]
    jp = plan(runs, jcfg, rubrics, cache)
    print("judges: " + jp.describe(jcfg))
    new = jp.calls - jp.cached
    if new and not yes:
        print("judges: dry run — no judge calls made. Add --yes to call the judge (this costs money). Grading without judges.\n")
        return None, None
    client = None
    if new:
        load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            _fail("ANTHROPIC_API_KEY is not set (see .env.example) — grading without judges")
            return None, None
        from anthropic import Anthropic  # noqa: PLC0415

        client = Anthropic()
    return RubricJudge(client, jcfg, cache), rubrics


def _grade_and_report(project: str, source: Path, out_dir: Path | None, gate: bool = True, judges: bool = False, yes: bool = False) -> int:
    """Grade every trajectory under source, print the scorecards and gate, write results.jsonl / scorecard.json / gate.json."""
    import json  # noqa: PLC0415
    from dataclasses import asdict  # noqa: PLC0415
    from datetime import UTC, datetime  # noqa: PLC0415

    from evalkit.config.registry import ProjectSuite  # noqa: PLC0415
    from evalkit.evaluators.grader import grade, summary  # noqa: PLC0415
    from evalkit.reporting.jsonl_writer import write_results  # noqa: PLC0415
    from evalkit.schema import Trajectory  # noqa: PLC0415
    from evalkit.scoring.gates import evaluate_gates, load_gates  # noqa: PLC0415

    suite = ProjectSuite.load(project)
    folder = source / "trajectories" if (source / "trajectories").is_dir() else source
    files = [source] if source.is_file() else sorted(folder.rglob("*.json"))
    trajs = []
    for f in files:
        try:
            trajs.append(Trajectory.load(f))
        except (ValueError, KeyError):
            continue  # not a trajectory (manifest, notes)
    if not trajs:
        _fail(f"no trajectories found under {source}")
        return 2
    judge, rubrics = _judge_for(suite, trajs, yes) if judges else (None, None)
    graded = grade(suite, trajs, judge, rubrics)
    if judge is not None:
        print(f"judges: {judge.calls} judge call(s) made; results are advisory (S3) until calibrated\n")
    gates_path = (suite.project_dir / suite.project_cfg.gates).resolve()
    verdict = evaluate_gates(load_gates(gates_path), graded.results, suite.cases, graded.case_checks, graded.flaky)
    _print_report(graded, suite, verdict)
    if out_dir is None:
        out_dir = runs_dir(load_eval_config()) / f"grade-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_results(out_dir / "results.jsonl", graded.results, graded.case_checks, out_dir.name)
    (out_dir / "scorecard.json").write_text(json.dumps(summary(graded, suite), indent=2, ensure_ascii=False), encoding="utf-8")
    gate_doc = asdict(verdict) | {"exit_code": verdict.exit_code}
    (out_dir / "gate.json").write_text(json.dumps(gate_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    from evalkit.harness.cost import write_cost  # noqa: PLC0415
    from evalkit.reporting.html_report import build_report  # noqa: PLC0415
    from evalkit.reporting.junit_writer import write_junit  # noqa: PLC0415
    from evalkit.reporting.redaction import Redactor  # noqa: PLC0415

    redactor = Redactor(suite.base.recognizers)
    write_junit(out_dir / "junit.xml", graded.results, graded.case_checks, out_dir.name, redactor)
    cfg = load_eval_config()
    cost = write_cost(out_dir, out_dir.name, trajs, cfg.budget, runs_dir(cfg) / "cost_ledger.jsonl", judge.usage if judge else None)
    for a in cost["alerts"]:
        _warn(a)
    build_report(out_dir / "report.html", summary=summary(graded, suite), graded=graded, verdict=verdict, trajectories=graded.trajectories,
                 redactor=redactor, run_id=out_dir.name, project=project, cost=cost)  # fmt: skip
    print(f"\nresults: {out_dir / 'results.jsonl'}  ·  junit: {out_dir / 'junit.xml'}  ·  report: {out_dir / 'report.html'}")
    if gate:
        return verdict.exit_code
    return 1 if verdict.s1_failures else 0


def cmd_grade(args: argparse.Namespace) -> int:
    src = Path(args.path)
    if not src.exists():
        src = runs_dir(load_eval_config()) / args.path  # a run ID
    if not src.exists():
        _fail(f"{args.path}: not a file, a folder, or a run ID in the runs folder")
        return 2
    out = src if (src / "manifest.json").is_file() else (Path(args.out) if args.out else None)
    return _grade_and_report(args.project, src.resolve(), out, gate=True, judges=args.judges, yes=args.yes)


def cmd_report(args: argparse.Namespace) -> int:
    """Rebuild results.jsonl, junit.xml, report.html and cost.json from a run's stored trajectories (offline, no judges)."""
    src = Path(args.path)
    src = src if src.exists() else runs_dir(load_eval_config()) / args.path
    if not src.exists():
        _fail(f"{args.path}: not a run folder or run ID")
        return 2
    out = src if (src / "manifest.json").is_file() else (Path(args.out) if args.out else None)
    _grade_and_report(args.project, src.resolve(), out, gate=False)
    return 0


def cmd_full(args: argparse.Namespace) -> int:
    """All cases (k per severity), graded with the advisory judges. Dry run unless --yes (agents and judges cost money)."""
    from evalkit.harness.runner import execute, make_plan  # noqa: PLC0415

    plan = make_plan(args.project, mode="full")
    print(plan.describe() + " — plus the advisory judges on every conversation")
    if not args.yes:
        print("dry run — no model calls made. Add --yes to run the agents and the judges (this costs money).")
        return 0
    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _fail("ANTHROPIC_API_KEY is not set (see .env.example)")
        return 1
    summary = execute(plan, max_workers=args.max_workers)
    print(f"run folder: {summary.run_dir}\n")
    return _grade_and_report(plan.project, summary.run_dir, summary.run_dir, gate=True, judges=True, yes=True)


def cmd_calibrate(args: argparse.Namespace) -> int:
    import json  # noqa: PLC0415
    from dataclasses import asdict  # noqa: PLC0415

    from evalkit.evaluators.judges import load_judges_config  # noqa: PLC0415
    from evalkit.evaluators.judges.calibration import calibrate, judge_labels, labelling_sheet, load_labels, render  # noqa: PLC0415
    from evalkit.scoring.gates import load_gates  # noqa: PLC0415

    jcfg = load_judges_config()
    if args.template:
        src = Path(args.template)
        src = src if src.exists() else runs_dir(load_eval_config()) / args.template
        out = Path(args.out or f"labels_{args.rater}.yaml")
        n = labelling_sheet(src, jcfg, args.rater, out)
        _ok(f"{out}: {n} item(s) for {args.rater} to score 0–3 (write each score, then run `evalkit calibrate {out} --judged {src}`)")
        return 0
    if not args.labels or not args.judged:
        _fail("give the label file(s) and --judged <run folder with judge results>, or --template <run> --rater T1")
        return 2
    judged = Path(args.judged)
    judged = judged if judged.exists() else runs_dir(load_eval_config()) / args.judged
    labels = [lb for p in args.labels for lb in load_labels(Path(p))] + judge_labels(judged / "results.jsonl", jcfg)
    g = load_gates(repo_root() / "configs" / "gates.yaml")
    bar = g.judges if g else None
    results = calibrate(labels, *((bar.min_kappa, bar.min_agreement) if bar else ()))
    print(render(results))
    out = judged / "calibration.json"
    out.write_text(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ncalibration report: {out}")
    return 0


# ---------------------------------------------------------------- case suite (WP6)
def cmd_cases(args: argparse.Namespace) -> int:
    from evalkit.datasets.catalogue_import import import_catalogue  # noqa: PLC0415

    root = repo_root()
    pdir = _project_dir(root, args.project)
    pcfg = load_project_config(pdir / "project.yaml")
    rep = import_catalogue(pdir, pcfg, workbook=Path(args.workbook) if args.workbook else None, force=args.force)
    print(f"case files: {len(rep.written)} written, {len(rep.unchanged)} unchanged, {len(rep.kept_edits)} kept (edited)")
    for p in rep.kept_edits:
        _warn(f"kept your edited {p.relative_to(pdir).as_posix()} — the catalogue row differs; use --force to overwrite it")
    for p in rep.not_in_catalogue:
        _ok(f"{p.relative_to(pdir).as_posix()} has no catalogue row (tester-added) — left as it is")
    if rep.written:
        print("next: `evalkit data` to rebuild the seed database's case tables, then `evalkit lint-cases`")
    return 0


def cmd_lint_cases(args: argparse.Namespace) -> int:
    from evalkit.datasets.lint import lint  # noqa: PLC0415

    root = repo_root()
    pdir = _project_dir(root, args.project)
    findings = lint(pdir, load_project_config(pdir / "project.yaml"), load_eval_config())
    shown = [f for f in findings if args.all or f.level != "note"]
    for f in shown:
        print(f.render(pdir))
    count = {lvl: sum(f.level == lvl for f in findings) for lvl in ("error", "warning", "note")}
    hidden = "" if args.all else f" ({count['note']} note(s) hidden — add --all to see what a reviewer checks by hand)"
    print(f"\nlint: {count['error']} error(s), {count['warning']} warning(s){hidden}")
    return 1 if count["error"] else 0


def cmd_coverage(args: argparse.Namespace) -> int:
    from evalkit.config.registry import load_references  # noqa: PLC0415
    from evalkit.datasets.coverage import catalogue_matrix, compare, coverage, render  # noqa: PLC0415
    from evalkit.datasets.loader import load_case_files  # noqa: PLC0415

    root = repo_root()
    pdir = _project_dir(root, args.project)
    pcfg = load_project_config(pdir / "project.yaml")
    loaded, problems = load_case_files(pdir, pcfg)
    if problems:
        _fail(f"{len(problems)} case file(s) could not be read — run `evalkit lint-cases`")
    _, unreviewed = load_references(pdir / "reference_trajectories")
    cov = coverage([lc.case for lc in loaded], pcfg, unreviewed, load_eval_config().trials_for)
    print(render(cov))
    if args.against_catalogue:
        if not pcfg.catalogue:
            _fail("project.yaml has no catalogue workbook to compare with")
            return 2
        diffs = compare(cov, catalogue_matrix((pdir / pcfg.catalogue).resolve()))
        print("\nAgainst the catalogue: " + ("identical" if not diffs else f"{len(diffs)} difference(s)"))
        for d in diffs:
            _fail(d)
        return 1 if diffs or problems else 0
    return 1 if problems else 0


def cmd_planned(args: argparse.Namespace) -> int:
    wp, when, what = PLANNED[args.command]
    print(f"'evalkit {args.command}' is not built yet. It will {what}; planned in {wp} (by {when}) — see EXECUTION_PLAN.md.")
    return 2


# ---------------------------------------------------------------- entry point
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evalkit", description="Evaluate every agent in a multi-agent BFSI system.")
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    def add(name: str, fn, help_: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.add_argument("--project", default="kyc_onboarding", help="project folder under projects/ (default: kyc_onboarding)")
        sp.set_defaults(func=fn)
        return sp

    add("doctor", cmd_doctor, "check Python, configuration, seed data, API key and NLP model")
    sp = add("data", cmd_data, "rebuild the synthetic seed database and run the fixture check")
    sp.add_argument("--check-only", action="store_true", help="only run the fixture check on the current seed database")
    sp = add("test", cmd_test, "run the framework's own tests (live-API tests excluded unless --with-api)")
    sp.add_argument("--with-api", action="store_true", help="include tests marked 'api' (needs ANTHROPIC_API_KEY)")
    sp.add_argument("pytest_args", nargs="*", help="extra arguments passed to pytest")
    add("smoke", cmd_smoke, "offline confidence check: setup, fixture check, framework tests (live golden cases: evalkit run --mode smoke)")
    for name, fn, help_ in (
        ("eval", cmd_eval, "run named case(s) live and store their trajectories (dry run unless --yes)"),
        ("run", cmd_run, "run every case of a run mode live and store trajectories (dry run unless --yes)"),
    ):
        sp = add(name, fn, help_)
        if name == "eval":
            sp.add_argument("--case", action="append", required=True, help="case id; repeat for several")
        else:
            sp.add_argument("--mode", choices=["smoke", "gate", "full"], required=True)
        sp.add_argument("--trials", type=int, default=None, help="override trials per case (default: per severity / case)")
        sp.add_argument("--max-workers", type=int, default=None, help="parallel trials (default: configs/eval.yaml)")
        sp.add_argument("--yes", action="store_true", help="really run: makes live model calls")
    sp = add("cases", cmd_cases, "import the catalogue workbook into datasets/<pattern>/<case_id>.yaml (keeps edited files unless --force)")
    sp.add_argument("--workbook", default=None, help="workbook to import (default: project.yaml › catalogue)")
    sp.add_argument("--force", action="store_true", help="overwrite case files that differ from the catalogue")
    sp = add("lint-cases", cmd_lint_cases, "check every case YAML file and explain each problem in plain English")
    sp.add_argument("--all", action="store_true", help="also show notes (what a reviewer checks by hand)")
    sp = add("coverage", cmd_coverage, "print the agent × pattern coverage matrix and oracle completeness")
    sp.add_argument("--against-catalogue", action="store_true", help="compare the matrix with the catalogue workbook")
    sp = add("gate", cmd_gate, "run all S1 cases (k = 3, judges off) live, grade them and apply configs/gates.yaml (dry run unless --yes)")
    sp.add_argument("--max-workers", type=int, default=None, help="parallel trials (default: configs/eval.yaml)")
    sp.add_argument("--yes", action="store_true", help="really run: makes live model calls")
    sp = add("grade", cmd_grade, "grade stored trajectories offline (a run folder or ID, a folder of trajectory files, or one file)")
    sp.add_argument("path", help="run folder, run ID, folder of trajectory JSON files, or one trajectory file")
    sp.add_argument("--out", default=None, help="where to write results.jsonl when grading files outside a run folder")
    sp.add_argument("--judges", action="store_true", help="add the advisory LLM judges (configs/judges.yaml); a dry run unless --yes")
    sp.add_argument("--yes", action="store_true", help="with --judges: really call the judge model (costs money)")
    sp = add("report", cmd_report, "rebuild results.jsonl, junit.xml, report.html and cost.json for a run (offline)")
    sp.add_argument("path", help="run folder or run ID")
    sp.add_argument("--out", default=None, help="output folder when the path is not a run folder")
    sp = add("full", cmd_full, "run all cases (k per severity) and grade them with the advisory judges (dry run unless --yes)")
    sp.add_argument("--max-workers", type=int, default=None, help="parallel trials (default: configs/eval.yaml)")
    sp.add_argument("--yes", action="store_true", help="really run: makes live agent and judge calls")
    sp = add("calibrate", cmd_calibrate, "compare judge scores with tester labels (agreement, Cohen's κ) or write a labelling sheet")
    sp.add_argument("labels", nargs="*", help="label files (YAML sheets or JSONL) from the testers")
    sp.add_argument(
        "--judged", default=None, help="run folder (or ID) graded with --judges --yes, whose results.jsonl holds the judge scores"
    )
    sp.add_argument("--template", default=None, help="write a labelling sheet for the traces of this run folder (or ID)")
    sp.add_argument("--rater", default="T1", help="who labels the sheet (T1, T2 …)")
    sp.add_argument("--out", default=None, help="where to write the labelling sheet")
    sp = add("lab", cmd_lab, "bug-hunt lab: run cases against one seeded-defect variant of the system (dry run unless --yes)")
    sp.add_argument("--variant", required=True, help="variant ID, e.g. LAB-3 (training/lab/variants/LAB-3.yaml)")
    sp.add_argument("--case", action="append", default=None, help="case id to run against the variant; repeat for several")
    sp.add_argument("--mode", choices=["smoke", "gate", "full"], default=None, help="or run a whole run mode against it")
    sp.add_argument("--trials", type=int, default=None, help="override trials per case (default: per severity / case)")
    sp.add_argument("--max-workers", type=int, default=None, help="parallel trials (default: configs/eval.yaml)")
    sp.add_argument("--yes", action="store_true", help="really run: makes live model calls")
    for name, (wp, when, what) in PLANNED.items():
        add(name, cmd_planned, f"[{wp}, by {when}] {what}")
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"configuration problem:\n{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
