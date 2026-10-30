"""Gold-backed connectors for the Order Intake agent (redline v2, data platform of
26 October 2026).

Reads come from the BigQuery gold tables and the files bucket the data platform
lands: the Salesforce case queue and the case email with its attachments (by
pointer and hash), SAP master data, SAP orders for the duplicate check and the
lookup before any retry, prices and contracts. Two things no copy replaces stay
live and are delegated: availability (ATP) and the order lookup immediately after a
timeout, when gold may not have caught up. Writes (the Salesforce case status, the
SAP order, the Outlook draft) are not here: they go through the live connectors,
whose shape is a Gate 2 decision.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from factory.intake.poller import RawCase
from factory.platform import FileStore, GoldClient, GoldReader, fetch_verified
from factory.platform.gold import iso, parse_ts

from ..models import (
    Attachment,
    CMIRMatch,
    DuplicateCandidate,
    EmailBundle,
    IntakeCase,
    PartnerMatch,
    UomConversion,
)
from . import SalesforceCases, SAPOrders

CASES = "gold_cases.email_order_case"
ATTACHMENTS = "gold_cases.case_attachment"
CUSTOMER = "gold_sales.customer"
MATERIAL_UOM = "gold_sales.material_uom"
CMIR = "gold_sales.customer_material"
ORDERS = "gold_sales.sales_order"
ITEMS = "gold_sales.sales_order_item"
CONDITION = "gold_pricing.condition"
CONTRACT = "gold_pricing.contract"
UOM = "gold_reference.uom_conversion"


def to_date(value: Any, default: dt.date | None = None) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if value:
        try:
            return dt.date.fromisoformat(str(value)[:10])
        except ValueError:
            return default
    return default


def window(on: dt.date) -> dict[str, tuple[Any, Any]]:
    """Valid on a date: ``valid_from <= on <= valid_to`` (open ends are 9999-12-31 in gold)."""
    return {"valid_from": (None, on), "valid_to": (on, None)}


def intake_from_row(row: dict[str, Any]) -> IntakeCase:
    return IntakeCase(
        case_id=str(row["case_id"]),
        source="salesforce_queue",
        cohort=row.get("cohort"),
        customer=row.get("customer_name"),
        received_at=iso(row.get("received_at")),
        record_id=str(row["case_number"]) if row.get("case_number") else None,
    )


class GoldCaseQueue(GoldReader):
    """``gold_cases.email_order_case`` rows routed to the agent, in ``updated_at`` order.
    Also an ``IntakeSource`` for the sweep poller (marker: ``updated_at``), which catches
    anything the change signal missed; the claim registry keeps every case to one run."""

    name = "gold_case_queue"

    def __init__(self, client: GoldClient, *, routed_to: str = "agent", statuses: list[str] | None = None, batch: int = 200, **kw: Any) -> None:
        super().__init__(client, **kw)
        self.routed_to = routed_to
        self.statuses = list(statuses) if statuses else None
        self.batch = batch

    def _rows(self, after: Any) -> list[dict[str, Any]]:
        where: dict[str, Any] = {"routed_to": self.routed_to}
        if self.statuses:
            where["status"] = self.statuses
        marker = parse_ts(after)
        return self.rows(CASES, where=where, gt={"updated_at": marker} if marker else {}, order_by=("updated_at",), limit=self.batch)

    def fetch_new(self, after: Any) -> list[IntakeCase]:
        return [intake_from_row(r) for r in self._rows(after)]

    def fetch(self, after: Any) -> list[RawCase]:
        return [RawCase(source_ref=str(r["case_id"]), marker=iso(r.get("updated_at")), payload=intake_from_row(r).model_dump(mode="json")) for r in self._rows(after)]


class GoldSalesforceCases(GoldReader):
    """The case email and attachments from gold and the files bucket; the three writes
    are delegated to ``writer`` (the Dev stub until the Salesforce interface exists)."""

    def __init__(self, client: GoldClient, files: FileStore, writer: SalesforceCases, **kw: Any) -> None:
        super().__init__(client, **kw)
        self.files = files
        self.writer = writer

    def get_email(self, case_id: str) -> EmailBundle:
        row = self.one(CASES, where={"case_id": case_id})
        if row is None:
            raise KeyError(f"no Salesforce case {case_id} in gold")
        attachments = []
        for att in self.rows(ATTACHMENTS, where={"case_id": case_id}, order_by=("received_at", "name")):
            content = fetch_verified(self.files, att["file_uri"], att.get("sha256"))
            attachments.append(Attachment(name=att["name"], content_type=att.get("content_type") or "application/octet-stream", content=content))
        return EmailBundle(subject=row.get("subject") or "", body=row.get("body") or "", sender=row.get("sender"), received_at=iso(row.get("received_at")), attachments=attachments)

    def set_status(self, case_id: str, status: str, note: str = "") -> None:
        self.writer.set_status(case_id, status, note)

    def complete(self, case_id: str, order_numbers: list[str], outcome: str, note: str, follow_ups: list[str] | None = None) -> None:
        self.writer.complete(case_id, order_numbers, outcome, note, follow_ups=follow_ups)

    def return_case(self, case_id: str, reason_codes: list[str], note: str) -> None:
        self.writer.return_case(case_id, reason_codes, note)


class GoldSAPMasterData(GoldReader):
    def find_partner(self, role: str, text: str) -> list[PartnerMatch]:
        if not text:
            return []
        found: dict[str, PartnerMatch] = {}
        for column in ("name", "customer_id"):
            for row in self.rows(CUSTOMER, where={"role": role}, within={column: text}):
                if row.get("blocked"):
                    continue
                found.setdefault(str(row["customer_id"]), PartnerMatch(role=role, id=str(row["customer_id"]), name=row.get("name") or "", score=1.0))
        return list(found.values())

    def cmir(self, sold_to: str, customer_material: str) -> list[CMIRMatch]:
        key = customer_material.strip()
        rows = self.rows(CMIR, where={"sold_to": sold_to, "customer_material": key})
        if not rows and key.upper() != key:
            rows = self.rows(CMIR, where={"sold_to": sold_to, "customer_material": key.upper()})
        return [CMIRMatch(customer_material=str(r["customer_material"]), sap_material=str(r["material_id"]), description=r.get("description"), sales_uom=r.get("sales_uom")) for r in rows]

    def _base_uom(self, sap_material: str) -> str | None:
        row = self.one(MATERIAL_UOM, where={"material_id": sap_material})
        return str(row["base_uom"]).upper() if row and row.get("base_uom") else None

    def uom_conversion(self, sap_material: str, from_uom: str) -> UomConversion | None:
        unit = from_uom.strip().upper()
        row = self.one(MATERIAL_UOM, where={"material_id": sap_material, "uom": unit})
        if row is not None:
            return UomConversion(from_uom=unit, to_uom=str(row["base_uom"]).upper(), factor=float(row["factor"]))
        base = self._base_uom(sap_material)
        if base:
            generic = self.one(UOM, where={"from_uom": unit, "to_uom": base})
            if generic is not None:
                return UomConversion(from_uom=unit, to_uom=base, factor=float(generic["factor"]))
        return None

    def allowed_uoms(self, sap_material: str) -> list[str]:
        rows = self.rows(MATERIAL_UOM, where={"material_id": sap_material})
        units = {str(r["uom"]).upper() for r in rows} | {str(r["base_uom"]).upper() for r in rows if r.get("base_uom")}
        return sorted(units)


class GoldSAPOrders(GoldReader):
    """Duplicates, the lookup before any retry, prices and contracts from gold.
    ``live`` (optional) is the SAP read connector used for availability and as the
    second look when gold has no order under the reference yet."""

    def __init__(self, client: GoldClient, *, live: SAPOrders | None = None, today: Callable[[], dt.date] = dt.date.today, **kw: Any) -> None:
        super().__init__(client, **kw)
        self.live = live
        self.today = today

    def find_duplicates(self, *, sold_to: str, ship_to: str | None, po_number: str | None, materials: list[str], date: str | None, quantities: list[float], window_days: int) -> list[DuplicateCandidate]:
        since = self.today() - dt.timedelta(days=window_days)
        orders = self.rows(ORDERS, where={"sold_to": sold_to}, between={"order_date": (since, None)}, order_by=("-order_date",), limit=500)
        if not orders:
            return []
        items_by_order: dict[str, list[dict[str, Any]]] = {}
        if materials:
            for item in self.rows(ITEMS, where={"order_ref": [o["order_ref"] for o in orders], "material_id": list(materials)}):
                items_by_order.setdefault(str(item["order_ref"]), []).append(item)
        wanted_po = (po_number or "").strip().upper()
        out: list[DuplicateCandidate] = []
        for order in orders:
            same_po = bool(wanted_po) and str(order.get("po_ref") or "").strip().upper() == wanted_po
            match_item = None
            if (ship_to is None or order.get("ship_to") == ship_to) and (date is None or iso(order.get("requested_delivery_date")) == iso(date)):
                for item in items_by_order.get(str(order["order_ref"]), []):
                    if float(item.get("quantity") or 0) in quantities:
                        match_item = item
                        break
            if same_po or match_item is not None:
                out.append(
                    DuplicateCandidate(
                        sap_order=str(order["order_ref"]),
                        po_number=order.get("po_ref"),
                        ship_to=order.get("ship_to"),
                        material=match_item.get("material_id") if match_item else None,
                        quantity=float(match_item["quantity"]) if match_item else None,
                        date=iso(order.get("requested_delivery_date")),
                        score=1.0 if same_po else 0.8,
                    )
                )
        return out

    def find_by_reference(self, idempotency_key: str, po_number: str | None, sold_to: str | None) -> str | None:
        row = self.one(ORDERS, where={"agent_reference": idempotency_key})
        if row is not None:
            return str(row["order_ref"])
        if self.live is not None:
            return self.live.find_by_reference(idempotency_key, po_number, sold_to)
        return None

    def price(self, sold_to: str, sap_material: str, date: str | None) -> tuple[float, str, str] | None:
        on = to_date(date, self.today()) or self.today()
        row = self.one(CONDITION, where={"sold_to": sold_to, "material_id": sap_material}, between=window(on), order_by=("-valid_from",))
        if row is None:
            return None
        return float(row["rate"]), str(row["price_uom"]), f"SAP condition {row.get('condition_type') or ''} {row.get('record') or ''}".strip()

    def contract(self, sold_to: str, sap_material: str, date: str | None) -> dict[str, Any] | None:
        on = to_date(date, self.today()) or self.today()
        row = self.one(CONTRACT, where={"sold_to": sold_to, "material_id": sap_material}, between=window(on), order_by=("-valid_from",))
        if row is None:
            return None
        return {
            "number": row.get("contract_ref"),
            "valid_to": iso(row.get("valid_to")),
            "remaining_quantity": float(row["remaining_quantity"]) if row.get("remaining_quantity") is not None else None,
            "quantity_uom": row.get("quantity_uom"),
            "price": float(row["price"]) if row.get("price") is not None else None,
            "price_uom": row.get("price_uom"),
            "currency": row.get("currency"),
        }

    def availability(self, sap_material: str, quantity: float, uom: str, date: str | None) -> dict[str, Any] | None:
        if self.live is not None:
            return self.live.availability(sap_material, quantity, uom, date)
        return None  # ATP is a live answer; without a live connector the check is reported as not done


__all__ = ["GoldCaseQueue", "GoldSAPMasterData", "GoldSAPOrders", "GoldSalesforceCases", "intake_from_row", "to_date", "window"]
