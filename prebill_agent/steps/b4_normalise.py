"""B4 · Normalise both documents into the invoice's units and currency, then pair
each invoice line with its PO line. A unit that cannot be converted (an ambiguous
"ton", a bag with no per-material weight) stops the price and quantity comparison
for that case rather than guessing."""

from __future__ import annotations

from factory.case import Case, StepResult

from ..context import PrebillContext
from ..normalise import UnitError, normalise_doc, pair_lines

STEP = "B4"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    po = case.data.get("po")
    invoice = case.data["invoice"]
    ref = case.data["invoice_ref"]
    case.data["normalisation_failed"] = False
    if po is None:
        case.data.update(po_n=None, invoice_n=invoice, pairs=[])
        ctx.log(case, STEP, "normalised", skipped="no PO")
        return StepResult.ok()

    first = invoice.lines[0] if invoice.lines else None
    qty_uom = first.qty_uom if first else "LB"
    price_uom = (first.price_uom or first.qty_uom) if first else "LB"
    factors: dict[str, float] = {}
    for material in {line.material for line in [*po.lines, *invoice.lines]}:
        factors.update(ctx.rate_files.material_factors(material))
    try:
        po_n = normalise_doc(po, qty_uom=qty_uom, price_uom=price_uom, currency=invoice.currency, on_date=ref.billing_date, rates=ctx.fx, factors=factors)
        invoice_n = normalise_doc(invoice, qty_uom=qty_uom, price_uom=price_uom, currency=invoice.currency, on_date=ref.billing_date, rates=ctx.fx, factors=factors)
    except UnitError as exc:
        case.data["normalisation_failed"] = True
        po_n, invoice_n = po, invoice
        ctx.log(case, STEP, "normalisation.failed", error=str(exc))
    pairs = pair_lines(po_n, invoice_n)
    case.data.update(po_n=po_n, invoice_n=invoice_n, pairs=pairs)
    ctx.log(
        case, STEP, "normalised",
        target_units={"qty": qty_uom, "price": price_uom, "currency": invoice.currency},
        conversions=[e.record for e in po_n.evidence if e.system == "conversion"],
        unpaired_invoice_lines=[inv.line_no for p, inv in pairs if p is None],
    )
    return StepResult.ok()
