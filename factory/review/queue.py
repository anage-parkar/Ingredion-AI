from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import Decision, ReviewItem


class AlreadyDecided(RuntimeError):
    pass


class ReviewQueue(ABC):
    @abstractmethod
    def enqueue(self, item: ReviewItem) -> ReviewItem: ...

    @abstractmethod
    def get(self, item_id: str) -> ReviewItem | None: ...

    @abstractmethod
    def list(self, *, status: str | None = None, agent: str | None = None, owner: str | None = None) -> list[ReviewItem]: ...

    @abstractmethod
    def _save(self, item: ReviewItem) -> None: ...

    def decide(self, item_id: str, decision: Decision) -> ReviewItem:
        item = self.get(item_id)
        if item is None:
            raise KeyError(item_id)
        if item.status != "open":
            raise AlreadyDecided(f"review item {item_id} was already decided")
        item.decision = decision
        item.status = "decided"
        self._save(item)
        return item

    def open_for_case(self, case_id: str) -> ReviewItem | None:
        for item in self.list(status="open"):
            if item.case_id == case_id:
                return item
        return None

    def count(self, status: str | None = None) -> int:
        return len(self.list(status=status))


class InMemoryReviewQueue(ReviewQueue):
    def __init__(self) -> None:
        self._items: dict[str, ReviewItem] = {}

    def enqueue(self, item: ReviewItem) -> ReviewItem:
        self._items[item.id] = item
        return item

    def get(self, item_id: str) -> ReviewItem | None:
        return self._items.get(item_id)

    def list(self, *, status: str | None = None, agent: str | None = None, owner: str | None = None) -> list[ReviewItem]:
        out = [
            i
            for i in self._items.values()
            if (status is None or i.status == status)
            and (agent is None or i.agent == agent)
            and (owner is None or i.owner == owner)
        ]
        return sorted(out, key=lambda i: i.created_at)

    def _save(self, item: ReviewItem) -> None:
        self._items[item.id] = item


class MongoReviewQueue(ReviewQueue):
    def __init__(self, collection: Any) -> None:
        self._col = collection
        self._col.create_index([("status", 1), ("created_at", 1)])
        self._col.create_index("case_id")

    @staticmethod
    def _doc(item: ReviewItem) -> dict[str, Any]:
        d = item.to_dict()
        d["_id"] = d.pop("id")
        return d

    @staticmethod
    def _item(doc: dict[str, Any] | None) -> ReviewItem | None:
        if not doc:
            return None
        d = dict(doc)
        d["id"] = d.pop("_id")
        return ReviewItem.from_dict(d)

    def enqueue(self, item: ReviewItem) -> ReviewItem:
        self._col.insert_one(self._doc(item))
        return item

    def get(self, item_id: str) -> ReviewItem | None:
        return self._item(self._col.find_one({"_id": item_id}))

    def list(self, *, status: str | None = None, agent: str | None = None, owner: str | None = None) -> list[ReviewItem]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if agent:
            query["agent"] = agent
        if owner:
            query["owner"] = owner
        return [i for i in (self._item(d) for d in self._col.find(query).sort("created_at", 1)) if i]

    def _save(self, item: ReviewItem) -> None:
        self._col.replace_one({"_id": item.id}, self._doc(item), upsert=True)
