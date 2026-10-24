# Working in this repository (for Claude Code sessions)

Read README.md (layout and per-file purpose) and EXECUTION_PLAN.md (which work package owns which file) first.

## Rules that protect the evaluation
- Never write or change **S1 expectations, policy YAML (`projects/*/policies/`), `configs/gates.yaml` thresholds or the lab answer key**. These are human-owned oracles. If the agent and its oracle come from the same assistant, their errors correlate and the tests pass for the wrong reason.
- Never edit `projects/kyc_onboarding/data/kyc_synthetic.sqlite` directly. Change `data/fixtures/*.py`, then run `uv run evalkit data`, which rebuilds the database and runs the conformance check.
- `evalkit/` must never import from `projects/`. Project-specific behaviour arrives through configuration and an adapter.
- All data is synthetic. Do not introduce real names, PANs, Aadhaar numbers, card numbers or documents.

## How to work
- One work package per session; tests first, then implementation; keep each change reviewable.
- Run `uv run --frozen evalkit test` and `uv run --frozen ruff check .` before declaring a step done.
- Configuration is strict (unknown keys fail). When adding a key, add it to the Pydantic model in `evalkit/config/loader.py` and to `docs/config_reference.md`.
- Messages shown to testers must say what is wrong and how to fix it, in plain English.
- Save any prompt used to generate code or fixtures under `prompts/claude_code/`.

## Environment
- Python 3.12, uv, lockfile `uv.lock` (`uv sync --frozen`).
- The repository lives in Dropbox: keep the virtual environment and run outputs outside it (`UV_PROJECT_ENVIRONMENT`, `EVALKIT_RUNS_DIR`).
- `make` may be missing on Windows; every Makefile target is `uv run evalkit <command>`.
