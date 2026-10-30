"""Per-case state machines.

The state is the idempotency record: a crash between two steps leaves a case in a
named state, and the pipeline knows exactly what to reconcile when it restarts
(for example, any Order Intake case in ``submitting`` is looked up in SAP before
anything else runs). Transitions outside the table raise, they are never silently
accepted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..case import Case, now_iso


class IllegalTransition(RuntimeError):
    pass


@dataclass(frozen=True)
class StateMachine:
    name: str
    initial: str
    transitions: Mapping[str, frozenset[str]]
    terminal: frozenset[str]

    @property
    def states(self) -> frozenset[str]:
        found = set(self.transitions) | set(self.terminal) | {self.initial}
        for targets in self.transitions.values():
            found |= set(targets)
        return frozenset(found)

    def can(self, src: str, dst: str) -> bool:
        return dst in self.transitions.get(src, frozenset())

    def is_terminal(self, state: str) -> bool:
        return state in self.terminal

    def start(self, case: Case, reason: str = "") -> None:
        case.history.append({"from": case.state, "to": self.initial, "at": now_iso(), "reason": reason})
        case.state = self.initial
        case.updated_at = now_iso()

    def move(self, case: Case, dst: str, reason: str = "") -> None:
        if not self.can(case.state, dst):
            raise IllegalTransition(f"{self.name}: {case.state!r} -> {dst!r} is not allowed")
        case.history.append({"from": case.state, "to": dst, "at": now_iso(), "reason": reason})
        case.state = dst
        case.updated_at = now_iso()


class OI:
    """Order Intake states (A1 to A10 plus the gate)."""

    PICKED_UP = "picked_up"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    SCORED = "scored"
    EXCEPTIONS = "exceptions"  # A6: clarification drafted (or nothing to draft)
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PAYLOAD_BUILT = "payload_built"
    SUBMITTING = "submitting"  # write-ahead: recorded before the SAP call
    CREATED = "created"
    CASE_UPDATED = "case_updated"
    RETURNED = "returned"  # left to the existing rework path
    DUPLICATE_CLOSED = "duplicate_closed"


ORDER_INTAKE = StateMachine(
    name="order_intake",
    initial=OI.PICKED_UP,
    transitions={
        # Any step before the gate may exit (rework path) or park the case for a
        # reviewer (guardrail block, unusable model answer, ambiguous master data).
        OI.PICKED_UP: frozenset({OI.CLASSIFIED, OI.IN_REVIEW, OI.RETURNED}),
        OI.CLASSIFIED: frozenset({OI.EXTRACTED, OI.IN_REVIEW, OI.RETURNED}),
        OI.EXTRACTED: frozenset({OI.EXTRACTED, OI.VALIDATED, OI.IN_REVIEW, OI.RETURNED}),  # re-read once
        OI.VALIDATED: frozenset({OI.SCORED, OI.IN_REVIEW, OI.RETURNED}),
        OI.SCORED: frozenset({OI.EXCEPTIONS, OI.IN_REVIEW, OI.PAYLOAD_BUILT, OI.RETURNED}),
        OI.EXCEPTIONS: frozenset({OI.IN_REVIEW, OI.PAYLOAD_BUILT, OI.RETURNED}),  # A7 summary then the gate
        OI.IN_REVIEW: frozenset({OI.APPROVED, OI.RETURNED, OI.DUPLICATE_CLOSED}),
        OI.APPROVED: frozenset({OI.PAYLOAD_BUILT, OI.IN_REVIEW, OI.RETURNED}),  # re-check may re-flag or exit
        OI.PAYLOAD_BUILT: frozenset({OI.SUBMITTING}),
        OI.SUBMITTING: frozenset({OI.SUBMITTING, OI.CREATED, OI.RETURNED}),
        OI.CREATED: frozenset({OI.CASE_UPDATED}),
    },
    terminal=frozenset({OI.CASE_UPDATED, OI.RETURNED, OI.DUPLICATE_CLOSED}),
)


class PB:
    """Pre-bill states (B1 to B8 plus the recheck loop)."""

    PICKED_UP = "picked_up"
    EVIDENCE_ASSEMBLED = "evidence_assembled"
    PO_READ = "po_read"
    NORMALISED = "normalised"
    COMPARED = "compared"
    EXPLAINED = "explained"
    IN_REVIEW = "in_review"
    DECIDED = "decided"
    RECORDED = "recorded"
    CLOSED = "closed"


PREBILL = StateMachine(
    name="prebill",
    initial=PB.PICKED_UP,
    transitions={
        PB.PICKED_UP: frozenset({PB.EVIDENCE_ASSEMBLED}),
        PB.EVIDENCE_ASSEMBLED: frozenset({PB.PO_READ}),
        PB.PO_READ: frozenset({PB.NORMALISED}),
        PB.NORMALISED: frozenset({PB.COMPARED}),
        PB.COMPARED: frozenset({PB.RECORDED, PB.EXPLAINED}),  # matched goes straight to B8
        PB.EXPLAINED: frozenset({PB.IN_REVIEW}),
        PB.IN_REVIEW: frozenset({PB.DECIDED}),
        PB.DECIDED: frozenset({PB.RECORDED}),
        PB.RECORDED: frozenset({PB.EVIDENCE_ASSEMBLED, PB.CLOSED}),  # recheck or close
    },
    terminal=frozenset({PB.CLOSED}),
)
