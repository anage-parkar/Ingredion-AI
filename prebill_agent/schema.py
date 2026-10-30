"""One canonical shape for the PO and the draft invoice, so every rule compares like
with like and every number carries the record it came from."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DocType(StrEnum):
    PO = "po"
    INVOICE = "invoice"


class EvidenceRef(BaseModel):
    field: str
    system: str  # SAP | PROS | Salesforce | Ariba | TermSync | rate_files | pdf | conversion
    record: str


class Charge(BaseModel):
    type: Literal["freight", "fuel_surcharge", "other"]
    amount: float
    description: str | None = None


class CanonicalLine(BaseModel):
    line_no: int
    material: str
    qty: float
    qty_uom: str
    tolerance_pct: float | None = None  # printed PO tolerance; None means exact
    unit_price: float | None = None
    price_uom: str | None = None
    price_date: str | None = None
    description: str | None = None


class CanonicalDoc(BaseModel):
    doc_type: DocType
    order_ref: str
    source: str  # ariba | sap | salesforce | pdf
    currency: str | None = None
    payment_terms_days: int | None = None
    lines: list[CanonicalLine] = Field(default_factory=list)
    charges: list[Charge] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)

    def charge_total(self, kind: str) -> float:
        return round(sum(c.amount for c in self.charges if c.type == kind), 2)


class PriceRecord(BaseModel):
    price: float
    price_uom: str
    currency: str
    source: str  # PROS | SAP condition | contract file
    record: str
    valid_from: str | None = None
    valid_to: str | None = None


class ChargeTerms(BaseModel):
    """What the contract or rate file says about a freight or surcharge charge."""

    applies: bool
    amount: float | None = None
    basis: str | None = None  # flat | per_cwt | per_shipment
    source: str = "rate_files"
    record: str = ""


class ReferenceData(BaseModel):
    """Evidence B2 assembles beside the PO and the invoice."""

    contract_prices: dict[int, PriceRecord] = Field(default_factory=dict)  # by invoice line number
    contract_terms_days: int | None = None
    terms_source: str | None = None
    terms_record: str | None = None
    freight_terms: ChargeTerms | None = None
    surcharge_terms: ChargeTerms | None = None
    shipment: dict[str, object] = Field(default_factory=dict)
    dispute_history: list[dict[str, object]] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)  # names of evidence that could not be found


class GapExplanation(BaseModel):
    """B6 answer: words only; verdicts and numbers come from the rules."""

    summary_by_category: dict[str, str] = Field(default_factory=dict)
    draft_request: str = ""
    draft_internal_note: str = ""
    risk_note: str = ""
