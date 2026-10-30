"""Typed records that move through A1 to A10. Pydantic so the model-facing schemas
(Classification, POExtraction, ClarificationDraft) double as the JSON schema sent
with the prompt."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorCategory(StrEnum):
    """Only used in fallback mode, when the intake is the RPA failure record."""

    EXTRACTION = "extraction"
    MAPPING_DATA = "mapping_data"
    SAP = "sap"
    MAX_LOAD = "max_load"
    UNKNOWN = "unknown"


class IntakeCase(BaseModel):
    """One Salesforce email-order case routed to the agent (primary mode), or one row
    of the RPA failure record (fallback mode during the transition)."""

    case_id: str
    source: Literal["salesforce_queue", "rpa_failure_record"] = "salesforce_queue"
    cohort: str | None = None  # the customer cohort Ingredion moved to the agent
    customer: str | None = None
    received_at: str | None = None
    record_id: str | None = None
    error_category: ErrorCategory | None = None
    error_detail: str = ""


class RPAFailure(IntakeCase):
    """Transition-period intake: a failed case from the PurchaseOrder PDF table."""

    source: Literal["salesforce_queue", "rpa_failure_record"] = "rpa_failure_record"
    error_category: ErrorCategory | None = ErrorCategory.UNKNOWN


class Attachment(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    name: str
    content_type: str
    content: bytes


class EmailBundle(BaseModel):
    subject: str = ""
    body: str = ""
    sender: str | None = None
    received_at: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)


class Intent(StrEnum):
    NEW_ORDER = "new_order"
    REVISED_PO = "revised_po"
    DUPLICATE = "duplicate"
    CHANGE = "change"
    CANCELLATION = "cancellation"
    INQUIRY = "inquiry"
    CREDIT_MEMO = "credit_memo"
    OTHER = "other"


class Classification(BaseModel):
    """A2 answer. The model decides intent, PO numbers, language; nothing else."""

    is_new_order: bool
    intent: Intent
    language: str = "en"
    po_count: int = 1
    po_numbers: list[str] = Field(default_factory=list)
    handwritten: bool = False
    reasons: list[str] = Field(default_factory=list)


class POLine(BaseModel):
    line_no: int
    customer_material: str
    description: str | None = None
    quantity: float
    uom: str
    unit_price: float | None = None
    price_uom: str | None = None
    line_total: float | None = None
    requested_date: str | None = None


class POExtraction(BaseModel):
    """A3 answer. ``confidence`` is the model's self-report; the composite score
    computed at A5 is what thresholds are applied to."""

    po_number: str | None = None
    sold_to: str | None = None
    ship_to: str | None = None
    bill_to: str | None = None
    requested_delivery_date: str | None = None
    currency: str | None = None
    lines: list[POLine] = Field(default_factory=list)
    total: float | None = None
    confidence: dict[str, float] = Field(default_factory=dict)


class PartnerMatch(BaseModel):
    role: str  # sold_to | ship_to | bill_to
    id: str
    name: str
    score: float = 1.0


class CMIRMatch(BaseModel):
    customer_material: str
    sap_material: str
    description: str | None = None
    sales_uom: str | None = None


class UomConversion(BaseModel):
    from_uom: str
    to_uom: str
    factor: float  # quantity_to = quantity_from * factor


class ValidatedLine(BaseModel):
    line_no: int
    customer_material: str
    sap_material: str | None = None
    candidates: list[CMIRMatch] = Field(default_factory=list)
    quantity: float
    uom: str
    converted_quantity: float | None = None
    converted_uom: str | None = None
    conversion_factor: float | None = None
    unit_price: float | None = None
    price_uom: str | None = None
    arithmetic_ok: bool | None = None


class Validation(BaseModel):
    sold_to: PartnerMatch | None = None
    ship_to: PartnerMatch | None = None
    bill_to: PartnerMatch | None = None
    partner_candidates: dict[str, list[PartnerMatch]] = Field(default_factory=dict)
    lines: list[ValidatedLine] = Field(default_factory=list)
    ok: bool = True


class DuplicateCandidate(BaseModel):
    sap_order: str
    po_number: str | None = None
    ship_to: str | None = None
    material: str | None = None
    quantity: float | None = None
    date: str | None = None
    score: float = 1.0


class PriceCheck(BaseModel):
    line_no: int
    sap_material: str
    po_price: float
    po_price_uom: str | None
    po_price_in_sap_uom: float
    sap_price: float
    sap_price_uom: str
    difference: float
    source: str


class Score(BaseModel):
    confidence: dict[str, float] = Field(default_factory=dict)
    low_confidence_fields: list[str] = Field(default_factory=list)
    duplicates: list[DuplicateCandidate] = Field(default_factory=list)
    price_checks: list[PriceCheck] = Field(default_factory=list)
    review_required: bool = True


class ClarificationDraft(BaseModel):
    """A6 answer: the email the reviewer may send to the customer's buyer."""

    to: list[str] = Field(default_factory=list)
    subject: str
    body: str
    reasons: list[str] = Field(default_factory=list)


class SAPItem(BaseModel):
    line_no: int
    material: str
    quantity: float
    uom: str
    customer_material: str
    unit_price: float | None = None
    price_uom: str | None = None


class SAPPayload(BaseModel):
    sold_to: str
    ship_to: str
    bill_to: str | None = None
    po_number: str
    requested_delivery_date: str | None = None
    currency: str | None = None
    items: list[SAPItem]
    idempotency_key: str
    source_case_id: str


class IncompletionItem(BaseModel):
    """One line of SAP's incompletion log for a created order."""

    field: str
    message: str
    item: int | None = None


class SAPOrderResult(BaseModel):
    created: bool
    order_number: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None
