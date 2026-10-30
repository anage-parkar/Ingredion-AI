"""/events: Pub/Sub push ingress for both agents, end to end through the inline
dispatcher to the review surface and back through a decision."""

from __future__ import annotations

import base64
import json

import pytest
from conftest import headers, oi_runtime, pb_runtime
from oi_fixtures import build as build_oi

from app import config, push_auth
from app.runtime import set_dispatcher, set_runtime
from factory.dispatch import WorkItem
from prebill_agent.fixtures import B6_ANSWER, kraft_heinz_world
from prebill_agent.fixtures import build as build_pb

CASE_EVENT = {"case_id": "CASE-1", "cohort": "cohort-1", "customer_name": "Kraft Heinz", "received_at": "2026-10-21T09:00:00Z", "gold_refresh_ts": "2026-10-21T09:00:30Z"}
INVOICE_EVENT = {"order_ref": "809-6862", "invoice_ref": "INV-90001", "sold_to": "KH-001", "customer_name": "Kraft Heinz", "billing_date": "2026-08-14", "po_ref": "KH-PO-55112"}


def envelope(payload, message_id="m-1", attributes=None, raw_data=None):
    data = raw_data if raw_data is not None else base64.b64encode(json.dumps(payload).encode()).decode()
    return {
        "message": {"data": data, "attributes": attributes or {}, "messageId": message_id, "publishTime": "2026-10-30T10:00:00Z"},
        "subscription": "projects/ingredion-dev/subscriptions/gold-cases-changed-agent-a",
    }


def test_case_event_runs_to_the_gate_and_the_decision_creates_the_order(client):
    h = build_oi()
    set_runtime("order_intake", oi_runtime(h))

    r = client.post("/events/order-intake/cases", json=envelope(CASE_EVENT), headers=headers())
    assert r.status_code == 204, r.text
    assert h.review.count("open") == 1 and h.ctx.claims.owner_of("CASE-1") == "order_intake:event"
    assert {"event.accepted", "event.dispatched", "case.started", "review.enqueued"} <= set(h.events())
    calls_after_first = len(h.fake.calls)

    # the same case delivered again (Pub/Sub at-least-once): acknowledged, no second run
    r = client.post("/events/order-intake/cases", json=envelope(CASE_EVENT, message_id="m-2"), headers=headers())
    assert r.status_code == 204
    assert h.review.count("open") == 1 and len(h.fake.calls) == calls_after_first
    assert h.events().count("event.duplicate") == 1

    items = client.get("/api/order-intake/review/items", headers=headers("reviewer-1")).json()["items"]
    assert len(items) == 1 and items[0]["source_ref"] == "4500123"
    r = client.post(f"/api/order-intake/review/items/{items[0]['id']}/decision", json={"kind": "approve"}, headers=headers("reviewer-1"))
    assert r.status_code == 200 and r.json()["resume"]["state"] == "case_updated"
    assert h.sf.completed["CASE-1"]["order_numbers"] == ["SO-1001"]


