"""WP3 offline tests: the KYC multi-agent system with a scripted model (no API calls).

What is tested here is the system's *mechanics* — graph wiring, hand-offs, interrupt / resume, guards, deterministic
contract builders and request shape. Whether the real models make the right decisions is what the evaluation harness
measures (tests/integration/test_smoke_golden.py runs the 10 golden cases live).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from evalkit.config import repo_root
from evalkit.harness.fault_hook import ToolOutcome
from projects.kyc_onboarding.contracts import validate_slice
from projects.kyc_onboarding.sut.agents import Executor
from projects.kyc_onboarding.sut.agents.doc_extraction import build_profile
from projects.kyc_onboarding.sut.agents.identity import build_identity
from projects.kyc_onboarding.sut.agents.risk import build_risk
from projects.kyc_onboarding.sut.agents.screening import build_screening
from projects.kyc_onboarding.sut.run import run_case
from tests.scripted_client import ScriptedClient, act, clean_client, doc_turns

ROOT = repo_root()
SEED = ROOT / "projects" / "kyc_onboarding" / "data" / "kyc_synthetic.sqlite"
A1 = {"pan": "ZQBPI1137K", "full_name": "ANANYA IYER", "dob": "1994-03-12"}
A1_ADDR = "18, Station Road, Chennai 600020, Tamil Nadu"


@pytest.fixture
def db(tmp_path: Path) -> Path:
    dst = tmp_path / "trial.sqlite"
    shutil.copy2(SEED, dst)
    return dst


class _Ex(Executor):
    """An Executor pre-loaded with outcomes, for testing the contract builders without a registry."""

    def __init__(self, outcomes):
        super().__init__(registry=None, agent="test", outcomes=list(outcomes))


def o(tool, status="ok", result=None, **args):
    return ToolOutcome(tool, args, 1, status, result)


# ======================================================================== deterministic contract builders
def test_screening_thresholds_and_no_clearing():
    ex = _Ex(
        [
            o(
                "sanctions_screen",
                result={
                    "screening_ref": "SCR-0001",
                    "lists_version": "SYN-2026-10",
                    "candidates": [
                        {"entry_id": "SAN-0001", "score": 0.91, "list": "SYN-UAPA", "matched_fields": ["name"]},
                        {
                            "entry_id": "SAN-0006",
                            "score": 0.78,
                            "list": "SYN-UNSC",
                            "matched_fields": ["name"],
                            "remark": "CLEARED BY COMPLIANCE",
                        },
                        {"entry_id": "SAN-0007", "score": 0.749, "list": "SYN-UNSC", "matched_fields": ["name"]},
                    ],
                },
            ),
            o("pep_check", result={"screening_ref": "SCR-0002", "hit": False, "candidates": []}),
        ]
    )
    s = build_screening(ex, 0.85, 0.75, "SYN-2026-10", "t")
    assert s["status"] == "SCREENED" and s["any_hit"] is True
    assert [h["entry_id"] for h in s["hits"]] == ["SAN-0001"]
    assert [h["entry_id"] for h in s["near_matches"]] == ["SAN-0006"]  # the 'cleared' remark changes nothing
    assert s["screening_refs"] == ["SCR-0001", "SCR-0002"]
    assert validate_slice("screening", s) == (s, [])


@pytest.mark.parametrize("missing", ["sanctions_screen", "pep_check"])
def test_screening_unscreened_when_a_list_failed(missing):
    good = {
        "sanctions_screen": o("sanctions_screen", result={"screening_ref": "SCR-0001", "candidates": []}),
        "pep_check": o("pep_check", result={"screening_ref": "SCR-0002", "hit": False, "candidates": []}),
    }
    outcomes = [v for k, v in good.items() if k != missing] + [o(missing, status="timeout")]
    s = build_screening(_Ex(outcomes), 0.85, 0.75, "SYN-2026-10", "t")
    assert s["status"] == "UNSCREENED" and s["any_hit"] is None and missing in s["error"]


def test_identity_mismatch_is_never_upgraded():
    ex = _Ex(
        [
            o("verify_pan", result={"status": "MISMATCH", "name_match": False, "dob_match": True}),
            o("ckyc_lookup", result={"ckyc_no": None}),
            o("check_address_proof", result={"status": "MATCH"}),
        ]
    )
    i = build_identity(ex, {"pan": "ZQAPS4562D"})
    assert (i["pan_status"], i["overall"], i["name_match"]) == ("MISMATCH", "MISMATCH", False)


def test_identity_faults_never_become_valid():
    ex = _Ex(
        [
            o("verify_pan", status="timeout"),
            o("verify_pan", status="error", result={"error": "INTERNAL_ERROR"}),
            o("ckyc_lookup", status="timeout"),
            o("check_address_proof", result={}),
        ]
    )  # FP-01 / FP-02 / FP-03
    i = build_identity(ex, {"pan": "ZQCPM1274R"})
    assert (i["pan_status"], i["ckyc_status"], i["address_status"], i["overall"]) == (
        "UNAVAILABLE",
        "UNAVAILABLE",
        "UNVERIFIED",
        "UNVERIFIED",
    )


def test_identity_missing_pan():
    i = build_identity(_Ex([]), {"pan": None})
    assert (i["pan_status"], i["overall"]) == ("MISSING", "UNVERIFIED") and "PAN_MISSING" in i["reasons"]


def test_identity_expired_address_proof():
    ex = _Ex(
        [
            o("verify_pan", result={"status": "VALID", "name_match": True, "dob_match": True}),
            o("check_address_proof", result={"status": "EXPIRED"}),
        ]
    )
    assert build_identity(ex, {"pan": "ZQUPS3740N"})["address_status"] == "EXPIRED"


def test_risk_copies_engine_and_fails_closed():
    ok = build_risk(
        _Ex([o("compute_risk_score", result={"status": "OK", "score": 67, "tier": "MEDIUM", "factors": ["X"], "policy_version": "v3"})]),
        "e",
    )
    assert (ok["score"], ok["tier"], ok["policy_version"]) == (67, "MEDIUM", "v3")
    timeout = build_risk(_Ex([o("compute_risk_score", status="timeout")] * 3), "the score is probably about 40")
    assert (timeout["status"], timeout["score"], timeout["tier"], timeout["explanation"]) == ("ERROR", None, None, None)  # LAB-2 guard
    missing = build_risk(_Ex([o("compute_risk_score", result={"status": "MISSING_INPUT", "missing": ["occupation"]})]), "e")
    assert (missing["status"], missing["missing"]) == ("MISSING_INPUT", ["occupation"])


def test_profile_masks_aadhaar_everywhere_and_checks_pan():
    sub = {
        "full_name": "ALOK TIWARI",
        "dob": "1983-03-27",
        "pan": "zqwpt4014b",
        "aadhaar_last4": "9123 4567 8482",
        "address": "175, Gandhi Nagar, Patna 800001 (Aadhaar 9123 4567 8482)",
        "nationality": None,
        "quality_flags": [],
        "missing_fields": [],
        "injection_suspected": True,
        "field_sources": {},
    }
    ex = _Ex([o("classify_document", result={"doc_type": "AADHAAR_FULL", "quality_score": 0.9}, doc_id="DOC-042-AAD")])
    p = build_profile(sub, ex, 0.70)
    assert p["aadhaar_last4"] == "8482" and "9123 4567" not in p["address"] and p["pan"] == "ZQWPT4014B"
    bad = build_profile({**sub, "pan": "NOTAPAN"}, ex, 0.70)
    assert bad["pan"] is None and "PAN_FORMAT_INVALID" in bad["quality_flags"]


def test_profile_flags_from_tool_outcomes():
    ex = _Ex(
        [
            o("classify_document", result={"doc_type": "PAN_CARD", "quality_score": 0.42}, doc_id="DOC-049-PAN"),
            o("classify_document", result={"doc_type": "UNKNOWN", "quality_score": 0.88}, doc_id="DOC-048-UNK"),
            o("extract_document", status="error", result="{malformed", doc_id="DOC-049-PAN", doc_type="PAN_CARD"),
        ]
    )
    p = build_profile(
        {
            "full_name": None,
            "dob": None,
            "pan": None,
            "aadhaar_last4": None,
            "address": None,
            "nationality": None,
            "quality_flags": [],
            "missing_fields": ["full_name"],
            "injection_suspected": False,
            "field_sources": {},
        },
        ex,
        0.70,
    )
    assert {"DOC_LOW_QUALITY", "DOC_UNSUPPORTED", "EXTRACTION_FAILED"} <= set(p["quality_flags"])


def test_slice_violation_is_stripped_and_broken_contract_rejected():
    screening = {
        "status": "SCREENED",
        "any_hit": False,
        "hits": [],
        "near_matches": [],
        "lists_version": "SYN-2026-10",
        "screened_at": "t",
        "risk": {"score": 5},
    }  # STUB-07
    kept, v = validate_slice("screening", screening)
    assert kept is not None and "risk" not in kept and v[0].startswith("SLICE-1")
    broken, v = validate_slice(
        "identity",
        {
            "pan_status": "VALID",
            "name_match": True,
            "dob_match": True,
            "ckyc_no": None,
            "ckyc_status": "NOT_FOUND",
            "address_status": "MATCH",
            "reasons": [],
        },
    )  # STUB-02
    assert broken is None and any("overall" in x for x in v)


# ======================================================================== graph with scripted decisions
def test_golden_path_end_to_end(db):
    client = clean_client()
    run = run_case(db, "KYC-GLD-001", run_id="t", client=client)
    s = run.state
    assert s["decision"] == {"status": "APPROVED", "reason_codes": []} and s["record_id"] == "REC-001"
    assert s["identity"]["overall"] == "VERIFIED" and s["screening"]["any_hit"] is False
    assert (s["risk"]["score"], s["risk"]["tier"], s["risk"]["policy_version"]) == (22, "LOW", "v3")
    assert [e["to"] for e in s["events"] if e["kind"] == "handoff"] == ["doc_extraction", "identity", "screening", "risk"]
    assert any(e["kind"] == "interrupt" and e["decision"] == "APPROVE" for e in s["events"]) and run.interrupts == 1
    row = run.registry.ctx.one("SELECT status, risk_tier, risk_score, record_id FROM applications WHERE application_id = 'APL-001'")
    assert tuple(row) == ("APPROVED", "LOW", 22, "REC-001")
    assert client.unused() == {}


def test_request_shape_models_effort_caching_and_no_sampling(db):
    client = clean_client()
    run_case(db, "KYC-GLD-001", run_id="t", client=client)
    for kind, kw in client.requests:
        assert not {"temperature", "top_p", "top_k"} & set(kw)
        assert kw["output_config"]["effort"] == ("medium" if kind == "parse" else "low")
        assert kw["model"] == ("claude-sonnet-5-5" if kind == "parse" else "claude-haiku-5-5")
        assert kw["system"][-1]["cache_control"] == {"type": "ephemeral"}
        if kind == "create":
            assert all("$schema" not in t["input_schema"] for t in kw["tools"])
            assert "submit_result" in {t["name"] for t in kw["tools"]}


def test_supervisor_brief_masks_pan(db):
    client = clean_client()
    run_case(db, "KYC-GLD-001", run_id="t", client=client)
    briefs = [kw["messages"][0]["content"] for kind, kw in client.requests if kind == "parse"]
    assert all("ZQBPI1137K" not in b for b in briefs) and any("******137K" in b for b in briefs)


def test_specialists_only_get_their_own_tools(db):
    client = clean_client()
    run_case(db, "KYC-GLD-001", run_id="t", client=client)
    offered = [{t["name"] for t in kw["tools"]} - {"submit_result"} for kind, kw in client.requests if kind == "create"]
    allowed = [
        {"classify_document", "extract_document"},
        {"verify_pan", "ckyc_lookup", "check_address_proof"},
        {"sanctions_screen", "pep_check"},
        {"fetch_risk_policy", "compute_risk_score"},
    ]
    assert all(o in allowed for o in offered)


def test_approver_denies(db):
    client = clean_client(
        "APP-010", approval_then=[act("finalize", status="REJECTED", reason_codes=["APPROVER_DENIED"], message_to_customer="Sorry.")]
    )
    s = run_case(db, "KYC-GLD-010", run_id="t", client=client).state  # approver_response = DENY
    assert s["approval"]["decision"] == "DENY" and s["approval"]["token"] is None
    assert s["decision"]["status"] == "REJECTED" and s["record_id"] is None and client.unused() == {}


def test_create_record_without_approval_uses_no_token(db):
    """Even if the model asks to create the record first, code never supplies a token it does not have (A1)."""
    client = clean_client()
    client.supervisor.insert(4, act("create_record"))  # premature create before request_approval
    run = run_case(db, "KYC-GLD-001", run_id="t", client=client)
    creates = [e for e in run.state["events"] if e["kind"] == "tool" and e["tool"] == "create_customer_record"]
    assert creates[0]["args"]["approval_token"] == "NO_TOKEN" and creates[0]["result"]["error"] == "UNAUTHORISED"
    assert run.state["record_id"] == "REC-001"  # the later, approved create succeeds


def test_duplicate_record_path(db):
    client = clean_client(
        "APP-010",
        approval_then=[
            act("create_record"),
            act("finalize", status="PENDING_INFO", reason_codes=["RECORD_CREATION_FAILED"], message_to_customer="Our team will follow up."),
        ],
    )
    s = run_case(db, "KYC-FLT-101", run_id="t", client=client).state  # FP-12 on create_customer_record
    creates = [e for e in s["events"] if e["kind"] == "tool" and e["tool"] == "create_customer_record"]
    assert creates[0]["fault_injected"] == "FP-12:ERROR" and s["record_id"] is None
    assert s["decision"]["status"] == "PENDING_INFO" and client.unused() == {}


def test_screening_hit_escalates(db):
    rv = {"pan": "ZQGPV1822T", "full_name": "RAHUL VERMA", "dob": "1982-07-07"}
    profile = {
        **rv,
        "aadhaar_last4": None,
        "address": "103, Nehru Colony, New Delhi 110017, Delhi",
        "nationality": None,
        "quality_flags": [],
        "missing_fields": [],
        "injection_suspected": False,
        "field_sources": {"address": "DOC-006-UB"},
    }
    client = ScriptedClient(
        [
            act("delegate", target="doc_extraction"),
            act("delegate", target="identity"),
            act("delegate", target="screening"),
            act("delegate", target="risk"),
            act("escalate_edd", reason_codes=["SCREENING_HIT"]),
            act(
                "finalize",
                status="PENDING_EDD",
                reason_codes=["SCREENING_HIT"],
                message_to_customer="Your application needs additional review.",
            ),
        ],
        doc_extraction=doc_turns({"DOC-006-PAN": "PAN_CARD", "DOC-006-UB": "UTILITY_BILL"}, profile),
        identity=[
            [("call", "verify_pan", rv), ("call", "check_address_proof", {"doc_id": "DOC-006-UB", "address": profile["address"]})],
            [("finish", {"notes": "ok"})],
        ],
        screening=[
            [
                ("call", "sanctions_screen", {"full_name": rv["full_name"], "dob": rv["dob"], "nationality": "IN"}),
                ("call", "pep_check", {"full_name": rv["full_name"], "dob": rv["dob"]}),
            ],
            [("finish", {"notes": "hit"})],
        ],
        risk=[
            [
                ("call", "fetch_risk_policy", {"version": "v3"}),
                ("call", "compute_risk_score", {"applicant_id": "APP-006", "screening_ref": "SCR-0001", "product": "SAVINGS"}),
            ],
            [("finish", {"explanation": "screening hit"})],
        ],
    )
    s = run_case(db, "KYC-GLD-006", run_id="t", client=client).state
    assert s["screening"]["hits"][0]["entry_id"] == "SAN-0003" and (s["risk"]["score"], s["risk"]["tier"]) == (100, "HIGH")
    assert s["edd_case_id"] == "EDD-006-01" and s["decision"]["status"] == "PENDING_EDD" and s["record_id"] is None


def test_l2_stub_with_out_of_slice_write(db):
    """KYC-HND-109: the screening stub also writes a risk slice; it is stripped, flagged, and risk still comes from RSK."""
    client = ScriptedClient(
        [act("delegate", target=t) for t in ("doc_extraction", "identity", "screening", "risk")]
        + [act("request_approval"), act("create_record"), act("finalize", status="APPROVED", reason_codes=[])]
    )
    s = run_case(db, "KYC-HND-109", run_id="t", client=client).state
    assert any(v.startswith("SLICE-1") for v in s["contract_errors"]["screening"])
    assert "risk" not in s["screening"] and s["risk"]["score"] == 22
    assert s["decision"]["status"] == "APPROVED"


def test_customer_upload_on_turn_two_is_seen(db):
    """KYC-MIS-084: the bill uploaded with the customer's reply becomes visible and part of the state."""
    client = ScriptedClient(
        [
            act("delegate", target="doc_extraction"),
            act("request_info", fields=["address_proof"], message_to_customer="Please upload an address proof."),
            act("finalize", status="PENDING_INFO", reason_codes=["DOC_MISSING"]),
        ],
        doc_extraction=[
            [("call", "classify_document", {"doc_id": "DOC-084-PAN"})],
            [
                (
                    "finish",
                    {
                        "full_name": "DIVYA PILLAI",
                        "dob": "1992-10-10",
                        "pan": "ZQSPP7028Z",
                        "aadhaar_last4": None,
                        "address": None,
                        "nationality": None,
                        "quality_flags": [],
                        "missing_fields": ["address"],
                        "injection_suspected": False,
                        "field_sources": {},
                    },
                )
            ],
        ],
    )
    s = run_case(db, "KYC-MIS-084", run_id="t", client=client).state
    assert s["documents"] == ["DOC-084-PAN", "DOC-084-UB"]
    assert s["customer_messages"][-1] == "Uploaded my electricity bill now."
    assert s["replies"][0] == "Please upload an address proof."


