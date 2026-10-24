"""Per-run context and SQLite access for the KYC mocks (contract: projects/kyc_onboarding/data/README.md).

A ToolContext points at one per-trial copy of the seed database and holds what a real channel would know:
the application in session, which scripted customer turn we are on, and the test clock. Timestamps and IDs are
derived from the test clock and per-run counters, never the wall clock, so identical runs give identical rows.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def norm(s: str | None) -> str:
    """Contract name normalisation: upper-case, non-letters → spaces, collapse spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z ]", " ", s or "").upper()).strip()


def split_turns(customer_turns: str | None) -> tuple[str | None, list[tuple[str, str | None]]]:
    """Parse the catalogue's scripted-turn notation.

    '"first" · on request: "reply" · after approval: "x"'  →  ("first", [("on request", "reply"), ("after approval", "x")])
    A '<no further response>' reply becomes None. L1 placeholders ('n/a (L1) …') give (None, []).
    """
    if not customer_turns or customer_turns.startswith("n/a"):
        return None, []
    parts = [p.strip() for p in customer_turns.split(" · ")]
    first = parts[0].strip('"')
    later: list[tuple[str, str | None]] = []
    for p in parts[1:]:
        trigger, _, text = p.partition(":")
        text = text.strip()
        later.append((trigger.strip(), None if text.startswith("<no further response>") else text.strip('"')))
    return first, later


@dataclass
class ToolContext:
    db_path: Path
    run_id: str = "adhoc"
    case_id: str | None = None
    trial: int = 1
    application_id: str | None = None
    applicant_id: str | None = None
    profile_ids: list[str] = field(default_factory=list)
    approver_response: str | None = None
    form_updates: dict[str, Any] | None = None
    first_turn: str | None = None
    later_turns: list[tuple[str, str | None]] = field(default_factory=list)
    turn: int = 1  # documents with uploaded_at_turn ≤ turn are visible
    _requests_answered: int = 0
    _seq: dict[str, int] = field(default_factory=dict)
    _conn: sqlite3.Connection | None = None

    # ---------------------------------------------------------------- construction
    @classmethod
    def for_case(cls, db_path: Path, case_id: str, run_id: str = "adhoc", trial: int = 1) -> ToolContext:
        """Build the context for one catalogue case from its test_cases row."""
        ctx = cls(db_path=Path(db_path), run_id=run_id, case_id=case_id, trial=trial)
        row = ctx.one("SELECT * FROM test_cases WHERE case_id = ?", (case_id,))
        if row is None:
            raise KeyError(f"case {case_id} not in test_cases")
        ctx.application_id, ctx.applicant_id = row["application_id"], row["applicant_id"]
        ctx.profile_ids = json.loads(row["profile_ids_json"] or "[]")
        ctx.approver_response = row["approver_response"]
        ctx.form_updates = json.loads(row["form_updates_json"]) if row["form_updates_json"] else None
        ctx.first_turn, ctx.later_turns = split_turns(row["customer_turns"])
        return ctx

    # ---------------------------------------------------------------- database
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def write(self, sql: str, params: tuple = ()) -> None:
        self.conn.execute(sql, params)
        self.conn.commit()

    def config(self, key: str) -> str:
        row = self.one("SELECT value FROM config WHERE key = ?", (key,))
        if row is None:
            raise KeyError(f"config key {key!r} missing from the seed database")
        return row["value"]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ---------------------------------------------------------------- determinism
    def next_seq(self, name: str) -> int:
        self._seq[name] = self._seq.get(name, 0) + 1
        return self._seq[name]

    def now(self) -> str:
        """Test-clock timestamp: AS_OF 09:00 IST plus one second per write in this run."""
        base = datetime.fromisoformat(f"{self.config('as_of')}T09:00:00+05:30")
        return (base + timedelta(seconds=self.next_seq("clock"))).isoformat()

    # ---------------------------------------------------------------- session rules
    def in_session(self, application_id: str) -> bool:
        """Write tools may only act on the application in session (no third-party actions)."""
        return self.application_id is None or application_id == self.application_id

    def visible_doc(self, doc_id: str) -> bool:
        """A document is visible once uploaded: always in ad-hoc use; per case_documents and the current turn in a case.
        A case with no uploads at all (L1 isolation of identity / screening / risk) sees its applicant's own documents."""
        if self.case_id is None:
            return True
        row = self.one("SELECT uploaded_at_turn FROM case_documents WHERE case_id = ? AND doc_id = ?", (self.case_id, doc_id))
        if row is not None:
            return row["uploaded_at_turn"] <= self.turn
        if self.one("SELECT 1 FROM case_documents WHERE case_id = ?", (self.case_id,)) is None:
            return self.one("SELECT 1 FROM documents WHERE doc_id = ? AND applicant_id = ?", (doc_id, self.applicant_id)) is not None
        return False

    def next_customer_reply(self) -> tuple[bool, str | None]:
        """(scripted, reply) for the next 'on request' turn. reply None = <no further response>; scripted False = script exhausted."""
        replies = [text for trigger, text in self.later_turns if trigger == "on request"]
        if self._requests_answered >= len(replies):
            return False, None
        reply = replies[self._requests_answered]
        self._requests_answered += 1
        return True, reply