def test_invoice_event_runs_prebill_and_lands_on_its_own_review_surface(client):
    h = build_pb(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    set_runtime("prebill", pb_runtime(h))

    r = client.post("/events/prebill/invoices", json=envelope(INVOICE_EVENT), headers=headers())
    assert r.status_code == 204, r.text
    items = client.get("/api/prebill/review/items", headers=headers("pricing-lead")).json()["items"]
    assert len(items) == 1 and items[0]["source_ref"] == "809-6862"
    assert items[0]["owner"] == "Ingredion owner (CBA, Sales, PROS for price)"
    assert client.get("/api/order-intake/review/items", headers=headers()).json()["items"] == []

    r = client.post(f"/api/prebill/review/items/{items[0]['id']}/decision", json={"kind": "approve", "reason": "confirmed"}, headers=headers("pricing-lead"))
    assert r.status_code == 200 and r.json()["resume"]["state"] == "recorded"


def test_events_need_auth_and_reject_what_is_not_an_event(client):
    h = build_oi()
    set_runtime("order_intake", oi_runtime(h))
    assert client.post("/events/order-intake/cases", json=envelope(CASE_EVENT)).status_code == 401
    assert client.post("/events/order-intake/cases", json=envelope(CASE_EVENT), headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/events/order-intake/cases", json=envelope({}, raw_data="not base64!"), headers=headers()).status_code == 400
    assert client.post("/events/order-intake/cases", json=envelope({"cohort": "x"}), headers=headers()).status_code == 400
    assert client.post("/events/order-intake/cases", json={"nope": 1}, headers=headers()).status_code == 422
    assert h.ctx.claims.count() == 0 and h.review.count() == 0


def test_event_is_refused_while_the_kill_switch_is_engaged(client):
    h = build_oi()
    set_runtime("order_intake", oi_runtime(h))
    h.kill.engage("ops", "drill")
    r = client.post("/events/order-intake/cases", json=envelope(CASE_EVENT), headers=headers())
    assert r.status_code == 503 and "kill switch" in r.json()["error"]
    assert h.ctx.claims.count() == 0


def test_a_failed_hand_over_releases_the_claim_so_the_retry_can_run(client):
    h = build_oi()
    set_runtime("order_intake", oi_runtime(h))

    class Broken:
        name = "broken"

        def submit(self, item: WorkItem) -> str:
            raise ConnectionError("topic unreachable")

    set_dispatcher(Broken())
    r = client.post("/events/order-intake/cases", json=envelope(CASE_EVENT), headers=headers())
    assert r.status_code == 503
    assert h.ctx.claims.owner_of("CASE-1") is None and "event.dispatch_failed" in h.events()

    set_dispatcher(None)  # back to inline: the redelivery now runs
    assert client.post("/events/order-intake/cases", json=envelope(CASE_EVENT, message_id="m-2"), headers=headers()).status_code == 204
    assert h.review.count("open") == 1


def test_an_unknown_case_fails_inline_and_the_claim_is_released(client):
    h = build_oi()  # the stub Salesforce only knows CASE-1
    set_runtime("order_intake", oi_runtime(h))
    r = client.post("/events/order-intake/cases", json=envelope({**CASE_EVENT, "case_id": "CASE-404"}), headers=headers())
    assert r.status_code == 503 and h.ctx.claims.owner_of("CASE-404") is None


@pytest.fixture
def oidc(monkeypatch):
    monkeypatch.setattr(config, "PUBSUB_PUSH_AUDIENCE", "https://api.ingredion.example/events/order-intake/cases")
    monkeypatch.setattr(config, "PUBSUB_PUSH_SERVICE_ACCOUNT", "pubsub-push-a@ingredion-dev.iam.gserviceaccount.com")

    def verify(token: str, audience: str) -> dict:
        assert audience == config.PUBSUB_PUSH_AUDIENCE
        if token == "good":
            return {"email": "pubsub-push-a@ingredion-dev.iam.gserviceaccount.com", "email_verified": True, "aud": audience}
        if token == "other-sa":
            return {"email": "someone-else@ingredion-dev.iam.gserviceaccount.com", "email_verified": True}
        raise ValueError("Token used too early or signature invalid")

    push_auth.set_verifier(verify)
    yield
    push_auth.set_verifier(None)


def test_in_the_project_only_the_subscriptions_oidc_token_is_accepted(client, oidc):
    h = build_oi()
    set_runtime("order_intake", oi_runtime(h))
    url = "/events/order-intake/cases"
    assert client.post(url, json=envelope(CASE_EVENT), headers=headers()).status_code == 401  # the service key no longer suffices
    assert client.post(url, json=envelope(CASE_EVENT), headers={"Authorization": "Bearer forged"}).status_code == 401
    assert client.post(url, json=envelope(CASE_EVENT), headers={"Authorization": "Bearer other-sa"}).status_code == 403
    assert client.post(url, json=envelope(CASE_EVENT), headers={"Authorization": "Bearer good"}).status_code == 204
    accepted = [r for r in h.audit.for_case("CASE-1") if r.event == "event.accepted"][0]
    assert accepted.actor == "pubsub-push-a@ingredion-dev.iam.gserviceaccount.com"
