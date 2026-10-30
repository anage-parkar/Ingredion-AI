"""Rows for ``agent_b_outcomes.prebill_outcome``: one per order and version (a recheck
is a new version), what the SOW 3.4 scorecard reads: checks run, verdicts, gap
amounts, owner, reviewer agreement, missing data, traceability, timings."""

from __future__ import annotations

from typing import Any

from factory.case import Case, now_iso
from factory.platform import base_row, json_text
from factory.platform.gold import parse_ts

from . import AGENT


def _ms_between(start: str | None, end: str | None) -> int | None:
    a, b = parse_ts(start), parse_ts(end)
    return int((b - a).total_seconds() * 1000) if a and b else None


def prebill_outcome_row(case: Case, ctx: Any) -> dict[str, Any]:
    ref = case.data["invoice_ref"]
    results = case.data.get("results") or []
    failed = [r for r in results if not r.passed]
    decision = case.data.get("decision")
    reference = case.data.get("reference")
    order = case.data.get("order") or {}
    model_calls = ctx.audit.model_calls(case.case_id)
    tokens = sum(int(((r.model_call or {}).get("tokens") or {}).get("total", 0) or 0) for r in model_calls)
    refresh = ctx.gold_refresh()
    row = base_row(case, AGENT)
    row.update(
        {
            "version": int(case.data.get("recheck_count", 0) or 0),
            "order_ref": ref.order_ref,
            "invoice_ref": ref.invoice_ref,
            "sold_to": ref.sold_to,
            "customer": ref.customer_name,
            "billing_date": ref.billing_date,
            "po_ref": order.get("po_ref") or ref.po_ref,
            "po_source": case.data.get("po_source"),
            "checks": list(ctx.policy.checks),
            "failed_checks": [r.rule for r in failed],
            "verdicts": json_text({r.rule: str(r.verdict) for r in failed}) if failed else None,
            "gaps": json_text({r.rule: r.evidence for r in failed}) if failed else None,
            "issue_owners": json_text(case.data.get("owners") or {}) if case.data.get("owners") else None,
            "reviewer": decision.reviewer if decision is not None else None,
            "decision_kind": str(decision.kind) if decision is not None else None,
            "decision_reason": decision.reason if decision is not None else None,
            "missing": list(reference.missing) if reference is not None else [],
            "traceable": all(bool(r.evidence) for r in failed) if failed else True,
            "model_calls": len(model_calls),
            "tokens_total": tokens,
            "evidence_uris": list(case.data.get("evidence_uris", [])),
            "gold_refresh": json_text(refresh) if refresh else None,
            "time_to_decision_ms": _ms_between(case.created_at, decision.decided_at) if decision is not None else None,
            "duration_ms": _ms_between(case.created_at, now_iso()),
        }
    )
    return row


__all__ = ["prebill_outcome_row"]
