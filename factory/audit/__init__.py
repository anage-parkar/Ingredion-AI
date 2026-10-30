"""Append-only audit trail: one record per event, never updated, never deleted."""

from .trail import AuditRecord, AuditTrail, InMemoryAuditTrail, MongoAuditTrail, Outcome

__all__ = ["AuditRecord", "AuditTrail", "InMemoryAuditTrail", "MongoAuditTrail", "Outcome"]
