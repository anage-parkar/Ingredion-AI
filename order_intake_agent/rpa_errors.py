"""The Existing RPA's failure taxonomy, mapped onto the agent.

Ingredion's "NA NoTouch Error Analysis" (1 June to 31 July 2026; 1,180 failed cases,
133 Customers, 159 ship-tos; the figures quoted in SOW No. 07 section 2.2) classifies
every RPA failure into sixteen error types from the free-text error message the bot
wrote on the case. This module reproduces that classification from the raw message
and says, for each type, which agent step absorbs it, which reason code the agent
raises when the same condition recurs, and whether the design addresses it.

Used for: labelling the historical sample for the Stage 1 backtest (A-D1, A-D2), the
exception map in the docs, and fallback-mode routing when the intake is the RPA
failure record (``ErrorCategory`` is the coarse grouping the policy switches on).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from enum import StrEnum

from .models import ErrorCategory


class RPAErrorType(StrEnum):
    """Ingredion's sixteen categories, spelled as in the workbook."""

    CUSTOMER_MATERIAL_NOT_AVAILABLE = "Customer Material Not Available"
    PO_ALREADY_CREATED = "PO Already Created"
    SUM_OF_LINE_TOTAL = "Sum of Line Total Validation"
    NO_LINE_ITEMS = "No Line Level Items"
    MULTIPLE_PROFILES = "Multiple Customer Material Profiles"
    ZERO_QUANTITY = "Zero Quantity"
    DELIVERY_DATE_FORMAT = "Delivery Date Format"
    MISSING_LABEL_NAMES = "Missing Label Names"
    GRAND_TOTAL_NOT_NUMERIC = "Grand Total Not Numeric"
    MAX_LOAD = "Customer Material Exists MAX Load"
    CUSTOMER_MAPPING_MISSING = "Customer Mapping Missing"
    SALES_ORDER_NOT_GENERATED = "Sales Order Number Not Generated"
    LABEL_VALUES_NOT_EXTRACTED = "Label Values Not Extracted"
    NO_MODEL_ID = "No Model ID"
    UNIT_PRICE_NOT_NUMERIC = "Unit Price Not Numeric"
    MISCELLANEOUS = "Miscellaneous"


class FailurePoint(StrEnum):
    """Where the Existing RPA failed, in Ingredion's own terms."""

    OCR = "OCR"
    DATABASE = "Database"
    SAP = "SAP"
    DATABASE_OCR = "Database/OCR"
    UNKNOWN = "Unknown"


class Addressed(StrEnum):
    BY_DESIGN = "by design"  # the agent does not have this failure mode
    PARTLY = "partly"  # resolved when the data exists in SAP; otherwise reported, not fixed
    ROUTING = "routing"  # not an order to create: classified and closed or sent to the reviewer
    REPORTED = "reported"  # outside the agent; recorded on the case


@dataclass(frozen=True)
class RPAErrorProfile:
    error_type: RPAErrorType
    failure_point: FailurePoint
    coarse: ErrorCategory
    agent_step: str
    reason_code: str
    addressed: Addressed
    how: str


def _p(error_type, failure_point, coarse, step, code, addressed, how):
    return RPAErrorProfile(error_type, failure_point, coarse, step, code, addressed, how)


