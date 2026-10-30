"""Agent B on the data platform: the Kraft Heinz anchor expressed as gold rows and as
landing-bucket extracts, read through the gold and landing connectors, run through
the real pipeline to the same four verdicts."""

from __future__ import annotations

import pytest

from factory.intake import PB, Poller
from factory.platform import InMemoryFileStore, InMemoryGoldClient, IntegrityError, sha256_hex
from factory.rules import Verdict
from prebill_agent.connectors.extracts import LocalExtractLanding
from prebill_agent.connectors.gold import (
    FilesBucketMailbox,
    GoldAriba,
    GoldPROS,
    GoldRateFiles,
    GoldSalesforceOrders,
    GoldSAPBilling,
    GoldTermSync,
)
from prebill_agent.connectors.landing import LandingRateFiles, LandingTermSync
from prebill_agent.fixtures import (
    B6_ANSWER,
    MATERIAL,
    ORDER,
    PO_REF,
    SOLD_TO,
    build,
    kraft_heinz_world,
)

PDF = b"%PDF-1.4 Kraft Heinz PO"
PDF_URI = "gs://ingredion-files-dev/cases/809-6862/KH-PO-55112.pdf"


def gold_world() -> tuple[InMemoryGoldClient, InMemoryFileStore]:
    c = InMemoryGoldClient()
    c.add("gold_billing.invoice_ready_order", {"order_ref": ORDER, "invoice_ref": "INV-90001", "sold_to": SOLD_TO, "customer_name": "Kraft Heinz", "billing_date": "2026-08-14", "po_ref": PO_REF, "ready_at": "2026-08-14T06:00:00+00:00"})
    c.add("gold_billing.billing_document",
        {"invoice_ref": "INV-90001", "order_ref": ORDER, "line_no": 1, "line_type": "item", "material_id": MATERIAL, "quantity": 170_250, "uom": "LB", "unit_price": 47.00, "price_uom": "CWT", "price_date": "2026-08-14", "description": "Corn starch", "currency": "USD", "payment_terms_days": 110, "price_record": "condition A005 KH-001/MAT-77001 2026-08", "terms_record": "customer master KH-001 ZTERM N110"},
        {"invoice_ref": "INV-90001", "order_ref": ORDER, "line_no": 2, "line_type": "charge", "charge_type": "fuel_surcharge", "amount": 300.0, "description": "Fuel surcharge Aug 2026", "currency": "USD", "payment_terms_days": 110},
    )
    c.add("gold_sales.delivery", {"delivery_ref": "80012345", "order_ref": ORDER, "line_no": 1, "ship_date": "2026-08-12", "shipped_qty": 170_250, "uom": "LB", "carrier": "XPO"})
    c.add("gold_sales.customer", {"customer_id": SOLD_TO, "role": "sold_to", "name": "Kraft Heinz", "payment_terms_days": 110, "payment_terms_code": "N110", "blocked": False, "valid_from": "2020-01-01", "valid_to": "9999-12-31"})
    c.add("gold_pricing.pros_agreement",
        {"agreement_ref": "PROS-KH-2026-08", "sold_to": SOLD_TO, "material_id": MATERIAL, "price": 47.00, "price_uom": "CWT", "currency": "USD", "valid_from": "2026-08-01", "valid_to": "2026-08-31", "record": "PROS monthly price Aug 2026 KH-001/MAT-77001"},
        {"agreement_ref": "KH-2026", "sold_to": SOLD_TO, "material_id": None, "payment_terms_days": 120, "valid_from": "2026-01-01", "valid_to": "2026-12-31", "record": "contract KH-2026 section 4: Net 120"},
    )
    c.add("gold_sales.sales_order", {"order_ref": ORDER, "sold_to": SOLD_TO, "po_ref": PO_REF, "po_source": "ariba", "order_date": "2026-07-01", "status": "shipped", "salesforce_case_id": "500KH"})
    c.add("gold_procurement.ariba_po", {"po_ref": PO_REF, "order_ref": ORDER, "sold_to": SOLD_TO, "line_no": 1, "line_type": "item", "material_id": MATERIAL, "customer_material": "KH-CS-4471", "quantity": 170_000, "uom": "LB", "tolerance_pct": None, "unit_price": 40.14, "price_uom": "CWT", "price_date": "2026-07-01", "currency": "USD", "payment_terms_days": 120})
    c.add("gold_pricing.freight_charge", {"sold_to": SOLD_TO, "applies": False, "amount": None, "basis": None, "currency": "USD", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "record": "KH contract: freight prepaid, included in price"})
    c.add("gold_pricing.fuel_rate", {"sold_to": SOLD_TO, "applies": True, "amount": 300.0, "basis": "flat", "currency": "USD", "valid_from": "2026-01-01", "valid_to": "2026-12-31", "record": "KH contract fuel surcharge schedule 2026"})
    c.add("gold_sales.material_uom", {"material_id": MATERIAL, "uom": "BAG", "base_uom": "LB", "factor": 50.0, "lb_per_unit": 50.0})
    c.add("gold_ar.dispute", {"dispute_ref": "D-1", "sold_to": SOLD_TO, "invoice_ref": "INV-80011", "code": "Pricing Discrepancy", "amount": 1200.0, "opened_at": "2026-06-02", "status": "closed"})
    c.add("gold_cases.case_attachment", {"attachment_id": "ATT-9", "case_id": "500KH", "order_ref": ORDER, "po_ref": PO_REF, "kind": "po", "name": "KH-PO-55112.pdf", "content_type": "application/pdf", "file_uri": PDF_URI, "sha256": sha256_hex(PDF), "size_bytes": len(PDF), "received_at": "2026-07-01T10:00:00+00:00"})
    return c, InMemoryFileStore({PDF_URI: PDF})


