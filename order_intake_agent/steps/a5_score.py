"""A5 · Rules and confidence.

* A **composite confidence** per key field from evidence (model self-report, layout
  agreement weighted by the Document AI confidence, arithmetic consistency,
  master-data match), never the model's number alone.
* The **duplicate-order check** against SAP on sold-to, ship-to, PO number,
  material, date and quantity.
* **Price, contract and availability (ATP)** checks: flags with both values, the
  difference and the source. The agent never changes anything in SAP; A6 drafts the
  clarification for the flags that need the customer.

Under Phase 1 every case goes on to the reviewer. In a re-check after corrections,
only a *new* flag sends the case back to the queue.
"""

from __future__ import annotations

from typing import Any

from factory.case import Case, StepResult
from factory.rules import FieldEvidence, Routing, layout_agreement, routing

from ..context import OrderIntakeContext
from ..models import PriceCheck, Score

STEP = "A5"
KEY_FIELDS = ("po_number", "sold_to", "ship_to", "bill_to", "requested_delivery_date", "currency")
A5_FLAG_CODES = {"EXTRACT.LOW_CONFIDENCE", "DUP.POSSIBLE", "PRICE.PO_VS_SAP", "CONTRACT.NONE", "CONTRACT.OUTSIDE_TERMS", "ATP.SHORT"}
_MASS_PRICE_FACTORS = {
    ("CWT", "LB"): 0.01,
    ("LB", "CWT"): 100.0,
    ("KG", "LB"): 1 / 2.20462,
    ("LB", "KG"): 2.20462,
    ("MT", "KG"): 0.001,
    ("KG", "MT"): 1000.0,
}


def _layout(value: Any, text: str, di_conf: float | None) -> float:
    agreement = layout_agreement(value, text)
    return agreement * di_conf if (di_conf is not None and agreement) else agreement


def price_in_uom(unit_price: float, price_uom: str | None, line_uom: str, conversion_factor: float | None, converted_uom: str | None, target_uom: str) -> float | None:
    """Express a PO unit price per ``target_uom`` (SAP's price unit), or None if unknown."""
    source_uom = (price_uom or line_uom or "").upper()
    target = target_uom.upper()
    if source_uom == target:
        return unit_price
    if conversion_factor and converted_uom and converted_uom.upper() == target and source_uom == line_uom.upper():
        return unit_price / conversion_factor
    factor = _MASS_PRICE_FACTORS.get((source_uom, target))
    return unit_price * factor if factor else None


