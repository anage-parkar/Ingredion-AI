"""One case, once.

The claim registry is the first of the three duplicate-order controls in the Order
Intake (the other two are the SAP duplicate check at A5 and the lookup before
any retry at A7). A claim is an atomic insert keyed by the client's case id, so two
pollers, or a poller and a restarted worker, can never both take the same case.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from ..case import now_iso

_WS = re.compile(r"\s+")


def idempotency_key(case_id: str, po_number: str | None) -> str:
    """Readable unique reference: ``<case id>:<PO number>`` (the SOW's "case ID + PO number").

    Normalised so the same PO typed with different spacing or case yields one key.
    """
    case = _WS.sub("", (case_id or "").strip()).upper()
    po = _WS.sub("", (po_number or "").strip()).upper() or "NOPO"
    return f"{case}:{po}"


class ClaimRegistry(ABC):
    @abstractmethod
    def claim(self, case_id: str, owner: str = "agent") -> bool:
        """Return True if this call took the claim; False if someone already holds it."""

    @abstractmethod
    def release(self, case_id: str) -> None:
        """Give a case back (only used when processing failed before any side effect)."""

    @abstractmethod
    def owner_of(self, case_id: str) -> str | None: ...

    @abstractmethod
    def count(self) -> int: ...


class InMemoryClaimRegistry(ClaimRegistry):
    def __init__(self) -> None:
        self._claims: dict[str, dict[str, Any]] = {}

    def claim(self, case_id: str, owner: str = "agent") -> bool:
        if case_id in self._claims:
            return False
        self._claims[case_id] = {"owner": owner, "claimed_at": now_iso()}
        return True

    def release(self, case_id: str) -> None:
        self._claims.pop(case_id, None)

    def owner_of(self, case_id: str) -> str | None:
        entry = self._claims.get(case_id)
        return entry["owner"] if entry else None

    def count(self) -> int:
        return len(self._claims)


class MongoClaimRegistry(ClaimRegistry):
    """Backed by a collection whose ``_id`` is the case id; the unique index is the lock."""

    def __init__(self, collection: Any) -> None:
        self._col = collection

    @classmethod
    def from_uri(cls, uri: str, collection: str = "factory_claims") -> MongoClaimRegistry:
        from pymongo import MongoClient
        from pymongo.errors import ConfigurationError

        client = MongoClient(uri)
        try:
            db = client.get_default_database()
        except ConfigurationError:
            db = client["ingredion"]
        return cls(db[collection])

    def claim(self, case_id: str, owner: str = "agent") -> bool:
        from pymongo.errors import DuplicateKeyError

        try:
            self._col.insert_one({"_id": case_id, "owner": owner, "claimed_at": now_iso()})
            return True
        except DuplicateKeyError:
            return False

    def release(self, case_id: str) -> None:
        self._col.delete_one({"_id": case_id})

    def owner_of(self, case_id: str) -> str | None:
        doc = self._col.find_one({"_id": case_id})
        return doc["owner"] if doc else None

    def count(self) -> int:
        return self._col.count_documents({})
