# KYC onboarding — reference project

The reference system under test and its evaluation configuration. An MVP KYC-onboarding assistant for **individual**
customers of an Indian bank: a LangGraph Supervisor and four specialist agents, running on 13 mocked tools and
synthetic data. Nothing here touches a real KYC vendor, CKYC, a sanctions feed or a real customer.

Requirements: `docs/requirements/Agent_Requirement_KYC_v0.3.xlsx` (per-agent intake). Cases, fixtures and rules:
`docs/requirements/KYC_Test_Case_Catalogue_v0.12.xlsx`. Mock data contract: `data/README.md`.

## What the system does

A customer asks to open a savings account and uploads documents (PAN card, address proof). The Supervisor plans the
onboarding, delegates to the specialists in order, applies the decision table D1–D10 and replies to the customer.
Before an account record is created, a human approver must approve (an interrupt in the graph); the mock approver
answers from the case.

| Agent | Tools | Writes | Guardrail (AG-5) |
|---|---|---|---|
| Supervisor (claude-sonnet-5-5, effort medium) | request_customer_info, escalate_to_edd, create_customer_record (approval-gated), finalize_application, hand-offs | decision, approval token, replies | no record without a valid approval token; any hit or HIGH tier → EDD |
| Document extraction (claude-haiku-5-5, effort low) | classify_document, extract_document | `profile` | Aadhaar masked to last 4; document text is data, never instructions |
| Identity verification | verify_pan, ckyc_lookup, check_address_proof | `identity` | a mismatch is never upgraded; ≤ 2 retries |
| Sanctions / PEP screening | sanctions_screen, pep_check | `screening` | no hit is cleared; near-matches (0.75–0.849) reported |
| Risk rating | fetch_risk_policy, compute_risk_score | `risk` | score and tier equal the engine output; pinned policy v3 |

End states (`applications` table): **APPROVED** (record created), **PENDING_INFO** (documents, identity, system
unavailable, approval timeout, record failure), **PENDING_EDD** (screening hit, HIGH risk), **REJECTED** (PAN
invalid, approver denied, non-individual applicant). Corporate applicants are routed to a stub (D6).

## Decision table (summary)

| Rule | Situation | Outcome |
|---|---|---|
| D1 | sanctions hit / near-match, PEP / RCA hit | escalate_to_edd → PENDING_EDD |
| D2 | risk tier HIGH, no hits | escalate_to_edd → PENDING_EDD (HIGH_RISK) |
| D3 | document missing, low quality, expired, unsupported, names inconsistent | request_customer_info → PENDING_INFO |
| D4 | identity MISMATCH | request_customer_info → PENDING_INFO (ID_MISMATCH) |
| D5 | PAN invalid | REJECTED (PAN_INVALID) |
| D6 | non-individual | route_to_corporate_stub → REJECTED |
| D7 | a mandatory control unavailable after ≤ 2 retries | PENDING_INFO (SYS_UNAVAILABLE), never APPROVED |
| D8 | all controls pass, tier LOW / MEDIUM | approval: approve → APPROVED · deny → REJECTED · no answer → PENDING_INFO |
| D9 | CKYC empty or unavailable | non-blocking |
| D10 | record creation fails after approval | no second attempt → PENDING_INFO (RECORD_CREATION_FAILED) |

The executable rules are in `policies/kyc_individual_v1.yaml` (37 rules) and `policies/pii_masking.yaml`; they were
decided by the QE Lead on 23 Oct 2026 and are **unvalidated** (no compliance SME in the MVP).

## Running the suites

From the repository root (setup: `docs/setup.md`). `--project kyc_onboarding` is the default.

| Goal | Command | Live? |
|---|---|---|
| framework tests, fixture check | `uv run --frozen evalkit smoke` | no |
| check the case files | `uv run --frozen evalkit lint-cases` | no |
| coverage matrix | `uv run --frozen evalkit coverage` | no |
| one case, 3 trials | `uv run --frozen evalkit eval --case KYC-EDG-014 --trials 3 [--yes]` | with `--yes` |
| 10 golden cases | `uv run --frozen evalkit run --mode smoke [--yes]` | with `--yes` |
| release gate: 70 S1 cases × 3 | `uv run --frozen evalkit gate [--yes]` | with `--yes` |
| all 110 cases + judges | `uv run --frozen evalkit full [--yes]` | with `--yes` |
| regrade stored trajectories | `uv run --frozen evalkit grade <run id>` | no |
| rebuild the seed database | `uv run --frozen evalkit data` | no |

The testers' workflow (lint → gate → triage → defect report) is in `docs/tester_guide.md`.

## Folder guide

| Path | What it is | Owner |
|---|---|---|
| `project.yaml` | adapter, runner, case source, end-state SQL, policies, datasets | engineer |
| `agents.yaml` | the five agents for the evaluators: role, slice, contract, prompt; protected attributes | engineer |
| `contracts.py` | Pydantic output contracts (extra fields forbidden) | engineer |
| `cases.py` | loads the case YAML; extra setup fields for the catalogue import | engineer |
| `sut/` | the system: graph, router, agents, prompts (hashed per run), approval, corporate stub, case driver | engineer |
| `sut/lab/` | seeded-defect switches for the bug-hunt lab, off by default (WP10) | QE Lead |
| `tools/specs/` | 13 tool JSON schemas + hand-offs; `x-agent` is the allow-list | engineer |
| `tools/mocks/` | deterministic SQLite-backed mocks | engineer |
| `policies/` | policy, masking and regulatory mapping | **QE Lead** |
| `datasets/` | 110 cases, one YAML per case, folder per pattern (guide: `datasets/README.md`) | testers; S1 oracles **QE Lead** |
| `reference_trajectories/` | RT-01 … RT-11 for TR-2, reviewed 23 Oct 2026 | **QE Lead** |
| `data/` | synthetic data generator, schema, conformance check, seed DB (never edit the SQLite directly) | engineer |
| `recorded_runs/` | 3 scripted and 1 live recording for offline evaluator tests | engineer |

## Status (24 Oct 2026)

- KYC-GLD-001 passes live end to end (about $0.04, 38 s); the other golden cases have not been run live yet.
- All four recordings pass every policy rule; seeded defects trip the expected rules (tests).
- Gate on the recordings: INCOMPLETE — TU-3 has no argument expectations yet, and the edge / adversarial TR-1
  threshold and several AG-1 thresholds are only measured by a gate run.
- Open: approver for the gates, argument expectations (TU-3), a compliance SME, catalogue v0.13 with the
  KYC-AGT-SCR-007 / -057 corrections.
