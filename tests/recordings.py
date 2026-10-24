"""Recorded runs: scripted (offline) trajectories stored in projects/kyc_onboarding/recorded_runs/, one per level.

They pin the adapter's event → Trajectory mapping (tests/unit/test_adapter_parity.py) and give WP5 evaluator tests real
trajectories without API calls. Refresh after an intended change:  uv run python -m tests.recordings --write
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tests.scripted_client import ScriptedClient, act, clean_client

RECORDINGS = Path(__file__).resolve().parents[1] / "projects" / "kyc_onboarding" / "recorded_runs"
ROHAN = {"pan": "ZQCPM1274R", "full_name": "ROHAN MEHTA", "dob": "1988-11-02"}


def flt021_client() -> ScriptedClient:
    """L1 identity agent under FP-01 (timeout → 500 → 500): two identical retries, then it moves on."""
    return ScriptedClient(
        [],
        identity=[
            [("call", "verify_pan", ROHAN)],
            [("call", "verify_pan", ROHAN)],
            [("call", "verify_pan", ROHAN)],
            [
                ("call", "ckyc_lookup", {"pan": ROHAN["pan"], "dob": ROHAN["dob"]}),
                ("call", "check_address_proof", {"doc_id": "DOC-002-PP", "address": "35, Gandhi Nagar, Ahmedabad 380009, Gujarat"}),
            ],
            [("finish", {"notes": "PAN service unavailable after 2 retries"})],
        ],
    )


def hnd109_client() -> ScriptedClient:
    return ScriptedClient(
        [act("delegate", target=t) for t in ("doc_extraction", "identity", "screening", "risk")]
        + [act("request_approval"), act("create_record"), act("finalize", status="APPROVED", reason_codes=[])]
    )


SCRIPTS = {"KYC-GLD-001": clean_client, "KYC-FLT-021": flt021_client, "KYC-HND-109": hnd109_client}


def normalise(data: dict) -> dict:
    """Drop what legitimately differs between identical runs (wall clock, durations, installed versions)."""
    meta = data["meta"]
    for k in ("started_at", "duration_s", "package_versions", "run_id"):
        meta.pop(k, None)
    for s in data["steps"]:
        if s.get("tool_call"):
            s["tool_call"].pop("latency_ms", None)
    return data


def record(out_dir: Path, run_dir: Path) -> dict[str, Path]:
    from evalkit.harness.runner import execute, make_plan  # noqa: PLC0415

    plan = make_plan("kyc_onboarding", case_ids=list(SCRIPTS), trials=1, run_id="recording")
    execute(plan, client_factory=lambda case, trial: SCRIPTS[case.case_id](), max_workers=1, progress=lambda _m: None)
    written = {}
    for cid in SCRIPTS:
        src = run_dir / "recording" / "trajectories" / cid / "t1.json"
        dst = out_dir / f"{cid}.json"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written[cid] = dst
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.write:
        import os
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        os.environ["EVALKIT_RUNS_DIR"] = str(tmp)
        for cid, path in record(RECORDINGS, tmp).items():
            print("recorded", cid, "->", path)
