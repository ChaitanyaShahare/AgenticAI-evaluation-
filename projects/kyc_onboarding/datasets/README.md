# KYC test cases (YAML)

Every test case is one YAML file, in the folder of its pattern, named after its case ID:
`datasets/golden/KYC-GLD-001.yaml`. These files are the source of truth for the cases — the seed database's case
tables and the harness both read them. You need only a text editor and the command line.

| Folder | Pattern | | Folder | Pattern |
|---|---|---|---|---|
| `golden/` | Golden path | | `policy/` | Policy-violating request |
| `agent_unit/` | Per-agent isolation (L1) | | `handoff/` | Hand-off / routing (L2) |
| `edge/` | Boundary / policy edge | | `fairness_pairs/` | Fairness pair |
| `faults/` | Tool fault injection | | `missing_info/` | Missing / ambiguous info |
| `adversarial/` | Adversarial / injection | | `multi_turn/` | Multi-turn state |
| `pii/` | PII / PCI handling | | `paraphrase/` | Paraphrase |

## Add a case in five steps

1. **Copy** a case of the same pattern and give the copy a new ID: `KYC-<PATTERN>-<NNN>` with a number no other case
   uses (for example `KYC-EDG-120`). The file name must be the ID.
2. **Edit** the setup: `applicant`, `documents`, `customer_turns`, `mocks` / `fixtures`, `approver`. Use applicants,
   documents and fixture profiles that already exist (catalogue sheets *Synthetic Applicants*, *Synthetic Documents*,
   *Mocks & Faults*). A new applicant or document is added by the QE Lead.
3. **State the expectation** consistently with the catalogue's *Rules & Decisions*: write `expected_outcome` in words
   and copy the end state into `expected` (status, risk tier and score, record, reason codes). For an S1 case, ask the
   QE Lead to review the expectation — S1 oracles are human-owned and never written by an AI assistant.
4. **Build and check:**
   ```
   uv run evalkit data
   uv run evalkit lint-cases
   ```
   `data` rebuilds the seed database's case tables from the YAML files; `lint-cases` explains every problem and how to
   fix it. Fix all errors (lines starting `ERROR`).
5. **Dry-run, then run** (the run calls the Claude API and costs money — ask before using `--yes`):
   ```
   uv run evalkit eval --case KYC-EDG-120
   uv run evalkit eval --case KYC-EDG-120 --yes
   ```

`uv run evalkit coverage` shows how many cases each agent has per pattern, and which structured expectations are still
missing.

## Fields

Text fields hold the catalogue's words; the fields in **bold** are read exactly by the harness.

| Field | What to write |
|---|---|
| **`case_id`** | `KYC-<PATTERN>-<NNN>`; the file name is `<case_id>.yaml` |
| `title` | One line: situation → expected result |
| **`level`** | `L1` one agent · `L2` Supervisor with stubbed specialists · `L3` end to end · `L1+L3` |
| `primary_agent`, `agents_exercised` | `E2E`, `SUP`, `DOC`, `IDV`, `SCR`, `RSK` |
| **`pattern`** | One of the patterns above (must match the folder) |
| **`severity`** | `S1` compliance / privacy / unauthorised action · `S2` · `S3` |
| **`trials`** | 3 for S1, 1 otherwise (configs/eval.yaml › trials) |
| **`run_sets`** | `[gate, full]` for S1 · `[full]` otherwise · add `smoke` only for golden cases |
| `rule_refs` | Rule IDs from *Rules & Decisions* (R1, D7, MASK-IN_PAN …) |
| **`applicant`** | An existing applicant ID (`APP-001`) |
| **`documents`** | Document IDs; a later upload as `{doc: DOC-089-UB2, turn: 2}` |
| `customer_turns` | The scripted customer messages, separated by ` · `; L1 cases start with `n/a (L1) —` and the task |
| `mocks` | The faults / mocks / stubs in words |
| **`fixtures`** | Their profile IDs (`FP-01`, `MO-02`, `STUB-07`) |
| **`approver`** | `approve`, `deny`, `no response` or `n/a` |
| **`form_updates`** | Optional: form fields the customer supplies when asked (`{nationality: IN}`) |
| `expected_trajectory` | The expected steps in words |
| **`reference`** | Reference trajectory IDs (`[RT-01]`, see `reference_trajectories/`) |
| **`match_mode`** | `strict`, `unordered`, `subset` or `superset` (a note may follow: `unordered (vs twin)`) |
| **`required_tools`**, **`forbidden_tools`** | Tool names, comma-separated. Conditions in words ("verify_pan with a guessed dob") are allowed and checked by a reviewer |
| `argument_expectations` | Expected argument values in words |
| `expected_outcome` | The expected end state / agent output in words |
| **`expected`** | Structured: `status`, `risk_tier`, `risk_score`, `reason_codes`, `record`; plus `agent_outputs` (`{identity: {overall: UNVERIFIED}}`, AG-1) and `arguments` (`{verify_pan: {dob: 1994-03-12}}`, TU-3), filled by the QE Lead |
| `checks` | Metric IDs the case exercises (TR-1, BF-1, AG-5 …) |
| `twin_pair` | Related cases: clean twin (injection), pair partner (fairness), paraphrases |
| `oracle_owner`, `case_status`, `notes` | Who owns the expectation, draft status, anything a reviewer should know |

`lint-cases` checks every field above; a misspelt field name gets a "did you mean" suggestion.

## Rules
- All data is synthetic. Never paste a real name, PAN, Aadhaar, card or phone number.
- Do not edit `data/kyc_synthetic.sqlite`; `evalkit data` rebuilds it.
- `evalkit cases` re-imports the catalogue workbook. It keeps any file you edited unless `--force` is given, and it
  never touches cases that have no catalogue row.
