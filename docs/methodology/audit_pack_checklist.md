# Audit pack checklist

What goes into the audit pack for a release candidate. Source: SOP-AIEVAL-001 §3.12 (auditability, model risk) and
§3.13 (reporting, sign-off). The pack is assembled from the final gate and full runs in the buffer (D28–D30); there
is no command that builds it yet, so this list is worked through by hand. Retain it per the institution's records
policy.

Run folders live in `EVALKIT_RUNS_DIR`, outside the repository. Copy them into the pack; do not rebuild them.

## 1. Identification

- [ ] System name and build: repository revision (commit), date, run IDs of the final gate and full runs
- [ ] Scope tested: cases (110, catalogue version), levels, run modes; scope reductions (SOP §1) restated
- [ ] Risk tier of the system and of each tool (`x-tool-class` in the specs)

## 2. Configuration and versions (per run: `manifest.json`, `RunMeta`)

- [ ] Model ID per role and effort per role (`configs/eval.yaml`)
- [ ] Prompt hashes for all five agents
- [ ] Package versions and the `uv.lock` hash
- [ ] Determinism block: AS_OF, seed, lists version, pinned risk-policy version
- [ ] Trials per severity and run-mode definitions
- [ ] Copies of `configs/eval.yaml`, `configs/gates.yaml`, `configs/judges.yaml`, `configs/pii_recognizers.yaml`
- [ ] Copies of the project's policy files and `pii_masking.yaml`, with `owner`, `version` and `validated`
- [ ] Tool specs (`tools/specs/*.json`) and the seed database version

## 3. Results

- [ ] `results.jsonl` (every case × trial × check with evidence step)
- [ ] `scorecard.json` (per-agent scorecards, suite and pattern roll-ups, pass^k, flaky cases)
- [ ] `gate.json` (verdict, every threshold with value, S1 failures) and the exit code
- [ ] `junit.xml`
- [ ] `report.html` (redacted; written only if the leak scan found no identifier)
- [ ] `cost.json` and the month's ledger line
- [ ] Trajectories (`trajectories/<case>/t<k>.json`) and per-trial databases (`db/`) — the raw evidence
- [ ] Audit completeness BF-6 = 100% on every trial

## 4. Oracle status

- [ ] Policy rules: who wrote them, the decision record (QE Lead decisions of 23 Oct 2026), `validated: false`
- [ ] Reference trajectories: `reviewed_by` on RT-01 … RT-11
- [ ] S1 expectations: who reviewed them
- [ ] Gates: `approved_by` names the release approver
- [ ] Statement: **"No compliance SME reviewed the policy rules or S1 expectations in the MVP; every S1 rule and result
      is unvalidated until a compliance reviewer signs it off."**
- [ ] Regulatory mapping (`policies/regulatory_mapping.yaml`) with clause numbers marked to be confirmed

## 5. Judges

- [ ] Calibration report (M3): per metric agreement and κ against each tester and the consensus, tester-to-tester
- [ ] Status per judge metric: gating or advisory
- [ ] Judge model, rubric version and prompt hash

## 6. Defects and waivers

- [ ] Defect list: new, open, closed by severity and root cause
- [ ] Zero open S1 defects; zero S1 check failures across all trials (exit criterion, SOP §3.5)
- [ ] Waivers (S2 / S3 only) signed by the approver, each with reason and expiry
- [ ] Regression re-run after the last fix with no new failures

## 7. Sign-off (SOP §3.13)

- [ ] QE Lead recommendation
- [ ] Residual risks and open items (risk register, SOP §7.1)
- [ ] Judge calibration statement
- [ ] Signatures: QE Lead · compliance SME for S1 rules (MVP: none — the unvalidated statement above) · approver
- [ ] Date and retention location

## Privacy check before the pack leaves the team

- [ ] All data is synthetic (SYNTHETIC tags; ZQ / ZX PANs)
- [ ] No API key, `.env` or credential in any file
- [ ] Raw trajectories contain synthetic identifiers in tool results by design; share them only where the records
      policy allows, and prefer report.html for wider audiences
