"""The factory's HTTP surface mounted per agent: review queue, kill switch, sweep."""

from __future__ import annotations

import pytest
from conftest import headers, oi_runtime
from oi_fixtures import build as build_oi
from oi_fixtures import make_case

from app.runtime import get_runtime, set_runtime
from factory.model_gateway import FakeStructuredExtractor
from factory.review import ReviewField, ReviewItem
from order_intake_agent.runtime import build_runtime


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.delenv("INGREDION_MONGO_URI", raising=False)
    rt = build_runtime(extractor=FakeStructuredExtractor())
    set_runtime("order_intake", rt)
    yield rt
    set_runtime("order_intake", None)


def _enqueue(rt, case_id="CASE-9", agent="order_intake"):
    return rt.ctx.review_queue.enqueue(
        ReviewItem(case_id=case_id, agent=agent, summary="PO 1 · 1 line", fields=[ReviewField("po_number", "1", 0.9)], source_ref="1")
    )


def test_review_routes_require_the_service_key(client, runtime):
    assert client.get("/api/order-intake/review/items").status_code == 401
    assert client.get("/api/order-intake/ops/kill-switch").status_code == 401
    assert client.post("/api/order-intake/ops/poll").status_code == 401


def test_review_queue_list_get_and_decide(client, runtime):
    item = _enqueue(runtime)
    listed = client.get("/api/order-intake/review/items", headers=headers("reviewer-1")).json()["items"]
    assert [i["id"] for i in listed] == [item.id]
    assert client.get(f"/api/order-intake/review/items/{item.id}", headers=headers()).json()["item"]["summary"] == "PO 1 · 1 line"

    r = client.post(f"/api/order-intake/review/items/{item.id}/decision", json={"kind": "reject"}, headers=headers("reviewer-1"))
    assert r.status_code == 422  # a reason is required to reject
    r = client.post(f"/api/order-intake/review/items/{item.id}/decision", json={"kind": "correct", "corrections": {}}, headers=headers("reviewer-1"))
    assert r.status_code == 422  # corrections are required to correct

    r = client.post(f"/api/order-intake/review/items/{item.id}/decision", json={"kind": "approve"}, headers=headers("reviewer-1"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["item"]["status"] == "decided" and body["item"]["decision"]["reviewer"] == "reviewer-1"
    assert "error" in body["resume"]  # no such case in the store: the decision is kept, the problem reported

    assert client.post(f"/api/order-intake/review/items/{item.id}/decision", json={"kind": "approve"}, headers=headers()).status_code == 409
    assert client.get("/api/order-intake/review/items/nope", headers=headers()).status_code == 404
    assert client.get("/api/order-intake/review/items", headers=headers()).json()["items"] == []  # default filter: open


def test_each_agent_sees_only_its_own_items_on_a_shared_queue(client, runtime):
    """One review collection in Mongo; the pre-bill surface must never show an Order
    Intake item, nor decide it."""
    prebill = get_runtime("prebill")
    prebill.ctx.review_queue = runtime.ctx.review_queue  # shared store, as in the project
    a_item = _enqueue(runtime, "CASE-A", agent="order_intake")
    b_item = _enqueue(runtime, "809-1", agent="prebill")

    assert [i["id"] for i in client.get("/api/order-intake/review/items", headers=headers()).json()["items"]] == [a_item.id]
    assert [i["id"] for i in client.get("/api/prebill/review/items", headers=headers()).json()["items"]] == [b_item.id]
    assert client.get(f"/api/prebill/review/items/{a_item.id}", headers=headers()).status_code == 404
    assert client.post(f"/api/prebill/review/items/{a_item.id}/decision", json={"kind": "approve"}, headers=headers()).status_code == 404
    assert runtime.ctx.review_queue.get(a_item.id).status == "open"


def test_kill_switch_is_controlled_and_audited(client, runtime):
    assert client.get("/api/order-intake/ops/kill-switch", headers=headers()).json()["kill_switch"]["engaged"] is False
    assert client.post("/api/order-intake/ops/kill-switch", json={"engaged": True}, headers=headers()).status_code == 422
    before = runtime.ctx.audit.count()

    r = client.post("/api/order-intake/ops/kill-switch", json={"engaged": True, "reason": "drill"}, headers=headers("ops-1"))
    state = r.json()["kill_switch"]
    assert state["engaged"] is True and state["by"] == "ops-1"
    assert runtime.ctx.kill_switch.is_engaged()
    assert runtime.ctx.audit.count() == before + 1

    r = client.post("/api/order-intake/ops/kill-switch", json={"engaged": False, "reason": "drill over"}, headers=headers("ops-1"))
    assert r.json()["kill_switch"]["engaged"] is False
    health = client.get("/api/order-intake/ops/health", headers=headers()).json()
    assert health["audit_records"] == before + 2


def test_sweep_claims_and_dispatches_queued_cases_once(client):
    h = build_oi()
    set_runtime("order_intake", oi_runtime(h))
    h.queue.add(make_case())

    first = client.post("/api/order-intake/ops/poll", headers=headers("ops-1")).json()["poll"]
    assert (first["fetched"], first["dispatched"], first["skipped"]) == (1, 1, 0)
    assert h.review.count("open") == 1 and h.ctx.claims.owner_of("CASE-1") == "order_intake:sweep"

    again = client.post("/api/order-intake/ops/poll", headers=headers("ops-1")).json()["poll"]
    assert again["fetched"] == 0 and h.review.count("open") == 1

    h.kill.engage("ops", "drill")
    assert client.post("/api/order-intake/ops/poll", headers=headers("ops-1")).json()["poll"]["halted"] is True
