"""Rows for ``agent_a_outcomes``: ``case_outcome`` (one per finished case, what the SOW
2.7 scorecard and the dashboards read) and ``field_corrections`` (one per field a
reviewer corrected, the signal for prompt and rule tuning)."""

from __future__ import annotations

from typing import Any

from factory.case import Case, now_iso
from factory.platform import base_row, json_text
from factory.platform.gold import parse_ts
from factory.review import DecisionKind

from . import AGENT


def _ms_between(start: str | None, end: str | None) -> int | None:
    a, b = parse_ts(start), parse_ts(end)
    return int((b - a).total_seconds() * 1000) if a and b else None


def case_outcome_row(case: Case, ctx: Any) -> dict[str, Any]:
    intake = case.data.get("intake")
    cls = case.data.get("classification")
    ex = case.data.get("extraction")
    val = case.data.get("validation")
    score = case.data.get("score")
    order = case.data.get("order") or {}
    decision = case.data.get("decision")
    submission = case.data.get("submission") or {}
    model_calls = ctx.audit.model_calls(case.case_id)
    tokens = sum(int(((r.model_call or {}).get("tokens") or {}).get("total", 0) or 0) for r in model_calls)
    refresh = ctx.gold_refresh()
    row = base_row(case, AGENT)
    row.update(
        {
            "source": getattr(intake, "source", None),
            "cohort": getattr(intake, "cohort", None),
            "customer": getattr(intake, "customer", None),
            "mode": ctx.policy.mode,
            "intent": str(cls.intent) if cls is not None else None,
            "po_number": getattr(ex, "po_number", None),
            "sold_to": val.sold_to.id if val is not None and val.sold_to else None,
            "ship_to": val.ship_to.id if val is not None and val.ship_to else None,
            "lines": len(ex.lines) if ex is not None else 0,
            "order_number": order.get("order_number"),
            "reconciled": bool(order.get("reconciled", False)),
            "sap_attempts": int(submission.get("attempts", 0) or 0),
            "reviewer": decision.reviewer if decision is not None else None,
            "decision_kind": str(decision.kind) if decision is not None else None,
            "confirmed_duplicate": bool(decision.confirmed_duplicate) if decision is not None else False,
            "corrections": json_text(decision.corrections) if decision is not None and decision.corrections else None,
            "confidence": json_text(score.confidence) if score is not None else None,
            "low_confidence_fields": list(score.low_confidence_fields) if score is not None else [],
            "duplicates_found": len(score.duplicates) if score is not None else 0,
            "model_calls": len(model_calls),
            "tokens_total": tokens,
            "evidence_uris": list(case.data.get("evidence_uris", [])),
            "gold_refresh": json_text(refresh) if refresh else None,
            "duration_ms": _ms_between(case.created_at, now_iso()),
        }
    )
    return row


def field_correction_rows(case: Case) -> list[dict[str, Any]]:
    decision = case.data.get("decision")
    if decision is None or decision.kind != DecisionKind.CORRECT or not decision.corrections:
        return []
    recorded = now_iso()
    return [
        {
            "case_id": case.case_id,
            "run_id": case.run_id,
            "field": name,
            "corrected_value": json_text(value),
            "reviewer": decision.reviewer,
            "decided_at": decision.decided_at,
            "recorded_at": recorded,
        }
        for name, value in decision.corrections.items()
    ]


__all__ = ["case_outcome_row", "field_correction_rows"]
