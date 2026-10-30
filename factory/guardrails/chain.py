from __future__ import annotations

from collections.abc import Iterable

from .base import Guard, GuardBlocked, GuardResult


class GuardChain:
    """Runs every guard; the text is allowed only if all of them allow it."""

    name = "chain"

    def __init__(self, guards: Iterable[Guard]) -> None:
        self.guards = list(guards)

    def screen(self, text: str, *, purpose: str = "") -> GuardResult:
        reasons: list[str] = []
        blocked_by: list[str] = []
        for guard in self.guards:
            result = guard.screen(text, purpose=purpose)
            if not result.allowed:
                blocked_by.append(result.guard)
                reasons.extend(f"{result.guard}: {r}" for r in result.reasons)
        name = "+".join(blocked_by) if blocked_by else self.name
        return GuardResult(not blocked_by, name, reasons)

    def require(self, text: str, *, purpose: str = "") -> GuardResult:
        """Screen and raise :class:`GuardBlocked` if the text must not reach a model."""
        result = self.screen(text, purpose=purpose)
        if not result.allowed:
            raise GuardBlocked(result, purpose)
        return result

    def require_all(self, texts: Iterable[str], *, purpose: str = "") -> list[GuardResult]:
        return [self.require(t, purpose=purpose) for t in texts if t]
