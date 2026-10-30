"""The audit trail both SOWs require: what was read (with confidence per field), what
was decided, drafted and posted, who approved, and the timings. Records are
appended and never changed; the class has no update or delete method on purpose,
and the Mongo backend only ever calls ``insert_one``.

Every scorecard and dashboard is computed from these records, so the record is
the product, not a by-product.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from ..case import now_iso


class Outcome(StrEnum):
    # Order Intake markers ("Processed by: Agent" on the Salesforce case)
    AGENT_CREATED = "AGENT_CREATED"  # reviewer confirmed the order as proposed
    AGENT_ASSISTED = "AGENT_ASSISTED"  # reviewer corrected it before creation
    RETURNED = "RETURNED"  # went to the rework path with a reason code
    DUPLICATE = "DUPLICATE"  # reviewer confirmed a duplicate; no order
    # Pre-bill outcomes
    MATCHED = "MATCHED"
    UPDATED_PO_REQUIRED = "UPDATED_PO_REQUIRED"
    INTERNAL_FIX_OR_MISSING_DATA = "INTERNAL_FIX_OR_MISSING_DATA"


@dataclass
class AuditRecord:
    case_id: str
    agent: str
    step: str
    event: str
    actor: str = "agent"
    data: dict[str, Any] = field(default_factory=dict)
    model_call: dict[str, Any] | None = None  # prompt ref + sha, model, tokens, latency, guard verdicts
    run_id: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditTrail(ABC):
    @abstractmethod
    def _insert(self, record: AuditRecord) -> None: ...

    @abstractmethod
    def for_case(self, case_id: str) -> list[AuditRecord]: ...

    @abstractmethod
    def count(self) -> int: ...

    def append(
        self,
        case_id: str,
        agent: str,
        step: str,
        event: str,
        *,
        actor: str = "agent",
        data: dict[str, Any] | None = None,
        model_call: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> AuditRecord:
        record = AuditRecord(
            case_id=case_id,
            agent=agent,
            step=step,
            event=event,
            actor=actor,
            data=dict(data or {}),
            model_call=dict(model_call) if model_call else None,
            run_id=run_id,
        )
        self._insert(record)
        return record

    def events(self, case_id: str) -> list[str]:
        return [r.event for r in self.for_case(case_id)]

    def model_calls(self, case_id: str) -> list[AuditRecord]:
        return [r for r in self.for_case(case_id) if r.model_call]


class InMemoryAuditTrail(AuditTrail):
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def _insert(self, record: AuditRecord) -> None:
        self._records.append(record)

    def for_case(self, case_id: str) -> list[AuditRecord]:
        return [r for r in self._records if r.case_id == case_id]

    def count(self) -> int:
        return len(self._records)

    def all(self) -> list[AuditRecord]:
        return list(self._records)


class MongoAuditTrail(AuditTrail):
    def __init__(self, collection: Any) -> None:
        self._col = collection
        self._col.create_index([("case_id", 1), ("at", 1)])

    def _insert(self, record: AuditRecord) -> None:
        doc = record.to_dict()
        doc["_id"] = doc.pop("id")
        self._col.insert_one(doc)

    def for_case(self, case_id: str) -> list[AuditRecord]:
        out: list[AuditRecord] = []
        for doc in self._col.find({"case_id": case_id}).sort("at", 1):
            d = dict(doc)
            d["id"] = d.pop("_id")
            out.append(AuditRecord(**d))
        return out

    def count(self) -> int:
        return self._col.count_documents({})
