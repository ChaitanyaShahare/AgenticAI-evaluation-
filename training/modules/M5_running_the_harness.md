# M5 — Running the harness (2 h)

**You will be able to:** run every mode safely (dry run first), read report.html and junit.xml, regrade without
spending, and label traces for judge calibration.

Reference: `docs/setup.md`, `docs/tester_guide.md` §1, §2, §4, §8.

## 1. Commands and run modes (30 min)

| Goal | Command | Costs money? |
|---|---|---|
| setup check | `uv run --frozen evalkit doctor` | no |
| offline smoke | `uv run --frozen evalkit smoke` | no |
| one case, 3 trials | `uv run --frozen evalkit eval --case KYC-EDG-014 --trials 3` (add `--yes` to run) | with `--yes` |
| the release gate | `uv run --frozen evalkit gate` (add `--yes`) | with `--yes` |
| regrade a stored run | `uv run --frozen evalkit grade <run id>` | no |
| rebuild a report | `uv run --frozen evalkit report <run id>` | no |

Rule: **every live command is a dry run unless `--yes` is given.** Read the dry run (trials, estimated cost), and get the
QE Lead's OK before `--yes`. Exit codes: 0 PASS · 1 FAIL · 2 INCOMPLETE / SUSPENDED / NO_GATES.

Hands-on (10 min): `evalkit doctor`, `evalkit smoke`, then the dry run of `evalkit gate` — how many trials, what cost?

## 2. Reading the report (40 min)

Build a report offline from the four recordings:
`uv run --frozen evalkit grade projects/kyc_onboarding/recorded_runs --out <a folder outside Dropbox>` and open
`report.html`. Walk it top to bottom (tester guide §4): verdict and notes → S1 failures → gate table (*met*, *missed*,
*not measured*) → per-agent scorecards → suite metrics → cost → trials (failing first; timelines with the evidence steps
highlighted).

Questions to answer from the report:
1. Why is the verdict INCOMPLETE and not PASS? (Which thresholds are "not measured", and why?)
2. Which agent has the lowest scorecard, and on which metric?
3. Pick one check per family (TR, TU, BF, AG) and find its evidence step in a timeline.

`junit.xml` holds the same checks, one test each, named `KYC-GLD-001 t1 · TR-3 (R1)` — this is what CI shows.

## 3. Regrading (15 min)

`evalkit grade` re-runs every check on stored trajectories with no model calls. Use it after the QE Lead fixes an
oracle, or to compare two runs. Grading the same recording twice gives identical results.

## 4. LLM judges and labelling (35 min)

Judges score quality 0–3 on three rubrics (task completion, plan adherence, customer explanation; anchors in
`docs/methodology/scoring_rubrics.md`). They are **advisory** until they agree with you: on 30 traces labelled by each
tester, κ ≥ 0.6 and ≥ 85% agreement with your consensus.

Labelling (D16–D20): the QE Lead gives you a sheet from `evalkit calibrate --template <run> --rater T1`. Score each
item alone, from the anchors only; never look at the judge's or the other tester's scores; give a one-line reason for
any 0 or 1.

Practice now: label the final reply of the live KYC-GLD-001 recording on the customer-explanation rubric, then compare
with your partner and discuss any difference against the anchors.

## Check yourself

1. What does the gate dry run tell you, and what must happen before `--yes`?
2. A threshold says "not measured". Agent defect or missing oracle — how do you tell?
3. Why must you not look at the judge's score while labelling?
