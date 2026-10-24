# Bug-hunt lab

Six variants of the KYC system, LAB-1 … LAB-6, each with one seeded defect. Your job: for each variant, find a case
that catches the defect, name the failing checks and the agent, and explain the root cause. You also write 10 new,
valid cases (`training/assessment/assessment.md`).

## Rules

- Work only through cases and the `evalkit` commands. Do **not** open `projects/kyc_onboarding/sut/lab/`,
  `tests/lab/` or `training/lab/answer_key/` (restricted until the assessment is marked).
- The variant files in `variants/` tell you nothing about the defect on purpose.
- Every live run costs money. Dry-run first and keep to the budget the QE Lead gives you (for example 40 trials per
  tester). Choose cases deliberately; do not run whole modes "to see what happens".
- Work alone. You may discuss commands and the report format, but not defects.

## How to run a variant

```bash
uv run --frozen evalkit lab --variant LAB-1 --case KYC-GLD-001
uv run --frozen evalkit lab --variant LAB-1 --case KYC-GLD-001 --yes
```

`--case` can be repeated; `--trials N` overrides the trials (1 is often enough to find a defect, 3 to show it is
reliable); `--mode smoke|gate|full` runs a whole run set (expensive — ask first). The run lands in
`<runs dir>/lab-LAB-1-<timestamp>/` with report.html and junit.xml, exactly like a normal run.

A defect switch is on only while `evalkit lab` runs. Normal commands refuse to run if the switch variable is set.

## Method that works

1. Run a **baseline**: the same cases on the normal system (`evalkit eval --case … --yes`, or an existing reference run
   the QE Lead shares), so you know what "good" looks like.
2. Form a hypothesis per variant: which agent, which control? Pick cases that exercise it: L1 cases isolate one
   agent; L3 cases show the effect on the end state.
3. Run 1 trial per chosen case on the variant and compare with the baseline report: new failing checks, different
   tool sequence, different end state.
4. When a check fails, confirm with 3 trials, and confirm the same case passes on the normal system.
5. If no listed check fails but behaviour differs, write a new case that would catch it (it counts towards your 10).

## What to submit per variant

| Field | Content |
|---|---|
| Variant | LAB-n |
| Cases run | IDs and run IDs |
| Catching case(s) | the case(s) where the defect shows |
| Failing checks | names as in report.html, with evidence steps |
| Agent and root cause | agent name and RC code (`docs/methodology/defect_taxonomy.md`) |
| Explanation | 2–4 sentences: what the defective system does differently, and why that is a defect |
| Severity | S1 / S2 / S3, with the reason |

Write each as a defect report (`docs/tester_guide.md › Defect report`). The QE Lead marks them against the restricted
answer key: a variant counts as **caught** when a submitted case fails at least one S1 or S2 check caused by the
defect, and the agent is named correctly.
