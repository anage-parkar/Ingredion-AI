"""Agent A on the gold tables: the same world as ``oi_fixtures`` expressed as gold
rows, read through the gold connectors, run through the real pipeline."""

from __future__ import annotations

import datetime as dt

import pytest
from oi_fixtures import BUYER, MATERIAL, PO_TEXT, SHIP_TO, SOLD_TO, build, make_case

from factory.intake import OI, Poller
from factory.platform import (
    GoldStale,
    InMemoryFileStore,
    InMemoryGoldClient,
    IntegrityError,
    sha256_hex,
)
from factory.review import Decision, DecisionKind
from order_intake_agent.connectors.gold import (
    GoldCaseQueue,
    GoldSalesforceCases,
    GoldSAPMasterData,
    GoldSAPOrders,
)

FILE = "gs://ingredion-files-dev/cases/CASE-1/PO_4500123.txt"
TS = "2026-10-21T09:00:00+00:00"


def gold_world() -> tuple[InMemoryGoldClient, InMemoryFileStore]:
    client = InMemoryGoldClient()
    client.add("gold_cases.email_order_case", {
        "case_id": "CASE-1", "case_number": "00001", "status": "new", "routed_to": "agent", "cohort": "cohort-1", "customer_id": SOLD_TO,
        "customer_name": "Kraft Heinz", "subject": "PO 4500123 Kraft Heinz", "body": "Please find attached our purchase order.", "sender": BUYER,
        "received_at": TS, "updated_at": TS, "po_ref": "4500123", "order_ref": None, "source_system": "salesforce",
    })
    client.add("gold_cases.case_attachment", {
        "attachment_id": "ATT-1", "case_id": "CASE-1", "order_ref": None, "po_ref": "4500123", "kind": "po", "name": "PO_4500123.txt",
        "content_type": "text/plain", "file_uri": FILE, "sha256": sha256_hex(PO_TEXT.encode("utf-8")), "size_bytes": len(PO_TEXT), "received_at": TS,
    })
    client.add("gold_sales.customer",
        {"customer_id": SOLD_TO, "role": "sold_to", "name": "Kraft Heinz Foods", "search_name": "KRAFT HEINZ FOODS", "blocked": False, "payment_terms_days": 120, "payment_terms_code": "N120", "currency": "USD", "valid_from": "2020-01-01", "valid_to": "9999-12-31"},
        {"customer_id": "100124", "role": "sold_to", "name": "Kraft Heinz Canada", "search_name": "KRAFT HEINZ CANADA", "blocked": False, "valid_from": "2020-01-01", "valid_to": "9999-12-31"},
        {"customer_id": SHIP_TO, "role": "ship_to", "name": "Kraft Heinz Plant Champaign", "search_name": "KRAFT HEINZ PLANT CHAMPAIGN", "blocked": False, "valid_from": "2020-01-01", "valid_to": "9999-12-31"},
    )
    client.add("gold_sales.customer_material", {"sold_to": SOLD_TO, "customer_material": "KH-CS-4471", "material_id": MATERIAL, "description": "Corn Starch", "sales_uom": "LB", "valid_from": "2020-01-01", "valid_to": "9999-12-31"})
    client.add("gold_sales.material_uom",
        {"material_id": MATERIAL, "uom": "LB", "base_uom": "LB", "factor": 1.0, "lb_per_unit": 1.0},
        {"material_id": MATERIAL, "uom": "CWT", "base_uom": "LB", "factor": 100.0, "lb_per_unit": 100.0},
        {"material_id": MATERIAL, "uom": "BAG", "base_uom": "LB", "factor": 50.0, "lb_per_unit": 50.0},
    )
    client.add("gold_pricing.condition", {"condition_type": "A005", "sold_to": SOLD_TO, "material_id": MATERIAL, "rate": 0.47, "price_uom": "LB", "currency": "USD", "valid_from": "2026-01-01", "valid_to": "9999-12-31", "record": "0000123456"})
    client.add("gold_pricing.contract", {"contract_ref": "C-2026-17", "sold_to": SOLD_TO, "material_id": MATERIAL, "valid_from": "2026-01-01", "valid_to": "2026-12-31", "remaining_quantity": 1_000_000, "quantity_uom": "LB", "price": 0.47, "price_uom": "LB", "currency": "USD"})
    client.add("gold_reference.uom_conversion", {"from_uom": "CWT", "to_uom": "LB", "factor": 100.0})
    files = InMemoryFileStore({FILE: PO_TEXT.encode("utf-8")})
    return client, files


def gold_harness(**kw):
    """The ordinary harness with its four read connectors swapped for the gold ones;
    the writes still land on the stubs the assertions look at."""
    h = build(**kw)
    client, files = gold_world()
    today = dt.date(2026, 10, 30)
    h.ctx.case_queue = GoldCaseQueue(client)
    h.ctx.salesforce = GoldSalesforceCases(client, files, writer=h.sf)
    h.ctx.sap_master = GoldSAPMasterData(client)
    h.ctx.sap_orders = GoldSAPOrders(client, live=h.orders, today=lambda: today)
    return h, client, files


