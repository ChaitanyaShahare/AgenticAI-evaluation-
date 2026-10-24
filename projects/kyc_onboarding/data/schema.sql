-- =====================================================================
-- KYC onboarding — synthetic fixture database (SQLite)
-- Schema v0.1 · 23 Oct 2026 · Owner: QE Lead
-- Every row is synthetic. Mocked tools READ the "seed" tables and
-- WRITE only the "runtime" tables. The harness copies this file per
-- trial, so every run starts from the same seed state.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 0. Run configuration (test clock, thresholds, versions)
-- ---------------------------------------------------------------------
CREATE TABLE config (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL,
    description  TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- 1. Seed tables — read by mocked tools
-- ---------------------------------------------------------------------

-- Application-form data. Protected attributes (gender, religion, region)
-- live here for fairness pairs only; the risk engine never reads them.
CREATE TABLE applicants (
    applicant_id   TEXT PRIMARY KEY,                 -- APP-001 (curated) / APP-B0001 (background)
    full_name      TEXT NOT NULL,
    dob            TEXT,                             -- ISO date; NULL for non-individuals
    gender         TEXT CHECK (gender IN ('M','F','X') OR gender IS NULL),
    religion       TEXT,                             -- synthetic, fairness pairs only
    region_state   TEXT,
    city           TEXT,
    pincode        TEXT,
    address        TEXT,
    nationality    TEXT,                             -- ISO-3166 alpha-2
    customer_type  TEXT NOT NULL CHECK (customer_type IN ('INDIVIDUAL','CORPORATE')),
    pan            TEXT,                             -- fictitious ZQ (curated) / ZX (background) series
    aadhaar_last4  TEXT,
    phone          TEXT,
    email          TEXT,
    occupation     TEXT,                             -- NULL ⇒ risk engine returns MISSING_INPUT
    income_band    TEXT,
    product        TEXT,
    persona_type   TEXT NOT NULL CHECK (persona_type IN ('CURATED','BACKGROUND')),
    scenario       TEXT,
    synthetic      INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
);

-- One row per uploaded document. ocr_text is what an OCR/IDP service
-- would return; it may contain planted injections or unmasked PII.
CREATE TABLE documents (
    doc_id                 TEXT PRIMARY KEY,         -- DOC-001-PAN, DOC-001-UB-INJ …
    applicant_id           TEXT NOT NULL REFERENCES applicants(applicant_id),
    doc_type               TEXT NOT NULL CHECK (doc_type IN
                             ('PAN_CARD','UTILITY_BILL','AADHAAR_MASKED','AADHAAR_FULL','PASSPORT','UNKNOWN')),
    quality_score          REAL NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    issue_date             TEXT,                     -- bill date for utility bills
    expiry_date            TEXT,                     -- passports
    has_injection          INTEGER NOT NULL DEFAULT 0,
    contains_unmasked_pii  INTEGER NOT NULL DEFAULT 0,
    ocr_text               TEXT NOT NULL,
    fixture_note           TEXT,
    synthetic              INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
);

-- Structured output of extract_document (what the IDP returns).
-- Values are returned as-is: masking and validation are the agent's job.
CREATE TABLE document_fields (
    doc_id       TEXT NOT NULL REFERENCES documents(doc_id),
    field_name   TEXT NOT NULL,                      -- full_name, dob, pan, address, aadhaar_number …
    field_value  TEXT,                               -- NULL = not found
    confidence   REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (doc_id, field_name)
);

-- Mock PAN authority. Match outcome is computed by verify_pan.
CREATE TABLE pan_registry (
    pan              TEXT PRIMARY KEY,
    registered_name  TEXT NOT NULL,
    dob              TEXT NOT NULL,
    pan_status       TEXT NOT NULL CHECK (pan_status IN ('ACTIVE','DEACTIVATED')),
    synthetic        INTEGER NOT NULL DEFAULT 1 CHECK (synthetic = 1)
);

-- Mock CKYC registry (14-digit KYC identifier).
CREATE TABLE ckyc_records (
    ckyc_no    TEXT PRIMARY KEY,
    pan        TEXT NOT NULL,
    full_name  TEXT NOT NULL,
    dob        TEXT NOT NULL
);

-- Synthetic watch lists (invented people only).
CREATE TABLE sanctions_list (
    entry_id       TEXT PRIMARY KEY,
    list_name      TEXT NOT NULL,                    -- SYN-UNSC, SYN-UAPA
    full_name      TEXT NOT NULL,
    aliases_json   TEXT NOT NULL DEFAULT '[]',
    dob            TEXT,
    nationality    TEXT,
    category       TEXT,
    lists_version  TEXT NOT NULL
);

CREATE TABLE pep_list (
    entry_id          TEXT PRIMARY KEY,
    full_name         TEXT NOT NULL,
    dob               TEXT,
    nationality       TEXT,
    pep_category      TEXT NOT NULL CHECK (pep_category IN ('DOMESTIC','FOREIGN','RCA')),
    position          TEXT,
    related_entry_id  TEXT REFERENCES pep_list(entry_id),
    lists_version     TEXT NOT NULL
);

-- Pre-computed fuzzy-match results ("vendor output"), keyed by the
-- normalised query. Makes planted scores (0.749 / 0.75 / 0.78 …) exact.
-- Tools return rows with match_score >= config.screening_return_floor.
CREATE TABLE screening_index (
    query_name_norm     TEXT NOT NULL,               -- upper-case, punctuation stripped, single spaces
    query_dob           TEXT NOT NULL,
    list_type           TEXT NOT NULL CHECK (list_type IN ('SANCTIONS','PEP')),
    entry_id            TEXT NOT NULL,
    match_score         REAL NOT NULL,
    matched_fields_json TEXT NOT NULL,
    PRIMARY KEY (query_name_norm, query_dob, list_type, entry_id)
);

CREATE TABLE risk_policy (
    version               TEXT PRIMARY KEY,
    effective_from        TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('CURRENT','SUPERSEDED')),
    medium_from           INTEGER NOT NULL,          -- score >= medium_from ⇒ MEDIUM
    high_from             INTEGER NOT NULL,          -- score >= high_from   ⇒ HIGH
    factors_json          TEXT NOT NULL,
    excluded_inputs_json  TEXT NOT NULL,
    screening_override    TEXT NOT NULL
);

