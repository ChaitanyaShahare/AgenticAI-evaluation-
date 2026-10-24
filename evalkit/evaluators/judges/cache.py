"""Judge result cache: a trace is judged once per (trace content, metric, rubric version, judge model, prompt).

The key ignores what legitimately differs between identical runs (run ID, wall clock, durations, latencies, installed
versions), so re-grading the same behaviour costs nothing, while any change to the trace, the rubric or the judge
model gives a new key. Entries are small JSON files under configs/judges.yaml › cache_dir.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evalkit.schema import Trajectory

VOLATILE_META = ("run_id", "started_at", "duration_s", "package_versions", "usage")


def trace_fingerprint(traj: Trajectory) -> str:
    data = traj.model_dump(mode="json")
    for k in VOLATILE_META:
        data["meta"].pop(k, None)
    for s in data["steps"]:
        if s.get("tool_call"):
            s["tool_call"].pop("latency_ms", None)
        if s.get("kind") == "llm":
            s.get("data", {}).pop("usage", None)
        if s.get("kind") == "note" and s.get("content") == "run_start":
            s.get("data", {}).pop("run_id", None)
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class JudgeCache:
    def __init__(self, folder: Path):
        self.folder = folder

    @staticmethod
    def key(traj: Trajectory, metric: str, rubric_version: str, model: str, prompt_hash: str = "") -> str:
        parts = "|".join([trace_fingerprint(traj), metric, rubric_version, model, prompt_hash])
        return hashlib.sha256(parts.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self.folder / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def put(self, key: str, result: dict[str, Any]) -> Path:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
        return p
