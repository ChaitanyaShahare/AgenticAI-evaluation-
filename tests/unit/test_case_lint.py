"""Case suite as YAML: the import reproduces the catalogue, the loader feeds the harness, coverage equals the catalogue's,
and lint catches every class of tester mistake with a message that says how to fix it."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from evalkit.config import load_eval_config, load_project_config, repo_root
from evalkit.datasets.catalogue_import import COLUMNS, EXCLUDED, import_catalogue, read_rows
from evalkit.datasets.coverage import catalogue_matrix, compare, coverage
from evalkit.datasets.lint import lint, prepare
from evalkit.datasets.loader import load_case_files, load_cases, read_case_file

ROOT = repo_root()
KYC = ROOT / "projects" / "kyc_onboarding"
PCFG = load_project_config(KYC / "project.yaml")
WORKBOOK = (KYC / PCFG.catalogue).resolve()
GLD = KYC / "datasets" / "golden" / "KYC-GLD-001.yaml"
# QE Lead decisions of 23 Oct 2026 that make a case file differ from catalogue v0.12 on purpose (catalogue v0.13 to follow)
OUTCOME_CORRECTED = {"KYC-AGT-SCR-007", "KYC-AGT-SCR-057"}  # expected_outcome text aligned with the fixtures


# ---------------------------------------------------------------- import
@pytest.fixture(scope="module")
def rows():
    return {r["Case ID"]: r for _, r in read_rows(WORKBOOK)}


def test_every_catalogue_row_has_a_case_file_with_its_columns(rows):
    loaded = {lc.case.case_id: lc for lc in load_case_files(KYC, PCFG)[0]}
    assert set(loaded) == set(rows) and len(rows) == 110
    for cid, row in rows.items():
        c = loaded[cid].case
        for fld, col in COLUMNS.items():
            if fld in ("trials", "run_sets", "documents") or (fld == "expected_outcome" and cid in OUTCOME_CORRECTED):
                continue
            assert getattr(c, fld) == ("" if row[col] is None else str(row[col]).strip()), (cid, fld)
        assert c.trials == row["Trials (k)"] and ", ".join(c.run_sets) == row["Run sets"]
        docs = [d.doc for d in c.documents]
        assert all(d in row["Documents"] for d in docs) and (docs or row["Documents"] == "—")
        assert loaded[cid].path.parent.name == Path(PCFG.datasets[c.pattern]).name


def test_lab_answer_key_never_reaches_case_files():
    for p in (KYC / "datasets").rglob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        assert "lab" not in yaml.safe_load(text) and "LAB-" not in text.split("notes:")[0], p.name
    assert EXCLUDED == ("Lab defect caught",)


def test_reimport_is_a_no_op_and_protects_edits(tmp_path):
    proj = tmp_path / "kyc"
    shutil.copytree(KYC / "datasets", proj / "datasets")
    rep = import_catalogue(proj, PCFG, workbook=WORKBOOK)
    # files the QE Lead completed (agent outputs) are kept; every other file is exactly the import
    completed = {p.stem for p in (proj / "datasets").rglob("*.yaml") if "drafted by Claude Code" in p.read_text(encoding="utf-8")}
    assert rep.written == [] and {p.stem for p in rep.kept_edits} == completed and len(rep.unchanged) == 110 - len(completed)
    assert OUTCOME_CORRECTED <= completed
    edited = proj / "datasets" / "golden" / "KYC-GLD-002.yaml"
    edited.write_text(edited.read_text(encoding="utf-8").replace("risk_score: 31", "risk_score: 32"), encoding="utf-8")
    added = proj / "datasets" / "golden" / "KYC-GLD-901.yaml"
    added.write_text(GLD.read_text(encoding="utf-8").replace("KYC-GLD-001", "KYC-GLD-901"), encoding="utf-8")
    rep = import_catalogue(proj, PCFG, workbook=WORKBOOK)
    assert edited in rep.kept_edits and rep.not_in_catalogue == [added]
    assert "risk_score: 32" in edited.read_text(encoding="utf-8")
    rep = import_catalogue(proj, PCFG, workbook=WORKBOOK, force=True)
    assert edited in rep.written and "risk_score: 31" in edited.read_text(encoding="utf-8")


def test_structured_end_state_follows_the_outcome_text():
    c = read_case_file(GLD)
    assert (c.expected.status, c.expected.risk_tier, c.expected.risk_score, c.expected.record, c.expected.reason_codes) == (
        "APPROVED", "LOW", 22, True, [],
    )  # fmt: skip
    assert c.expected.agent_outputs == {} and c.expected.arguments == {}  # left for the QE Lead
    mtn = read_case_file(KYC / "datasets" / "multi_turn" / "KYC-MTN-089.yaml")
    assert [(d.doc, d.turn) for d in mtn.documents] == [("DOC-089-PAN", 1), ("DOC-089-UB", 1), ("DOC-089-UB2", 2)]
    assert read_case_file(KYC / "datasets" / "missing_info" / "KYC-MIS-087.yaml").form_updates == {"nationality": "IN"}


def test_loader_gives_the_harness_its_cases():
    cases = {c.case_id: c for c in load_cases(KYC, PCFG)}
    g = cases["KYC-GLD-001"]
    assert g.match_mode == "superset" and g.reference == ["RT-01"] and g.forbidden_tools == ["escalate_to_edd"]
    assert "KYC-PAR-094" in g.twins and "TU-7" in g.metrics
    assert cases["KYC-MIS-081"].tool_notes == ["forbidden: verify_pan (any PAN value)"]


# ---------------------------------------------------------------- coverage
def test_coverage_equals_the_catalogue():
    cov = coverage([lc.case for lc in load_case_files(KYC, PCFG)[0]], PCFG, trials_for=load_eval_config().trials_for)
    assert {a: cov.total(a) for a in cov.agents} == {"E2E": 15, "DOC": 17, "IDV": 11, "RSK": 18, "SCR": 15, "SUP": 34}
    assert cov.run_sets == {"smoke": (10, 10), "gate": (70, 210), "full": (110, 250)}
    assert compare(cov, catalogue_matrix(WORKBOOK)) == []
    assert cov.gaps == []


# ---------------------------------------------------------------- lint
@pytest.fixture(scope="module")
def cfg():
    return load_eval_config()


def test_shipped_cases_lint_without_errors(cfg):
    findings = lint(KYC, PCFG, cfg)
    assert [f.message for f in findings if f.level == "error"] == []


def base() -> dict:
    data = yaml.safe_load(GLD.read_text(encoding="utf-8"))
    data["case_id"] = "KYC-GLD-901"
    return data


def write(tmp_path: Path, data, folder: str = "golden", name: str | None = None) -> Path:
    p = tmp_path / folder / f"{name or (data['case_id'] if isinstance(data, dict) else 'x')}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def prepared(cfg):
    return prepare(KYC, PCFG, cfg)


def messages(prepared, cfg, path: Path) -> list[str]:
    return [f.message for f in lint(KYC, PCFG, cfg, extra_files=[path], prepared=prepared) if f.file == path]


def edit(**changes):
    def apply(d):
        for k, v in changes.items():
            target = d
            *parents, last = k.split("__")
            for p in parents:
                target = target[p]
            if v is DROP:
                target.pop(last)
            else:
                target[last] = v
        return d

    return apply


DROP = object()
MISTAKES = [
    ("unknown field", edit(severty="S1"), "unknown field — did you mean 'severity'?"),
    ("missing field", edit(title=DROP), "title: required field is missing"),
    ("value not allowed", edit(severity="S4"), "'S4' is not allowed"),
    ("bad run set", edit(run_sets=["nightly"]), "'nightly' is not allowed"),
    ("ID scheme", edit(case_id="kyc-gld-1"), "does not follow the ID scheme"),
    ("unknown pattern", edit(pattern="Happy path"), "'Happy path' is not a catalogue pattern"),
    ("trials", edit(trials=1), "S1 cases run k = 3 trial(s)"),
    ("gate set", edit(run_sets=["smoke", "full"]), "an S1 case must be in the gate run set"),
    ("full set", edit(run_sets=["smoke", "gate"]), "every case is in the full run set"),
    ("approver", edit(approver="yes"), "approver 'yes' is not allowed"),
    ("match mode", edit(match_mode="loose"), "match_mode 'loose' must start with"),
    ("unknown tool", edit(required_tools="verfy_pan, pep_check"), "unknown tool 'verfy_pan' — did you mean 'verify_pan'?"),
    ("required and forbidden", edit(forbidden_tools="pep_check"), "pep_check is both required and forbidden"),
    ("unknown reference", edit(reference=["RT-99"]), "reference trajectory RT-99 does not exist"),
    ("unknown twin", edit(twin_pair="Clean twin of KYC-ADV-999"), "names KYC-ADV-999, which is not a case"),
    ("unknown metric", edit(checks="TR-1, TU-9"), "names TU-9, which is not a metric"),
    ("missing end state", edit(expected__status=None), "expected_outcome states status = 'APPROVED' but expected.status is empty"),
    ("L3 without status", edit(expected__status=None, expected_outcome="profile fields extracted"), "an L3 case needs expected.status"),
    ("text disagrees", edit(expected__risk_score=23), "expected.risk_score is 23 but expected_outcome says 22"),
    (
        "contradiction",
        edit(expected__record=False, expected_outcome="applications.status = APPROVED"),
        "an approved application gets a record",
    ),
    ("unknown agent", edit(expected__agent_outputs={"IDV": {"overall": "VERIFIED"}}), "names agent 'IDV'"),
    ("unknown argument", edit(expected__arguments={"verify_pan": {"pan_no": "X"}}), "names argument 'pan_no' — did you mean 'pan'?"),
    ("applicant", edit(applicant="APP-999"), "applicant APP-999 is not in the seed database"),
    ("document", edit(documents=["DOC-999-PAN"]), "document DOC-999-PAN is not in the seed database"),
    ("fixture", edit(fixtures=["FP-99"]), "fixture profile FP-99 does not exist"),
    ("not in seed", edit(), "not built into the seed database yet — run `evalkit data`"),
]


@pytest.mark.parametrize(("label", "mutate", "expected"), MISTAKES, ids=[m[0] for m in MISTAKES])
def test_lint_catches_each_mistake(tmp_path, cfg, prepared, label, mutate, expected):
    data = mutate(base())
    path = write(tmp_path, data, name=data.get("case_id", "KYC-GLD-901") if label != "ID scheme" else "kyc-gld-1")
    found = messages(prepared, cfg, path)
    assert any(expected in m for m in found), found


def test_lint_file_level_mistakes(tmp_path, cfg, prepared):
    broken = write(tmp_path, "case_id: KYC-GLD-902\ntitle: [unclosed\n", name="KYC-GLD-902")
    assert any("not valid YAML" in m and "line" in m for m in messages(prepared, cfg, broken))
    misnamed = write(tmp_path, base(), name="KYC-GLD-903")
    assert any("rename KYC-GLD-903.yaml to KYC-GLD-901.yaml" in m for m in messages(prepared, cfg, misnamed))
    wrong_folder = write(tmp_path, base(), folder="edge")
    assert any("belongs in datasets/golden/" in m for m in messages(prepared, cfg, wrong_folder))
    dup = write(tmp_path, {**base(), "case_id": "KYC-GLD-001"})
    assert any("case ID KYC-GLD-001 is also used by" in m for m in messages(prepared, cfg, dup))


def test_cli_lint_and_coverage(capsys):
    from evalkit import cli

    assert cli.main(["lint-cases"]) == 0
    assert "0 error(s)" in capsys.readouterr().out
    assert cli.main(["coverage", "--against-catalogue"]) == 0
    assert "Against the catalogue: identical" in capsys.readouterr().out
