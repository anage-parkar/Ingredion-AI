"""Scheduled pick-up from a client queue (the RPA failure record, the SAP billing
due list), with the last processed marker tracked and the kill switch honoured.

The source is read-only for the agent: the poller never edits or deletes the
client's records. It remembers where it got to and claims each case before
dispatching it, so a restart or a second replica cannot process a case twice.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .claims import ClaimRegistry

logger = logging.getLogger("factory.intake")


@dataclass
class RawCase:
    source_ref: str  # the client's id for the case (Salesforce case id, SAP order ref)
    marker: Any  # monotonic position in the source (record id, timestamp)
    payload: dict[str, Any] = field(default_factory=dict)


class IntakeSource(Protocol):
    name: str

    def fetch(self, after: Any) -> list[RawCase]:
        """Return cases with a marker greater than ``after``, in marker order."""
        ...


class _KillSwitchLike(Protocol):
    def is_engaged(self) -> bool: ...


@dataclass
class PollReport:
    fetched: int = 0
    dispatched: int = 0
    skipped: int = 0  # already claimed by someone else
    failed: int = 0  # handler raised; claim released so the case is retried
    halted: bool = False  # kill switch engaged, nothing fetched
    last_marker: Any = None
    errors: list[str] = field(default_factory=list)


class Poller:
    def __init__(
        self,
        source: IntakeSource,
        claims: ClaimRegistry,
        on_case: Callable[[RawCase], None],
        *,
        kill_switch: _KillSwitchLike | None = None,
        marker: Any = None,
        owner: str = "agent",
    ) -> None:
        self.source = source
        self.claims = claims
        self.on_case = on_case
        self.kill_switch = kill_switch
        self.marker = marker
        self.owner = owner

    def poll_once(self) -> PollReport:
        report = PollReport(last_marker=self.marker)
        if self.kill_switch is not None and self.kill_switch.is_engaged():
            report.halted = True
            logger.warning("kill switch engaged: %s poll skipped", self.source.name)
            return report

        for raw in self.source.fetch(self.marker):
            report.fetched += 1
            if not self.claims.claim(raw.source_ref, self.owner):
                report.skipped += 1
            else:
                try:
                    self.on_case(raw)
                    report.dispatched += 1
                except Exception as exc:  # the handler is client code; keep polling
                    self.claims.release(raw.source_ref)
                    report.failed += 1
                    report.errors.append(f"{raw.source_ref}: {exc}")
                    logger.exception("case %s failed in handler", raw.source_ref)
            self.marker = raw.marker
            report.last_marker = raw.marker
        return report