PROFILES: dict[RPAErrorType, RPAErrorProfile] = {
    p.error_type: p
    for p in (
        _p(RPAErrorType.CUSTOMER_MATERIAL_NOT_AVAILABLE, FailurePoint.DATABASE, ErrorCategory.MAPPING_DATA, "A4", "MASTER.MATERIAL_NOT_FOUND", Addressed.PARTLY,
           "A4 validates the customer material against SAP CMIR directly, so a material that exists in SAP but not in the mapping database is resolved; one missing in SAP is reported to Ingredion, not fixed (SOW 10.2)."),
        _p(RPAErrorType.PO_ALREADY_CREATED, FailurePoint.SAP, ErrorCategory.SAP, "A2 / A5", "EMAIL.DUPLICATE_SUBMISSION", Addressed.ROUTING,
           "The bot's own duplicate check: the PO number was processed before (re-sent emails, revisions such as -R2). A2 classifies the email as a duplicate or a revised PO and A5 checks existing SAP orders; the case is closed as a duplicate or sent to the reviewer, never created twice."),
        _p(RPAErrorType.SUM_OF_LINE_TOTAL, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3 / A5", "EXTRACT.LINE_TOTALS_MISMATCH", Addressed.BY_DESIGN,
           "Gemini reads line totals and the grand total in context; the arithmetic check feeds the composite confidence instead of failing the case, and a genuine difference (freight, discount, tax line) is flagged to the reviewer."),
        _p(RPAErrorType.NO_LINE_ITEMS, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A2 / A3", "EXTRACT.NO_LINES", Addressed.BY_DESIGN,
           "No per-customer model to train: Gemini reads any layout. Part of these are terms-and-conditions attachments the bot ran as POs; A2 classifies each attachment first."),
        _p(RPAErrorType.MULTIPLE_PROFILES, FailurePoint.DATABASE, ErrorCategory.MAPPING_DATA, "A4", "CMIR.MULTIPLE_MATCHES", Addressed.PARTLY,
           "A4 disambiguates the ship-to from the PO address against SAP master data; where several CMIR records still match, the candidates go to the reviewer with the evidence."),
        _p(RPAErrorType.ZERO_QUANTITY, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3 / A4", "EXTRACT.ZERO_QUANTITY", Addressed.BY_DESIGN,
           "The bot divided the ordered quantity by bag weight and pallet from SAP and got zero. A3 reads quantity and unit together; A4 converts with SAP's own factors and flags an ambiguous unit instead of writing zero."),
        _p(RPAErrorType.DELIVERY_DATE_FORMAT, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3", "EXTRACT.DATE_FORMAT", Addressed.BY_DESIGN,
           "Dates are returned in ISO form by the extraction schema whatever the PO prints (weekday names, 'Aug 4 at 10:00 hours'); an unparseable date is a flagged field, not a failed case."),
        _p(RPAErrorType.MISSING_LABEL_NAMES, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3", "EXTRACT.LOW_CONFIDENCE", Addressed.BY_DESIGN,
           "Form Recognizer labels that were never trained for the layout. Gemini extraction has no labels; a field it cannot find is reported with low confidence and a re-read."),
        _p(RPAErrorType.GRAND_TOTAL_NOT_NUMERIC, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3", "EXTRACT.NOT_NUMERIC", Addressed.BY_DESIGN,
           "The OCR label captured a terms sentence as the grand total (all 44 cases are one Customer's layout). The extraction schema types the total as a number and the arithmetic check cross-validates it."),
        _p(RPAErrorType.MAX_LOAD, FailurePoint.DATABASE_OCR, ErrorCategory.MAX_LOAD, "A3 / A5", "QTY.MAX_LOAD", Addressed.PARTLY,
           "Where the OCR misread the quantity, A3 and the unit conversion remove the error; where the PO really exceeds the material's MAX load, A5 flags the quantity for the reviewer instead of failing the case."),
        _p(RPAErrorType.CUSTOMER_MAPPING_MISSING, FailurePoint.DATABASE, ErrorCategory.MAPPING_DATA, "A3", "EXTRACT.NO_LINES", Addressed.BY_DESIGN,
           "Ingredion's bucket for the validation 'No line level Items are not extracted properly with Model ID ...': the customer's OCR model has no usable line-item labels, which the analysis files under the database. It is an extraction failure in substance; the agent has no per-customer model, so it does not recur."),
        _p(RPAErrorType.SALES_ORDER_NOT_GENERATED, FailurePoint.SAP, ErrorCategory.SAP, "A9", "SAP.RECONCILED", Addressed.BY_DESIGN,
           "SAP returned success messages without an order number. A9 writes a submitting marker before the call, looks the order up by the customer PO number before any retry and reads the incompletion log, so a half-created order is reconciled rather than re-sent."),
        _p(RPAErrorType.LABEL_VALUES_NOT_EXTRACTED, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3", "EXTRACT.LOW_CONFIDENCE", Addressed.BY_DESIGN,
           "As for missing label names: the field is read in context or reported with low confidence."),
        _p(RPAErrorType.NO_MODEL_ID, FailurePoint.DATABASE, ErrorCategory.MAPPING_DATA, "A3 / A4", "MASTER.SOLD_TO_NOT_FOUND", Addressed.BY_DESIGN,
           "No OCR model existed for the account, so the bot never read the PO. The agent needs no per-customer model; the Customer is resolved in SAP master data."),
        _p(RPAErrorType.UNIT_PRICE_NOT_NUMERIC, FailurePoint.OCR, ErrorCategory.EXTRACTION, "A3", "EXTRACT.NOT_NUMERIC", Addressed.BY_DESIGN,
           "The price column carried the unit ('LB'). The schema separates price, currency and unit."),
        _p(RPAErrorType.MISCELLANEOUS, FailurePoint.UNKNOWN, ErrorCategory.UNKNOWN, "A1", "EXTRACT.FORMAT_ERROR", Addressed.REPORTED,
           "Logic-app or empty failures; the agent's own retry and audit trail cover them."),
    )
}

