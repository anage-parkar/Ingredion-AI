"""Order Intake scorecard.

Definitions follow Parkar's responses to the clarification questions:

* **Recovery**: the agent's order matches the final SAP order on *all* key fields.
* **Undetected error**: a key field read with confidence at or above the threshold
  that is nevertheless wrong. Reported per key field evaluated.
* **Field-level accuracy**: per field, and broken down by failure category, customer
  and file type.

Only in-scope cases count toward recovery. Cases marked not document-recoverable
(the final order contains information that is not in the PO) are reported
separately so the target is not measured against an unreachable ceiling.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

KEY_FIELDS: tuple[str, ...] = (
    "po_number",
    "sold_to",
    "ship_to",
    "material",
    "quantity",
    "uom",
    "price",
    "requested_delivery_date",
)
_LINE_FIELDS = {"material", "quantity", "uom", "price"}

GATE_THRESHOLDS: dict[str, dict[str, float]] = {
    "gate1": {"recovery": 0.50, "undetected": 0.020},
    "gate4": {"recovery": 0.70, "undetected": 0.020},
    "phase2": {"recovery": 0.80, "undetected": 0.005},
}

_WS = re.compile(r"\s+")


@dataclass
class Prediction:
    case_id: str
    fields: dict[str, Any]
    confidence: dict[str, float] = field(default_factory=dict)
    category: str | None = None
    customer: str | None = None
    file_type: str | None = None
    in_scope: bool = True
    recoverable: bool = True


@dataclass
class Answer:
    case_id: str
    fields: dict[str, Any]


@dataclass
class Scorecard:
    n_total: int
    n_in_scope: int
    n_recoverable: int
    recovered: int
    recovery_rate: float
    key_fields_evaluated: int
    confident_fields: int
    undetected_errors: int
    undetected_error_rate: float
    field_accuracy: dict[str, float]
    by_category: dict[str, float]
    by_customer: dict[str, float]
    by_file_type: dict[str, float]
    unrecoverable_share: float
    passes: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return round(float(value), 6)
    text = _WS.sub(" ", str(value)).strip().casefold()
    try:
        return round(float(text.replace(",", "")), 6)
    except ValueError:
        return text


def values_match(a: Any, b: Any) -> bool:
    if isinstance(a, list | tuple) or isinstance(b, list | tuple):
        a_list = list(a or []) if isinstance(a, list | tuple) else [a]
        b_list = list(b or []) if isinstance(b, list | tuple) else [b]
        return len(a_list) == len(b_list) and all(values_match(x, y) for x, y in zip(a_list, b_list, strict=True))
    na, nb = _norm(a), _norm(b)
    if isinstance(na, float) and isinstance(nb, float):
        return abs(na - nb) <= 1e-6 * max(1.0, abs(na), abs(nb))
    return na == nb


def field_value(fields: dict[str, Any], name: str) -> Any:
    """Line-level fields are compared across all lines, in order."""
    if name in _LINE_FIELDS and isinstance(fields.get("lines"), list):
        return [line.get(name) if isinstance(line, dict) else None for line in fields["lines"]]
    return fields.get(name)


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def score_order_intake(
    predictions: Iterable[Prediction],
    answers: Iterable[Answer],
    *,
    key_fields: tuple[str, ...] = KEY_FIELDS,
    confidence_threshold: float = 0.80,
) -> Scorecard:
    truth = {a.case_id: a for a in answers}
    preds = list(predictions)
    in_scope = [p for p in preds if p.in_scope and p.case_id in truth]
    recoverable = [p for p in in_scope if p.recoverable]

    correct_by_field: dict[str, int] = defaultdict(int)
    recovered = 0
    confident = 0
    undetected = 0
    evaluated = 0
    group_hits: dict[str, dict[str, list[int]]] = {"category": defaultdict(list), "customer": defaultdict(list), "file_type": defaultdict(list)}

    for p in recoverable:
        answer = truth[p.case_id]
        all_ok = True
        for name in key_fields:
            evaluated += 1
            ok = values_match(field_value(p.fields, name), field_value(answer.fields, name))
            if ok:
                correct_by_field[name] += 1
            else:
                all_ok = False
            conf = p.confidence.get(name)
            if conf is not None and conf >= confidence_threshold:
                confident += 1
                if not ok:
                    undetected += 1
        recovered += int(all_ok)
        for key, value in (("category", p.category), ("customer", p.customer), ("file_type", p.file_type)):
            if value:
                group_hits[key][value].append(int(all_ok))

    n_rec = len(recoverable)
    recovery_rate = _rate(recovered, n_rec)
    undetected_rate = _rate(undetected, evaluated)
    return Scorecard(
        n_total=len(preds),
        n_in_scope=len(in_scope),
        n_recoverable=n_rec,
        recovered=recovered,
        recovery_rate=recovery_rate,
        key_fields_evaluated=evaluated,
        confident_fields=confident,
        undetected_errors=undetected,
        undetected_error_rate=undetected_rate,
        field_accuracy={name: _rate(correct_by_field[name], n_rec) for name in key_fields},
        by_category={k: _rate(sum(v), len(v)) for k, v in sorted(group_hits["category"].items())},
        by_customer={k: _rate(sum(v), len(v)) for k, v in sorted(group_hits["customer"].items())},
        by_file_type={k: _rate(sum(v), len(v)) for k, v in sorted(group_hits["file_type"].items())},
        unrecoverable_share=_rate(len(in_scope) - n_rec, len(in_scope)),
        passes={
            gate: recovery_rate >= t["recovery"] and undetected_rate <= t["undetected"]
            for gate, t in GATE_THRESHOLDS.items()
        },
    )
