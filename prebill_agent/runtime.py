"""Wiring for a running pre-bill service in Ingredion's Google Cloud project: Gemini
on Vertex AI behind Model Armor, Document AI for PDF POs when a processor is
configured, Mongo-backed stores when configured, the evidence bucket and the
outcomes dataset. Sources: ``INGREDION_PLATFORM=gold`` reads the gold tables and the
files bucket; ``EXTRACT_BUCKET`` (or ``EXTRACT_DIR``) serves the rate files and the
TermSync history from the extract landing whatever the platform; the default
``stub`` keeps the in-memory Dev sources. Nothing here can write to an Ingredion
system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factory import settings
from factory.intake import PB, IntakeSource, Poller, RawCase
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
from .connectors import DraftInvoiceRef
from .connectors.extracts import ExtractLanding, GcsExtractLanding, LocalExtractLanding
from .connectors.gold import (
    FilesBucketMailbox,
    GoldAriba,
    GoldPROS,
    GoldRateFiles,
    GoldSalesforceOrders,
    GoldSAPBilling,
    GoldTermSync,
)
from .connectors.landing import LandingRateFiles, LandingTermSync
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

# A redelivered or swept order may be re-run from these states (no review item open yet).
RESTARTABLE_STATES = frozenset({PB.PICKED_UP, PB.EVIDENCE_ASSEMBLED, PB.PO_READ, PB.NORMALISED, PB.COMPARED, PB.EXPLAINED})


def ref_from_event(payload: dict[str, Any]) -> DraftInvoiceRef:
    """The ``gold.orders.invoice_ready`` signal (or a DraftInvoiceRef document)."""
    data = {
        "order_ref": payload.get("order_ref") or payload.get("key"),
        "invoice_ref": payload.get("invoice_ref"),
        "sold_to": payload.get("sold_to"),
        "customer_name": payload.get("customer_name") or payload.get("customer") or "",
        "billing_date": (payload.get("billing_date") or "")[:10],
        "po_ref": payload.get("po_ref"),
    }
    if not data["order_ref"]:
        raise ValueError("event has no order_ref")
    return DraftInvoiceRef.model_validate(data)


def build_landing() -> ExtractLanding | None:
    bucket = settings.extract_bucket()
    if bucket:
        return GcsExtractLanding(bucket)
    folder = settings.extract_dir()
    if folder:
        return LocalExtractLanding(folder)
    return None


@dataclass
class PrebillRuntime:
    ctx: PrebillContext
    pipeline: PrebillPipeline
    poller: Poller
    source: IntakeSource
    backend: str
    platform: str
    landing: str | None = None
    agent: str = AGENT
    restartable_states: frozenset[str] = field(default=RESTARTABLE_STATES)

    def raw_from_event(self, payload: dict[str, Any], attributes: dict[str, str] | None = None) -> RawCase:
        ref = ref_from_event(payload)
        marker = payload.get("ready_at") or payload.get("gold_refresh_ts") or (attributes or {}).get("gold_refresh_ts")
        return RawCase(source_ref=ref.order_ref, marker=marker, payload=ref.model_dump())

    @property
    def store(self) -> Any:
        return self.pipeline.store


def build_runtime(*, extractor: StructuredExtractor | None = None) -> PrebillRuntime:
    stores = build_stores(AGENT)
    platform = settings.platform()
    landing = build_landing()

    if platform == "gold":
        gold = build_gold_client()
        files = build_file_store()
        max_age = settings.gold_max_age_minutes()
        sap: Any = GoldSAPBilling(gold, max_age_minutes=max_age)
        pros: Any = GoldPROS(gold, max_age_minutes=max_age)
        salesforce: Any = GoldSalesforceOrders(gold, max_age_minutes=max_age)
        ariba: Any = GoldAriba(gold, max_age_minutes=max_age)
        termsync: Any = GoldTermSync(gold, max_age_minutes=max_age)
        rate_files: Any = GoldRateFiles(gold, max_age_minutes=max_age)
        mailbox: Any = FilesBucketMailbox(gold, files, max_age_minutes=max_age)
    elif platform == "stub":
        sap, pros, salesforce, ariba = StubSAPBilling(), StubPROS(), StubSalesforceOrders(), StubAriba()
        termsync, rate_files, mailbox = StubTermSync(), StubRateFiles(), StubMailbox()
    else:
        raise RuntimeError(f"INGREDION_PLATFORM={platform!r} is not one of stub, gold")
    if landing is not None:  # explicit extracts win for the two sources that have no interface yet
        rate_files = LandingRateFiles(landing)
        termsync = LandingTermSync(landing)

    ctx = PrebillContext(
        sap=sap, pros=pros, salesforce=salesforce, ariba=ariba, termsync=termsync, rate_files=rate_files, mailbox=mailbox,
        extractor=extractor or build_extractor(),
        layout_reader=build_layout_reader(),
        audit=stores.audit, review_queue=stores.review, claims=stores.claims, kill_switch=stores.kill,
        evidence=build_evidence_store(AGENT),
        outcomes=build_outcome_sink(AGENT),
    )
    pipeline = PrebillPipeline(ctx)
    poller = Poller(sap, stores.claims, pipeline.process_raw, kill_switch=stores.kill, owner=f"{AGENT}:poller")
    return PrebillRuntime(
        ctx=ctx, pipeline=pipeline, poller=poller, source=sap, backend=stores.backend, platform=platform,
        landing=getattr(landing, "bucket_name", None) or getattr(landing, "root", None) and str(landing.root),
    )


__all__ = ["RESTARTABLE_STATES", "PrebillRuntime", "build_landing", "build_runtime", "ref_from_event"]
