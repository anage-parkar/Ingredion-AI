"""Connector contracts for the Ingredion systems the Order Intake agent touches
(redline v2).

Reads: the Salesforce case queue and cases, SAP master data (direct, no mapping
database), SAP orders and pricing, and in fallback mode the RPA failure record.
Writes: the SAP order (A9) and the Salesforce case (A10), plus an Outlook *draft*
through Microsoft Graph at A6 that only a reviewer can send. Nothing else.

Only protocols live here. ``gold.py`` implements the reads over the data platform
(BigQuery gold tables and the files bucket); the writes are implemented against the
interfaces Ingredion confirms (Stage 1, Gate 2); ``stubs.py`` holds the in-memory
versions used in Dev and in the tests. Keeping the contract this narrow is what lets the
write permissions be scoped to three operations.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..models import (
    CMIRMatch,
    DuplicateCandidate,
    EmailBundle,
    IncompletionItem,
    IntakeCase,
    PartnerMatch,
    SAPOrderResult,
    SAPPayload,
    UomConversion,
)


class SAPTimeout(Exception):
    """The order call did not answer in time; the order may or may not exist."""


class SAPUnavailable(Exception):
    """SAP or the API gateway refused the connection."""


class CaseQueue(Protocol):
    """New email-order cases Salesforce routes to the agent (primary mode)."""

    def fetch_new(self, after: Any) -> list[IntakeCase]: ...


class FailureRecordReader(Protocol):
    """Read-only view of the PurchaseOrder PDF table (fallback mode only)."""

    def fetch_failures(self, after: Any) -> list[IntakeCase]: ...


class SalesforceCases(Protocol):
    def get_email(self, case_id: str) -> EmailBundle: ...

    def set_status(self, case_id: str, status: str, note: str = "") -> None:
        """Claim / progress status so the RPA and manual staff skip the case (write)."""
        ...

    def complete(self, case_id: str, order_numbers: list[str], outcome: str, note: str, follow_ups: list[str] | None = None) -> None:
        """Order number(s), outcome marker, audit note and incompletion follow-ups (write, A10)."""
        ...

    def return_case(self, case_id: str, reason_codes: list[str], note: str) -> None:
        """Hand the case to the manual queue with the agent's reason on it (write)."""
        ...


class SAPMasterData(Protocol):
    def find_partner(self, role: str, text: str) -> list[PartnerMatch]: ...

    def cmir(self, sold_to: str, customer_material: str) -> list[CMIRMatch]: ...

    def uom_conversion(self, sap_material: str, from_uom: str) -> UomConversion | None: ...

    def allowed_uoms(self, sap_material: str) -> list[str]: ...


class SAPOrders(Protocol):
    def find_duplicates(
        self,
        *,
        sold_to: str,
        ship_to: str | None,
        po_number: str | None,
        materials: list[str],
        date: str | None,
        quantities: list[float],
        window_days: int,
    ) -> list[DuplicateCandidate]: ...

    def find_by_reference(self, idempotency_key: str, po_number: str | None, sold_to: str | None) -> str | None:
        """Order number already created for this case, if any (the lookup before any retry)."""
        ...

    def price(self, sold_to: str, sap_material: str, date: str | None) -> tuple[float, str, str] | None:
        """(price, price unit of measure, source name) or None when no price exists."""
        ...

    def contract(self, sold_to: str, sap_material: str, date: str | None) -> dict[str, Any] | None: ...

    def availability(self, sap_material: str, quantity: float, uom: str, date: str | None) -> dict[str, Any] | None: ...


class SAPOrderAPI(Protocol):
    def create_order(self, payload: SAPPayload) -> SAPOrderResult:
        """The one SAP write (order API or BAPI via APIM; method approved at Gate 2).
        Raises :class:`SAPTimeout` or :class:`SAPUnavailable`."""
        ...

    def incompletion_log(self, order_number: str) -> list[IncompletionItem]:
        """SAP's incompletion log for the created order (read)."""
        ...


class GraphMail(Protocol):
    def create_draft(self, mailbox: str, to: list[str], subject: str, body: str, *, case_ref: str) -> str:
        """Save a draft in the shared mailbox for the reviewer to send; returns the draft id."""
        ...


class Alerts(Protocol):
    def raise_alert(self, kind: str, message: str, **data: Any) -> None: ...


__all__ = [
    "Alerts",
    "CaseQueue",
    "FailureRecordReader",
    "GraphMail",
    "SAPMasterData",
    "SAPOrderAPI",
    "SAPOrders",
    "SAPTimeout",
    "SAPUnavailable",
    "SalesforceCases",
]
