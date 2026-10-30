"""The worker: pulls accepted cases, runs the pipeline, acknowledges, retries."""

from __future__ import annotations

import time

from conftest import oi_runtime, pb_runtime
from oi_fixtures import build as build_oi
from oi_fixtures import make_case

from app.worker import Worker
from factory.dispatch import InMemoryWorkQueue, WorkItem
from factory.intake import OI, RawCase
from factory.platform import GoldStale
from prebill_agent.fixtures import B6_ANSWER, kraft_heinz_world
from prebill_agent.fixtures import build as build_pb


def case_item(case_id: str = "CASE-1") -> WorkItem:
    return WorkItem.from_raw("order_intake", RawCase(case_id, "2026-10-21T09:00:30Z", make_case(case_id).model_dump(mode="json")), origin="test")


def _raise(exc):
    raise exc


def test_worker_runs_queued_cases_acks_them_and_skips_a_redelivery_after_the_gate():
    h = build_oi()
    rt = oi_runtime(h)
    queue = InMemoryWorkQueue([case_item()])
    worker = Worker(rt, queue, extend_every_seconds=0.01)

    report = worker.run_once()
    assert (report.pulled, report.done, report.failed) == (1, 1, 0) and len(queue.acked) == 1
    assert h.store.get("CASE-1").state == OI.IN_REVIEW and h.review.count("open") == 1

    queue.put(case_item())  # Pub/Sub redelivers after a lost ack
    report = worker.run_once()
    assert report.skipped == 1 and h.review.count("open") == 1 and len(queue.acked) == 2
    assert "event.already_processed" in h.events()


def test_worker_nacks_a_failed_run_and_pauses_on_stale_gold(monkeypatch):
    h = build_oi()  # the stub Salesforce has no CASE-404: A1 fails
    rt = oi_runtime(h)
    worker = Worker(rt, InMemoryWorkQueue([case_item("CASE-404")]), extend_every_seconds=0.01)
    delivery = worker.queue.pull(1, 0)[0]
    assert worker.handle(delivery) == "failed"
    assert worker.queue.nacked[-1][0].item.source_ref == "CASE-404" and len(worker.queue) == 1  # requeued for attempt 2
    assert "run.failed" in h.events("CASE-404")

    monkeypatch.setattr(rt.pipeline, "process_raw", lambda raw: _raise(GoldStale("gold_sales.customer", "2026-10-30T06:00:00+00:00", 60)))
    worker = Worker(rt, InMemoryWorkQueue([case_item()]), extend_every_seconds=0.01, stale_retry_seconds=120)
    delivery = worker.queue.pull(1, 0)[0]
    assert worker.handle(delivery) == "retried"
    assert worker.queue.nacked[-1][1] == 120 and "gold.stale" in h.events()


def test_worker_halts_while_the_kill_switch_is_engaged():
    h = build_oi()
    rt = oi_runtime(h)
    h.kill.engage("ops", "drill")
    worker = Worker(rt, InMemoryWorkQueue([case_item()]), halted_retry_seconds=60)
    delivery = worker.queue.pull(1, 0)[0]
    assert worker.handle(delivery) == "halted"
    assert worker.queue.nacked[-1][1] == 60 and h.review.count() == 0 and h.fake.calls == []


def test_the_lease_is_extended_while_a_case_runs(monkeypatch):
    h = build_oi()
    rt = oi_runtime(h)
    original = rt.pipeline.process_raw

    def slow(raw):
        time.sleep(0.08)
        return original(raw)

    monkeypatch.setattr(rt.pipeline, "process_raw", slow)
    worker = Worker(rt, InMemoryWorkQueue([case_item()]), extend_every_seconds=0.01, lease_seconds=600)
    assert worker.run_once().done == 1
    assert worker.queue.extended and worker.queue.extended[0][1] == 600


def test_prebill_worker_runs_an_invoice_to_the_owner_gate():
    h = build_pb(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    rt = pb_runtime(h)
    item = WorkItem.from_raw("prebill", RawCase("809-6862", None, h.world.ref.model_dump()))
    worker = Worker(rt, InMemoryWorkQueue([item]), extend_every_seconds=0.01)
    report = worker.run_once()
    assert report.done == 1 and h.review.count("open") == 1
    worker.queue.put(item)
    assert worker.run_once().skipped == 1


def test_work_item_survives_the_wire():
    item = case_item()
    item.message_id = "m-9"
    back = WorkItem.from_json(item.to_json())
    assert (back.agent, back.source_ref, back.marker, back.message_id, back.attributes) == ("order_intake", "CASE-1", "2026-10-21T09:00:30Z", "m-9", {"origin": "test"})
    assert back.to_raw().payload["case_id"] == "CASE-1"
