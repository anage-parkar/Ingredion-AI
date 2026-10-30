"""Worlds the tests and the evaluation CLI run on.

``kraft_heinz_world`` is the anchor case from the business briefing: sales order
809-6862, all four checks must be caught (price 40.14 vs 47.00 USD/CWT, a 300 USD
fuel surcharge not on the PO, 170,250 lb shipped against 170,000, Net 110 vs 120).
``clean_world`` is the same order with nothing wrong, so false alarms show up.
"""

from __future__ import annotations

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

from .connectors import DraftInvoiceRef
from .connectors.stubs import (
    StubAriba,
    StubMailbox,
    StubPROS,
    StubRateFiles,
    StubSalesforceOrders,
    StubSAPBilling,
    StubTermSync,
)
from .context import PrebillContext
from .pipeline import PrebillPipeline
from .policy import PrebillPolicy
from .schema import (
    CanonicalDoc,
    CanonicalLine,
    Charge,
    ChargeTerms,
    DocType,
    EvidenceRef,
    PriceRecord,
)

SOLD_TO = "KH-001"
MATERIAL = "MAT-77001"
ORDER = "809-6862"
PO_REF = "KH-PO-55112"


@dataclass
class World:
    ref: DraftInvoiceRef
    sap: StubSAPBilling
    pros: StubPROS
    salesforce: StubSalesforceOrders
    ariba: StubAriba
    termsync: StubTermSync
    rate_files: StubRateFiles
    mailbox: StubMailbox
    expected_flags: set[str] = field(default_factory=set)


def _invoice(*, qty: float = 170_250, price: float = 47.00, terms: int = 110, surcharge: float | None = 300.0) -> CanonicalDoc:
    charges = [Charge(type="fuel_surcharge", amount=surcharge, description="Fuel surcharge Aug 2026")] if surcharge else []
    return CanonicalDoc(
        doc_type=DocType.INVOICE, order_ref=ORDER, source="sap", currency="USD", payment_terms_days=terms,
        lines=[CanonicalLine(line_no=1, material=MATERIAL, qty=qty, qty_uom="LB", unit_price=price, price_uom="CWT", price_date="2026-08-14", description="Corn starch")],
        charges=charges,
        evidence=[
            EvidenceRef(field="line1.unit_price", system="SAP", record="condition A005 KH-001/MAT-77001 2026-08"),
            EvidenceRef(field="payment_terms_days", system="SAP", record="customer master KH-001 ZTERM N110"),
        ],
    )


def _po(*, qty: float = 170_000, qty_uom: str = "LB", price: float = 40.14, price_uom: str = "CWT", terms: int = 120, surcharge: float | None = None, tolerance_pct: float | None = None) -> CanonicalDoc:
    charges = [Charge(type="fuel_surcharge", amount=surcharge, description="Fuel surcharge")] if surcharge else []
    return CanonicalDoc(
        doc_type=DocType.PO, order_ref=PO_REF, source="ariba", currency="USD", payment_terms_days=terms,
        lines=[CanonicalLine(line_no=1, material=MATERIAL, qty=qty, qty_uom=qty_uom, unit_price=price, price_uom=price_uom, price_date="2026-07-01", tolerance_pct=tolerance_pct)],
        charges=charges,
        evidence=[EvidenceRef(field="line1.unit_price", system="Ariba", record=f"PO {PO_REF} line 1")],
    )


