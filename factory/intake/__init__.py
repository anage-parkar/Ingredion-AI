"""Case intake: pollers over the client's queues, the one-case-once claim registry
and the per-case state machines that make every transition explicit and auditable."""

from .claims import ClaimRegistry, InMemoryClaimRegistry, MongoClaimRegistry, idempotency_key
from .poller import IntakeSource, Poller, PollReport, RawCase
from .state_machine import OI, ORDER_INTAKE, PB, PREBILL, IllegalTransition, StateMachine

__all__ = [
    "OI",
    "ORDER_INTAKE",
    "PB",
    "PREBILL",
    "ClaimRegistry",
    "IllegalTransition",
    "InMemoryClaimRegistry",
    "IntakeSource",
    "MongoClaimRegistry",
    "PollReport",
    "Poller",
    "RawCase",
    "StateMachine",
    "idempotency_key",
]
