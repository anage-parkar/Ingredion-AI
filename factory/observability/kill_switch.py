"""Client-controlled kill switch.

Engaged, the agents stop taking new cases immediately; cases already in progress
complete or return to the rework path; new failed cases follow today's path. Each
use is recorded (listeners feed the audit trail). Backends: in-memory (tests), an
environment variable (read-only, for emergencies without a database) and MongoDB
(shared between replicas). A composite reads all of them and writes to the first
writable one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from .. import settings
from ..case import now_iso


class ReadOnlyKillSwitch(RuntimeError):
    pass


@dataclass
class KillSwitchState:
    engaged: bool
    backend: str
    by: str | None = None
    reason: str | None = None
    at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class KillSwitch(ABC):
    backend = "abstract"

    def __init__(self) -> None:
        self.listeners: list[Callable[[KillSwitchState], None]] = []

    @abstractmethod
    def status(self) -> KillSwitchState: ...

    def is_engaged(self) -> bool:
        return self.status().engaged

    @abstractmethod
    def _write(self, engaged: bool, actor: str, reason: str) -> None: ...

    def engage(self, actor: str, reason: str) -> KillSwitchState:
        self._write(True, actor, reason)
        return self._notify()

    def release(self, actor: str, reason: str = "") -> KillSwitchState:
        self._write(False, actor, reason)
        return self._notify()

    def _notify(self) -> KillSwitchState:
        state = self.status()
        for listener in self.listeners:
            listener(state)
        return state


class InMemoryKillSwitch(KillSwitch):
    backend = "memory"

    def __init__(self, engaged: bool = False) -> None:
        super().__init__()
        self._state = KillSwitchState(engaged=engaged, backend=self.backend)

    def status(self) -> KillSwitchState:
        return KillSwitchState(**self._state.to_dict())

    def _write(self, engaged: bool, actor: str, reason: str) -> None:
        self._state = KillSwitchState(engaged, self.backend, actor, reason, now_iso())


class EnvKillSwitch(KillSwitch):
    """``INGREDION_KILL_SWITCH=on``; cannot be changed through the API by design."""

    backend = "env"

    def status(self) -> KillSwitchState:
        return KillSwitchState(engaged=settings.kill_switch_env(), backend=self.backend)

    def _write(self, engaged: bool, actor: str, reason: str) -> None:
        raise ReadOnlyKillSwitch("the environment kill switch is read-only; change the variable and restart")


class MongoKillSwitch(KillSwitch):
    backend = "mongo"

    def __init__(self, collection: Any, key: str = "factory") -> None:
        super().__init__()
        self._col = collection
        self._key = key

    def status(self) -> KillSwitchState:
        doc = self._col.find_one({"_id": self._key}) or {}
        return KillSwitchState(
            engaged=bool(doc.get("engaged", False)),
            backend=self.backend,
            by=doc.get("by"),
            reason=doc.get("reason"),
            at=doc.get("at"),
        )

    def _write(self, engaged: bool, actor: str, reason: str) -> None:
        self._col.replace_one(
            {"_id": self._key},
            {"_id": self._key, "engaged": engaged, "by": actor, "reason": reason, "at": now_iso()},
            upsert=True,
        )


class CompositeKillSwitch(KillSwitch):
    """Engaged if any backend is engaged; writes go to the first writable backend."""

    backend = "composite"

    def __init__(self, switches: list[KillSwitch]) -> None:
        super().__init__()
        self.switches = switches

    def status(self) -> KillSwitchState:
        states = [s.status() for s in self.switches]
        engaged = [s for s in states if s.engaged]
        if engaged:
            first = engaged[0]
            return KillSwitchState(True, "+".join(s.backend for s in engaged), first.by, first.reason, first.at)
        return KillSwitchState(False, self.backend)

    def _write(self, engaged: bool, actor: str, reason: str) -> None:
        for switch in self.switches:
            try:
                switch._write(engaged, actor, reason)
            except ReadOnlyKillSwitch:
                continue
            switch._notify()  # the backend's own listeners (audit) see the change too
            return
        raise ReadOnlyKillSwitch("no writable kill switch backend configured")