def test_the_happy_path_runs_on_gold_rows_exactly_as_on_the_stubs():
    h, client, _ = gold_harness()
    case = h.pipeline.process(make_case())
    assert case.state == OI.IN_REVIEW and case.flags == [] and h.sf.status_of("CASE-1") == "agent_in_progress"
    assert case.data["email"].attachments[0].name == "PO_4500123.txt"  # fetched by pointer, hash verified

    case = h.pipeline.resume(case, Decision(kind=DecisionKind.APPROVE, reviewer="reviewer-1"))
    assert case.state == OI.CASE_UPDATED and case.outcome == "AGENT_CREATED"
    payload = h.api.calls[0]
    assert (payload.sold_to, payload.ship_to, payload.items[0].material) == (SOLD_TO, SHIP_TO, MATERIAL)
    assert payload.items[0].quantity == 170_000 and payload.items[0].uom == "LB"  # CWT → LB from gold_sales.material_uom
    assert case.data["score"].price_checks[0].source.startswith("SAP condition A005")
    assert set(h.ctx.gold_refresh()) == {"gold_cases.email_order_case", "gold_cases.case_attachment", "gold_sales.customer", "gold_sales.customer_material", "gold_sales.material_uom", "gold_sales.sales_order", "gold_pricing.condition", "gold_pricing.contract"}
    tables = {q.table for q in client.queries}
    assert "gold_sales.sales_order" in tables and not any(t.startswith(("bronze", "silver")) for t in tables)


def test_a_previous_order_for_the_same_po_in_gold_is_a_possible_duplicate():
    h, client, _ = gold_harness()
    client.add("gold_sales.sales_order", {"order_ref": "SO-0999", "sold_to": SOLD_TO, "ship_to": SHIP_TO, "po_ref": "4500123", "po_source": "email", "order_date": "2026-10-20", "requested_delivery_date": "2026-11-15", "status": "open", "agent_reference": None})
    client.add("gold_sales.sales_order_item", {"order_ref": "SO-0999", "line_no": 10, "material_id": MATERIAL, "quantity": 170_000, "uom": "LB"})
    case = h.pipeline.process(make_case())
    assert case.has_flag("DUP.POSSIBLE")
    duplicates = case.data["score"].duplicates
    assert duplicates[0].sap_order == "SO-0999" and duplicates[0].score == 1.0

    gold = h.ctx.sap_orders
    assert gold.find_by_reference("CASE-0:4500123", "4500123", SOLD_TO) is None  # not in gold, not live either
    client.add("gold_sales.sales_order", {"order_ref": "SO-1234", "sold_to": SOLD_TO, "po_ref": "4500123", "order_date": "2026-10-29", "agent_reference": "CASE-0:4500123"})
    assert gold.find_by_reference("CASE-0:4500123", "4500123", SOLD_TO) == "SO-1234"
    assert gold.price(SOLD_TO, MATERIAL, "2026-11-15") == (0.47, "LB", "SAP condition A005 0000123456")
    assert gold.price(SOLD_TO, MATERIAL, "2025-06-01") is None  # before the condition's validity
    assert gold.contract(SOLD_TO, MATERIAL, "2026-11-15")["number"] == "C-2026-17"
    assert gold.availability(MATERIAL, 170_000, "LB", "2026-11-15")["available"] == 500_000  # delegated to the live connector


def test_master_data_lookups_match_the_stub_semantics():
    _, client, _ = gold_harness()
    master = GoldSAPMasterData(client)
    assert [p.id for p in master.find_partner("sold_to", "Kraft Heinz Foods")] == [SOLD_TO]
    assert [p.id for p in master.find_partner("sold_to", "Sold-to 100124 Kraft Heinz Canada")] == ["100124"]
    assert master.find_partner("ship_to", "Kraft Heinz Plant Champaign")[0].id == SHIP_TO and master.find_partner("bill_to", "") == []
    assert master.cmir(SOLD_TO, "kh-cs-4471")[0].sap_material == MATERIAL and master.cmir(SOLD_TO, "KH-NOPE") == []
    assert master.uom_conversion(MATERIAL, "CWT").factor == 100.0 and master.uom_conversion(MATERIAL, "TON") is None
    assert master.allowed_uoms(MATERIAL) == ["BAG", "CWT", "LB"]
    client.add("gold_sales.material_uom", {"material_id": "MAT-88002", "uom": "LB", "base_uom": "LB", "factor": 1.0})
    assert master.uom_conversion("MAT-88002", "CWT").factor == 100.0  # from gold_reference.uom_conversion


def test_the_case_queue_is_also_an_intake_source_and_a_stale_table_releases_the_claim():
    h, client, _ = gold_harness()
    queue = h.ctx.case_queue
    assert [c.case_id for c in queue.fetch_new(None)] == ["CASE-1"]
    raws = queue.fetch(None)
    assert raws[0].marker == TS and queue.fetch(raws[0].marker) == []

    poller = Poller(queue, h.ctx.claims, h.pipeline.process_raw, kill_switch=h.kill)
    client.set_freshness("gold_sales.customer", "2026-10-30T06:00:00+00:00")  # three hours old, limit 60 min
    h.ctx.sap_master = GoldSAPMasterData(client, now=lambda: dt.datetime(2026, 10, 30, 9, tzinfo=dt.UTC))
    report = poller.poll_once()
    assert report.fetched == 1 and report.failed == 1 and "older than 60 minutes" in report.errors[0]
    assert h.ctx.claims.owner_of("CASE-1") is None  # released: the sweep will take it again once gold is current
    with pytest.raises(GoldStale):
        h.ctx.sap_master.find_partner("sold_to", "Kraft Heinz Foods")


def test_an_attachment_whose_hash_does_not_match_the_gold_row_is_refused():
    h, client, files = gold_harness()
    files.put(FILE, b"tampered content")
    with pytest.raises(IntegrityError):
        h.ctx.salesforce.get_email("CASE-1")
