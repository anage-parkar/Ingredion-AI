"""A8 · Build the SAP payload: ordinary code, from validated and reviewer-corrected
data. Anything still unresolved (an ambiguous partner, a material without a chosen
CMIR record, an unconverted unit) goes back to the reviewer; nothing is guessed."""

from __future__ import annotations

from factory.case import Case, StepResult
from factory.intake import idempotency_key

from ..context import OrderIntakeContext
from ..models import SAPItem, SAPPayload

STEP = "A8"


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    ex = case.data["extraction"]
    val = case.data["validation"]
    if not val.sold_to or not val.ship_to:
        return StepResult.review("MASTER.PARTNER_AMBIGUOUS", note="reviewer must choose the sold-to / ship-to")
    items: list[SAPItem] = []
    for vl in val.lines:
        if not vl.sap_material:
            return StepResult.review("CMIR.MULTIPLE_MATCHES", note=f"line {vl.line_no}: reviewer must choose the SAP material")
        if vl.converted_quantity is None or not vl.converted_uom:
            return StepResult.review("UOM.NO_CONVERSION", note=f"line {vl.line_no}: unit of measure not resolved")
        items.append(SAPItem(line_no=vl.line_no, material=vl.sap_material, quantity=vl.converted_quantity, uom=vl.converted_uom, customer_material=vl.customer_material, unit_price=vl.unit_price, price_uom=vl.price_uom))
    key = idempotency_key(case.case_id, ex.po_number)
    case.idempotency_key = key
    payload = SAPPayload(
        sold_to=val.sold_to.id, ship_to=val.ship_to.id, bill_to=val.bill_to.id if val.bill_to else None,
        po_number=ex.po_number or "", requested_delivery_date=ex.requested_delivery_date, currency=ex.currency,
        items=items, idempotency_key=key, source_case_id=case.case_id,
    )
    case.data["payload"] = payload
    ctx.keep(case, STEP, "sap_payload.json", payload)
    ctx.log(case, STEP, "payload.built", idempotency_key=key, items=len(items), sold_to=payload.sold_to, ship_to=payload.ship_to)
    return StepResult.ok()
