"""A9 · Create the order in SAP (the SAP write), then read the incompletion log.

Exactly-once protection, in order:

1. the pipeline has already moved the case to ``submitting`` (write-ahead) and
   recorded the idempotency key (case ID + PO number);
2. before the first attempt, and after every timeout, SAP is asked whether an order
   with that reference already exists; if so the case is reconciled, never resubmitted;
3. retries follow the policy (up to 3, increasing waits); after that the case exits
   to the manual queue with ``SAP.UNAVAILABLE`` and an alert is raised;
4. a rejection by SAP exits with the SAP message attached.

After creation the SAP incompletion log is read; its entries become follow-ups on
the Salesforce case at A10 and a flag on the audit record.
"""

from __future__ import annotations

from factory.case import Case, StepResult

from ..connectors import SAPTimeout, SAPUnavailable
from ..context import OrderIntakeContext

STEP = "A9"


def _read_incompletion(case: Case, ctx: OrderIntakeContext, order_number: str) -> None:
    if not ctx.policy.read_incompletion_log:
        return
    try:
        items = ctx.sap_order_api.incompletion_log(order_number)
    except Exception as exc:  # the order exists; the log is advisory
        ctx.log(case, STEP, "sap.incompletion_log_failed", order_number=order_number, error=str(exc))
        return
    case.data["incompletion"] = items
    if items:
        case.add_flag("SAP.INCOMPLETE", f"SAP incompletion log lists {len(items)} item(s) on {order_number}", items=[i.model_dump() for i in items])
    ctx.log(case, STEP, "sap.incompletion_log", order_number=order_number, items=[i.model_dump() for i in items])


def _done(case: Case, ctx: OrderIntakeContext, order_number: str, *, reconciled: bool, attempts: int, when: str = "") -> StepResult:
    case.data["order"] = {"order_number": order_number, "reconciled": reconciled, "attempts": attempts}
    ctx.keep(case, STEP, "sap_order.json", {**case.data["order"], "idempotency_key": case.idempotency_key, "when": when})
    if reconciled:
        case.add_codes("SAP.RECONCILED")
        ctx.log(case, STEP, "sap.reconciled", order_number=order_number, when=when)
    else:
        ctx.log(case, STEP, "sap.order_created", order_number=order_number, attempts=attempts)
    _read_incompletion(case, ctx, order_number)
    return StepResult.ok()


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    payload = case.data["payload"]
    sub = case.data.setdefault("submission", {"idempotency_key": payload.idempotency_key, "attempts": 0})

    existing = ctx.sap_orders.find_by_reference(payload.idempotency_key, payload.po_number, payload.sold_to)
    if existing:
        return _done(case, ctx, existing, reconciled=True, attempts=sub["attempts"], when="before the first attempt")

    max_attempts = 1 + ctx.policy.max_sap_retries
    backoff = ctx.policy.retry_backoff_seconds
    while True:
        sub["attempts"] += 1
        try:
            result = ctx.sap_order_api.create_order(payload)
        except (SAPTimeout, SAPUnavailable) as exc:
            ctx.log(case, STEP, "sap.call_failed", attempt=sub["attempts"], error=f"{type(exc).__name__}: {exc}")
            existing = ctx.sap_orders.find_by_reference(payload.idempotency_key, payload.po_number, payload.sold_to)
            if existing:
                return _done(case, ctx, existing, reconciled=True, attempts=sub["attempts"], when=f"after {type(exc).__name__} on attempt {sub['attempts']}")
            if sub["attempts"] >= max_attempts:
                ctx.alert("sap_unavailable", f"SAP did not answer after {sub['attempts']} attempts for case {case.case_id}", case_id=case.case_id, idempotency_key=payload.idempotency_key)
                ctx.log(case, STEP, "sap.unavailable", attempts=sub["attempts"])
                return StepResult.exit("SAP.UNAVAILABLE", note=f"{type(exc).__name__}: {exc}")
            wait = backoff[min(sub["attempts"] - 1, len(backoff) - 1)] if backoff else 0.0
            ctx.sleep(wait)
            continue

        if result.created and result.order_number:
            return _done(case, ctx, result.order_number, reconciled=False, attempts=sub["attempts"])
        ctx.log(case, STEP, "sap.rejected", error=result.error, attempts=sub["attempts"])
        return StepResult.exit("SAP.REJECTED", note=result.error or "rejected by SAP")
