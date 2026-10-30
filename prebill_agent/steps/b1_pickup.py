"""B1 · Pick up a shipped order whose draft invoice is ready to send (SAP billing due list)."""

from __future__ import annotations

from factory.case import Case, StepResult

from ..context import PrebillContext

STEP = "B1"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    ref = case.data["invoice_ref"]
    ctx.log(case, STEP, "invoice.picked_up", invoice_ref=ref.invoice_ref, sold_to=ref.sold_to, customer=ref.customer_name, billing_date=ref.billing_date, po_ref=ref.po_ref)
    return StepResult.ok()
