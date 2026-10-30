"""A4 · Validate and enrich against SAP master data.

Code only. Sold-to, ship-to and bill-to are matched in SAP master data; each line's
customer material is resolved through the customer-material info record (CMIR);
units are converted with SAP's own conversion data and never assumed. A partner or
material that does not exist in SAP is a gap for Ingredion's master-data team and
the case exits; an ambiguous match is a candidate list for the reviewer.

The first time an extraction fails a hard check (no PO number, no lines, zero
quantity, line totals that do not add up, unreadable date) the step asks the
pipeline to re-read the PO once with hints; the second time, the problems become
flags the reviewer sees.
"""

from __future__ import annotations

from datetime import date

from factory.case import Case, StepResult

from ..context import OrderIntakeContext
from ..models import PartnerMatch, POExtraction, POLine, ValidatedLine, Validation

STEP = "A4"

_PROBLEM_MESSAGES = {
    "EXTRACT.PO_NUMBER_MISSING": "no PO number was read",
    "EXTRACT.NO_LINES": "no order lines were read",
    "EXTRACT.ZERO_QUANTITY": "a line has zero or negative quantity",
    "EXTRACT.LINE_TOTALS_MISMATCH": "quantity × price does not equal the line total",
    "EXTRACT.DATE_FORMAT": "requested delivery date is missing or not a date",
}
A4_FLAG_CODES = set(_PROBLEM_MESSAGES) | {
    "MASTER.PARTNER_AMBIGUOUS",
    "CMIR.MULTIPLE_MATCHES",
    "UOM.NO_CONVERSION",
    "UOM.INVALID",
    "UOM.AMBIGUOUS",
}


def _is_iso_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def arithmetic_ok(line: POLine) -> bool | None:
    """Does quantity × price reproduce the line total? None when a value is missing.

    The price may be quoted per a different unit than the quantity (USD/CWT for a
    quantity in lb), so the common decimal factors are accepted.
    """
    if line.unit_price is None or line.line_total is None or not line.quantity:
        return None
    expected = line.quantity * line.unit_price
    tolerance = max(0.02, 0.005 * abs(line.line_total))
    return any(abs(expected * f - line.line_total) <= tolerance for f in (1, 0.01, 100, 0.001, 1000))


def extraction_problems(ex: POExtraction) -> list[str]:
    codes: list[str] = []
    if not ex.po_number:
        codes.append("EXTRACT.PO_NUMBER_MISSING")
    if not ex.lines:
        codes.append("EXTRACT.NO_LINES")
    if any(line.quantity is None or line.quantity <= 0 for line in ex.lines):
        codes.append("EXTRACT.ZERO_QUANTITY")
    if any(arithmetic_ok(line) is False for line in ex.lines):
        codes.append("EXTRACT.LINE_TOTALS_MISMATCH")
    if not _is_iso_date(ex.requested_delivery_date):
        codes.append("EXTRACT.DATE_FORMAT")
    return codes


