"""Read-only connector contracts for the six pre-bill sources (SAP, PROS, Salesforce,
Ariba, TermSync, contract and fuel-rate files) plus the mailbox fallback and FX
rates. ``gold.py`` implements them over the data platform, ``landing.py`` over the
extract landing, ``stubs.py`` in memory. There is no write protocol in this package
on purpose: the pre-bill agent writes to no Ingredion system."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from ..schema import CanonicalDoc, ChargeTerms, PriceRecord


class DraftInvoiceRef(BaseModel):
    order_ref: str  # SAP sales order, e.g. 809-6862
    invoice_ref: str
    sold_to: str
    customer_name: str
    billing_date: str  # actual goods issue / billing date the price applies to
    po_ref: str | None = None


class SAPBilling(Protocol):
    def list_ready(self, after: Any) -> list[DraftInvoiceRef]: ...

    def draft_invoice(self, ref: DraftInvoiceRef) -> CanonicalDoc: ...

    def shipment(self, ref: DraftInvoiceRef) -> dict[str, Any] | None: ...

    def price_condition(self, sold_to: str, material: str, on_date: str) -> PriceRecord | None: ...

    def payment_terms(self, sold_to: str) -> tuple[int, str] | None:
        """(days, record) from the customer master."""
        ...


class PROS(Protocol):
    def contract_price(self, sold_to: str, material: str, on_date: str) -> PriceRecord | None: ...

    def contract_terms(self, sold_to: str, on_date: str) -> tuple[int, str] | None: ...


class SalesforceOrders(Protocol):
    def order(self, order_ref: str) -> dict[str, Any] | None:
        """Sales order record: ``po_ref``, ``po_source`` and, when captured, ``captured_po``."""
        ...


class Ariba(Protocol):
    def purchase_order(self, po_ref: str) -> CanonicalDoc | None: ...


class TermSync(Protocol):
    def dispute_history(self, sold_to: str) -> list[dict[str, Any]]: ...


class RateFiles(Protocol):
    def freight_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None: ...

    def surcharge_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None: ...

    def material_factors(self, material: str) -> dict[str, float]:
        """Pounds per packaging unit for the material (BAG, DRUM ...)."""
        ...


class Mailbox(Protocol):
    def find_po_pdf(self, order_ref: str, po_ref: str | None) -> tuple[bytes, str] | None:
        """(content, content type) of the PO attachment, when it exists nowhere structured."""
        ...


__all__ = ["PROS", "Ariba", "DraftInvoiceRef", "Mailbox", "RateFiles", "SAPBilling", "SalesforceOrders", "TermSync"]
