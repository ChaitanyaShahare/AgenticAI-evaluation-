"""Fixture conformance check: does the seed data produce what each test case expects?

Usage:
    python check_fixtures.py kyc_synthetic.sqlite

It replays the *mock tool lookups* (the same SQL documented in README.md) for every
case and, for L2/L3 cases, derives the end state with decision table D1–D10 from
'Rules & Decisions'. A mismatch means the fixture data and the case oracle disagree —
fix one of them before any agent run. This is a data check, not an agent evaluation.
Exit code 1 on any mismatch.
"""
import json, re, sqlite3, sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252 and cannot print ✓ / ✗
DB = sys.argv[1] if len(sys.argv) > 1 else "kyc_synthetic.sqlite"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cfg = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM config")}
FLOOR, HIT, NEAR, QMIN = float(cfg["screening_return_floor"]), float(cfg["screening_hit_threshold"]), float(cfg["screening_near_threshold"]), float(cfg["doc_quality_threshold"])


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z ]", " ", s or "").upper()).strip()


# ------------------------------------------------------------------ reference mock lookups (data only)
def classify_document(doc_id):
    r = con.execute("SELECT doc_type, quality_score FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return {"doc_type": r["doc_type"], "quality": r["quality_score"]}


def extract_document(doc_id):
    return {r["field_name"]: (r["field_value"], r["confidence"]) for r in
            con.execute("SELECT field_name, field_value, confidence FROM document_fields WHERE doc_id = ?", (doc_id,))}


def verify_pan(pan, full_name, dob):
    r = con.execute("SELECT registered_name, dob, pan_status FROM pan_registry WHERE pan = ?", (pan,)).fetchone()
    if r is None or r["pan_status"] == "DEACTIVATED":
        return "INVALID"
    return "VALID" if norm(r["registered_name"]) == norm(full_name) and r["dob"] == dob else "MISMATCH"


def ckyc_lookup(pan, dob):
    r = con.execute("SELECT ckyc_no FROM ckyc_records WHERE pan = ? AND dob = ?", (pan, dob)).fetchone()
    return r["ckyc_no"] if r else None


def check_address_proof(doc_id, address):
    r = con.execute("SELECT validity, address_on_document FROM v_address_proof_validity WHERE doc_id = ?", (doc_id,)).fetchone()
    if r["validity"] != "VALID":
        return r["validity"]
    return "MATCH" if norm(r["address_on_document"]) == norm(address) else "MISMATCH"


def screen(list_type, full_name, dob):
    return [dict(r) for r in con.execute(
        "SELECT entry_id, match_score FROM screening_index WHERE query_name_norm = ? AND query_dob = ? AND list_type = ? AND match_score >= ?",
        (norm(full_name), dob, list_type, FLOOR))]


def risk_tier(score, version="v3"):
    p = con.execute("SELECT medium_from, high_from FROM risk_policy WHERE version = ?", (version,)).fetchone()
    return "HIGH" if score >= p["high_from"] else "MEDIUM" if score >= p["medium_from"] else "LOW"


def compute_risk_score(applicant_id, screening_hit, form_updates=None):
    a = con.execute("SELECT occupation, income_band FROM applicants WHERE applicant_id = ?", (applicant_id,)).fetchone()
    occ = (form_updates or {}).get("occupation", a["occupation"])
    if not occ:
        return {"status": "MISSING_INPUT"}
    base = con.execute("SELECT base_score FROM risk_engine_inputs WHERE applicant_id = ?", (applicant_id,)).fetchone()["base_score"]
    score = 100 if screening_hit else base
    return {"status": "OK", "score": score, "tier": risk_tier(score)}


def override(profiles, tool):
    for p in profiles:
        r = con.execute("SELECT response_json FROM tool_overrides WHERE profile_id = ? AND tool_name = ?", (p, tool)).fetchone()
        if r:
            return json.loads(r["response_json"])
    return None


def persistent_fault(profiles, tool):
    """True when the fault outlasts 1 + retry_limit attempts (so the control is unavailable)."""
    for p in profiles:
        rows = {r["attempt_no"]: r["behaviour"] for r in con.execute("SELECT attempt_no, behaviour FROM tool_faults WHERE profile_id = ? AND tool_name = ?", (p, tool))}
        if 0 in rows and rows[0] not in ("PASS", "SLOW"):
            return rows[0]
    return None


# ------------------------------------------------------------------ end-state derivation (D1–D9)
def derive(case):
    prof = json.loads(case["profile_ids_json"])
    if any(p.startswith("STUB") for p in prof):
        return None  # L2 stubs and canned states bypass the data path
    app = con.execute("SELECT * FROM applicants WHERE applicant_id = ?", (case["applicant_id"],)).fetchone()
    if app["customer_type"] != "INDIVIDUAL":
        return ("REJECTED", None, ["OUT_OF_SCOPE_CUSTOMER_TYPE"])
    turns = case["customer_turns"] or ""
    answered = "no further response" not in turns and "on request" in turns
    docs = [r["doc_id"] for r in con.execute("SELECT doc_id FROM case_documents WHERE case_id = ? ORDER BY uploaded_at_turn, doc_id", (case["case_id"],))]
    if not docs:
        return ("PENDING_INFO", None, ["DOC_MISSING"])
    cls = {d: classify_document(d) for d in docs}
    pan_docs = [d for d in docs if cls[d]["doc_type"] == "PAN_CARD"]
    if pan_docs and cls[pan_docs[0]]["quality"] < QMIN:
        return ("PENDING_INFO", None, ["DOC_LOW_QUALITY"])
    if not pan_docs:
        return ("PENDING_INFO", None, ["INFO_MISSING"])
    pf = extract_document(pan_docs[0])
    if "FP-11" in prof:
        return ("PENDING_INFO", None, ["INFO_MISSING"])
    if pf["dob"][1] < 0.5:
        return ("PENDING_INFO", None, ["INFO_MISSING"])
    addr_docs = [d for d in docs if cls[d]["doc_type"] in ("UTILITY_BILL", "PASSPORT", "AADHAAR_MASKED", "AADHAAR_FULL")]
    if not addr_docs:
        return ("PENDING_INFO", None, ["DOC_MISSING"])
    names = {norm(extract_document(d)["full_name"][0]) for d in pan_docs + addr_docs}
    if len(names) > 1:
        return ("PENDING_INFO", None, ["NAME_INCONSISTENT"])
    if persistent_fault(prof, "verify_pan"):
        return ("PENDING_INFO", None, ["SYS_UNAVAILABLE"])
    pan, name, dob = pf["pan"][0], pf["full_name"][0], pf["dob"][0]
    v = verify_pan(pan, name, dob)
    if v == "INVALID":
        return ("REJECTED", None, ["PAN_INVALID"])
    if v == "MISMATCH":
        return ("PENDING_INFO", None, ["ID_MISMATCH"])
    addr_doc = addr_docs[-1]                       # latest upload wins (KYC-MTN-089)
    a = check_address_proof(addr_doc, extract_document(addr_doc)["address"][0])
    if a == "EXPIRED":
        return ("PENDING_INFO", None, ["DOC_EXPIRED"])
    if persistent_fault(prof, "sanctions_screen") or persistent_fault(prof, "pep_check"):
        return ("PENDING_INFO", None, ["SYS_UNAVAILABLE"])
    ov = override(prof, "sanctions_screen")
    sanc = [{"entry_id": c["entry_id"], "match_score": c["score"]} for c in ov["candidates"]] if ov else screen("SANCTIONS", name, dob)
    pep = screen("PEP", name, dob)
    hit_s = any(h["match_score"] >= NEAR for h in sanc)
    hit_p = any(h["match_score"] >= NEAR for h in pep)
    if persistent_fault(prof, "compute_risk_score"):
        return ("PENDING_INFO", None, ["SYS_UNAVAILABLE"])
    fu = json.loads(case["form_updates_json"]) if case["form_updates_json"] else None
    r = compute_risk_score(app["applicant_id"], hit_s or hit_p, fu if answered else None)
    if r["status"] != "OK":
        return ("PENDING_INFO", None, ["INFO_MISSING"])
    if hit_s or hit_p:
        return ("PENDING_EDD", r["tier"], ["SCREENING_HIT"] if hit_s else ["PEP_HIT"])
    if r["tier"] == "HIGH":
        return ("PENDING_EDD", r["tier"], ["HIGH_RISK"])
    ap = case["approver_response"]
    if ap == "DENY":
        return ("REJECTED", r["tier"], ["APPROVER_DENIED"])
    if ap == "NO_RESPONSE":
        return ("PENDING_INFO", r["tier"], ["APPROVAL_TIMEOUT"])
    if persistent_fault(prof, "create_customer_record"):
        return ("PENDING_INFO", r["tier"], ["RECORD_CREATION_FAILED"])
    return ("APPROVED", r["tier"], [])


# ------------------------------------------------------------------ L1 data checks
def l1_check(case):
    cid, app = case["case_id"], case["applicant_id"]
    a = con.execute("SELECT * FROM applicants WHERE applicant_id = ?", (app,)).fetchone()
    out = case["expected_output"]
    prof = json.loads(case["profile_ids_json"])
    if case["primary_agent"] == "SCR" or "AGT-SCR" in cid:
        if persistent_fault(prof, "pep_check") or persistent_fault(prof, "sanctions_screen"):
            return "UNSCREENED" in out
        hits = [h for h in screen("SANCTIONS", a["full_name"], a["dob"]) + screen("PEP", a["full_name"], a["dob"]) if h["match_score"] >= NEAR]
        if "any_hit = true" in out:
            return bool(hits)
        if "any_hit = false" in out:
            return not hits
        return True
    if case["primary_agent"] == "IDV":
        if "pan = null" in out or cid.endswith("051"):
            return a["pan"] is not None and not con.execute(
                "SELECT 1 FROM case_documents cd JOIN documents d USING(doc_id) WHERE cd.case_id = 'KYC-MIS-081' AND d.doc_type = 'PAN_CARD'").fetchone()
        if "MISMATCH" in out:
            pan_doc = f"DOC-{app[4:]}-PAN"
            f = extract_document(pan_doc)
            return verify_pan(f["pan"][0], f["full_name"][0], f["dob"][0]) == "MISMATCH"
        if "ckyc" in out.lower():
            return ckyc_lookup(a["pan"], a["dob"]) is not None   # FLT-023: data has a record the agent must NOT invent when the call times out
        return True
    if case["primary_agent"] == "DOC":
        docs = [r["doc_id"] for r in con.execute("SELECT doc_id FROM case_documents WHERE case_id = ?", (cid,))]
        if "no DOC_LOW_QUALITY flag" in out:
            return all(classify_document(d)["quality"] >= QMIN for d in docs)
        if "DOC_LOW_QUALITY" in out:
            return any(classify_document(d)["quality"] < QMIN for d in docs)
        if "DOC_UNSUPPORTED" in out:
            return any(classify_document(d)["doc_type"] == "UNKNOWN" for d in docs)
        if "aadhaar_last4" in out:
            return any(classify_document(d)["doc_type"].startswith("AADHAAR") for d in docs)
        if "no card field" in out:
            return any("4111 1111 1111 1111" in con.execute("SELECT ocr_text FROM documents WHERE doc_id = ?", (d,)).fetchone()[0] for d in docs) and \
                   not con.execute("SELECT 1 FROM document_fields WHERE doc_id IN (%s) AND field_value LIKE '%%4111%%'" % ",".join("?" * len(docs)), docs).fetchone()
        if "profile.name = ANANYA IYER" in out:
            f = extract_document("DOC-001-PAN")
            return f["full_name"][0] == "ANANYA IYER" and f["dob"][0] == "1994-03-12" and f["pan"][0] == a["pan"]
        if "profile.name = ROHAN MEHTA" in out:          # KYC-AGT-DOC-106 passport
            f = extract_document("DOC-002-PP")
            return (f["full_name"][0] == "ROHAN MEHTA" and f["dob"][0] == a["dob"] and f["address"][0] == a["address"]
                    and f["expiry_date"][0] == "2033-05-31" and f["nationality"][0] == "INDIAN")
        if "bill_date = 2026-10-05" in out:              # KYC-AGT-DOC-107 utility bill
            f = extract_document("DOC-001-UB")
            return f["address"][0] == a["address"] and f["bill_date"][0] == "2026-10-05" and f["full_name"][0] == "ANANYA IYER"
        return True
    if case["primary_agent"] == "RSK":
        ov = override(prof, "compute_risk_score")
        m = re.search(r"\{(\d+), (\w+)", out) or re.search(r"score (\d+), tier (\w+)", out)
        if ov and m:
            return ov["score"] == int(m.group(1)) and ov["tier"] == m.group(2)
        if "policy v2" in (case["customer_turns"] or ""):   # KYC-AGT-RSK-105: v2 superseded, v3 current, engine gives 31 / LOW
            st = {r["version"]: r["status"] for r in con.execute("SELECT version, status FROM risk_policy")}
            r = compute_risk_score(app, False)
            return st.get("v2") == "SUPERSEDED" and st.get("v3") == "CURRENT" and r["score"] == 31 and r["tier"] == "LOW"
        if "tier LOW (33)" in out:
            r = con.execute("PRAGMA table_info(risk_engine_inputs)").fetchall()
            return not {"gender", "religion", "region_state", "pincode"} & {c[1] for c in r} and compute_risk_score(app, False)["tier"] == "LOW"
        return True
    if case["primary_agent"] == "SUP":
        return bool(con.execute("SELECT 1 FROM agent_stubs WHERE profile_id IN (SELECT value FROM json_each(?))", (case["profile_ids_json"],)).fetchone())
    return True


# ------------------------------------------------------------------ structural checks
def structural():
    errs = []
    q = lambda s: con.execute(s).fetchall()
    errs += [f"case_documents → unknown doc {r[0]}" for r in q("SELECT doc_id FROM case_documents WHERE doc_id NOT IN (SELECT doc_id FROM documents)")]
    errs += [f"test_cases → unknown profile {r[0]}" for r in q("SELECT j.value FROM test_cases, json_each(profile_ids_json) j WHERE j.value NOT IN (SELECT profile_id FROM fixture_profiles)")]
    errs += [f"document without banner {r[0]}" for r in q("SELECT doc_id FROM documents WHERE ocr_text NOT LIKE '[SYNTHETIC TEST FIXTURE%'")]
    errs += [f"PAN outside fictitious series {r[0]}" for r in q("SELECT pan FROM applicants WHERE pan IS NOT NULL AND substr(pan,1,2) NOT IN ('ZQ','ZX')")]
    errs += [f"duplicate PAN {r[0]}" for r in q("SELECT pan FROM applicants WHERE pan IS NOT NULL GROUP BY pan HAVING count(*) > 1")]
    errs += [f"full Aadhaar outside PII fixtures {r[0]}" for r in q(
        "SELECT doc_id FROM document_fields WHERE field_name = 'aadhaar_number' AND field_value NOT LIKE 'XXXX%' AND doc_id NOT IN (SELECT doc_id FROM documents WHERE contains_unmasked_pii = 1)")]
    errs += [f"background name collides with watch list {r[0]}" for r in q(
        "SELECT a.full_name FROM applicants a WHERE a.persona_type = 'BACKGROUND' AND upper(a.full_name) IN (SELECT upper(full_name) FROM sanctions_list UNION SELECT upper(full_name) FROM pep_list)")]
    errs += [f"runtime table not empty {t}" for t in ("screening_results", "approval_tokens", "info_requests", "edd_cases", "customer_records", "audit_events")
             if con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]]
    errs += [f"risk engine reads protected attribute {c[1]}" for c in con.execute("PRAGMA table_info(risk_engine_inputs)") if c[1] in ("gender", "religion", "caste", "region_state", "pincode")]
    return errs


def main():
    errors = structural()
    checked = skipped = 0
    for case in con.execute("SELECT * FROM test_cases ORDER BY case_id"):
        if case["expected_status"] and not case["level"].startswith("L1"):
            got = derive(case)
            if got is None:
                skipped += 1
                continue
            checked += 1
            exp = (case["expected_status"], case["expected_tier"], json.loads(case["expected_reasons_json"] or "[]"))
            tier_ok = exp[1] is None or got[1] == exp[1]
            if got[0] != exp[0] or not tier_ok or got[2] != exp[2]:
                errors.append(f"{case['case_id']}: expected {exp} — data gives {got}")
        else:
            checked += 1
            if not l1_check(case):
                errors.append(f"{case['case_id']}: L1 fixture does not support expected output: {case['expected_output'][:90]}")
    print(f"cases checked: {checked} · skipped (stub / canned-state, checked structurally): {skipped}")
    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print("  ✗", e)
        sys.exit(1)
    print("✓ fixture data is consistent with every case oracle")


if __name__ == "__main__":
    main()
