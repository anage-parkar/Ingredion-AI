from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from ..case import now_iso


class DecisionKind(StrEnum):
    APPROVE = "approve"
    CORRECT = "correct"
    REJECT = "reject"


@dataclass
class Decision:
    kind: DecisionKind
    reviewer: str
    reason: str = ""
    corrections: dict[str, Any] = field(default_factory=dict)  # field -> corrected value
    confirmed_duplicate: bool = False
    decided_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = str(self.kind)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Decision:
        return cls(
            kind=DecisionKind(d["kind"]),
            reviewer=d["reviewer"],
            reason=d.get("reason", ""),
            corrections=dict(d.get("corrections") or {}),
            confirmed_duplicate=bool(d.get("confirmed_duplicate", False)),
            decided_at=d.get("decided_at") or now_iso(),
        )


@dataclass
class ReviewField:
    """One value the reviewer sees: the agent's reading, its confidence, candidates."""

    name: str
    value: Any
    confidence: float | None = None
    flagged: bool = False
    candidates: list[Any] = field(default_factory=list)
    note: str = ""


@dataclass
class ReviewItem:
    case_id: str
    agent: str
    summary: str
    fields: list[ReviewField] = field(default_factory=list)
    flags: list[dict[str, Any]] = field(default_factory=list)  # Flag.to_dict()
    drafts: dict[str, str] = field(default_factory=dict)  # e.g. clarification_email, po_update_request
    owner: str | None = None  # proposed owner / team (pre-bill RACI)
    source_ref: str | None = None  # PO number or order reference, for the reviewer's search
    status: str = "open"
    decision: Decision | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "agent": self.agent,
            "summary": self.summary,
            "fields": [asdict(f) for f in self.fields],
            "flags": list(self.flags),
            "drafts": dict(self.drafts),
            "owner": self.owner,
            "source_ref": self.source_ref,
            "status": self.status,
            "decision": self.decision.to_dict() if self.decision else None,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReviewItem:
        return cls(
            id=d["id"],
            case_id=d["case_id"],
            agent=d["agent"],
            summary=d.get("summary", ""),
            fields=[ReviewField(**f) for f in d.get("fields", [])],
            flags=list(d.get("flags", [])),
            drafts=dict(d.get("drafts", {})),
            owner=d.get("owner"),
            source_ref=d.get("source_ref"),
            status=d.get("status", "open"),
            decision=Decision.from_dict(d["decision"]) if d.get("decision") else None,
            created_at=d.get("created_at") or now_iso(),
        )
