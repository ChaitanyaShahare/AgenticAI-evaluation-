"""Test clock. Tools read AS_OF from the seed database's config table (key `as_of`); configs/eval.yaml pins the same date.

check_clock() fails fast when the two disagree, because expiry and bill-age results depend on it (KYC-EDG-020 / 104).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class ClockMismatch(RuntimeError):
    pass


def seed_as_of(seed: Path) -> str | None:
    con = sqlite3.connect(f"file:{seed}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT value FROM config WHERE key = 'as_of'").fetchone()
    except sqlite3.OperationalError:
        return None  # project without a config table: nothing to check
    finally:
        con.close()
    return row[0] if row else None


def check_clock(seed: Path, as_of: str) -> None:
    db = seed_as_of(seed)
    if db is not None and db != as_of:
        raise ClockMismatch(f"test clock mismatch: seed database says {db}, configs/eval.yaml says {as_of}")
