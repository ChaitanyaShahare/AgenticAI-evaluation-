# WP10 — training and bug-hunt lab (24 Oct 2026)

## Request

"START WP10". EXECUTION_PLAN.md › WP10 asks for:
- the LAB-1 … LAB-6 switches;
- 7 modules and 6 exercises with expected answers;
- the answer key, the assessment and the scoring sheet;
- a dry run on D22.

## How it was done

- **Switches:** each defect is a small code change in one agent, guarded by `"LAB-n" in rt.lab`. The prompts are
  untouched, so a defect shows in the trajectory as a real bug would. `KYCRuntime.lab` comes from
  `EVALKIT_LAB_SWITCHES`. Only `evalkit lab` sets it, and only for one run. The runner refuses any other run while it
  is set.
- **Variant files:** each states only the ID, the switch and a neutral brief, and a test checks that they hint at
  nothing.
- **Acceptance test:** the test runs one case per variant, taken from the catalogue's Lab Mapping sheet (the human
  source), offline with a scripted model, once with the switch on and once with it off. It asserts that new S1 / S2
  failures appear. It does not encode which checks the testers must name.
- **Training material:** written from the code, the SOP and the case suite. E1's answers are read from the live
  KYC-GLD-001 recording. The other model answers are drafts for the QE Lead.

## Boundaries kept

- `training/lab/answer_key/answer_key.md` is the human-owned lab answer key (CLAUDE.md). It was left empty, then transcribed on the
  QE Lead's explicit request: Lab Mapping and the defects.py descriptions copied verbatim, with nothing inferred,
  marked for review.
- No live calls were made.

## Side fixes

- A tester-guide defect example described LAB-1 exactly, so it was replaced with a different defect.
- The README's variant rows described each defect, so they are now neutral.
