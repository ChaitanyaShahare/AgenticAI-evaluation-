# E5 — Write an L1 case for one specialist (M3, M6 · 45 min)

**Agent:** identity verification. **Behaviour:** the PAN registry says the name matches but the date of birth does not.
The agent must report the mismatch and never upgrade it to VERIFIED (guardrail GR-IDV.no-upgrade).

1. Find an applicant whose PAN registry entry has a different DOB from the document (catalogue sheet *Registry Mocks*).
   If there is none, write the persona request for the QE Lead: what the PAN card says, what the registry must say.
2. Write the L1 case in `datasets/agent_unit/` (`KYC-AGT-IDV-<NNN>`):
   - `level: L1`, `primary_agent: IDV`, the task in `customer_turns` starting `n/a (L1) —`;
   - `required_tools`, `match_mode`;
   - `expected_outcome` in words;
   - `expected.agent_outputs.identity` with the fields AG-1 should compare.
3. Which checks run on an L1 identity case, and which do not? (Hint: whole-run rules apply to L2 / L3.)
4. Lint it and dry-run it.

Answers: `expected_answers.md › E5`.
