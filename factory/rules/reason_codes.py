"""One reason-code catalogue for both agents.

Every exit, flag and review item carries a code from this table, so the audit
trail, the dashboards and the reviewer screen all speak the same language. The
list is the proposal for the Stage 2 agreement with Ingredion; adding a code is a
reviewed change, using an unknown one is an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .. import AGENT_ORDER_INTAKE, AGENT_PREBILL


class Routing(StrEnum):
    EXIT = "exit"  # leave to the existing rework path (Order Intake)
    REVIEW = "review"  # must be seen by a reviewer
    FLAG = "flag"  # shown to the reviewer; does not by itself force review in Phase 2
    INFO = "info"  # recorded only


@dataclass(frozen=True)
class ReasonCode:
    code: str
    routing: Routing
    agent: str
    description: str
    owner: str | None = None  # proposed owner (pre-bill RACI) or team that fixes the gap


class UnknownReasonCode(KeyError):
    pass


_OI = AGENT_ORDER_INTAKE
_PB = AGENT_PREBILL
_BOTH = "both"

_CODES: list[ReasonCode] = [
    # ── Order Intake: routing on the recorded RPA error ─────────────────────
    ReasonCode("RPA.SAP_CAUSE", Routing.EXIT, _OI, "RPA failure caused by SAP; not attempted in Release 1"),
    ReasonCode("RPA.MAX_LOAD", Routing.EXIT, _OI, "MAX load exceeded; cause to confirm in Stage 1"),
    ReasonCode("RPA.MAPPING_EXCLUDED", Routing.EXIT, _OI, "Mapping-data failure excluded by policy"),
    # ── A2: not a new order, or a format out of scope ───────────────────────
    ReasonCode("NOT_ORDER.CHANGE", Routing.EXIT, _OI, "Email is a change to an existing order"),
    ReasonCode("NOT_ORDER.CANCELLATION", Routing.EXIT, _OI, "Email is a cancellation"),
    ReasonCode("NOT_ORDER.INQUIRY", Routing.EXIT, _OI, "Email is an inquiry"),
    ReasonCode("NOT_ORDER.CREDIT_MEMO", Routing.EXIT, _OI, "Email is a credit memo or non-shipment transaction"),
    ReasonCode("NOT_ORDER.OTHER", Routing.EXIT, _OI, "Email is not an order"),
    ReasonCode("FORMAT.NON_ENGLISH", Routing.EXIT, _OI, "PO is not in English (later release)"),
    ReasonCode("FORMAT.HANDWRITTEN", Routing.EXIT, _OI, "PO is handwritten (later release)"),
    ReasonCode("FORMAT.UNREADABLE", Routing.REVIEW, _OI, "No readable PO content in the email or its attachments"),
    ReasonCode("EMAIL.MULTI_PO", Routing.REVIEW, _OI, "Email holds more than one PO; split into separate orders"),
    ReasonCode("EMAIL.REVISED_PO", Routing.REVIEW, _OI, "Revised copy of a PO already received; reviewer confirms replace or new"),
    ReasonCode("EMAIL.DUPLICATE_SUBMISSION", Routing.REVIEW, _OI, "Same PO received again in another email"),
    ReasonCode("EXCEPTION.UNRESOLVED", Routing.EXIT, _OI, "Exception cannot be cleared by a clarification; manual queue"),
    ReasonCode("SAP.INCOMPLETE", Routing.FLAG, _OI, "SAP incompletion log lists missing data on the created order"),
    # ── A3: extraction quality ──────────────────────────────────────────────
    ReasonCode("EXTRACT.REREAD", Routing.INFO, _OI, "A field failed validation; PO re-read once"),
    ReasonCode("EXTRACT.FORMAT_ERROR", Routing.REVIEW, _OI, "Model answer did not fit the schema twice"),
    ReasonCode("EXTRACT.LOW_CONFIDENCE", Routing.REVIEW, _OI, "Composite confidence below threshold"),
    ReasonCode("EXTRACT.NO_LINES", Routing.REVIEW, _OI, "No order lines could be read"),
    ReasonCode("EXTRACT.ZERO_QUANTITY", Routing.REVIEW, _OI, "A line has zero or negative quantity"),
    ReasonCode("EXTRACT.LINE_TOTALS_MISMATCH", Routing.REVIEW, _OI, "Quantity × price does not equal the line total"),
    ReasonCode("EXTRACT.NOT_NUMERIC", Routing.REVIEW, _OI, "Total or price could not be read as a number"),
    ReasonCode("EXTRACT.DATE_FORMAT", Routing.REVIEW, _OI, "Requested date missing or unreadable"),
    ReasonCode("EXTRACT.PO_NUMBER_MISSING", Routing.REVIEW, _OI, "No PO number found"),
    ReasonCode("GUARD.BLOCKED", Routing.REVIEW, _OI, "Text failed the guardrails; the model was not called"),
    # ── A4: master data, CMIR, units ────────────────────────────────────────
    ReasonCode("MASTER.SOLD_TO_NOT_FOUND", Routing.EXIT, _OI, "Sold-to not in SAP master data", "Master-data team"),
    ReasonCode("MASTER.SHIP_TO_NOT_FOUND", Routing.EXIT, _OI, "Ship-to not in SAP master data", "Master-data team"),
    ReasonCode("MASTER.BILL_TO_NOT_FOUND", Routing.EXIT, _OI, "Bill-to not in SAP master data", "Master-data team"),
    ReasonCode("MASTER.MATERIAL_NOT_FOUND", Routing.EXIT, _OI, "No CMIR for the customer material", "Master-data team"),
    ReasonCode("MASTER.PARTNER_AMBIGUOUS", Routing.REVIEW, _OI, "More than one partner matches; reviewer chooses"),
    ReasonCode("CMIR.MULTIPLE_MATCHES", Routing.REVIEW, _OI, "More than one CMIR record; reviewer chooses"),
    ReasonCode("UOM.NO_CONVERSION", Routing.REVIEW, _OI, "SAP holds no conversion for this unit and material", "Master-data team"),
    ReasonCode("UOM.INVALID", Routing.REVIEW, _OI, "Unit not allowed for this material"),
    ReasonCode("UOM.AMBIGUOUS", Routing.REVIEW, _OI, "Unit is ambiguous (for example 'ton'); never assumed"),
    # ── A5: duplicates and business checks ──────────────────────────────────
    ReasonCode("DUP.POSSIBLE", Routing.REVIEW, _OI, "An SAP order with the same key fields exists"),
    ReasonCode("DUP.CONFIRMED", Routing.INFO, _OI, "Reviewer confirmed the duplicate; no order created"),
    ReasonCode("PRICE.PO_VS_SAP", Routing.FLAG, _OI, "PO unit price differs from the SAP price after UOM conversion"),
    ReasonCode("CONTRACT.NONE", Routing.FLAG, _OI, "No valid contract for customer and material"),
    ReasonCode("CONTRACT.OUTSIDE_TERMS", Routing.FLAG, _OI, "PO is outside the contract terms"),
    ReasonCode("ATP.SHORT", Routing.FLAG, _OI, "Availability check short of the requested quantity"),
    ReasonCode("ALLOC.EXCEEDED", Routing.FLAG, _OI, "Allocation limit exceeded"),
    ReasonCode("QTY.MAX_LOAD", Routing.FLAG, _OI, "Ordered quantity exceeds the material's MAX load (the Existing RPA failed these; the agent flags them)"),
    ReasonCode("PRODUCT.RESTRICTED", Routing.FLAG, _OI, "Restricted product or not sold to this customer"),
    # ── Gate and writes ─────────────────────────────────────────────────────
    ReasonCode("REVIEW.REJECTED", Routing.EXIT, _OI, "Reviewer rejected the case"),
    ReasonCode("REVIEW.CORRECTED", Routing.INFO, _OI, "Reviewer corrected one or more fields"),
    ReasonCode("REVIEW.RECHECK_FLAGGED", Routing.REVIEW, _OI, "Re-validation after correction raised a new flag"),
    ReasonCode("SAP.REJECTED", Routing.EXIT, _OI, "SAP rejected the order"),
    ReasonCode("SAP.UNAVAILABLE", Routing.EXIT, _OI, "SAP did not respond after the retry policy"),
    ReasonCode("SAP.RECONCILED", Routing.INFO, _OI, "Order found in SAP before a retry; no second submission"),
    ReasonCode("KILL_SWITCH", Routing.INFO, _BOTH, "Kill switch engaged; no new cases taken"),
    # ── Pre-bill: the five checks and their verdicts ─────────────────────────
    ReasonCode("PRICE.PO_STALE", Routing.REVIEW, _PB, "Invoice price equals the contract price; the PO is stale", "Pricing & Billing"),
    ReasonCode("PRICE.SAP_WRONG", Routing.REVIEW, _PB, "Invoice price differs from the contract price; SAP side to fix", "Pricing & Billing"),
    ReasonCode("PRICE.MISSING_SAP", Routing.REVIEW, _PB, "No SAP or contract price to compare; flagged, not fixed here", "Pricing & Billing"),
    ReasonCode("FREIGHT.NOT_ON_PO", Routing.REVIEW, _PB, "Freight charged but not on the PO", "O2C ownership"),
    ReasonCode("FREIGHT.SAP_WRONG", Routing.REVIEW, _PB, "Freight charged against the agreed terms", "O2C ownership"),
    ReasonCode("FREIGHT.NO_TERMS", Routing.REVIEW, _PB, "No freight terms found to judge the charge", "O2C ownership"),
    ReasonCode("SURCHARGE.NOT_ON_PO", Routing.REVIEW, _PB, "Fuel surcharge charged but not on the PO", "Pricing & Billing"),
    ReasonCode("SURCHARGE.SAP_WRONG", Routing.REVIEW, _PB, "Fuel surcharge charged against the agreement", "Pricing & Billing"),
    ReasonCode("SURCHARGE.NO_TERMS", Routing.REVIEW, _PB, "No surcharge terms found to judge the charge", "Pricing & Billing"),
    ReasonCode("QTY.OVER", Routing.REVIEW, _PB, "Shipped quantity above the PO range", "Customer Service"),
    ReasonCode("QTY.UNDER", Routing.REVIEW, _PB, "Shipped quantity below the PO range", "Customer Service"),
    ReasonCode("TERMS.PO_STALE", Routing.REVIEW, _PB, "Invoice terms equal the contract; the PO is stale", "AR & Collections"),
    ReasonCode("TERMS.SAP_WRONG", Routing.REVIEW, _PB, "Invoice terms differ from the contract; SAP or PROS to fix", "AR & Collections"),
    ReasonCode("TERMS.MISSING", Routing.REVIEW, _PB, "No contract terms to compare", "AR & Collections"),
    ReasonCode("LINE.UNPAIRED", Routing.REVIEW, _PB, "Invoice line with no matching PO line", "Customer Service"),
    ReasonCode("PO.NOT_FOUND", Routing.REVIEW, _PB, "No PO in any structured source or mailbox", "PoC lead / IT data owners"),
    ReasonCode("DATA.MISSING", Routing.REVIEW, _PB, "Evidence missing; never treated as matched", "PoC lead / IT data owners"),
]

CATALOGUE: dict[str, ReasonCode] = {c.code: c for c in _CODES}
assert len(CATALOGUE) == len(_CODES), "duplicate reason code"


def get(code: str) -> ReasonCode:
    try:
        return CATALOGUE[code]
    except KeyError as exc:
        raise UnknownReasonCode(code) from exc


def exists(code: str) -> bool:
    return code in CATALOGUE


def routing(code: str) -> Routing:
    return get(code).routing


def for_agent(agent: str) -> list[ReasonCode]:
    return [c for c in _CODES if c.agent in (agent, _BOTH)]
