"""A small, realistic Order Intake world: one customer cohort, one material, stub
systems, a fake model with canned answers. Every test builds a fresh harness."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from factory.audit import InMemoryAuditTrail
from factory.guardrails import GuardChain, PatternGuard
from factory.intake import InMemoryClaimRegistry
from factory.model_gateway import (
    CompositeReader,
    FakeStructuredExtractor,
    GuardedExtractor,
    PlainTextReader,
)
from factory.observability import InMemoryKillSwitch
from factory.review import InMemoryReviewQueue
from order_intake_agent.case_store import InMemoryCaseStore
from order_intake_agent.connectors.stubs import (
    StubAlerts,
    StubCaseQueue,
    StubFailureRecord,
    StubGraphMail,
    StubSalesforce,
    StubSAPMasterData,
    StubSAPOrderAPI,
    StubSAPOrders,
)
from order_intake_agent.context import OrderIntakeContext
from order_intake_agent.models import (
    Attachment,
    CMIRMatch,
    EmailBundle,
    ErrorCategory,
    IncompletionItem,
    IntakeCase,
    PartnerMatch,
    RPAFailure,
    UomConversion,
)
from order_intake_agent.pipeline import OrderIntakePipeline
from order_intake_agent.policy import OrderIntakePolicy

SOLD_TO = "100123"
SHIP_TO = "200456"
MATERIAL = "MAT-77001"
BUYER = "buyer@kraftheinz.example"

PO_TEXT = """PURCHASE ORDER
PO Number: 4500123
Sold-to: Kraft Heinz Foods
Ship-to: Kraft Heinz Plant Champaign
Requested delivery: 2026-11-15
Line 1: KH-CS-4471 Corn Starch 1,700 CWT @ 47.00 USD/CWT = 79,900.00 USD
Currency: USD
"""

A2_OK: dict[str, Any] = {
    "is_new_order": True,
    "intent": "new_order",
    "language": "en",
    "po_count": 1,
    "po_numbers": ["4500123"],
    "handwritten": False,
    "reasons": ["subject and attachment carry PO 4500123"],
}
A3_OK: dict[str, Any] = {
    "po_number": "4500123",
    "sold_to": "Kraft Heinz Foods",
    "ship_to": "Kraft Heinz Plant Champaign",
    "bill_to": None,
    "requested_delivery_date": "2026-11-15",
    "currency": "USD",
    "lines": [
        {"line_no": 1, "customer_material": "KH-CS-4471", "description": "Corn Starch", "quantity": 1700, "uom": "CWT", "unit_price": 47.0, "price_uom": "CWT", "line_total": 79900.0}
    ],
    "total": 79900.0,
    "confidence": {"po_number": 0.95, "sold_to": 0.9, "ship_to": 0.9, "requested_delivery_date": 0.9, "currency": 0.9, "lines": 0.9},
}
A6_OK: dict[str, Any] = {
    "to": [BUYER],
    "subject": "Purchase order 4500123: price confirmation needed",
    "body": "Hello,\n\nThank you for PO 4500123. Line 1 shows 0.47 per LB; our current price is 0.50 per LB. Could you confirm or send an updated PO?\n\nKind regards,\nIngredion Customer Service",
    "reasons": ["PRICE.PO_VS_SAP"],
}


def a2_with(**changes: Any) -> dict[str, Any]:
    answer = copy.deepcopy(A2_OK)
    answer.update(changes)
    return answer


def a3_with(**changes: Any) -> dict[str, Any]:
    answer = copy.deepcopy(A3_OK)
    line_changes = changes.pop("line", None)
    answer.update(changes)
    if line_changes:
        answer["lines"][0].update(line_changes)
    return answer


def make_case(case_id: str = "CASE-1", cohort: str = "cohort-1", customer: str = "Kraft Heinz") -> IntakeCase:
    return IntakeCase(case_id=case_id, cohort=cohort, customer=customer, received_at="2026-10-21T09:00:00Z")


def make_failure(case_id: str = "CASE-1", category: ErrorCategory = ErrorCategory.EXTRACTION, detail: str = "line totals do not add up") -> RPAFailure:
    return RPAFailure(case_id=case_id, record_id=f"R-{case_id}", error_category=category, error_detail=detail, customer="Kraft Heinz")


def make_email(body: str = "Please find attached our purchase order.", subject: str = "PO 4500123 Kraft Heinz", po_text: str | None = PO_TEXT) -> EmailBundle:
    attachments = [Attachment(name="PO_4500123.txt", content_type="text/plain", content=po_text.encode("utf-8"))] if po_text else []
    return EmailBundle(subject=subject, body=body, sender=BUYER, attachments=attachments)


@dataclass
class Harness:
    ctx: OrderIntakeContext
    pipeline: OrderIntakePipeline
    fake: FakeStructuredExtractor
    sf: StubSalesforce
    master: StubSAPMasterData
    orders: StubSAPOrders
    api: StubSAPOrderAPI
    graph: StubGraphMail
    alerts: StubAlerts
    audit: InMemoryAuditTrail
    review: InMemoryReviewQueue
    kill: InMemoryKillSwitch
    store: InMemoryCaseStore
    queue: StubCaseQueue
    failure_record: StubFailureRecord
    sleeps: list[float] = field(default_factory=list)

    def events(self, case_id: str = "CASE-1") -> list[str]:
        return self.audit.events(case_id)


def build(
    *,
    a2: list[dict[str, Any]] | None = None,
    a3: list[dict[str, Any]] | None = None,
    a6: list[dict[str, Any]] | None = None,
    api_script: list[str] | None = None,
    incompletion: list[IncompletionItem] | None = None,
    policy: OrderIntakePolicy | None = None,
    email: EmailBundle | None = None,
    case_store: Any = None,
) -> Harness:
    responses: dict[str, Any] = {"order_intake/a2_classify": list(a2 or [A2_OK]), "order_intake/a3_extract": list(a3 or [A3_OK])}
    if a6 is not None:
        responses["order_intake/a6_exceptions"] = list(a6)
    fake = FakeStructuredExtractor(responses)
    sf = StubSalesforce(emails={"CASE-1": email or make_email()})
    master = StubSAPMasterData(
        partners={
            "sold_to": [PartnerMatch(role="sold_to", id=SOLD_TO, name="Kraft Heinz Foods"), PartnerMatch(role="sold_to", id="100124", name="Kraft Heinz Canada")],
            "ship_to": [PartnerMatch(role="ship_to", id=SHIP_TO, name="Kraft Heinz Plant Champaign")],
            "bill_to": [],
        },
        cmir_records={
            (SOLD_TO, "KH-CS-4471"): [CMIRMatch(customer_material="KH-CS-4471", sap_material=MATERIAL, sales_uom="LB")],
            (SOLD_TO, "KH-AMB-9"): [
                CMIRMatch(customer_material="KH-AMB-9", sap_material="MAT-88001", sales_uom="LB"),
                CMIRMatch(customer_material="KH-AMB-9", sap_material="MAT-88002", sales_uom="LB"),
            ],
        },
        conversions={
            (MATERIAL, "CWT"): UomConversion(from_uom="CWT", to_uom="LB", factor=100.0),
            (MATERIAL, "BAG"): UomConversion(from_uom="BAG", to_uom="LB", factor=50.0),
            ("MAT-88002", "CWT"): UomConversion(from_uom="CWT", to_uom="LB", factor=100.0),
        },
        allowed={MATERIAL: ["LB", "CWT", "BAG"]},
    )
    orders = StubSAPOrders(
        prices={(SOLD_TO, MATERIAL): (0.47, "LB", "SAP condition A005")},
        contracts={(SOLD_TO, MATERIAL): {"number": "C-2026-17", "valid_to": "2026-12-31", "remaining_quantity": 1_000_000}},
        stock={MATERIAL: 500_000},
    )
    api = StubSAPOrderAPI(script=api_script, orders=orders, incompletion=incompletion)
    graph, alerts, audit, review, kill = StubGraphMail(), StubAlerts(), InMemoryAuditTrail(), InMemoryReviewQueue(), InMemoryKillSwitch()
    sleeps: list[float] = []
    queue, failure_record = StubCaseQueue(), StubFailureRecord()
    store = case_store or InMemoryCaseStore()
    ctx = OrderIntakeContext(
        salesforce=sf,
        sap_master=master,
        sap_orders=orders,
        sap_order_api=api,
        extractor=GuardedExtractor(fake, GuardChain([PatternGuard()])),
        layout_reader=CompositeReader([PlainTextReader()]),
        audit=audit,
        review_queue=review,
        claims=InMemoryClaimRegistry(),
        case_queue=queue,
        failure_record=failure_record,
        graph=graph,
        draft_mailbox="orders@ingredion.example",
        kill_switch=kill,
        alerts=alerts,
        policy=policy or OrderIntakePolicy(),
        sleep=sleeps.append,
    )
    pipeline = OrderIntakePipeline(ctx, store)
    return Harness(ctx, pipeline, fake, sf, master, orders, api, graph, alerts, audit, review, kill, store, queue, failure_record, sleeps)
