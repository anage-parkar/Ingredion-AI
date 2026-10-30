"""Dict-backed read-only sources for Dev and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factory.intake.poller import RawCase

from ..schema import CanonicalDoc, ChargeTerms, PriceRecord
from . import DraftInvoiceRef


class StubSAPBilling:
    """Also an ``IntakeSource`` for the factory poller (marker = row index)."""

    name = "sap_billing_due_list"

    def __init__(self) -> None:
        self.ready: list[DraftInvoiceRef] = []
        self.invoices: dict[str, CanonicalDoc] = {}
        self.shipments: dict[str, dict[str, Any]] = {}
        self.conditions: dict[tuple[str, str], PriceRecord] = {}
        self.terms: dict[str, tuple[int, str]] = {}

    def add(self, ref: DraftInvoiceRef, invoice: CanonicalDoc, shipment: dict[str, Any] | None = None) -> None:
        self.ready.append(ref)
        self.invoices[ref.order_ref] = invoice
        if shipment:
            self.shipments[ref.order_ref] = shipment

    def list_ready(self, after: Any) -> list[DraftInvoiceRef]:
        start = -1 if after is None else int(after)
        return [r for i, r in enumerate(self.ready) if i > start]

    def fetch(self, after: Any) -> list[RawCase]:
        start = -1 if after is None else int(after)
        return [RawCase(source_ref=r.order_ref, marker=i, payload=r.model_dump()) for i, r in enumerate(self.ready) if i > start]

    def draft_invoice(self, ref: DraftInvoiceRef) -> CanonicalDoc:
        return self.invoices[ref.order_ref]

    def shipment(self, ref: DraftInvoiceRef) -> dict[str, Any] | None:
        return self.shipments.get(ref.order_ref)

    def price_condition(self, sold_to: str, material: str, on_date: str) -> PriceRecord | None:
        return self.conditions.get((sold_to, material))

    def payment_terms(self, sold_to: str) -> tuple[int, str] | None:
        return self.terms.get(sold_to)


@dataclass
class StubPROS:
    prices: dict[tuple[str, str], PriceRecord] = field(default_factory=dict)
    terms: dict[str, tuple[int, str]] = field(default_factory=dict)

    def contract_price(self, sold_to: str, material: str, on_date: str) -> PriceRecord | None:
        return self.prices.get((sold_to, material))

    def contract_terms(self, sold_to: str, on_date: str) -> tuple[int, str] | None:
        return self.terms.get(sold_to)


@dataclass
class StubSalesforceOrders:
    orders: dict[str, dict[str, Any]] = field(default_factory=dict)

    def order(self, order_ref: str) -> dict[str, Any] | None:
        return self.orders.get(order_ref)


@dataclass
class StubAriba:
    pos: dict[str, CanonicalDoc] = field(default_factory=dict)

    def purchase_order(self, po_ref: str) -> CanonicalDoc | None:
        return self.pos.get(po_ref)


@dataclass
class StubTermSync:
    history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def dispute_history(self, sold_to: str) -> list[dict[str, Any]]:
        return list(self.history.get(sold_to, []))


@dataclass
class StubRateFiles:
    freight: dict[str, ChargeTerms] = field(default_factory=dict)
    surcharge: dict[str, ChargeTerms] = field(default_factory=dict)
    factors: dict[str, dict[str, float]] = field(default_factory=dict)

    def freight_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None:
        return self.freight.get(sold_to)

    def surcharge_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None:
        return self.surcharge.get(sold_to)

    def material_factors(self, material: str) -> dict[str, float]:
        return dict(self.factors.get(material, {}))


@dataclass
class StubMailbox:
    pdfs: dict[str, tuple[bytes, str]] = field(default_factory=dict)  # by order ref or PO ref

    def find_po_pdf(self, order_ref: str, po_ref: str | None) -> tuple[bytes, str] | None:
        return self.pdfs.get(order_ref) or (self.pdfs.get(po_ref) if po_ref else None)