-- Risk-engine inputs. Deliberately has NO gender / religion / caste /
-- region / pincode columns (BF-5).
CREATE TABLE risk_engine_inputs (
    applicant_id         TEXT PRIMARY KEY REFERENCES applicants(applicant_id),
    occupation_category  TEXT,
    income_band          TEXT,
    product              TEXT,
    cash_intensive       INTEGER NOT NULL DEFAULT 0,
    base_score           INTEGER NOT NULL CHECK (base_score BETWEEN 0 AND 100),
    factors_json         TEXT NOT NULL
);

-- One application per persona, status NEW. The SUT moves it to an end state.
CREATE TABLE applications (
    application_id     TEXT PRIMARY KEY,             -- APL-001
    applicant_id       TEXT NOT NULL REFERENCES applicants(applicant_id),
    product            TEXT,
    channel            TEXT NOT NULL DEFAULT 'CHAT',
    status             TEXT NOT NULL DEFAULT 'NEW' CHECK (status IN
                         ('NEW','IN_PROGRESS','APPROVED','PENDING_INFO','PENDING_EDD','REJECTED')),
    risk_tier          TEXT,
    risk_score         INTEGER,
    record_id          TEXT,
    ckyc_no            TEXT,
    reason_codes_json  TEXT NOT NULL DEFAULT '[]',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- 2. Fault, override and stub profiles — read by the mock fault hook
-- ---------------------------------------------------------------------
CREATE TABLE fixture_profiles (
    profile_id         TEXT PRIMARY KEY,             -- FP-01, MO-02, STUB-03 …
    profile_type       TEXT NOT NULL CHECK (profile_type IN ('FAULT','OVERRIDE','DATA','STUB','CANNED_STATE')),
    target             TEXT NOT NULL,                -- tool or agent
    description        TEXT NOT NULL,
    expected_handling  TEXT NOT NULL
);

-- attempt_no = 0 means "every attempt not listed explicitly".
-- Attempts not covered by any row behave normally (PASS).
CREATE TABLE tool_faults (
    profile_id    TEXT NOT NULL REFERENCES fixture_profiles(profile_id),
    tool_name     TEXT NOT NULL,
    attempt_no    INTEGER NOT NULL,
    behaviour     TEXT NOT NULL CHECK (behaviour IN
                    ('PASS','TIMEOUT','HTTP_500','MALFORMED_JSON','EMPTY','SLOW','ERROR','REPLACE_FIELDS')),
    delay_ms      INTEGER,
    error_code    TEXT,
    payload       TEXT,                              -- raw body for MALFORMED_JSON / EMPTY / REPLACE_FIELDS
    PRIMARY KEY (profile_id, tool_name, attempt_no)
);

CREATE TABLE tool_overrides (
    profile_id     TEXT NOT NULL REFERENCES fixture_profiles(profile_id),
    tool_name      TEXT NOT NULL,
    response_json  TEXT NOT NULL,
    PRIMARY KEY (profile_id, tool_name)
);

-- L2 specialist stubs and L1 canned supervisor state.
CREATE TABLE agent_stubs (
    profile_id     TEXT NOT NULL REFERENCES fixture_profiles(profile_id),
    agent          TEXT NOT NULL,                    -- doc_extraction | identity | screening | risk | state
    attempt_no     INTEGER NOT NULL,                 -- 0 = every attempt
    contract_json  TEXT NOT NULL,
    PRIMARY KEY (profile_id, agent, attempt_no)
);

-- ---------------------------------------------------------------------
-- 3. Case index — links each test case to its fixtures
--    (case YAML stays the source of truth for expectations)
-- ---------------------------------------------------------------------
CREATE TABLE test_cases (
    case_id                TEXT PRIMARY KEY,
    level                  TEXT NOT NULL,
    primary_agent          TEXT NOT NULL,
    pattern                TEXT NOT NULL,
    severity               TEXT NOT NULL,
    trials                 INTEGER NOT NULL,
    run_sets               TEXT NOT NULL,
    applicant_id           TEXT NOT NULL REFERENCES applicants(applicant_id),
    application_id         TEXT REFERENCES applications(application_id),
    approver_response      TEXT CHECK (approver_response IN ('APPROVE','DENY','NO_RESPONSE') OR approver_response IS NULL),
    profile_ids_json       TEXT NOT NULL DEFAULT '[]',
    form_updates_json      TEXT,                     -- applied by request_customer_info when the scripted customer answers
    customer_turns         TEXT,
    expected_status        TEXT,                     -- L2/L3 only
    expected_tier          TEXT,
    expected_reasons_json  TEXT,
    expected_record        INTEGER,
    expected_output        TEXT NOT NULL
);

CREATE TABLE case_documents (
    case_id           TEXT NOT NULL REFERENCES test_cases(case_id),
    doc_id            TEXT NOT NULL REFERENCES documents(doc_id),
    uploaded_at_turn  INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (case_id, doc_id)
);

-- ---------------------------------------------------------------------
-- 4. Runtime tables — EMPTY in the seed; written by mocked tools
-- ---------------------------------------------------------------------
CREATE TABLE screening_results (
    screening_ref   TEXT PRIMARY KEY,                -- returned to the agent; passed to compute_risk_score
    application_id  TEXT,
    tool_name       TEXT NOT NULL,
    request_json    TEXT NOT NULL,
    response_json   TEXT NOT NULL,
    max_score       REAL,
    created_at      TEXT NOT NULL
);

CREATE TABLE approval_tokens (
    token           TEXT PRIMARY KEY,
    application_id  TEXT NOT NULL,
    decision        TEXT NOT NULL CHECK (decision IN ('APPROVE','DENY')),
    issued_by       TEXT NOT NULL DEFAULT 'MOCK_APPROVER',
    issued_at       TEXT NOT NULL,
    consumed        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE info_requests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  TEXT NOT NULL,
    fields_json     TEXT NOT NULL,
    reason          TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE edd_cases (
    edd_case_id        TEXT PRIMARY KEY,
    application_id     TEXT NOT NULL,
    reason_codes_json  TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

CREATE TABLE customer_records (
    record_id       TEXT PRIMARY KEY,
    application_id  TEXT NOT NULL UNIQUE,            -- UNIQUE drives the DUPLICATE_RECORD path
    applicant_id    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE audit_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    case_id         TEXT,
    trial           INTEGER,
    step            INTEGER,
    agent           TEXT,
    tool            TEXT,
    args_json       TEXT,
    result_json     TEXT,
    status          TEXT,                            -- ok | error | timeout
    fault_injected  TEXT,
    ts              TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- 5. Views used by mocks
-- ---------------------------------------------------------------------

-- Address-proof validity on the test clock (config.as_of).
-- Utility bill older than 2 months, or passport past expiry ⇒ EXPIRED.
CREATE VIEW v_address_proof_validity AS
SELECT d.doc_id,
       d.applicant_id,
       d.doc_type,
       CASE
         WHEN d.doc_type = 'PASSPORT'
              AND d.expiry_date < (SELECT value FROM config WHERE key = 'as_of')              THEN 'EXPIRED'
         WHEN d.doc_type = 'UTILITY_BILL'
              AND d.issue_date < date((SELECT value FROM config WHERE key = 'as_of'), '-2 months') THEN 'EXPIRED'
         WHEN d.doc_type IN ('PASSPORT','UTILITY_BILL','AADHAAR_MASKED','AADHAAR_FULL')        THEN 'VALID'
         ELSE 'NOT_ADDRESS_PROOF'
       END AS validity,
       (SELECT f.field_value FROM document_fields f
         WHERE f.doc_id = d.doc_id AND f.field_name = 'address') AS address_on_document
FROM documents d;

-- Tier for every policy version, computed from thresholds (engine logic).
CREATE VIEW v_risk_tier AS
SELECT r.applicant_id, p.version, r.base_score,
       CASE WHEN r.base_score >= p.high_from   THEN 'HIGH'
            WHEN r.base_score >= p.medium_from THEN 'MEDIUM'
            ELSE 'LOW' END AS tier_without_screening_override
FROM risk_engine_inputs r CROSS JOIN risk_policy p;

CREATE INDEX ix_documents_applicant ON documents(applicant_id);
CREATE INDEX ix_ckyc_pan ON ckyc_records(pan);
CREATE INDEX ix_audit_run ON audit_events(run_id, step);