def gold_harness():
    h = build(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    client, files = gold_world()
    h.ctx.sap = GoldSAPBilling(client)
    h.ctx.pros = GoldPROS(client)
    h.ctx.salesforce = GoldSalesforceOrders(client)
    h.ctx.ariba = GoldAriba(client)
    h.ctx.termsync = GoldTermSync(client)
    h.ctx.rate_files = GoldRateFiles(client)
    h.ctx.mailbox = FilesBucketMailbox(client, files)
    return h, client, files


def _failed(case):
    return {r.rule: r for r in case.data["results"] if not r.passed}


def test_kraft_heinz_is_caught_four_of_four_from_gold_rows():
    h, client, _ = gold_harness()
    ref = h.ctx.sap.list_ready(None)[0]
    assert (ref.order_ref, ref.invoice_ref, ref.billing_date, ref.po_ref) == (ORDER, "INV-90001", "2026-08-14", PO_REF)

    case = h.pipeline.process(ref)
    failed = _failed(case)
    assert set(failed) == {"unit_price", "fuel_surcharge", "quantity", "payment_terms"}
    assert failed["unit_price"].verdict == Verdict.UPDATED_PO_REQUIRED and failed["unit_price"].evidence["po_price"] == 40.14
    assert failed["quantity"].evidence["difference"] == 250 and failed["payment_terms"].verdict == Verdict.INTERNAL_FIX
    assert case.outcome == "INTERNAL_FIX_OR_MISSING_DATA" and case.state == PB.IN_REVIEW
    reference = case.data["reference"]
    assert reference.terms_source == "PROS" and reference.contract_terms_days == 120
    assert reference.contract_prices[1].source == "PROS" and reference.shipment["shipped_qty"] == 170_250
    assert reference.dispute_history[0]["code"] == "Pricing Discrepancy"
    assert case.data["po_source"] == "ariba" and case.data["invoice"].evidence[0].record.startswith("condition A005")
    assert set(h.ctx.gold_refresh()) >= {"gold_billing.billing_document", "gold_pricing.pros_agreement", "gold_procurement.ariba_po", "gold_ar.dispute"}
    assert not any(q.table.startswith(("bronze", "silver")) for q in client.queries)


def test_gold_billing_is_an_intake_source_and_the_pdf_fallback_reads_the_files_bucket():
    h, client, files = gold_harness()
    poller = Poller(h.ctx.sap, h.ctx.claims, h.pipeline.process_raw, kill_switch=h.kill)
    first = poller.poll_once()
    assert (first.fetched, first.dispatched) == (1, 1) and first.last_marker == "2026-08-14T06:00:00+00:00"
    assert poller.poll_once().fetched == 0 and h.review.count("open") == 1

    content, content_type = h.ctx.mailbox.find_po_pdf(ORDER, PO_REF)
    assert content == PDF and content_type == "application/pdf"
    assert h.ctx.mailbox.find_po_pdf("000-0000", None) is None
    files.put(PDF_URI, b"something else")
    with pytest.raises(IntegrityError):
        h.ctx.mailbox.find_po_pdf(ORDER, PO_REF)

    assert h.ctx.sap.payment_terms(SOLD_TO) == (110, "customer master KH-001 N110")
    assert h.ctx.sap.price_condition(SOLD_TO, MATERIAL, "2026-08-14") is None  # no SAP condition row: PROS wins in B2
    assert h.ctx.pros.contract_price(SOLD_TO, MATERIAL, "2026-09-14") is None  # August price only
    assert h.ctx.rate_files.material_factors(MATERIAL) == {"BAG": 50.0}
    assert h.ctx.salesforce.order(ORDER)["po_source"] == "ariba" and h.ctx.salesforce.order("nope") is None
    assert h.ctx.ariba.purchase_order(PO_REF).lines[0].unit_price == 40.14 and h.ctx.ariba.purchase_order("nope") is None


def test_rate_files_and_disputes_can_come_from_the_extract_landing(tmp_path):
    (tmp_path / "freight_terms").mkdir()
    (tmp_path / "freight_terms" / "2026-10-29.csv").write_text("sold_to,applies,amount,basis,currency,valid_from,valid_to,record\nKH-001,false,,,USD,2026-01-01,2026-12-31,KH contract: freight prepaid\n")
    (tmp_path / "fuel_surcharge").mkdir()
    (tmp_path / "fuel_surcharge" / "2026-10-29.csv").write_text("sold_to,applies,amount,basis,currency,valid_from,valid_to,record\nKH-001,true,300,flat,USD,2026-01-01,2026-12-31,KH fuel schedule 2026\nKH-001,true,250,flat,USD,2025-01-01,2025-12-31,KH fuel schedule 2025\n")
    (tmp_path / "material_factors").mkdir()
    (tmp_path / "material_factors" / "latest.csv").write_text("material,uom,lb_per_unit\nMAT-77001,BAG,50\nMAT-77001,DRUM,400\n")
    (tmp_path / "disputes").mkdir()
    (tmp_path / "disputes" / "2026-10-29.csv").write_text("sold_to,invoice,code,date,amount,status\nKH-001,INV-80011,Pricing Discrepancy,2026-06-02,1200,closed\nOTHER,INV-1,Short pay,2026-01-01,5,open\n")
    landing = LocalExtractLanding(tmp_path)
    rates, termsync = LandingRateFiles(landing), LandingTermSync(landing)

    assert rates.freight_terms(SOLD_TO, "2026-08-14").applies is False
    surcharge = rates.surcharge_terms(SOLD_TO, "2026-08-14")
    assert (surcharge.applies, surcharge.amount, surcharge.basis, surcharge.source) == (True, 300.0, "flat", "extract:fuel_surcharge")
    assert rates.surcharge_terms(SOLD_TO, "2025-03-01").amount == 250.0 and rates.surcharge_terms("NOPE", "2026-08-14") is None
    assert rates.material_factors(MATERIAL) == {"BAG": 50.0, "DRUM": 400.0}
    assert termsync.dispute_history(SOLD_TO) == [{"invoice": "INV-80011", "code": "Pricing Discrepancy", "date": "2026-06-02", "amount": 1200.0, "status": "closed"}]

    h = build(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    h.ctx.rate_files, h.ctx.termsync = rates, termsync
    case = h.pipeline.process(h.world.ref)
    assert set(_failed(case)) == {"unit_price", "fuel_surcharge", "quantity", "payment_terms"}
    assert case.data["reference"].surcharge_terms.record == "KH fuel schedule 2026"
