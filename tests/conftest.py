"""Test fixtures: environment, a TestClient over the api, and runtimes built from the
two agents' test harnesses so the HTTP surface and the worker run real pipelines on
stubs and a fake model. No cloud, no Pub/Sub."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Must be set before `app.config` is imported (fail-closed key); nothing cloud-side may leak in.
os.environ.setdefault("INGREDION_API_KEY", "test-service-key")
for _name in (
    "INGREDION_MONGO_URI", "INGREDION_PLATFORM", "GOOGLE_CLOUD_PROJECT", "PUBSUB_PUSH_AUDIENCE",
    "PUBSUB_PUSH_SERVICE_ACCOUNT", "WORK_TOPIC_ORDER_INTAKE", "WORK_TOPIC_PREBILL", "EXTRACT_BUCKET", "EXTRACT_DIR",
    "EVIDENCE_BUCKET_ORDER_INTAKE", "EVIDENCE_BUCKET_PREBILL", "OUTCOMES_DATASET_ORDER_INTAKE", "OUTCOMES_DATASET_PREBILL",
):
    os.environ.pop(_name, None)

# the Order Intake harness lives beside its tests; make it importable from every test folder
sys.path.insert(0, str(Path(__file__).parent / "order_intake"))

from fastapi.testclient import TestClient  # noqa: E402

from app import runtime as app_runtime  # noqa: E402
from app.main import app  # noqa: E402
from factory.intake import Poller  # noqa: E402
from order_intake_agent.runtime import OrderIntakeRuntime  # noqa: E402
from prebill_agent.runtime import PrebillRuntime  # noqa: E402

API_KEY = "test-service-key"


def headers(user: str = "user-1", key: str = API_KEY) -> dict[str, str]:
    return {"X-API-Key": key, "X-User-Id": user}


def oi_runtime(h) -> OrderIntakeRuntime:
    """An Order Intake runtime over the ``oi_fixtures`` harness."""
    return OrderIntakeRuntime(
        ctx=h.ctx, pipeline=h.pipeline, case_store=h.store,
        poller=Poller(h.queue, h.ctx.claims, h.pipeline.process_raw, kill_switch=h.kill),
        source=h.queue, backend="memory", platform="stub",
    )


def pb_runtime(h) -> PrebillRuntime:
    """A pre-bill runtime over the ``prebill_agent.fixtures`` harness."""
    return PrebillRuntime(
        ctx=h.ctx, pipeline=h.pipeline,
        poller=Poller(h.world.sap, h.ctx.claims, h.pipeline.process_raw, kill_switch=h.kill),
        source=h.world.sap, backend="memory", platform="stub",
    )


@pytest.fixture
def client():
    app_runtime.reset()
    with TestClient(app) as c:
        yield c
    app_runtime.reset()
