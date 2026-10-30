"""In-memory connectors for Dev and tests. They behave like the real systems in the
ways the pipeline depends on (claims visible, orders findable after a timeout,
duplicates by key fields, incompletion log per order) and nothing more."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factory.intake.poller import RawCase

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
from . import SAPTimeout, SAPUnavailable


class StubCaseQueue:
    """Salesforce email-order cases routed to the agent; also an ``IntakeSource``."""

    name = "salesforce_case_queue"

    def __init__(self, cases: list[IntakeCase] | None = None) -> None:
        self.rows: list[IntakeCase] = list(cases or [])

    def add(self, case: IntakeCase) -> None:
        self.rows.append(case)

    def fetch_new(self, after: Any) -> list[IntakeCase]:
        start = -1 if after is None else int(after)
        return [c for i, c in enumerate(self.rows) if i > start]

    def fetch(self, after: Any) -> list[RawCase]:
        start = -1 if after is None else int(after)
        return [RawCase(source_ref=c.case_id, marker=i, payload=c.model_dump(mode="json")) for i, c in enumerate(self.rows) if i > start]


class StubFailureRecord(StubCaseQueue):
    """Transition period: the RPA failure record as the intake (fallback mode)."""

    name = "rpa_failure_record"

    def fetch_failures(self, after: Any) -> list[IntakeCase]:
        return self.fetch_new(after)


@dataclass
class StubSalesforce:
    emails: dict[str, EmailBundle] = field(default_factory=dict)
    statuses: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    completed: dict[str, dict[str, Any]] = field(default_factory=dict)
    returned: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_email(self, case_id: str) -> EmailBundle:
        if case_id not in self.emails:
            raise KeyError(f"no Salesforce case {case_id}")
        return self.emails[case_id]

    def set_status(self, case_id: str, status: str, note: str = "") -> None:
        self.statuses.setdefault(case_id, []).append((status, note))

    def complete(self, case_id: str, order_numbers: list[str], outcome: str, note: str, follow_ups: list[str] | None = None) -> None:
        self.completed[case_id] = {"order_numbers": list(order_numbers), "outcome": outcome, "note": note, "follow_ups": list(follow_ups or [])}
        self.set_status(case_id, "completed", note)

    def return_case(self, case_id: str, reason_codes: list[str], note: str) -> None:
        self.returned[case_id] = {"reason_codes": list(reason_codes), "note": note}
        self.set_status(case_id, "manual_queue", note)

    def status_of(self, case_id: str) -> str | None:
        history = self.statuses.get(case_id)
        return history[-1][0] if history else None


@dataclass
class StubSAPMasterData:
    partners: dict[str, list[PartnerMatch]] = field(default_factory=dict)  # role -> partners
    cmir_records: dict[tuple[str, str], list[CMIRMatch]] = field(default_factory=dict)  # (sold_to, cust mat)
    conversions: dict[tuple[str, str], UomConversion] = field(default_factory=dict)  # (material, from uom)
    allowed: dict[str, list[str]] = field(default_factory=dict)

    def find_partner(self, role: str, text: str) -> list[PartnerMatch]:
        if not text:
            return []
        needle = text.casefold()
        return [p for p in self.partners.get(role, []) if p.name.casefold() in needle or p.id.casefold() in needle]

    def cmir(self, sold_to: str, customer_material: str) -> list[CMIRMatch]:
        return list(self.cmir_records.get((sold_to, customer_material.strip().upper()), []))

    def uom_conversion(self, sap_material: str, from_uom: str) -> UomConversion | None:
        return self.conversions.get((sap_material, from_uom.upper()))

    def allowed_uoms(self, sap_material: str) -> list[str]:
        return list(self.allowed.get(sap_material, []))


@dataclass
class StubSAPOrders:
    orders: list[dict[str, Any]] = field(default_factory=list)
    prices: dict[tuple[str, str], tuple[float, str, str]] = field(default_factory=dict)  # (sold_to, mat)
    contracts: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    stock: dict[str, float] = field(default_factory=dict)  # material -> available quantity

    def record(self, **order: Any) -> None:
        self.orders.append(order)

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
    ) -> list[DuplicateCandidate]:
        out: list[DuplicateCandidate] = []
        for o in self.orders:
            if o.get("sold_to") != sold_to:
                continue
            same_po = bool(po_number) and o.get("po_number") == po_number
            same_lines = (
                o.get("material") in materials
                and o.get("quantity") in quantities
                and (ship_to is None or o.get("ship_to") == ship_to)
                and (date is None or o.get("date") == date)
            )
            if same_po or same_lines:
                out.append(
                    DuplicateCandidate(
                        sap_order=o["order_number"], po_number=o.get("po_number"), ship_to=o.get("ship_to"),
                        material=o.get("material"), quantity=o.get("quantity"), date=o.get("date"), score=1.0 if same_po else 0.8,
                    )
                )
        return out

    def find_by_reference(self, idempotency_key: str, po_number: str | None, sold_to: str | None) -> str | None:
        for o in self.orders:
            if o.get("idempotency_key") == idempotency_key:
                return o["order_number"]
        return None

    def price(self, sold_to: str, sap_material: str, date: str | None) -> tuple[float, str, str] | None:
        return self.prices.get((sold_to, sap_material))

    def contract(self, sold_to: str, sap_material: str, date: str | None) -> dict[str, Any] | None:
        return self.contracts.get((sold_to, sap_material))

    def availability(self, sap_material: str, quantity: float, uom: str, date: str | None) -> dict[str, Any] | None:
        if sap_material not in self.stock:
            return None
        return {"available": self.stock[sap_material], "uom": uom, "date": date or str(date.today())}


class StubSAPOrderAPI:
    """Scripted behaviour per call: ``"created"``, ``"rejected:<message>"``, ``"timeout"``,
    ``"unavailable"`` or ``"timeout_but_created"`` (SAP created the order, the answer
    was lost: the case the pre-retry lookup exists for). ``incompletion`` lists the
    incompletion-log entries SAP will report for every created order."""

    def __init__(self, script: list[str] | None = None, orders: StubSAPOrders | None = None, incompletion: list[IncompletionItem] | None = None) -> None:
        self.script = list(script or [])
        self.orders = orders
        self.incompletion = list(incompletion or [])
        self.calls: list[SAPPayload] = []
        self.created: dict[str, str] = {}
        self.log_reads: list[str] = []
        self._seq = 0

    def _create(self, payload: SAPPayload) -> str:
        self._seq += 1
        number = f"SO-{1000 + self._seq}"
        self.created[payload.idempotency_key] = number
        if self.orders is not None:
            first = payload.items[0] if payload.items else None
            self.orders.record(
                order_number=number, sold_to=payload.sold_to, ship_to=payload.ship_to, po_number=payload.po_number,
                material=first.material if first else None, quantity=first.quantity if first else None,
                date=payload.requested_delivery_date, idempotency_key=payload.idempotency_key,
            )
        return number

    def create_order(self, payload: SAPPayload) -> SAPOrderResult:
        self.calls.append(payload)
        action = self.script.pop(0) if self.script else "created"
        if action == "created":
            return SAPOrderResult(created=True, order_number=self._create(payload))
        if action == "timeout_but_created":
            self._create(payload)
            raise SAPTimeout("gateway timeout after the order was created")
        if action == "timeout":
            raise SAPTimeout("gateway timeout")
        if action == "unavailable":
            raise SAPUnavailable("connection refused")
        if action.startswith("rejected"):
            return SAPOrderResult(created=False, error=action.partition(":")[2] or "rejected by SAP")
        raise ValueError(f"unknown scripted action {action!r}")

    def incompletion_log(self, order_number: str) -> list[IncompletionItem]:
        self.log_reads.append(order_number)
        return list(self.incompletion)


@dataclass
class StubGraphMail:
    drafts: list[dict[str, Any]] = field(default_factory=list)

    def create_draft(self, mailbox: str, to: list[str], subject: str, body: str, *, case_ref: str) -> str:
        draft_id = f"draft-{len(self.drafts) + 1}"
        self.drafts.append({"id": draft_id, "mailbox": mailbox, "to": list(to), "subject": subject, "body": body, "case_ref": case_ref})
        return draft_id


@dataclass
class StubAlerts:
    raised: list[dict[str, Any]] = field(default_factory=list)

    def raise_alert(self, kind: str, message: str, **data: Any) -> None:
        self.raised.append({"kind": kind, "message": message, **data})
