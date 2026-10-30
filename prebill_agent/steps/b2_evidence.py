"""B2 · Assemble the evidence: draft invoice and shipment from SAP, the sales order
from Salesforce, the contract or condition price per line (PROS first, then the
SAP condition), the contract payment terms, freight and surcharge terms from the
rate files, and the dispute history. Anything missing is named, never papered over."""

from __future__ import annotations

from factory.case import Case, StepResult

from ..context import PrebillContext
from ..schema import ReferenceData

STEP = "B2"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    ref = case.data["invoice_ref"]
    invoice = ctx.sap.draft_invoice(ref)
    order = ctx.salesforce.order(ref.order_ref) or {}
    reference = ReferenceData(shipment=ctx.sap.shipment(ref) or {}, dispute_history=ctx.termsync.dispute_history(ref.sold_to))

    for line in invoice.lines:
        price = ctx.pros.contract_price(ref.sold_to, line.material, ref.billing_date) or ctx.sap.price_condition(ref.sold_to, line.material, ref.billing_date)
        if price is None:
            reference.missing.append(f"price:line{line.line_no}")
        else:
            reference.contract_prices[line.line_no] = price
        if line.unit_price is None:
            reference.missing.append(f"invoice_price:line{line.line_no}")

    pros_terms = ctx.pros.contract_terms(ref.sold_to, ref.billing_date)
    terms = pros_terms or ctx.sap.payment_terms(ref.sold_to)
    if terms:
        reference.contract_terms_days, reference.terms_record = terms
        reference.terms_source = "PROS" if pros_terms else "SAP customer master"
    else:
        reference.missing.append("contract_terms")
    reference.freight_terms = ctx.rate_files.freight_terms(ref.sold_to, ref.billing_date)
    reference.surcharge_terms = ctx.rate_files.surcharge_terms(ref.sold_to, ref.billing_date)
    if not order:
        reference.missing.append("sales_order")

    case.data["invoice"] = invoice
    case.data["order"] = order
    case.data["reference"] = reference
    ctx.keep(case, STEP, f"evidence_v{case.data.get('recheck_count', 0)}.json", {"invoice": invoice, "order": order, "reference": reference, "gold_refresh": ctx.gold_refresh()})
    for item in reference.missing:
        if item.startswith("invoice_price"):
            case.add_flag("DATA.MISSING", f"draft invoice has no price on {item.split(':')[1]}", item)
    ctx.log(
        case, STEP, "evidence.assembled",
        invoice_lines=len(invoice.lines), charges=[c.model_dump() for c in invoice.charges],
        prices_found=sorted(reference.contract_prices), contract_terms=reference.contract_terms_days,
        freight_terms=bool(reference.freight_terms), surcharge_terms=bool(reference.surcharge_terms),
        po_ref=order.get("po_ref") or ref.po_ref, missing=list(reference.missing),
    )
    return StepResult.ok()
