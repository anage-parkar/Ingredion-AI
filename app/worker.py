"""Ingredion Agentic AI Factory — the ``worker`` service.

    python -m app.worker --agent order-intake          # pull and run until SIGTERM
    python -m app.worker --agent prebill --once        # drain what is queued, then exit (jobs, tests)

One agent per process. It pulls accepted cases from the agent's work subscription,
runs the pipeline up to the human gate (and, for Agent A, after a decision the
api resumes the case itself), acknowledges on success and lets Pub/Sub redeliver
on failure. While a case runs the lease is extended, so a slow Document AI or SAP
answer never causes a second delivery mid-run. On start-up Agent A reconciles any
case left in ``submitting``.

What a redelivery means: the claim was taken at ingress and is never released
here, so a case already at the gate or beyond is acknowledged without a second
run; a case that failed before the gate is re-run from A1 / B1; a stale gold
table or an engaged kill switch is a nack with a pause. After the subscription's
maximum delivery attempts the message lands in the dead-letter topic for ops.

Cloud Run: deploy the same image with this command, CPU always allocated and
concurrency 1; the process also answers ``/health`` on ``PORT`` when one is set.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from factory import settings
from factory.dispatch import Delivery, PubSubWorkQueue, WorkQueue
from factory.platform import GoldStale

from .runtime import SLUGS, get_runtime

logger = logging.getLogger("ingredion.worker")


@dataclass
class WorkerReport:
    pulled: int = 0
    done: int = 0
    skipped: int = 0
    retried: int = 0
    halted: int = 0
    failed: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)

    def add(self, delivery: Delivery, result: str) -> None:
        setattr(self, result, getattr(self, result) + 1)
        self.results.append({"source_ref": delivery.item.source_ref, "attempt": delivery.attempt, "result": result})


class _Lease(threading.Thread):
    """Extends the ack deadline every ``every`` seconds while a case runs."""

    def __init__(self, queue: WorkQueue, delivery: Delivery, every: float, seconds: int) -> None:
        super().__init__(daemon=True, name=f"lease-{delivery.ack_id}")
        self.queue, self.delivery, self.every, self.seconds = queue, delivery, every, seconds
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(self.every):
            try:
                self.queue.extend(self.delivery, self.seconds)
            except Exception:  # the lease is best effort; the run goes on
                logger.exception("lease extension failed for %s", self.delivery.item.source_ref)

    def stop(self) -> None:
        self._stop.set()


class Worker:
    def __init__(
        self,
        runtime: Any,
        queue: WorkQueue,
        *,
        max_messages: int = 4,
        pull_timeout: float = 30.0,
        lease_seconds: int = 600,
        extend_every_seconds: float = 240.0,
        stale_retry_seconds: int = 120,
        halted_retry_seconds: int = 60,
    ) -> None:
        self.runtime = runtime
        self.queue = queue
        self.max_messages = max_messages
        self.pull_timeout = pull_timeout
        self.lease_seconds = lease_seconds
        self.extend_every_seconds = extend_every_seconds
        self.stale_retry_seconds = stale_retry_seconds
        self.halted_retry_seconds = halted_retry_seconds

    def _audit(self, ref: str, event: str, **data: Any) -> None:
        try:
            self.runtime.ctx.audit.append(ref, self.runtime.agent, "worker", event, data=data)
        except Exception:
            logger.exception("audit append failed for %s", ref)

    def handle(self, delivery: Delivery) -> str:
        rt = self.runtime
        ref = delivery.item.source_ref
        switch = rt.ctx.kill_switch
        if switch is not None and switch.is_engaged():
            self.queue.nack(delivery, delay_seconds=self.halted_retry_seconds)
            return "halted"
        existing = rt.store.get(ref)
        if existing is not None and existing.state not in rt.restartable_states:
            self._audit(ref, "event.already_processed", state=existing.state, attempt=delivery.attempt, message_id=delivery.item.message_id)
            self.queue.ack(delivery)
            return "skipped"
        lease = _Lease(self.queue, delivery, self.extend_every_seconds, self.lease_seconds)
        lease.start()
        try:
            rt.pipeline.process_raw(delivery.item.to_raw())
        except GoldStale as exc:
            self._audit(ref, "gold.stale", table=exc.table, refreshed_at=exc.refreshed_at, max_age_minutes=exc.max_age_minutes, attempt=delivery.attempt)
            logger.warning("%s: %s; retrying in %ss", ref, exc, self.stale_retry_seconds)
            self.queue.nack(delivery, delay_seconds=self.stale_retry_seconds)
            return "retried"
        except Exception as exc:
            if type(exc).__name__ == "KillSwitchEngaged":
                self.queue.nack(delivery, delay_seconds=self.halted_retry_seconds)
                return "halted"
            self._audit(ref, "run.failed", error=f"{type(exc).__name__}: {exc}", attempt=delivery.attempt)
            logger.exception("%s failed on attempt %s", ref, delivery.attempt)
            self.queue.nack(delivery)
            return "failed"
        finally:
            lease.stop()
        self.queue.ack(delivery)
        return "done"

    def run_once(self) -> WorkerReport:
        report = WorkerReport()
        while True:
            deliveries = self.queue.pull(self.max_messages, 0.0)
            if not deliveries:
                return report
            for delivery in deliveries:
                report.pulled += 1
                report.add(delivery, self.handle(delivery))

    def run_forever(self, stop: threading.Event) -> WorkerReport:
        report = WorkerReport()
        while not stop.is_set():
            try:
                deliveries = self.queue.pull(self.max_messages, self.pull_timeout)
            except Exception:
                logger.exception("pull failed; backing off")
                stop.wait(5.0)
                continue
            for delivery in deliveries:
                report.pulled += 1
                report.add(delivery, self.handle(delivery))
                if stop.is_set():
                    break
        return report


def build_queue(agent: str, subscription: str | None = None) -> WorkQueue:
    sub = subscription or settings.work_subscription(agent)
    project, _ = settings.gcp()
    if not sub or not project:
        raise SystemExit(f"the worker needs WORK_SUBSCRIPTION_{agent.upper()} and GOOGLE_CLOUD_PROJECT (Dev runs cases inline in the api)")
    return PubSubWorkQueue(project, sub)


class _Health(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        body = json.dumps({"status": "ok", "service": "ingredion-factory-worker"}).encode()
        self.send_response(200 if self.path in ("/", "/health") else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # quiet
        return


def serve_health(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), _Health)
    threading.Thread(target=server.serve_forever, daemon=True, name="health").start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.worker", description="Run one agent's pipeline from its work subscription.")
    parser.add_argument("--agent", required=True, choices=sorted(SLUGS))
    parser.add_argument("--once", action="store_true", help="drain what is queued and exit")
    parser.add_argument("--max-messages", type=int, default=4)
    parser.add_argument("--pull-timeout", type=float, default=30.0)
    parser.add_argument("--subscription", default=None, help="override WORK_SUBSCRIPTION_<AGENT>")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    agent = SLUGS[args.agent]
    runtime = get_runtime(agent)
    queue = build_queue(agent, args.subscription)
    if hasattr(runtime.pipeline, "reconcile_in_flight"):
        reconciled = runtime.pipeline.reconcile_in_flight()
        if reconciled:
            logger.info("reconciled %d case(s) left in submitting", len(reconciled))
    worker = Worker(runtime, queue, max_messages=args.max_messages, pull_timeout=args.pull_timeout)
    logger.info("worker up: agent=%s platform=%s backend=%s queue=%s", agent, runtime.platform, runtime.backend, queue.name)

    if args.once:
        report = worker.run_once()
        print(json.dumps(asdict(report), indent=2))
        return 0 if report.failed == 0 else 1

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    health = serve_health(int(os.environ["PORT"])) if os.getenv("PORT") else None
    try:
        report = worker.run_forever(stop)
    finally:
        if health is not None:
            health.shutdown()
    logger.info("worker stopped: %s", json.dumps(asdict(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
