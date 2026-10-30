from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GuardResult:
    allowed: bool
    guard: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "guard": self.guard, "reasons": list(self.reasons)}


class GuardBlocked(RuntimeError):
    """Raised by :meth:`GuardChain.require` when text must not reach a model."""

    def __init__(self, result: GuardResult, purpose: str = "") -> None:
        super().__init__(f"blocked by {result.guard} for {purpose or 'model call'}: {', '.join(result.reasons)}")
        self.result = result
        self.purpose = purpose


class Guard(Protocol):
    name: str

    def screen(self, text: str, *, purpose: str = "") -> GuardResult: ...
