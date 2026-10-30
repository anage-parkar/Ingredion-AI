"""Wiring for a running Order Intake service in Ingredion's Google Cloud project.

``build_runtime`` assembles the context from the environment: Gemini on Vertex AI
behind Model Armor, Document AI for layout when a processor is configured,
Mongo-backed stores when ``INGREDION_MONGO_URI`` is set and in-memory otherwise,
the evidence bucket and the outcomes dataset when configured. Connectors:
``INGREDION_PLATFORM=gold`` reads the gold tables and the files bucket; the default
``stub`` keeps the in-memory Dev systems. The three writes (Salesforce case, SAP
order, Outlook draft) stay on the Dev stubs until the write path is approved at
Gate 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factory import settings
from factory.intake import OI, IntakeSource, Poller, RawCase
from factory.model_gateway import StructuredExtractor
from factory.wiring import (
    build_evidence_store,
    build_extractor,
    build_file_store,
    build_gold_client,
    build_layout_reader,
    build_outcome_sink,
    build_stores,
)

from . import AGENT
from .case_store import CaseStore, InMemoryCaseStore, MongoCaseStore
from .connectors.gold import GoldCaseQueue, GoldSalesforceCases, GoldSAPMasterData, GoldSAPOrders
from .connectors.stubs import (
    StubAlerts,
    StubCaseQueue,
    StubFailureRecord,
    StubGraphMail,
    StubSalesforce,
    StubSAPMasterData,
    StubSAPOrderAPI,
    StubSAPOrders,
)
from .context import OrderIntakeContext
from .models import IntakeCase
from .pipeline import OrderIntakePipeline
from .policy import OrderIntakePolicy

# States a redelivered or swept case may be re-run from (nothing written yet, no
# review item open). Anything else means the case already reached the gate or beyond.
RESTARTABLE_STATES = frozenset({OI.PICKED_UP, OI.CLASSIFIED, OI.EXTRACTED, OI.VALIDATED, OI.SCORED, OI.EXCEPTIONS})


def intake_from_event(payload: dict[str, Any]) -> IntakeCase:
    """The ``gold.cases.changed`` signal (or an IntakeCase document) as an IntakeCase."""
    data = {
        "case_id": payload.get("case_id") or payload.get("key"),
        "source": payload.get("source") or "salesforce_queue",
        "cohort": payload.get("cohort"),
        "customer": payload.get("customer") or payload.get("customer_name"),
        "received_at": payload.get("received_at"),
        "record_id": payload.get("record_id") or payload.get("case_number"),
        "error_category": payload.get("error_category"),
        "error_detail": payload.get("error_detail") or "",
    }
    if not data["case_id"]:
        raise ValueError("event has no case_id")
    return IntakeCase.model_validate(data)


@dataclass
class OrderIntakeRuntime:
    ctx: OrderIntakeContext
    pipeline: OrderIntakePipeline
    case_store: CaseStore
    poller: Poller
    source: IntakeSource
    backend: str
    platform: str
    agent: str = AGENT
    restartable_states: frozenset[str] = field(default=RESTARTABLE_STATES)

    def raw_from_event(self, payload: dict[str, Any], attributes: dict[str, str] | None = None) -> RawCase:
        intake = intake_from_event(payload)
        marker = payload.get("gold_refresh_ts") or payload.get("updated_at") or (attributes or {}).get("gold_refresh_ts")
        return RawCase(source_ref=intake.case_id, marker=marker, payload=intake.model_dump(mode="json"))

    @property
    def store(self) -> CaseStore:
        return self.case_store


def build_runtime(*, extractor: StructuredExtractor | None = None, policy: OrderIntakePolicy | None = None) -> OrderIntakeRuntime:
    stores = build_stores(AGENT)
    cases: CaseStore = MongoCaseStore(stores.db["order_intake_cases"]) if stores.db is not None else InMemoryCaseStore()

    policy = policy or OrderIntakePolicy(mode="fallback" if (settings.env("ORDER_INTAKE_MODE", "primary") or "primary").lower() == "fallback" else "primary")
    platform = settings.platform()
    failure_record = StubFailureRecord()
    salesforce_writer = StubSalesforce()  # Salesforce writes: interface confirmed in Stage 1
    sap_orders_stub = StubSAPOrders()
    sap_order_api = StubSAPOrderAPI(orders=sap_orders_stub)  # the SAP write: method approved at Gate 2
    if platform == "gold":
        gold = build_gold_client()
        files = build_file_store()
        max_age = settings.gold_max_age_minutes()
        case_queue: Any = GoldCaseQueue(gold, max_age_minutes=max_age)
        salesforce: Any = GoldSalesforceCases(gold, files, salesforce_writer, max_age_minutes=max_age)
        sap_master: Any = GoldSAPMasterData(gold, max_age_minutes=max_age)
        sap_orders: Any = GoldSAPOrders(gold, live=sap_orders_stub, max_age_minutes=max_age)
    elif platform == "stub":
        case_queue = StubCaseQueue()
        salesforce = salesforce_writer
        sap_master = StubSAPMasterData()
        sap_orders = sap_orders_stub
    else:
        raise RuntimeError(f"INGREDION_PLATFORM={platform!r} is not one of stub, gold")

    ctx = OrderIntakeContext(
        salesforce=salesforce,
        sap_master=sap_master,
        sap_orders=sap_orders,
        sap_order_api=sap_order_api,
        extractor=extractor or build_extractor(),
        layout_reader=build_layout_reader(),
        audit=stores.audit,
        review_queue=stores.review,
        claims=stores.claims,
        case_queue=case_queue,
        failure_record=failure_record,
        graph=StubGraphMail(),
        draft_mailbox=settings.graph_mailbox() or "orders@ingredion.example",
        kill_switch=stores.kill,
        alerts=StubAlerts(),
        evidence=build_evidence_store(AGENT),
        outcomes=build_outcome_sink(AGENT),
        policy=policy,
    )
    pipeline = OrderIntakePipeline(ctx, cases)
    source: IntakeSource = failure_record if policy.mode == "fallback" else case_queue
    poller = Poller(source, stores.claims, pipeline.process_raw, kill_switch=stores.kill, owner=f"{AGENT}:poller")
    return OrderIntakeRuntime(ctx=ctx, pipeline=pipeline, case_store=cases, poller=poller, source=source, backend=stores.backend, platform=platform)


__all__ = ["RESTARTABLE_STATES", "OrderIntakeRuntime", "build_runtime", "intake_from_event"]
