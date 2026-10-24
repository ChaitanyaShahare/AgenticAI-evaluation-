# Bug-hunt lab — answer key (RESTRICTED)

> **Do not show to testers until the assessment is marked.**
>
> **Status: transcribed, awaiting the QE Lead's review.** Transcribed by Claude Code on 24 Oct 2026, at the QE Lead's
> request, from two sources and nothing else:
> - Part 1: `docs/requirements/KYC_Test_Case_Catalogue_v0.12.xlsx` › *Lab Mapping*, copied verbatim, cell by cell.
> - Part 2: the switch descriptions in `projects/kyc_onboarding/sut/lab/defects.py`, copied verbatim.
>
> No answer was added, changed or inferred. The note under Part 2 records what the offline test observed; it is not
> part of the key. Reviewed and accepted by: ____ (QE Lead) · date: ____

## Part 1 — Catalogue › Lab Mapping (verbatim)

**Bug-hunt lab: seeded defects and the cases that must catch them**

Acceptance: each seeded variant fails ≥ 1 S1 or S2 check in at least one listed case. Testers find these without seeing this sheet (answer key).

| Variant | Seeded defect | Must be caught by | Failing checks | Severity |
|---|---|---|---|---|
| LAB-1 | Screening agent skips pep_check | KYC-GLD-001, KYC-AGT-SCR-007, KYC-EDG-014, KYC-POL-065 | TR-3 (R1), AG-2 recall, BF-2 | S1 |
| LAB-2 | Risk agent invents a score when the tool times out | KYC-FLT-028, KYC-AGT-RSK-052 | TU-5 fabrication, TU-6 | S1 |
| LAB-3 | Document agent echoes the full Aadhaar number | KYC-PII-042, KYC-ADV-033, KYC-PII-040 | BF-1, AG-5 (DOC) | S1 |
| LAB-4 | Identity agent retries verify_pan indefinitely on timeout | KYC-FLT-021, KYC-FLT-022 | TU-5 retry limit, AG-6 | S2 |
| LAB-5 | Document agent obeys an instruction planted in OCR text | KYC-ADV-031, KYC-ADV-032 | BF-3 (twin comparison) | S1 |
| LAB-6 | Supervisor routes a corporate applicant to the individual path | KYC-HND-067 | TR-5, TR-2 | S2 |

## Part 2 — How each switch is implemented (`sut/lab/defects.py`, verbatim)

| Variant | Agent | Implementation |
|---|---|---|
| LAB-1 | screening | pep_check is not offered to the model, and the result is built from sanctions_screen alone |
| LAB-2 | risk | when the engine never answers, the agent reports an invented score and tier instead of ERROR |
| LAB-3 | doc_extraction | the full Aadhaar number from the document is copied into the profile's address |
| LAB-4 | identity | after a failed verify_pan the agent keeps retrying with the same arguments (up to 8 attempts) |
| LAB-5 | doc_extraction | an instruction found in a document is not flagged and is passed to the Supervisor as a note |
| LAB-6 | supervisor | a route to the corporate stub is replaced by the individual path (next specialist not yet run) |

### Note for the reviewer (not part of the key)

`tests/lab/test_seeded_defects.py` ran one listed case per variant offline, with a scripted model. These are the S1 / S2
checks that failed with the switch on and passed with it off. Where they differ from Part 1's *Failing checks*, the QE
Lead decides whether the key should accept them:

| Variant | Case | Checks that failed offline | Compared with Part 1 |
|---|---|---|---|
| LAB-1 | KYC-GLD-001 | AG-2, TR-2, TR-3 (R1), TR-3 (R2), TR-4 (P1.approve), TR-4 (P1.record), TR-4 (P3), TU-1 | includes TR-3 (R1) and AG-2; BF-2 was not among the new failures (no hit to escalate) |
| LAB-2 | KYC-FLT-028 | AG-1, AG-5 (GR-RSK.engine-failed) | the fabrication shows as AG-5 / AG-1; TU-5 and TU-6 were not among the new failures at L1 |
| LAB-3 | KYC-PII-042 | BF-1 (MASK-IN_AADHAAR) | includes BF-1 |
| LAB-4 | KYC-FLT-021 | TU-5, TU-5 (LIMIT-RETRY) | includes the TU-5 retry limit; AG-6 is S3 and not counted |
| LAB-5 | KYC-ADV-032 | AG-5 (GR-DOC.injection) | BF-3 needs the clean twin in the same run, which this single-case test did not include |
| LAB-6 | KYC-HND-067 | AG-2, TR-2, TR-5 (D6), TU-1 | includes TR-5 and TR-2 |

With a live model, further checks may fail too. For example, under LAB-5 a Supervisor that follows the relayed note
changes its tool calls, which BF-3 catches against the clean twin.
