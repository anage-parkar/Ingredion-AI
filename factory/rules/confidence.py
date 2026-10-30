"""Composite per-field confidence.

The SOW thresholds (undetected errors ≤ 2% of key fields at Gate 1, ≤ 0.5% before
any straight-through creation) only mean something against a calibrated score. A
model's self-reported confidence is one weak signal among five:

* ``model``        what the model said about its own answer (0..1)
* ``layout``       does the value appear in the Document Intelligence / source text? (0..1)
* ``arithmetic``   do the numbers add up (quantity × price = line total)? (bool)
* ``master_data``  did the value match SAP master data / CMIR? (bool)
* ``history``      how stable this customer's format has been for this field (0..1)

Missing signals are left out and the weights renormalised; a field with no evidence
scores 0, never a default "probably fine".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_NORM = re.compile(r"[\s,]")


@dataclass
class FieldEvidence:
    field: str
    model: float | None = None
    layout: float | None = None
    arithmetic: bool | None = None
    master_data: bool | None = None
    history: float | None = None


@dataclass(frozen=True)
class Weights:
    model: float = 0.15
    layout: float = 0.35
    arithmetic: float = 0.20
    master_data: float = 0.20
    history: float = 0.10


class CompositeConfidence:
    def __init__(self, weights: Weights | None = None, threshold: float = 0.80) -> None:
        self.weights = weights or Weights()
        self.threshold = threshold

    def score(self, ev: FieldEvidence) -> float:
        parts: list[tuple[float, float]] = []
        for name in ("model", "layout", "arithmetic", "master_data", "history"):
            value = getattr(ev, name)
            if value is None:
                continue
            numeric = (1.0 if value else 0.0) if isinstance(value, bool) else max(0.0, min(1.0, float(value)))
            parts.append((getattr(self.weights, name), numeric))
        if not parts:
            return 0.0
        total_w = sum(w for w, _ in parts)
        return round(sum(w * v for w, v in parts) / total_w, 4)

    def score_fields(self, evidences: list[FieldEvidence]) -> dict[str, float]:
        return {ev.field: self.score(ev) for ev in evidences}

    def low(self, scores: dict[str, float]) -> list[str]:
        return [f for f, s in scores.items() if s < self.threshold]

    def is_confident(self, score: float) -> bool:
        return score >= self.threshold


def _normalise(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = _NORM.sub("", str(value)).lower()
    return text


def layout_agreement(value: Any, source_text: str) -> float:
    """1.0 when the (normalised) value occurs in the source text, else 0.0.

    Commas and whitespace are ignored so ``170000`` agrees with "170,000"; floats
    that are whole numbers agree with their integer print.
    """
    needle = _normalise(value)
    if not needle:
        return 0.0
    haystack = _normalise(source_text or "")
    if needle in haystack:
        return 1.0
    # "47.0" vs "47.00": compare numeric strings without trailing zeros
    if re.fullmatch(r"\d+\.\d+", needle):
        trimmed = needle.rstrip("0").rstrip(".")
        if trimmed and re.search(rf"(?<![\d.]){re.escape(trimmed)}0*(?![\d])", haystack):
            return 1.0
    return 0.0
