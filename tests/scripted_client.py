"""A scripted stand-in for anthropic.Anthropic, so the KYC graph runs offline (CI has no API key; tests cost nothing).

It implements only what the agents use: messages.create (specialist tool loops) and messages.parse (Supervisor router).
Each agent has its own queue of scripted turns; the agent is recognised from the tools offered to it, not from prompt
text. Every request is recorded so tests can assert model, effort, caching and the absence of sampling parameters.

Script items for a specialist turn:   [("call", tool_name, {args}), …]   or   [("finish", {submission})]
Script items for the Supervisor:      {SupervisorAction fields}
"""

from __future__ import annotations

import itertools
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

AGENT_BY_TOOL = {
    "classify_document": "doc_extraction",
    "verify_pan": "identity",
    "sanctions_screen": "screening",
    "fetch_risk_policy": "risk",
}


class ScriptExhausted(AssertionError):
    pass


class _Messages:
    def __init__(self, owner: ScriptedClient):
        self.o = owner

    def create(self, **kw):
        self.o.requests.append(("create", kw))
        names = {t["name"] for t in kw.get("tools", [])}
        agent = next((a for t, a in AGENT_BY_TOOL.items() if t in names), "unknown")
        queue = self.o.scripts.get(agent)
        if not queue:
            raise ScriptExhausted(f"no scripted turn left for {agent}")
        turn = queue.pop(0)
        blocks = []
        for item in turn:
            if item[0] == "call":
                blocks.append(SimpleNamespace(type="tool_use", id=f"tu_{next(self.o.ids)}", name=item[1], input=item[2]))
            elif item[0] == "finish":
                blocks.append(SimpleNamespace(type="tool_use", id=f"tu_{next(self.o.ids)}", name="submit_result", input=item[1]))
            elif item[0] == "text":
                blocks.append(SimpleNamespace(type="text", text=item[1]))
        stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
        return SimpleNamespace(content=blocks, stop_reason=turn[0][1] if turn and turn[0][0] == "stop" else stop, usage=_usage())

    def parse(self, **kw):
        self.o.requests.append(("parse", kw))
        if not self.o.supervisor:
            raise ScriptExhausted("no scripted Supervisor decision left")
        item = self.o.supervisor.pop(0)
        if item == "REFUSAL":
            return SimpleNamespace(parsed_output=None, stop_reason="refusal", usage=_usage(), content=[])
        return SimpleNamespace(parsed_output=kw["output_format"](**item), stop_reason="end_turn", usage=_usage(), content=[])


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)


class ScriptedClient:
    def __init__(self, supervisor: list[Any], **agent_scripts: list[list[tuple]]):
        self.supervisor = list(supervisor)
        self.scripts = {k: list(v) for k, v in agent_scripts.items()}
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.ids = itertools.count(1)
        self.messages = _Messages(self)

    def unused(self) -> dict[str, int]:
        left = {k: len(v) for k, v in self.scripts.items() if v}
        if self.supervisor:
            left["supervisor"] = len(self.supervisor)
        return left


def act(action: str, **kw) -> dict[str, Any]:
    """Shorthand for a SupervisorAction."""
    return {"action": action, "reason": kw.pop("reason", action), **kw}


SEED = Path(__file__).resolve().parents[1] / "projects" / "kyc_onboarding" / "data" / "kyc_synthetic.sqlite"


def doc_turns(docs, profile):
    return [
        [("call", "classify_document", {"doc_id": d}) for d in docs],
        [("call", "extract_document", {"doc_id": d, "doc_type": t}) for d, t in docs.items()],
        [("finish", profile)],
    ]


def persona(app_id: str) -> dict:
    con = sqlite3.connect(SEED)
    con.row_factory = sqlite3.Row
    a = con.execute("SELECT * FROM applicants WHERE applicant_id = ?", (app_id,)).fetchone()
    docs = {
        r["doc_id"]: r["doc_type"]
        for r in con.execute(
            "SELECT doc_id, doc_type FROM documents WHERE applicant_id = ? AND doc_id NOT LIKE '%-INJ' ORDER BY doc_id", (app_id,)
        )
    }
    con.close()
    return {
        "app": app_id,
        "pan": a["pan"],
        "full_name": a["full_name"].upper(),
        "dob": a["dob"],
        "address": a["address"],
        "docs": docs,
        "proof": next(d for d, t in docs.items() if t != "PAN_CARD"),
    }


def clean_client(app_id: str = "APP-001", approval_then=None):
    """Scripted run of the clean path (RT-01) for any curated applicant: correct tool use by every agent."""
    p = persona(app_id)
    who = {"pan": p["pan"], "full_name": p["full_name"], "dob": p["dob"]}
    profile = {
        **who,
        "aadhaar_last4": None,
        "address": p["address"],
        "nationality": None,
        "quality_flags": [],
        "missing_fields": [],
        "injection_suspected": False,
        "field_sources": {"full_name": f"DOC-{app_id[4:]}-PAN", "address": p["proof"]},
    }
    sup = [
        act("delegate", target="doc_extraction"),
        act("delegate", target="identity"),
        act("delegate", target="screening"),
        act("delegate", target="risk"),
        act("request_approval"),
    ]
    sup += approval_then or [
        act("create_record"),
        act("finalize", status="APPROVED", reason_codes=[], message_to_customer="Your account is open."),
    ]
    return ScriptedClient(
        sup,
        doc_extraction=doc_turns(p["docs"], profile),
        identity=[
            [("call", "verify_pan", who)],
            [
                ("call", "ckyc_lookup", {"pan": p["pan"], "dob": p["dob"]}),
                ("call", "check_address_proof", {"doc_id": p["proof"], "address": p["address"]}),
            ],
            [("finish", {"notes": "ok"})],
        ],
        screening=[
            [
                ("call", "sanctions_screen", {"full_name": p["full_name"], "dob": p["dob"], "nationality": "IN"}),
                ("call", "pep_check", {"full_name": p["full_name"], "dob": p["dob"]}),
            ],
            [("finish", {"notes": "clean"})],
        ],
        risk=[
            [("call", "fetch_risk_policy", {"version": "v3"})],
            [("call", "compute_risk_score", {"applicant_id": app_id, "screening_ref": "SCR-0001", "product": "SAVINGS"})],
            [("finish", {"explanation": "Salaried, mid income band."})],
        ],
    )
