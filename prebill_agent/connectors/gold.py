"""Gold-backed, read-only connectors for the pre-bill agent (redline v2, data
platform of 26 October 2026).

The six sources arrive as gold tables: the SAP billing due list, billing documents
and deliveries (``gold_billing``, ``gold_sales``), SAP conditions and the customer
master, PROS agreements, freight and fuel-surcharge schedules (``gold_pricing``),
Salesforce sales orders (``gold_sales``), Ariba POs (``gold_procurement``), TermSync
disputes (``gold_ar``). PO PDFs the pipeline landed are read from the files bucket
by pointer and hash. There is still no write method anywhere in this module.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from factory.intake.poller import RawCase
from factory.platform import FileStore, GoldClient, GoldReader, fetch_verified
from factory.platform.gold import iso, parse_ts

from ..schema import (
    CanonicalDoc,
    CanonicalLine,
    Charge,
    ChargeTerms,
    DocType,
    EvidenceRef,
    PriceRecord,
)
from . import DraftInvoiceRef

INVOICE_READY = "gold_billing.invoice_ready_order"
BILLING = "gold_billing.billing_document"
DELIVERY = "gold_sales.delivery"
CUSTOMER = "gold_sales.customer"
ORDERS = "gold_sales.sales_order"
MATERIAL_UOM = "gold_sales.material_uom"
CONDITION = "gold_pricing.condition"
PROS_AGREEMENT = "gold_pricing.pros_agreement"
FREIGHT = "gold_pricing.freight_charge"
FUEL = "gold_pricing.fuel_rate"
ARIBA = "gold_procurement.ariba_po"
DISPUTE = "gold_ar.dispute"
ATTACHMENTS = "gold_cases.case_attachment"

_CHARGE_TYPES = {"freight": "freight", "fuel_surcharge": "fuel_surcharge", "fuel": "fuel_surcharge", "surcharge": "fuel_surcharge"}


def to_date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def window(on: Any) -> dict[str, tuple[Any, Any]]:
    day = to_date(on)
    return {"valid_from": (None, day), "valid_to": (day, None)}


def _float(value: Any) -> float | None:
    return None if value in (None, "") else float(value)


def _int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _charge_type(value: Any) -> str:
    return _CHARGE_TYPES.get(str(value or "").strip().lower(), "other")


def _line(row: dict[str, Any]) -> CanonicalLine:
    return CanonicalLine(
        line_no=int(row["line_no"]),
        material=str(row["material_id"]),
        qty=float(row["quantity"]),
        qty_uom=str(row["uom"]).upper(),
        tolerance_pct=_float(row.get("tolerance_pct")),
        unit_price=_float(row.get("unit_price")),
        price_uom=(str(row["price_uom"]).upper() if row.get("price_uom") else None),
        price_date=iso(row.get("price_date"))[:10] if row.get("price_date") else None,
        description=row.get("description"),
    )


def ref_from_row(row: dict[str, Any]) -> DraftInvoiceRef:
    return DraftInvoiceRef(
        order_ref=str(row["order_ref"]),
        invoice_ref=str(row["invoice_ref"]),
        sold_to=str(row["sold_to"]),
        customer_name=row.get("customer_name") or "",
        billing_date=(iso(row.get("billing_date")) or "")[:10],
        po_ref=row.get("po_ref"),
    )


class GoldSAPBilling(GoldReader):
    """The billing due list and the draft invoice from gold; also an ``IntakeSource``
    for the sweep poller (marker: ``ready_at``)."""

    name = "gold_invoice_ready"

    def __init__(self, client: GoldClient, *, batch: int = 200, **kw: Any) -> None:
        super().__init__(client, **kw)
        self.batch = batch

    def _ready_rows(self, after: Any) -> list[dict[str, Any]]:
        marker = parse_ts(after)
        return self.rows(INVOICE_READY, gt={"ready_at": marker} if marker else {}, order_by=("ready_at",), limit=self.batch)

    def list_ready(self, after: Any) -> list[DraftInvoiceRef]:
        return [ref_from_row(r) for r in self._ready_rows(after)]

    def fetch(self, after: Any) -> list[RawCase]:
        return [RawCase(source_ref=str(r["order_ref"]), marker=iso(r.get("ready_at")), payload=ref_from_row(r).model_dump()) for r in self._ready_rows(after)]

    def draft_invoice(self, ref: DraftInvoiceRef) -> CanonicalDoc:
        rows = self.rows(BILLING, where={"invoice_ref": ref.invoice_ref}, order_by=("line_no",))
        if not rows:
            raise KeyError(f"no billing document {ref.invoice_ref} in gold")
        head = rows[0]
        items = [r for r in rows if (r.get("line_type") or "item") == "item"]
        charges = [r for r in rows if r.get("line_type") == "charge"]
        evidence = [EvidenceRef(field=f"line{int(r['line_no'])}.unit_price", system="SAP", record=str(r["price_record"])) for r in items if r.get("price_record")]
        if head.get("terms_record"):
            evidence.append(EvidenceRef(field="payment_terms_days", system="SAP", record=str(head["terms_record"])))
        return CanonicalDoc(
            doc_type=DocType.INVOICE,
            order_ref=ref.order_ref,
            source="sap",
            currency=head.get("currency"),
            payment_terms_days=_int(head.get("payment_terms_days")),
            lines=[_line(r) for r in items],
            charges=[Charge(type=_charge_type(r.get("charge_type")), amount=float(r["amount"]), description=r.get("description")) for r in charges],
            evidence=evidence,
        )

    def shipment(self, ref: DraftInvoiceRef) -> dict[str, Any] | None:
        rows = self.rows(DELIVERY, where={"order_ref": ref.order_ref}, order_by=("ship_date",))
        if not rows:
            return None
        return {
            "ship_date": iso(rows[-1].get("ship_date")),
            "shipped_qty": sum(float(r.get("shipped_qty") or 0) for r in rows),
            "uom": str(rows[0].get("uom") or "").upper(),
            "deliveries": [str(r.get("delivery_ref")) for r in rows],
        }

    def price_condition(self, sold_to: str, material: str, on_date: str) -> PriceRecord | None:
        row = self.one(CONDITION, where={"sold_to": sold_to, "material_id": material}, between=window(on_date), order_by=("-valid_from",))
        if row is None:
            return None
        return PriceRecord(
            price=float(row["rate"]),
            price_uom=str(row["price_uom"]).upper(),
            currency=str(row.get("currency") or "USD"),
            source="SAP condition",
            record=f"condition {row.get('condition_type') or ''} {row.get('record') or ''}".strip(),
            valid_from=iso(row.get("valid_from")),
            valid_to=iso(row.get("valid_to")),
        )

    def payment_terms(self, sold_to: str) -> tuple[int, str] | None:
        row = self.one(CUSTOMER, where={"customer_id": sold_to, "role": "sold_to"})
        if row is None or row.get("payment_terms_days") in (None, ""):
            return None
        return int(row["payment_terms_days"]), f"customer master {sold_to} {row.get('payment_terms_code') or ''}".strip()


class GoldPROS(GoldReader):
    def contract_price(self, sold_to: str, material: str, on_date: str) -> PriceRecord | None:
        row = self.one(PROS_AGREEMENT, where={"sold_to": sold_to, "material_id": material}, between=window(on_date), order_by=("-valid_from",))
        if row is None or row.get("price") in (None, ""):
            return None
        return PriceRecord(
            price=float(row["price"]),
            price_uom=str(row["price_uom"]).upper(),
            currency=str(row.get("currency") or "USD"),
            source="PROS",
            record=str(row.get("record") or row.get("agreement_ref")),
            valid_from=iso(row.get("valid_from")),
            valid_to=iso(row.get("valid_to")),
        )

    def contract_terms(self, sold_to: str, on_date: str) -> tuple[int, str] | None:
        row = self.one(PROS_AGREEMENT, where={"sold_to": sold_to, "material_id": None}, between=window(on_date), order_by=("-valid_from",))
        if row is None or row.get("payment_terms_days") in (None, ""):
            return None
        return int(row["payment_terms_days"]), str(row.get("record") or row.get("agreement_ref"))


class GoldSalesforceOrders(GoldReader):
    def order(self, order_ref: str) -> dict[str, Any] | None:
        row = self.one(ORDERS, where={"order_ref": order_ref})
        if row is None:
            return None
        out: dict[str, Any] = {"po_ref": row.get("po_ref"), "po_source": row.get("po_source"), "sold_to": row.get("sold_to"), "salesforce_case_id": row.get("salesforce_case_id")}
        captured = row.get("captured_po_json")
        if captured:
            out["captured_po"] = CanonicalDoc.model_validate(json.loads(captured) if isinstance(captured, str) else captured)
        return out


class GoldAriba(GoldReader):
    def purchase_order(self, po_ref: str) -> CanonicalDoc | None:
        rows = self.rows(ARIBA, where={"po_ref": po_ref}, order_by=("line_no",))
        if not rows:
            return None
        head = rows[0]
        items = [r for r in rows if (r.get("line_type") or "item") == "item"]
        charges = [r for r in rows if r.get("line_type") == "charge"]
        return CanonicalDoc(
            doc_type=DocType.PO,
            order_ref=po_ref,
            source="ariba",
            currency=head.get("currency"),
            payment_terms_days=_int(head.get("payment_terms_days")),
            lines=[_line(r) for r in items],
            charges=[Charge(type=_charge_type(r.get("charge_type")), amount=float(r["charge_amount"]), description=r.get("description")) for r in charges],
            evidence=[EvidenceRef(field=f"line{int(r['line_no'])}.unit_price", system="Ariba", record=f"PO {po_ref} line {int(r['line_no'])}") for r in items],
        )


class GoldTermSync(GoldReader):
    def dispute_history(self, sold_to: str) -> list[dict[str, Any]]:
        rows = self.rows(DISPUTE, where={"sold_to": sold_to}, order_by=("-opened_at",), limit=50)
        return [{"invoice": r.get("invoice_ref"), "code": r.get("code"), "date": iso(r.get("opened_at")), "amount": _float(r.get("amount")), "status": r.get("status")} for r in rows]


class GoldRateFiles(GoldReader):
    def _terms(self, table: str, sold_to: str, on_date: str) -> ChargeTerms | None:
        row = self.one(table, where={"sold_to": sold_to}, between=window(on_date), order_by=("-valid_from",))
        if row is None:
            return None
        return ChargeTerms(applies=bool(row.get("applies")), amount=_float(row.get("amount")), basis=row.get("basis") or None, source=table, record=str(row.get("record") or ""))

    def freight_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None:
        return self._terms(FREIGHT, sold_to, on_date)

    def surcharge_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None:
        return self._terms(FUEL, sold_to, on_date)

    def material_factors(self, material: str) -> dict[str, float]:
        return {str(r["uom"]).upper(): float(r["lb_per_unit"]) for r in self.rows(MATERIAL_UOM, where={"material_id": material}) if r.get("lb_per_unit") not in (None, "")}


class FilesBucketMailbox(GoldReader):
    """PO PDFs the pipeline landed: ``case_attachment`` rows of kind ``po`` by order or
    PO reference, fetched from the files bucket by pointer and verified by hash."""

    def __init__(self, client: GoldClient, files: FileStore, **kw: Any) -> None:
        super().__init__(client, **kw)
        self.files = files

    def find_po_pdf(self, order_ref: str, po_ref: str | None) -> tuple[bytes, str] | None:
        row = self.one(ATTACHMENTS, where={"kind": "po", "order_ref": order_ref}, order_by=("-received_at",))
        if row is None and po_ref:
            row = self.one(ATTACHMENTS, where={"kind": "po", "po_ref": po_ref}, order_by=("-received_at",))
        if row is None:
            return None
        return fetch_verified(self.files, row["file_uri"], row.get("sha256")), row.get("content_type") or "application/pdf"


__all__ = ["FilesBucketMailbox", "GoldAriba", "GoldPROS", "GoldRateFiles", "GoldSAPBilling", "GoldSalesforceOrders", "GoldTermSync", "ref_from_row", "to_date", "window"]
