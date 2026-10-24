# E1 — Read a trajectory (M1 · 40 min)

**Material:** `projects/kyc_onboarding/recorded_runs/live/KYC-GLD-001.json`, a real model run of the golden case.
Make its report first (offline, free):

```bash
uv run --frozen evalkit report projects/kyc_onboarding/recorded_runs/live --out <a folder outside Dropbox>
```

Open `report.html`, expand the trial and its timeline. Answer from the trajectory only.

1. List the agents in the order they first act, with the step index where each starts.
2. For each specialist, write its tool calls in order with their status.
3. Which step is the approval? What did the approver decide, and what token was issued?
4. Which step creates the customer record? Which argument proves the approval, and where did its value come from?
5. Which steps satisfy rule R1 (documents, PAN valid, sanctions, PEP and risk before the record)? Give their indices.
6. What are the end state (status, tier, score, record, reason codes) and the final message's first sentence?
7. The CKYC lookup found no record. Why did the run still approve? Which decision rule says so?
8. The profile has no nationality, yet `sanctions_screen` was called with `nationality: IN`. Where did `IN` come from?
   Which check would fail if it had come from nowhere?
9. Count the Supervisor's decisions. How many hand-offs were there, and did any specialist get a second hand-off?
10. Name one thing in this run that an outcome-only test could not have told you was correct.

Answers: `expected_answers.md › E1`.
