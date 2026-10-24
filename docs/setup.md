# Setup: from a clean laptop to a green smoke run

About 20 minutes. Commands are for Windows (PowerShell or Git Bash); on macOS / Linux drop the `setx` step and use
`export`. Every `make` target is also `uv run evalkit <command>`, so `make` is optional.

## 1. Prerequisites

| Need | Why | Check |
|---|---|---|
| Python 3.12 | the pinned interpreter (`.python-version`) | `python --version` |
| uv | installs the exact versions in `uv.lock` | `uv --version` |
| An Anthropic API key **with a spending limit** | only for live runs (`eval`, `run`, `gate`, `full`, judges); everything else is offline | — |
| Written approval to send synthetic data to the API | SOP §7.2 assumption A3 | — |

No spaCy model is needed: the PII checks use regular expressions with checksums (Verhoeff for Aadhaar, Luhn for cards).
`evalkit doctor` reports the spaCy model as optional.

## 2. Keep the environment and run outputs outside Dropbox

The repository lives in Dropbox. A virtual environment (≈ 340 MB, tens of thousands of files) and run outputs inside
it would be synced and can get locked mid-run. Point both somewhere else, then **open a new terminal**:

```powershell
setx UV_PROJECT_ENVIRONMENT "C:\Users\<you>\.venvs\bfsi-agent-eval"
setx EVALKIT_RUNS_DIR "C:\Users\<you>\.evalkit-runs"
```

If a `.venv` folder ever appears in the repository, a command ran without `UV_PROJECT_ENVIRONMENT`; delete the folder.

## 3. Install

From the repository folder:

```bash
uv sync --frozen
```

`--frozen` installs exactly what `uv.lock` pins and never re-resolves. Use `uv run --frozen …` for every command.

## 4. Configure

Copy `.env.example` to `.env` (git-ignored) and set:

- `ANTHROPIC_API_KEY` — needed only for live runs. Never paste it into a file that is committed or shared.
- optional `EVALKIT_RUNS_DIR`, `EVALKIT_MAX_WORKERS` (lower it on HTTP 429).

Model IDs, effort per role, run modes and trials are in `configs/eval.yaml` (see `docs/config_reference.md`). Before
the first paid run, fill `budget.pricing`, `budget.usd_to_inr` and `budget.monthly_limit_inr` from the current price
list; until then `cost.json` reports tokens with cost "unknown" and budget alerts are off.

## 5. Check the setup

```bash
uv run --frozen evalkit doctor
```

Checks Python, every configuration file (strict: an unknown key is an error with the fix), the seed database, the API
key (presence only — it is never printed) and the optional NLP model.

## 6. Smoke run (offline)

```bash
uv run --frozen evalkit smoke
```

Runs the setup check, the fixture conformance check and the framework's own tests (334 on 24 Oct 2026, no API calls).
Expected: every step ✓ and exit code 0.

## 7. First live case (optional, costs money)

Every live command is a **dry run** unless `--yes` is given: it prints the trials, model calls and estimated cost.

```bash
uv run --frozen evalkit eval --case KYC-GLD-001
uv run --frozen evalkit eval --case KYC-GLD-001 --yes
```

One live KYC-GLD-001 trial took 38 s and cost about $0.04 on 23 Oct 2026. The run lands in
`<runs dir>/adhoc-<timestamp>/`; grade it offline with `uv run --frozen evalkit grade <run id>`.

| Run | Trials | Cost |
|---|---|---|
| `evalkit run --mode smoke --yes` | 10 | read the dry run's estimate |
| `evalkit gate --yes` | 210 (70 S1 cases × 3) | the dry run estimated about $4.26 on 23 Oct 2026 |
| `evalkit full --yes` | 250, plus one judge call per trace and rubric | read the dry run; judges are priced once `configs/judges.yaml › pricing` is set |

Always read the dry run before adding `--yes`, and get the spend approved.

## 8. Rebuild the synthetic data (only when fixtures or cases change)

```bash
uv run --frozen evalkit data
```

Rebuilds the seed database in a temporary file from `data/fixtures/*.py` and the case YAML files, runs the conformance
check and replaces `kyc_synthetic.sqlite` only if the check passes. Never edit the SQLite file directly.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `configs/eval.yaml: unknown key …` | Strict configuration: fix the spelling shown, or add the key to `evalkit/config/loader.py` and `docs/config_reference.md` |
| A `.venv` folder appears in the repo | `UV_PROJECT_ENVIRONMENT` not set in this terminal — open a new one after `setx` |
| `PermissionError` / file locked under Dropbox | Run outputs inside Dropbox: set `EVALKIT_RUNS_DIR` |
| HTTP 429 during a run | Lower `execution.max_workers` or `EVALKIT_MAX_WORKERS` |
| `ANTHROPIC_API_KEY is not set` | Only live commands need it; put it in `.env` |
| Gate prints `NO_GATES` | `configs/gates.yaml` is blank — thresholds are human-owned |
| Gate prints `INCOMPLETE` | A threshold had no checks to measure it (for example TU-3 before argument expectations exist); see the gate table in report.html |
| CRLF warnings from yamllint | Save YAML with LF line endings |
