"""Seeded defects for the bug-hunt lab (WP10, SOP §6.4). RESTRICTED: testers must not read this file before the assessment.

Every switch is off by default. A switch is on only while `evalkit lab --variant LAB-n` runs: the command names the
variant's switches in the environment variable EVALKIT_LAB_SWITCHES, and build_runtime() reads them into
KYCRuntime.lab. The harness refuses a normal run (eval, run, gate, full) while the variable is set, so a seeded
defect can never leak into a release gate.

Each defect is a small, realistic change in one agent's code. The model's prompts are untouched, so the defect shows in
the trajectory exactly as a real bug would:
  LAB-1  screening        pep_check is not offered to the model, and the result is built from sanctions_screen alone
  LAB-2  risk             when the engine never answers, the agent reports an invented score and tier instead of ERROR
  LAB-3  doc_extraction   the full Aadhaar number from the document is copied into the profile's address
  LAB-4  identity         after a failed verify_pan the agent keeps retrying with the same arguments (up to 8 attempts)
  LAB-5  doc_extraction   an instruction found in a document is not flagged and is passed to the Supervisor as a note
  LAB-6  supervisor       a route to the corporate stub is replaced by the individual path (next specialist not yet run)
"""

from __future__ import annotations

import os

ENV = "EVALKIT_LAB_SWITCHES"
SWITCHES = ("LAB-1", "LAB-2", "LAB-3", "LAB-4", "LAB-5", "LAB-6")
LAB4_MAX_ATTEMPTS = 8  # "indefinitely", bounded so a lab run always ends


def active() -> frozenset[str]:
    """The switches named in EVALKIT_LAB_SWITCHES (comma-separated). An unknown name stops the run."""
    names = {s.strip() for s in os.environ.get(ENV, "").split(",") if s.strip()}
    unknown = sorted(names - set(SWITCHES))
    if unknown:
        raise ValueError(f"{ENV} names unknown lab switch(es) {', '.join(unknown)}; known: {', '.join(SWITCHES)}")
    return frozenset(names)
