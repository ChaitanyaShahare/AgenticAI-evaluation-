"""junit.xml: one test per case × trial × check, so CI names the failing rule.

Test names read `KYC-GLD-001 t1 · TR-3 (R1)` (agent checks add `[identity]`); the test suite is the case. A failed
check is a <failure>, an evaluator error an <error>, a skipped check <skipped> with its reason. Case-level checks
(TR-7 pass^k) are trial 0. Messages are redacted before writing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from evalkit.reporting.redaction import Redactor
from evalkit.schema import CaseResult, CheckResult


def check_name(case_id: str, trial: int, c: CheckResult) -> str:
    rule = f" ({c.rule})" if c.rule else ""
    agent = f" [{c.agent}]" if c.agent else ""
    return f"{case_id} t{trial} · {c.metric}{rule}{agent}"


def write_junit(path: Path, results: list[CaseResult], case_checks: dict[str, CheckResult], run_id: str, redactor: Redactor) -> Path:
    rows: dict[str, list[tuple[int, CheckResult]]] = defaultdict(list)
    for r in results:
        rows[r.case_id] += [(r.trial, c) for c in r.checks]
    for cid, c in case_checks.items():
        rows[cid].append((0, c))
    root = ET.Element("testsuites", name=f"evalkit {run_id}")
    for cid in sorted(rows):
        checks = rows[cid]
        suite = ET.SubElement(
            root, "testsuite", name=cid, tests=str(len(checks)),
            failures=str(sum(c.verdict == "fail" for _, c in checks)), errors=str(sum(c.verdict == "error" for _, c in checks)),
            skipped=str(sum(c.verdict == "skip" for _, c in checks)),
        )  # fmt: skip
        for trial, c in checks:
            case = ET.SubElement(suite, "testcase", classname=f"{cid}.{c.metric}", name=check_name(cid, trial, c))
            msg = redactor.text(f"{c.severity}: {c.detail}")
            if c.verdict == "fail":
                ET.SubElement(case, "failure", message=msg, type=c.severity).text = msg
            elif c.verdict == "error":
                ET.SubElement(case, "error", message=msg, type="evaluator").text = msg
            elif c.verdict == "skip":
                ET.SubElement(case, "skipped", message=msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path
