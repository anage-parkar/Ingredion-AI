"""Environment contract for the api and worker services.

Only the client-facing secret is required at boot (fail closed). Everything the
runtime needs (Google Cloud project, model, platform, buckets, topics) is read
lazily by ``factory.settings`` so a service can start, serve ``/health`` and answer
honestly until the project exists.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable {name!r} is not set. "
            "Refusing to start without it (see Ingredion/.env.example)."
        )
    return value


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# ── Client authentication ────────────────────────────────────────────────────
INGREDION_API_KEY: str = _require("INGREDION_API_KEY")

# ── Which agents this api instance serves (one per Cloud Run service in the project,
#    both on a laptop). Slugs: order-intake, prebill. ───────────────────────────
AGENTS: list[str] = _list("INGREDION_AGENTS", "order-intake,prebill")

# ── Pub/Sub push authentication on /events/*. Unset = Dev: the service key stands in.
PUBSUB_PUSH_AUDIENCE: str | None = os.getenv("PUBSUB_PUSH_AUDIENCE") or None
PUBSUB_PUSH_SERVICE_ACCOUNT: str | None = os.getenv("PUBSUB_PUSH_SERVICE_ACCOUNT") or None

# ── Storage ──────────────────────────────────────────────────────────────────
INGREDION_MONGO_URI: str | None = os.getenv("INGREDION_MONGO_URI") or None

# ── HTTP ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS: list[str] = _list("INGREDION_CORS_ORIGINS", "http://localhost:3000")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
