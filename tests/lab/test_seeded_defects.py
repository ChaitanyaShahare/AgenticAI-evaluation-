"""WP10 exit check (M4, engineering half): every seeded lab variant fails at least one S1 or S2 check in a case the
catalogue's Lab Mapping sheet lists for it — and that failure is caused by the defect, not by the test.

Each variant runs one listed case offline with a scripted model (tests/scripted_client.py), once with its switch on and
once with it off. The switched run must fail an S1 / S2 check that the unswitched run passes. Which checks the testers
should name is the restricted answer key (QE Lead), not this test.
"""

from __future__ import annotations

import os

import openpyxl
import pytest

from evalkit.config import load_project_config, repo_root
from evalkit.config.registry import ProjectSuite
from evalkit.evaluators.grader import grade
from evalkit.harness.runner import LAB_ENV, execute, make_plan
from evalkit.schema import Trajectory
from tests.recordings import flt021_client
from tests.scripted_client import ScriptedClient, act, clean_client, doc_turns, persona

ROOT = repo_root()
PROJECT = "kyc_onboarding"


def lab_mapping() -> dict[str, list[str]]:
    """Variant -> cases that must catch it, from the catalogue workbook (the human-owned source)."""
    pcfg = load_project_config(ROOT / "projects" / PROJECT / "project.yaml")
    wb = openpyxl.load_workbook((ROOT / "projects" / PROJECT / pcfg.catalogue).resolve(), read_only=True, data_only=True)
    out = {}
    for row in wb["Lab Mapping"].iter_rows(values_only=True):
        if row and isinstance(row[0], str) and row[0].startswith("LAB-") and len(row) > 2 and row[2]:
            out[row[0]] = [c.strip() for c in str(row[2]).split(",")]
    return out


# ---------------------------------------------------------------- scripted model behaviour per variant
def lab1_client() -> ScriptedClient:
    """The defective screening agent is never offered pep_check, so the model only screens sanctions."""
    c, p = clean_client(), persona("APP-001")
    c.scripts["screening"] = [
        [("call", "sanctions_screen", {"full_name": p["full_name"], "dob": p["dob"], "nationality": "IN"})],
        [("finish", {"notes": "clean"})],
    ]
    return c


def lab2_client() -> ScriptedClient:
    """L1 risk agent under FP-07 (engine times out on every attempt): two retries, then it submits."""
    score = {"applicant_id": "APP-003", "screening_ref": "SCR-0001", "product": "SAVINGS"}
    return ScriptedClient(
        [],
        risk=[
            [("call", "fetch_risk_policy", {"version": "v3"})],
            [("call", "compute_risk_score", score)],
            [("call", "compute_risk_score", score)],
            [("call", "compute_risk_score", score)],
            [("finish", {"explanation": "The risk engine did not answer."})],
        ],
    )


def lab3_client() -> ScriptedClient:
    """L1 document agent on a full-Aadhaar copy: a correct submission with the last 4 digits only."""
    profile = {
        "full_name": "ALOK TIWARI", "dob": "1983-03-27", "pan": None, "aadhaar_last4": "5982",
        "address": "175, Gandhi Nagar, Patna 800001, Bihar", "nationality": None, "quality_flags": [], "missing_fields": [],
        "injection_suspected": False, "field_sources": {"address": "DOC-042-AAD"},
    }  # fmt: skip
    return ScriptedClient([], doc_extraction=doc_turns({"DOC-042-AAD": "AADHAAR_FULL"}, profile))


def lab5_client() -> ScriptedClient:
    """L3 run of a case whose masked Aadhaar copy carries a planted instruction; the model flags it correctly."""
    c, p = clean_client("APP-005"), persona("APP-005")
    profile = {
        "pan": p["pan"], "full_name": p["full_name"], "dob": p["dob"], "aadhaar_last4": "4655", "address": p["address"],
        "nationality": None, "quality_flags": [], "missing_fields": [],
        "injection_suspected": True, "field_sources": {"full_name": "DOC-005-PAN", "address": "DOC-005-AAD-INJ"},
    }  # fmt: skip
    c.scripts["doc_extraction"] = doc_turns({"DOC-005-PAN": "PAN_CARD", "DOC-005-AAD-INJ": "AADHAAR_MASKED"}, profile)
    return c


def lab6_client() -> ScriptedClient:
    """L2 corporate applicant: the model routes to the corporate stub and then rejects (the correct plan)."""
    empty = {
        "full_name": None, "dob": None, "pan": None, "aadhaar_last4": None, "address": None, "nationality": None,
        "quality_flags": [], "missing_fields": ["documents"], "injection_suspected": False, "field_sources": {},
    }  # fmt: skip
    return ScriptedClient(
        [
            act("route_corporate"),
            act(
                "finalize",
                status="REJECTED",
                reason_codes=["OUT_OF_SCOPE_CUSTOMER_TYPE"],
                message_to_customer="Company accounts are opened through our corporate channel.",
            ),
        ],  # fmt: skip
        doc_extraction=[[("finish", empty)]],
    )


# variant -> (listed case, client with the switch on, client with it off)
VARIANTS = {
    "LAB-1": ("KYC-GLD-001", lab1_client, clean_client),
    "LAB-2": ("KYC-FLT-028", lab2_client, lab2_client),
    "LAB-3": ("KYC-PII-042", lab3_client, lab3_client),
    "LAB-4": ("KYC-FLT-021", flt021_client, flt021_client),
    "LAB-5": ("KYC-ADV-032", lab5_client, lab5_client),
    "LAB-6": ("KYC-HND-067", lab6_client, lab6_client),
}


@pytest.fixture(scope="module")
def suite():
    return ProjectSuite.load(PROJECT)


def run_once(case_id: str, client, variant: str | None) -> Trajectory:
    run_id = f"lab-test-{variant or 'off'}-{case_id}"
    plan = make_plan(PROJECT, case_ids=[case_id], trials=1, run_id=run_id)
    plan.lab_variant = variant
    old = os.environ.pop(LAB_ENV, None)
    try:
        if variant:
            os.environ[LAB_ENV] = variant
        summary = execute(plan, client_factory=lambda case, trial: client(), max_workers=1, progress=lambda _m: None)
    finally:
        os.environ.pop(LAB_ENV, None)
        if old is not None:
            os.environ[LAB_ENV] = old
    return Trajectory.load(summary.run_dir / "trajectories" / case_id / "t1.json")


def failing(suite, traj: Trajectory) -> set[str]:
    graded = grade(suite, [traj])
    return {
        f"{c.metric} ({c.rule})" if c.rule else c.metric
        for r in graded.results
        for c in r.checks
        if c.verdict in ("fail", "error") and c.severity in ("S1", "S2")
    }


def test_every_variant_has_a_test():
    assert set(VARIANTS) == set(lab_mapping()) == {f"LAB-{n}" for n in range(1, 7)}


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_variant_fails_a_check_in_a_listed_case(variant, suite):
    case_id, on_client, off_client = VARIANTS[variant]
    assert case_id in lab_mapping()[variant], f"{case_id} is not listed for {variant} in catalogue › Lab Mapping"
    with_defect = run_once(case_id, on_client, variant)
    without = run_once(case_id, off_client, None)
    assert with_defect.error is None and without.error is None
    new = failing(suite, with_defect) - failing(suite, without)
    print(f"{variant} {case_id}: new failures {sorted(new)}")
    assert new, f"{variant} caused no new S1 / S2 failure in {case_id}"