def _world(invoice: CanonicalDoc, po: CanonicalDoc | None, expected: set[str]) -> World:
    ref = DraftInvoiceRef(order_ref=ORDER, invoice_ref="INV-90001", sold_to=SOLD_TO, customer_name="Kraft Heinz", billing_date="2026-08-14", po_ref=PO_REF)
    sap = StubSAPBilling()
    sap.add(ref, invoice, shipment={"ship_date": "2026-08-12", "shipped_qty": invoice.lines[0].qty, "uom": "LB"})
    sap.terms[SOLD_TO] = (110, "customer master KH-001 ZTERM N110")
    pros = StubPROS(
        prices={(SOLD_TO, MATERIAL): PriceRecord(price=47.00, price_uom="CWT", currency="USD", source="PROS", record="PROS monthly price Aug 2026 KH-001/MAT-77001", valid_from="2026-08-01", valid_to="2026-08-31")},
        terms={SOLD_TO: (120, "contract KH-2026 section 4: Net 120")},
    )
    salesforce = StubSalesforceOrders(orders={ORDER: {"po_ref": PO_REF, "po_source": "ariba"}})
    ariba = StubAriba(pos={PO_REF: po} if po else {})
    rate_files = StubRateFiles(
        freight={SOLD_TO: ChargeTerms(applies=False, record="KH contract: freight prepaid, included in price")},
        surcharge={SOLD_TO: ChargeTerms(applies=True, amount=300.0, basis="flat", record="KH contract fuel surcharge schedule 2026")},
        factors={MATERIAL: {"BAG": 50.0}},
    )
    termsync = StubTermSync(history={SOLD_TO: [{"invoice": "INV-80011", "code": "Pricing Discrepancy", "date": "2026-06-02"}]})
    return World(ref, sap, pros, salesforce, ariba, termsync, rate_files, StubMailbox(), expected)


def kraft_heinz_world() -> World:
    return _world(_invoice(), _po(), {"unit_price", "fuel_surcharge", "quantity", "payment_terms"})


def clean_world() -> World:
    return _world(_invoice(), _po(qty=170_250, price=47.00, terms=110, surcharge=300.0), set())


def converted_units_world() -> World:
    """PO in bags priced per CWT, invoice in pounds priced per CWT: matched after normalisation."""
    return _world(_invoice(), _po(qty=3_405, qty_uom="BAG", price=47.00, price_uom="CWT", terms=110, surcharge=300.0), set())


def missing_po_world() -> World:
    world = _world(_invoice(), None, set())
    world.salesforce.orders[ORDER] = {"po_ref": None, "po_source": None}
    world.ref.po_ref = None
    return world


B6_ANSWER: dict[str, Any] = {
    "summary_by_category": {
        "unit_price": "The invoice carries 47.00 USD/CWT, the August PROS price; the PO still shows July's 40.14.",
        "fuel_surcharge": "A 300 USD fuel surcharge from the contract schedule is on the invoice and not on the PO.",
        "quantity": "170,250 lb shipped against a PO for 170,000 lb with no tolerance; Ariba blocks over-quantity.",
        "payment_terms": "The invoice carries Net 110; the contract and the PO say Net 120, so SAP/PROS need correcting.",
    },
    "draft_request": "Dear buyer, before invoicing order 809-6862 we need an updated PO reflecting 47.00 USD/CWT, the 300 USD fuel surcharge and 170,250 lb shipped.",
    "draft_internal_note": "AR & Collections: set KH-001 payment terms to Net 120 in SAP (PROS lacked the option).",
    "risk_note": "Sent as is, Ariba rejects the invoice for over-quantity and the price mismatch triggers a dispute.",
}


@dataclass
class Harness:
    world: World
    ctx: PrebillContext
    pipeline: PrebillPipeline
    fake: FakeStructuredExtractor
    audit: InMemoryAuditTrail
    review: InMemoryReviewQueue
    kill: InMemoryKillSwitch


def build(world: World | None = None, *, b6_answers: list[dict[str, Any]] | None = None, b3_answers: list[dict[str, Any]] | None = None, policy: PrebillPolicy | None = None) -> Harness:
    world = world or kraft_heinz_world()
    responses: dict[str, Any] = {}
    if b6_answers:
        responses["prebill/b6_explain"] = list(b6_answers)
    if b3_answers:
        responses["prebill/b3_read_po"] = list(b3_answers)
    fake = FakeStructuredExtractor(responses)
    audit, review, kill = InMemoryAuditTrail(), InMemoryReviewQueue(), InMemoryKillSwitch()
    ctx = PrebillContext(
        sap=world.sap, pros=world.pros, salesforce=world.salesforce, ariba=world.ariba, termsync=world.termsync,
        rate_files=world.rate_files, mailbox=world.mailbox,
        extractor=GuardedExtractor(fake, GuardChain([PatternGuard()])),
        layout_reader=CompositeReader([PlainTextReader()]),
        audit=audit, review_queue=review, claims=InMemoryClaimRegistry(), kill_switch=kill,
        policy=policy or PrebillPolicy(),
    )
    return Harness(world, ctx, PrebillPipeline(ctx), fake, audit, review, kill)