def run(case: Case, ctx: OrderIntakeContext, *, recheck: bool = False) -> StepResult:
    ex: POExtraction = case.data["extraction"]
    overrides = case.data.get("overrides", {})
    policy = ctx.policy

    if recheck:  # corrections applied: rebuild from scratch, no re-read
        case.flags = [f for f in case.flags if f.code not in A4_FLAG_CODES]

    problems = extraction_problems(ex)
    if problems and not recheck and not case.data.get("reread_done"):
        case.data["reread_done"] = True
        case.data["reread_hints"] = [f"{c}: {_PROBLEM_MESSAGES[c]}" for c in problems]
        case.add_codes("EXTRACT.REREAD")
        ctx.log(case, STEP, "extraction.reread_requested", problems=problems)
        return StepResult.retry(*problems)
    for code in problems:
        case.add_flag(code, _PROBLEM_MESSAGES[code])

    val = Validation()

    # ── partners ─────────────────────────────────────────────────────────────
    for role in ("sold_to", "ship_to", "bill_to"):
        text = getattr(ex, role)
        override = overrides.get(f"{role}_id")
        if override:
            setattr(val, role, PartnerMatch(role=role, id=str(override), name=f"reviewer:{override}"))
            continue
        if role == "bill_to" and not text:
            continue  # optional on the PO; SAP derives it from the sold-to
        matches = ctx.sap_master.find_partner(role, text or "")
        if len(matches) == 1:
            setattr(val, role, matches[0])
        elif not matches:
            code = f"MASTER.{role.upper()}_NOT_FOUND"
            val.ok = False
            case.data["validation"] = val
            ctx.log(case, STEP, "master_data.gap", code=code, role=role, value=text)
            return StepResult.exit(code, note=f"{role} not found in SAP master data: {text!r}")
        else:
            val.partner_candidates[role] = matches
            case.add_flag(
                "MASTER.PARTNER_AMBIGUOUS",
                f"{len(matches)} SAP partners match the {role.replace('_', '-')}",
                role,
                candidates=[m.model_dump() for m in matches],
            )

    # ── lines: CMIR and units ────────────────────────────────────────────────
    sold_to_id = val.sold_to.id if val.sold_to else None
    line_overrides = overrides.get("lines", {})
    for line in ex.lines:
        vl = ValidatedLine(
            line_no=line.line_no,
            customer_material=line.customer_material,
            quantity=line.quantity,
            uom=(line.uom or "").strip().upper(),
            unit_price=line.unit_price,
            price_uom=(line.price_uom or "").strip().upper() or None,
            arithmetic_ok=arithmetic_ok(line),
        )
        sales_uom: str | None = None
        lo = line_overrides.get(str(line.line_no), {})
        if lo.get("sap_material"):
            vl.sap_material = str(lo["sap_material"])
            sales_uom = lo.get("sales_uom")
        elif sold_to_id:
            matches = ctx.sap_master.cmir(sold_to_id, line.customer_material)
            if not matches:
                val.ok = False
                case.data["validation"] = val
                ctx.log(
                    case, STEP, "master_data.gap", code="MASTER.MATERIAL_NOT_FOUND",
                    customer_material=line.customer_material, sold_to=sold_to_id,
                )
                return StepResult.exit(
                    "MASTER.MATERIAL_NOT_FOUND",
                    note=f"no CMIR for {line.customer_material!r} and sold-to {sold_to_id}",
                )
            if len(matches) > 1:
                vl.candidates = matches
                case.add_flag(
                    "CMIR.MULTIPLE_MATCHES",
                    f"{len(matches)} CMIR records for {line.customer_material}; reviewer chooses",
                    f"line{line.line_no}.sap_material",
                    candidates=[m.model_dump() for m in matches],
                )
            else:
                vl.sap_material = matches[0].sap_material
                sales_uom = matches[0].sales_uom

        if vl.uom in policy.ambiguous_units:
            case.add_flag(
                "UOM.AMBIGUOUS",
                f"'{line.uom}' on line {line.line_no} could be US or metric tons; not converted",
                f"line{line.line_no}.uom",
                quantity=line.quantity,
            )
        elif vl.sap_material and sales_uom and vl.uom != sales_uom.upper():
            conv = ctx.sap_master.uom_conversion(vl.sap_material, vl.uom)
            if conv is None:
                allowed = [u.upper() for u in ctx.sap_master.allowed_uoms(vl.sap_material)]
                code = "UOM.INVALID" if allowed and vl.uom not in allowed else "UOM.NO_CONVERSION"
                case.add_flag(
                    code,
                    f"no SAP conversion from {vl.uom} to {sales_uom.upper()} for {vl.sap_material}",
                    f"line{line.line_no}.uom",
                    allowed=allowed,
                    quantity=line.quantity,
                )
                if code == "UOM.NO_CONVERSION":
                    ctx.log(case, STEP, "master_data.gap", code=code, material=vl.sap_material, uom=vl.uom)
            else:
                vl.converted_quantity = round(line.quantity * conv.factor, 6)
                vl.converted_uom = conv.to_uom.upper()
                vl.conversion_factor = conv.factor
        elif vl.sap_material:
            vl.converted_quantity = line.quantity
            vl.converted_uom = vl.uom
            vl.conversion_factor = 1.0
        val.lines.append(vl)

    case.data["validation"] = val
    ctx.log(
        case,
        STEP,
        "validated" if not recheck else "revalidated",
        sold_to=val.sold_to.id if val.sold_to else None,
        ship_to=val.ship_to.id if val.ship_to else None,
        bill_to=val.bill_to.id if val.bill_to else None,
        lines=[
            {"line_no": vl.line_no, "sap_material": vl.sap_material, "quantity": vl.converted_quantity, "uom": vl.converted_uom}
            for vl in val.lines
        ],
        flags=[f.code for f in case.flags],
    )
    return StepResult.ok()