# The bot concatenates several runs and validations into one field, and Ingredion's analysis
# files such a message under ONE category. Recovered from the workbook (ship-tos that carry a
# single category are ground truth): three categories take precedence whatever their position,
# then the failure that appears FIRST in the text wins. "Customer Mapping Missing" (29 cases)
# is not derivable from the text at all; Ingredion assigned it from the mapping database, so
# those cases land here under the extraction failure the message actually reports.
_RULES: tuple[tuple[RPAErrorType, re.Pattern[str]], ...] = (
    (RPAErrorType.MULTIPLE_PROFILES, re.compile(r"multiple profiles available", re.I)),
    (RPAErrorType.CUSTOMER_MATERIAL_NOT_AVAILABLE, re.compile(r"customer mapping material details are not available", re.I)),
    (RPAErrorType.DELIVERY_DATE_FORMAT, re.compile(r"delivery date|date format conversion issue", re.I)),
    (RPAErrorType.PO_ALREADY_CREATED, re.compile(r"already (?:been )?processed by bot", re.I)),
    (RPAErrorType.SUM_OF_LINE_TOTAL, re.compile(r"sum of line total", re.I)),
    (RPAErrorType.GRAND_TOTAL_NOT_NUMERIC, re.compile(r"grand total is not numeric", re.I)),
    (RPAErrorType.ZERO_QUANTITY, re.compile(r"zero quantity error", re.I)),
    (RPAErrorType.MAX_LOAD, re.compile(r"customer material exists max load", re.I)),
    (RPAErrorType.SALES_ORDER_NOT_GENERATED, re.compile(r"salesordernumber could not be generated", re.I)),
    (RPAErrorType.NO_MODEL_ID, re.compile(r"no model id exists", re.I)),
    (RPAErrorType.UNIT_PRICE_NOT_NUMERIC, re.compile(r"unit price is not a numeric", re.I)),
    (RPAErrorType.NO_LINE_ITEMS, re.compile(r"no line level items", re.I)),
    (RPAErrorType.MISSING_LABEL_NAMES, re.compile(r"label name\(s\) are not present", re.I)),
    (RPAErrorType.LABEL_VALUES_NOT_EXTRACTED, re.compile(r"label name\(s\) values are not extracted", re.I)),
)
_PRIORITY = (RPAErrorType.MULTIPLE_PROFILES, RPAErrorType.CUSTOMER_MATERIAL_NOT_AVAILABLE, RPAErrorType.DELIVERY_DATE_FORMAT)
TEXT_DERIVED = frozenset(t for t, _ in _RULES) | {RPAErrorType.MISCELLANEOUS}

_SEP = "--->"


@dataclass(frozen=True)
class RPAError:
    error_type: RPAErrorType
    attachment: str | None  # the file the bot was processing when it failed
    detail: str  # the failure text, cleaned
    multi_attachment: bool  # the bot ran more than one attachment of the email through the model
    also: tuple[RPAErrorType, ...]  # other failure types present in the same message

    @property
    def profile(self) -> RPAErrorProfile:
        return PROFILES[self.error_type]

    @property
    def coarse(self) -> ErrorCategory:
        return self.profile.coarse


def normalise_message(raw: str | None) -> str:
    """HTML-escaped text with <br> separators, as exported from the case."""
    text = html.unescape(str(raw or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def classify_rpa_message(raw: str | None) -> RPAError:
    text = normalise_message(raw)
    found: dict[RPAErrorType, int] = {}
    for error_type, pattern in _RULES:
        m = pattern.search(text)
        if m:
            found[error_type] = m.start()
    ordered = [t for t in _PRIORITY if t in found] + sorted((t for t in found if t not in _PRIORITY), key=found.__getitem__)
    if ordered:
        error_type, also = ordered[0], tuple(ordered[1:])
    else:
        error_type, also = RPAErrorType.MISCELLANEOUS, ()

    segments = [s.strip() for s in text.split(_SEP)]
    attachment = None
    if len(segments) > 1 and re.search(r"\.(pdf|xlsx?|docx?|csv|txt)\s*$", segments[0], re.I):
        attachment = segments[0]
    detail = segments[-1] if segments else text
    multi_attachment = bool(re.search(r"success\s*--->", text, re.I)) or len(re.findall(r"\.pdf\s*--->", text, re.I)) > 1
    return RPAError(error_type=error_type, attachment=attachment, detail=detail, multi_attachment=multi_attachment, also=also)


def coarse_category(error_type: RPAErrorType) -> ErrorCategory:
    return PROFILES[error_type].coarse