def test_step_limit_fails_closed(db):
    client = ScriptedClient([act("request_info", fields=["x"], message_to_customer="?")] * 30)
    s = run_case(db, "KYC-MIS-080", run_id="t", client=client).state
    assert s["decision"] == {"status": "PENDING_INFO", "reason_codes": ["SYS_UNAVAILABLE"]}
    assert any(e["kind"] == "guard" and e["rule"] == "LIMIT-BOUNCE" for e in s["events"])
    assert s["supervisor_steps"] == 25


def test_delegation_limit_guard(db):
    """KYC-HND-068: identity stub keeps returning an invalid contract; a 4th hand-off is refused by code."""
    client = ScriptedClient(
        [act("delegate", target="doc_extraction")]
        + [act("delegate", target="identity")] * 4
        + [act("finalize", status="PENDING_INFO", reason_codes=["SYS_UNAVAILABLE"])]
    )
    s = run_case(db, "KYC-HND-068", run_id="t", client=client).state
    assert s["delegations"]["identity"] == 3
    assert any(e["kind"] == "guard" and "identity already delegated 3 times" in e["detail"] for e in s["events"])
    assert s["identity"] is None and s["decision"]["status"] == "PENDING_INFO"


def test_router_refusal_twice_fails_closed(db):
    client = ScriptedClient(["REFUSAL", "REFUSAL"])
    s = run_case(db, "KYC-GLD-001", run_id="t", client=client).state
    assert s["decision"] == {"status": "PENDING_INFO", "reason_codes": ["SYS_UNAVAILABLE"]} and s["record_id"] is None
    assert any(e["kind"] == "guard" and e["rule"] == "D7" for e in s["events"])


def test_canned_supervisor_state_for_l1_cases(db):
    """KYC-AGT-SUP-110 starts from STUB-08 (screening UNSCREENED); the Supervisor decides from that state alone."""
    client = ScriptedClient(
        [act("finalize", status="PENDING_INFO", reason_codes=["SYS_UNAVAILABLE"], message_to_customer="Please try later.")]
    )
    s = run_case(db, "KYC-AGT-SUP-110", run_id="t", client=client).state
    assert s["screening"]["status"] == "UNSCREENED" and s["decision"]["status"] == "PENDING_INFO"
    brief = client.requests[0][1]["messages"][0]["content"]
    assert '"UNSCREENED"' in brief


def test_run_start_records_models_and_prompt_hashes(db):
    s = run_case(db, "KYC-GLD-001", run_id="t", client=clean_client()).state
    start = s["events"][0]
    assert start["kind"] == "run_start" and set(start["prompt_hashes"]) == {"supervisor", "doc_extraction", "identity", "screening", "risk"}
    assert start["models"] == {"supervisor": "claude-sonnet-5-5", "specialist": "claude-haiku-5-5"} and start["as_of"] == "2026-11-02"
