"""The unit of work both agents move through their steps.

A :class:`Case` is deliberately plain: a dict of step outputs, a list of flags, the
reason codes collected so far and the transition history the state machine writes.
Steps return a :class:`StepResult` that tells the pipeline what to do next; they
never call each other.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Disposition(StrEnum):
    CONTINUE = "continue"  # next step
    RETRY = "retry"  # re-run the previous model step once (A3 re-read)
    REVIEW = "review"  # park at the human gate
    EXIT = "exit"  # leave to the existing rework path with reason codes
    DONE = "done"  # terminal success


@dataclass
class Flag:
    """Something a reviewer must see. ``code`` is a reason code from the catalogue."""

    code: str
    message: str
    field: str | None = None
    evidence: dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StepResult:
    disposition: Disposition
    codes: list[str] = dc_field(default_factory=list)
    note: str = ""

    @classmethod
    def ok(cls, note: str = "") -> StepResult:
        return cls(Disposition.CONTINUE, note=note)

    @classmethod
    def exit(cls, *codes: str, note: str = "") -> StepResult:
        return cls(Disposition.EXIT, list(codes), note)

    @classmethod
    def review(cls, *codes: str, note: str = "") -> StepResult:
        return cls(Disposition.REVIEW, list(codes), note)

    @classmethod
    def retry(cls, *codes: str, note: str = "") -> StepResult:
        return cls(Disposition.RETRY, list(codes), note)

    @classmethod
    def done(cls, note: str = "") -> StepResult:
        return cls(Disposition.DONE, note=note)


@dataclass
class Case:
    case_id: str
    agent: str
    state: str = "new"
    idempotency_key: str | None = None
    data: dict[str, Any] = dc_field(default_factory=dict)
    flags: list[Flag] = dc_field(default_factory=list)
    reason_codes: list[str] = dc_field(default_factory=list)
    outcome: str | None = None
    history: list[dict[str, Any]] = dc_field(default_factory=list)
    run_id: str = dc_field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = dc_field(default_factory=now_iso)
    updated_at: str = dc_field(default_factory=now_iso)

    # ── convenience ──────────────────────────────────────────────────────────
    def add_flag(self, code: str, message: str, field_name: str | None = None, **evidence: Any) -> Flag:
        flag = Flag(code=code, message=message, field=field_name, evidence=dict(evidence))
        self.flags.append(flag)
        if code not in self.reason_codes:
            self.reason_codes.append(code)
        self.updated_at = now_iso()
        return flag

    def add_codes(self, *codes: str) -> None:
        for code in codes:
            if code and code not in self.reason_codes:
                self.reason_codes.append(code)
        self.updated_at = now_iso()

    def has_flag(self, code: str) -> bool:
        return any(f.code == code for f in self.flags)

    def flags_with_prefix(self, prefix: str) -> list[Flag]:
        return [f for f in self.flags if f.code.startswith(prefix)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "agent": self.agent,
            "state": self.state,
            "idempotency_key": self.idempotency_key,
            "flags": [f.to_dict() for f in self.flags],
            "reason_codes": list(self.reason_codes),
            "outcome": self.outcome,
            "history": list(self.history),
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "data_keys": sorted(self.data.keys()),
        }
