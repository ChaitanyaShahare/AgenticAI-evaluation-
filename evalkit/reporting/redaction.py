"""Mask identifiers in anything the harness renders or exports (report.html, junit.xml, check details).

Uses the same recognisers as BF-1 (configs/pii_recognizers.yaml): every recognised PAN, Aadhaar, card number, phone or
e-mail becomes "…" plus its last 4 characters. `leaks()` scans a finished output, so a writer can refuse to publish a
file that still holds an identifier.
"""

from __future__ import annotations

from typing import Any

from evalkit.evaluators.bfsi.pii import Recognizer, mask, scan


class Redactor:
    def __init__(self, recognizers: list[Recognizer]):
        self.recognizers = recognizers

    def text(self, value: str) -> str:
        for _, found in scan(value, self.recognizers):
            value = value.replace(found, mask(found))
        return value

    def deep(self, obj: Any) -> Any:
        """A copy of a JSON-like value with every string redacted."""
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, dict):
            return {k: self.deep(v) for k, v in obj.items()}
        if isinstance(obj, list | tuple):
            return [self.deep(v) for v in obj]
        return obj

    def leaks(self, rendered: str) -> list[tuple[str, str]]:
        """(entity, masked value) for each identifier still present in a rendered output."""
        return [(entity, mask(v)) for entity, v in scan(rendered, self.recognizers)]
