"""Environment-backed settings for the shared runtime.

Everything is read lazily, at call time, so tests can set or monkeypatch variables
and nothing is required at import. The platform is Ingredion's Google Cloud project
(SOW No. 07 redline v2, 20 October 2026): Vertex AI for the model, Document AI for
layout, Model Armor for guardrails, BigQuery gold tables and Cloud Storage buckets
from the data platform, Pub/Sub between the api and the worker, Cloud Trace for
tracing, Secret Manager for credentials. There is no other provider.
"""

from __future__ import annotations

import os

DEFAULT_VERTEX_MODEL = "gemini-3.8-flash"  # GA on Vertex AI since 2 Sep 2026; 2.5 Pro was retired on 16 Oct 2026


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _flag(name: str, default: str) -> bool:
    return (env(name, default) or default).strip().lower() in {"on", "1", "true", "yes"}


def _agent_key(agent: str) -> str:
    return agent.upper().replace("-", "_")


# ── Google Cloud ────────────────────────────────────────────────────────────


def gcp() -> tuple[str | None, str]:
    """(project id, location). Location defaults to us-central1."""
    return env("GOOGLE_CLOUD_PROJECT"), env("GOOGLE_CLOUD_LOCATION", "us-central1") or "us-central1"


def vertex_model() -> str:
    """The approved Gemini model on Vertex AI (allow-listed by Ingredion)."""
    return env("VERTEX_MODEL", DEFAULT_VERTEX_MODEL) or DEFAULT_VERTEX_MODEL


def vertex_controlled_generation() -> bool:
    """Send the JSON schema as ``response_schema`` (falls back to JSON mode if rejected)."""
    return _flag("VERTEX_CONTROLLED_GENERATION", "on")


def document_ai_processor() -> str | None:
    """Full processor name: projects/<p>/locations/<l>/processors/<id>."""
    return env("DOCUMENT_AI_PROCESSOR")


def model_armor_template() -> str | None:
    """Full template name: projects/<p>/locations/<l>/templates/<id>."""
    return env("MODEL_ARMOR_TEMPLATE")


def graph_mailbox() -> str | None:
    """Shared mailbox the clarification drafts are created in (Microsoft Graph)."""
    return env("GRAPH_DRAFT_MAILBOX")


# ── Data platform (gold tables, buckets) ────────────────────────────────────


def platform() -> str:
    """``stub`` (Dev stubs, default) or ``gold`` (BigQuery gold tables and the files bucket)."""
    return (env("INGREDION_PLATFORM", "stub") or "stub").strip().lower()


def gold_project() -> str | None:
    """Project that holds the gold datasets; defaults to the agent project."""
    return env("GOLD_PROJECT") or gcp()[0]


def gold_dataset_suffix() -> str:
    """Suffix the data team appends per environment (``_dev``, ``_test``); empty in Prod."""
    return env("GOLD_DATASET_SUFFIX", "") or ""


def gold_max_age_minutes() -> int | None:
    """Global override of the per-table staleness limit; unset uses the registry values."""
    value = env("GOLD_MAX_AGE_MINUTES")
    return int(value) if value else None


def files_bucket() -> str | None:
    """Bucket with the PO files, contracts and rate files the pipeline lands (read by both agents)."""
    return env("FILES_BUCKET")


def extract_bucket() -> str | None:
    """Landing bucket for scheduled CSV extracts of sources without a read interface."""
    return env("EXTRACT_BUCKET")


def extract_dir() -> str | None:
    """Local folder with the same layout as the extract bucket (Dev)."""
    return env("EXTRACT_DIR")


def evidence_bucket(agent: str) -> str | None:
    """Per-agent evidence bucket (``EVIDENCE_BUCKET_ORDER_INTAKE`` / ``EVIDENCE_BUCKET_PREBILL``)."""
    return env(f"EVIDENCE_BUCKET_{_agent_key(agent)}")


def evidence_dir(agent: str) -> str | None:
    """Local evidence folder for Dev (``EVIDENCE_DIR_<AGENT>``)."""
    return env(f"EVIDENCE_DIR_{_agent_key(agent)}")


def outcomes_dataset(agent: str) -> str | None:
    """BigQuery dataset the agent writes its outcome rows to (``OUTCOMES_DATASET_<AGENT>``)."""
    return env(f"OUTCOMES_DATASET_{_agent_key(agent)}")


# ── Pub/Sub between the api and the worker ─────────────────────────────────


def work_topic(agent: str) -> str | None:
    """Topic the api publishes accepted cases to (``WORK_TOPIC_<AGENT>``); unset runs cases inline (Dev)."""
    return env(f"WORK_TOPIC_{_agent_key(agent)}")


def work_subscription(agent: str) -> str | None:
    """Subscription the worker pulls from (``WORK_SUBSCRIPTION_<AGENT>``)."""
    return env(f"WORK_SUBSCRIPTION_{_agent_key(agent)}")


# ── Stores and controls ─────────────────────────────────────────────────────


def mongo_uri() -> str | None:
    return env("INGREDION_MONGO_URI")


def kill_switch_env() -> bool:
    """``INGREDION_KILL_SWITCH=on`` stops the agents taking new cases (read-only backend)."""
    return _flag("INGREDION_KILL_SWITCH", "off")
