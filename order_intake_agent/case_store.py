"""Where a case lives between steps and across the human gate.

A reviewer may decide hours after A5 parked the case, possibly in another process,
so the case (state, data, flags, history) must survive. The in-memory store is for
tests and single-process Dev; the Mongo store serialises the Pydantic models in
``case.data`` by name so they come back as the same types.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from factory.case import Case, Flag
from factory.review import Decision

from .models import (
    ClarificationDraft,
    Classification,
    EmailBundle,
    IncompletionItem,
    IntakeCase,
    POExtraction,
    RPAFailure,
    SAPPayload,
    Score,
    Validation,
)

_MODELS: dict[str, type[BaseModel]] = {
    m.__name__: m
    for m in (IntakeCase, RPAFailure, EmailBundle, Classification, POExtraction, Validation, Score, SAPPayload, ClarificationDraft, IncompletionItem)
}


class CaseStore(Protocol):
    def save(self, case: Case) -> None: ...

    def get(self, case_id: str) -> Case | None: ...

    def in_state(self, state: str) -> list[Case]: ...


def serialize_case(case: Case) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in case.data.items():
        if isinstance(value, BaseModel):
            data[key] = {"__model__": type(value).__name__, "value": value.model_dump(mode="json")}
        elif isinstance(value, list) and value and all(isinstance(v, BaseModel) for v in value):
            data[key] = {"__models__": type(value[0]).__name__, "values": [v.model_dump(mode="json") for v in value]}
        elif isinstance(value, Decision):
            data[key] = {"__decision__": value.to_dict()}
        else:
            data[key] = value
    return {
        "_id": case.case_id,
        "agent": case.agent,
        "state": case.state,
        "idempotency_key": case.idempotency_key,
        "data": data,
        "flags": [f.to_dict() for f in case.flags],
        "reason_codes": list(case.reason_codes),
        "outcome": case.outcome,
        "history": list(case.history),
        "run_id": case.run_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


def deserialize_case(doc: dict[str, Any]) -> Case:
    data: dict[str, Any] = {}
    for key, value in (doc.get("data") or {}).items():
        if isinstance(value, dict) and "__model__" in value:
            data[key] = _MODELS[value["__model__"]].model_validate(value["value"])
        elif isinstance(value, dict) and "__models__" in value:
            model = _MODELS[value["__models__"]]
            data[key] = [model.model_validate(v) for v in value["values"]]
        elif isinstance(value, dict) and "__decision__" in value:
            data[key] = Decision.from_dict(value["__decision__"])
        else:
            data[key] = value
    return Case(
        case_id=doc["_id"],
        agent=doc["agent"],
        state=doc["state"],
        idempotency_key=doc.get("idempotency_key"),
        data=data,
        flags=[Flag(**f) for f in doc.get("flags", [])],
        reason_codes=list(doc.get("reason_codes", [])),
        outcome=doc.get("outcome"),
        history=list(doc.get("history", [])),
        run_id=doc.get("run_id") or "",
        created_at=doc.get("created_at") or "",
        updated_at=doc.get("updated_at") or "",
    )


class InMemoryCaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}

    def save(self, case: Case) -> None:
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def in_state(self, state: str) -> list[Case]:
        return [c for c in self._cases.values() if c.state == state]

    def all(self) -> list[Case]:
        return list(self._cases.values())


class MongoCaseStore:
    def __init__(self, collection: Any) -> None:
        self._col = collection
        self._col.create_index("state")

    def save(self, case: Case) -> None:
        self._col.replace_one({"_id": case.case_id}, serialize_case(case), upsert=True)

    def get(self, case_id: str) -> Case | None:
        doc = self._col.find_one({"_id": case_id})
        return deserialize_case(doc) if doc else None

    def in_state(self, state: str) -> list[Case]:
        return [deserialize_case(d) for d in self._col.find({"state": state})]