def run(case: Case, ctx: OrderIntakeContext, *, recheck: bool = False) -> StepResult:
    ex = case.data["extraction"]
    val = case.data["validation"]
    source = case.data["source_text"]
    text, di_conf = source["all"], source.get("mean_confidence")
    policy = ctx.policy
    if recheck:
        case.flags = [f for f in case.flags if f.code not in A5_FLAG_CODES]

    # ── composite confidence ─────────────────────────────────────────────────
    evidences: list[FieldEvidence] = []
    for name in KEY_FIELDS:
        value = getattr(ex, name)
        if value is None and name in ("bill_to", "currency"):
            continue
        master = (getattr(val, name) is not None) if name in ("sold_to", "ship_to", "bill_to") else None
        evidences.append(FieldEvidence(name, model=ex.confidence.get(name), layout=_layout(value, text, di_conf), master_data=master))
    line_conf = ex.confidence.get("lines")
    for vl in val.lines:
        n = vl.line_no
        evidences.append(FieldEvidence(f"line{n}.customer_material", model=line_conf, layout=_layout(vl.customer_material, text, di_conf), master_data=vl.sap_material is not None))
        evidences.append(FieldEvidence(f"line{n}.quantity", model=line_conf, layout=_layout(vl.quantity, text, di_conf), arithmetic=vl.arithmetic_ok))
        evidences.append(FieldEvidence(f"line{n}.uom", model=line_conf, layout=_layout(vl.uom, text, di_conf)))
        if vl.unit_price is not None:
            evidences.append(FieldEvidence(f"line{n}.unit_price", model=line_conf, layout=_layout(vl.unit_price, text, di_conf), arithmetic=vl.arithmetic_ok))
    scores = ctx.confidence.score_fields(evidences)
    low = ctx.confidence.low(scores)
    if low:
        case.add_flag("EXTRACT.LOW_CONFIDENCE", f"{len(low)} field(s) below the {ctx.confidence.threshold:.0%} confidence threshold", fields=low, scores={f: scores[f] for f in low})

    # ── duplicate-order check ────────────────────────────────────────────────
    duplicates = []
    if val.sold_to:
        duplicates = ctx.sap_orders.find_duplicates(
            sold_to=val.sold_to.id,
            ship_to=val.ship_to.id if val.ship_to else None,
            po_number=ex.po_number,
            materials=[vl.sap_material for vl in val.lines if vl.sap_material],
            date=ex.requested_delivery_date,
            quantities=[vl.converted_quantity if vl.converted_quantity is not None else vl.quantity for vl in val.lines],
            window_days=policy.duplicate_window_days,
        )
    if duplicates:
        case.add_flag("DUP.POSSIBLE", f"{len(duplicates)} SAP order(s) share the key fields: " + ", ".join(d.sap_order for d in duplicates), candidates=[d.model_dump() for d in duplicates])

    # ── price, contract, availability: checks only ───────────────────────────
    price_checks: list[PriceCheck] = []
    if val.sold_to:
        for vl in val.lines:
            if not vl.sap_material:
                continue
            n = vl.line_no
            ref = ctx.sap_orders.price(val.sold_to.id, vl.sap_material, ex.requested_delivery_date)
            if ref and vl.unit_price is not None:
                sap_price, sap_uom, source_name = ref
                po_price = price_in_uom(vl.unit_price, vl.price_uom, vl.uom, vl.conversion_factor, vl.converted_uom, sap_uom)
                if po_price is not None:
                    check = PriceCheck(
                        line_no=n, sap_material=vl.sap_material, po_price=vl.unit_price, po_price_uom=vl.price_uom or vl.uom,
                        po_price_in_sap_uom=round(po_price, 4), sap_price=sap_price, sap_price_uom=sap_uom,
                        difference=round(po_price - sap_price, 4), source=source_name,
                    )
                    price_checks.append(check)
                    if abs(check.difference) > policy.price_tolerance:
                        case.add_flag("PRICE.PO_VS_SAP", f"line {n}: PO {check.po_price_in_sap_uom}/{sap_uom} vs SAP {sap_price}/{sap_uom} ({source_name})", f"line{n}.unit_price", **check.model_dump())
            contract = ctx.sap_orders.contract(val.sold_to.id, vl.sap_material, ex.requested_delivery_date)
            qty = vl.converted_quantity if vl.converted_quantity is not None else vl.quantity
            if contract is None:
                case.add_flag("CONTRACT.NONE", f"line {n}: no valid contract for {vl.sap_material}", f"line{n}")
            else:
                valid_to = contract.get("valid_to")
                remaining = contract.get("remaining_quantity")
                if (valid_to and ex.requested_delivery_date and ex.requested_delivery_date > valid_to) or (remaining is not None and qty > remaining):
                    case.add_flag("CONTRACT.OUTSIDE_TERMS", f"line {n}: PO outside contract {contract.get('number', '')} terms", f"line{n}", valid_to=valid_to, remaining_quantity=remaining, requested=qty)
            atp = ctx.sap_orders.availability(vl.sap_material, qty, vl.converted_uom or vl.uom, ex.requested_delivery_date)
            if atp and atp.get("available") is not None and atp["available"] < qty:
                case.add_flag("ATP.SHORT", f"line {n}: {atp['available']} available of {qty} requested", f"line{n}.quantity", **atp)

    review_codes = [f.code for f in case.flags if routing(f.code) == Routing.REVIEW]
    if recheck:
        already = set(case.data.get("reviewed_codes", []))
        review_required = any(c not in already for c in review_codes)
    else:
        review_required = policy.review_every_case or bool(review_codes)

    case.data["score"] = Score(confidence=scores, low_confidence_fields=low, duplicates=duplicates, price_checks=price_checks, review_required=review_required)
    ctx.log(
        case, STEP, "rechecked" if recheck else "scored",
        confidence=scores, low_confidence=low, duplicates=len(duplicates),
        price_checks=[p.model_dump() for p in price_checks], flags=[f.code for f in case.flags], review_required=review_required,
    )
    if recheck and review_required:
        return StepResult.review(*review_codes)
    return StepResult.ok()
