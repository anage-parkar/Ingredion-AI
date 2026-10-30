"""Builders both agent runtimes share: the model stack, the stores, the platform
clients. Each reads the environment through ``factory.settings`` at call time and
imports cloud SDKs lazily, so Dev and the tests build everything in memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import settings
from .audit import AuditTrail, InMemoryAuditTrail, MongoAuditTrail
from .guardrails import default_chain
from .intake import ClaimRegistry, InMemoryClaimRegistry, MongoClaimRegistry
from .model_gateway import (
    CompositeReader,
    DocumentAIReader,
    ExcelReader,
    GuardedExtractor,
    PlainTextReader,
    StructuredExtractor,
    VertexStructuredExtractor,
    WordReader,
)
from .observability import (
    CompositeKillSwitch,
    EnvKillSwitch,
    InMemoryKillSwitch,
    KillSwitch,
    MongoKillSwitch,
)
from .platform import (
    BigQueryGoldClient,
    BigQueryOutcomeSink,
    EvidenceStore,
    FileStore,
    GcsEvidenceStore,
    GcsFileStore,
    GoldClient,
    InMemoryEvidenceStore,
    InMemoryFileStore,
    InMemoryOutcomeSink,
    LocalEvidenceStore,
    OutcomeSink,
)
from .review import InMemoryReviewQueue, MongoReviewQueue, ReviewQueue


def build_extractor() -> StructuredExtractor:
    """Gemini on Vertex AI behind the guard chain (Model Armor when configured)."""
    return GuardedExtractor(VertexStructuredExtractor(), default_chain())


def build_layout_reader() -> CompositeReader:
    """Text, Excel and Word without a cloud call; Document AI for PDFs and scans when a processor is set."""
    readers: list[Any] = [PlainTextReader(), ExcelReader(), WordReader()]
    if settings.document_ai_processor():
        readers.append(DocumentAIReader())
    return CompositeReader(readers)


@dataclass
class Stores:
    audit: AuditTrail
    review: ReviewQueue
    claims: ClaimRegistry
    kill: KillSwitch
    backend: str
    db: Any = None


def _mongo_db(uri: str) -> Any:
    from pymongo import MongoClient
    from pymongo.errors import ConfigurationError

    client = MongoClient(uri)
    try:
        return client.get_default_database()
    except ConfigurationError:
        return client["ingredion"]


def build_stores(agent: str) -> Stores:
    """Mongo-backed audit, review queue, claims and kill switch when ``INGREDION_MONGO_URI``
    is set; in-memory otherwise. The review queue and the audit trail are shared by both
    agents; claims and the kill switch key are per agent."""
    uri = settings.mongo_uri()
    if uri:
        db = _mongo_db(uri)
        claims_collection = "factory_claims" if agent == "order_intake" else f"factory_claims_{agent}"
        return Stores(
            audit=MongoAuditTrail(db["factory_audit"]),
            review=MongoReviewQueue(db["factory_review"]),
            claims=MongoClaimRegistry(db[claims_collection]),
            kill=CompositeKillSwitch([EnvKillSwitch(), MongoKillSwitch(db["factory_kill_switch"], key=agent)]),
            backend="mongo",
            db=db,
        )
    return Stores(
        audit=InMemoryAuditTrail(),
        review=InMemoryReviewQueue(),
        claims=InMemoryClaimRegistry(),
        kill=CompositeKillSwitch([EnvKillSwitch(), InMemoryKillSwitch()]),
        backend="memory",
    )


def build_evidence_store(agent: str) -> EvidenceStore:
    bucket = settings.evidence_bucket(agent)
    if bucket:
        return GcsEvidenceStore(bucket)
    folder = settings.evidence_dir(agent)
    if folder:
        return LocalEvidenceStore(folder)
    return InMemoryEvidenceStore()


def build_outcome_sink(agent: str) -> OutcomeSink:
    dataset = settings.outcomes_dataset(agent)
    if dataset:
        project = settings.gold_project()
        if not project:
            raise RuntimeError(f"OUTCOMES_DATASET_{agent.upper()} is set but no project is configured (GOOGLE_CLOUD_PROJECT)")
        return BigQueryOutcomeSink(project, dataset)
    return InMemoryOutcomeSink()


def build_gold_client() -> GoldClient:
    project = settings.gold_project()
    if not project:
        raise RuntimeError("INGREDION_PLATFORM=gold needs GOLD_PROJECT or GOOGLE_CLOUD_PROJECT")
    return BigQueryGoldClient(project, dataset_suffix=settings.gold_dataset_suffix())


def build_file_store() -> FileStore:
    return GcsFileStore() if settings.platform() == "gold" else InMemoryFileStore()


__all__ = [
    "Stores",
    "build_evidence_store",
    "build_extractor",
    "build_file_store",
    "build_gold_client",
    "build_layout_reader",
    "build_outcome_sink",
    "build_stores",
]
