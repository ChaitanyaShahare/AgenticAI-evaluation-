# M7 — Triage and defects (2 h)

**You will be able to:** decide whether a failure is the agent, the mock, the case or the evaluator; assign severity
and root cause; write a defect report another person can reproduce.

Reference: `docs/tester_guide.md` §5–§7, `docs/methodology/defect_taxonomy.md`.

## 1. The triage order (30 min)

For every failing check, rule out the evaluation before blaming the system:

1. **The case** (RC-TST): does `expected` agree with `expected_outcome` and the decision table?
2. **The mock or fixture** (RC-ENV): does the tool result in the timeline match the data contract
   (`projects/kyc_onboarding/data/README.md`)?
3. **The evaluator** (RC-EVL): does the check's detail contradict what the timeline shows?
4. **The model** (RC-MDL): did a new model ID appear in `manifest.json` with nothing else changed?
5. Otherwise **the agent**: the agent named in the check, at the evidence step → RC-PLN, RC-SEL, RC-ARG, RC-ERR,
   RC-INT, RC-HND, RC-GRD or RC-PII.

One root cause usually fails several checks (a skipped control fails a required rule, a precedence rule and tool
selection together). Write **one defect per root cause**, listing all its failing checks.

## 2. Severity (15 min)

The check sets the floor: S1 checks (TR-3, TR-4, TU-4, TU-5 fabrication, TU-6, TU-7, BF-1, BF-2, BF-3, BF-5, BF-6,
AG-5) make an S1 defect — blocks release, no waiver. S2 blocks unless the approver waives it; S3 is logged. A defect
found in 1 of 3 trials is still a defect (pass^k), and flaky.

## 3. Reproduce (20 min)

`uv run --frozen evalkit eval --case <id> --trials 3` (dry run, then `--yes` with the QE Lead's OK). If it fails every
time it is deterministic; some of the time, flaky — say so in the report with the count (for example 2 of 3).

## 4. Write the report (30 min)

Use the template in the tester guide §6: ID and title, severity and root cause, agent and level, case / trial / run,
failing checks with evidence steps, expected vs actual, a masked trajectory excerpt copied from report.html,
reproduction command, owner and status. Write so that someone who never saw the run can find the step in two minutes.

Bad: "Screening broken." Good: "DEF-7 — Supervisor finalises APPROVED before the screening result returns
(KYC-PAR-091 t2): TR-4 (P1.approve) evidence step 38; expected screening's agent_result before
finalize_application."

## 5. Hands-on: a full cycle (25 min)

On the build the QE Lead names: `lint-cases` → gate dry run → (approved) gate run or a regrade of a stored run → triage
every failure → one defect report per root cause. This is the WP9 exit check and the dress rehearsal for the bug hunt.

## Check yourself

1. TR-1 fails, and the case expects MEDIUM where the catalogue says HIGH. What is the root cause and who fixes it?
2. Three checks fail at the same step. How many defect reports?
3. What goes in "Reproduction"?
