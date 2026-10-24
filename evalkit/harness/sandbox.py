"""Per-trial database sandbox: every case × trial starts from an identical private copy of the project's seed database.

The mocks write runtime rows (screening results, tokens, audit events …) into the copy, never into the seed.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def trial_db(seed: Path, run_dir: Path, case_id: str, trial: int) -> Path:
    if not seed.is_file():
        raise FileNotFoundError(f"seed database not found: {seed} — run `evalkit data`")
    dst = run_dir / "db" / case_id / f"t{trial}.sqlite"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed, dst)
    return dst
