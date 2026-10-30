"""Ingredion Agentic AI Factory — the ``api`` service (FastAPI on Cloud Run).

Per agent it serves (``INGREDION_AGENTS``): the event endpoint the data platform
pushes to, the review queue and the operations routes. The pipelines run in the
``worker`` service (``python -m app.worker``); on a laptop, without a work topic,
they run inline in the request.

    /events/order-intake/cases         Pub/Sub push: gold.cases.changed
    /events/prebill/invoices           Pub/Sub push: gold.orders.invoice_ready
    /api/<agent>/review/...            review queue (human gate)
    /api/<agent>/ops/...               kill switch, sweep, runtime health
    /health                            liveness, no auth

Run locally:   uvicorn app.main:app --reload --port 8100
Container:     see ../Dockerfile (same image as the worker, different command)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from factory.observability.router import build_ops_router
from factory.review import build_review_router

from . import config
from .auth import current_user
from .push_auth import require_push_auth
from .routers.events import build_events_router
from .runtime import EVENT_KINDS, agent_for, get_dispatcher, get_runtime, get_sweeper

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("ingredion")

_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def create_app(agents: list[str] | None = None) -> FastAPI:
    slugs = list(agents or config.AGENTS)
    app = FastAPI(
        title="Ingredion Agentic AI Factory · api",
        description=(
            "Event ingress, review queue and operations API for the Email Order Intake and "
            "Pre-bill Validation agents on Google Cloud."
        ),
        version="0.3.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-User-Id"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path not in _DOCS_PATHS:  # a blanket CSP breaks Swagger UI
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "success": False})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"error": "Internal server error", "success": False})

    for slug in slugs:
        agent = agent_for(slug)
        app.include_router(
            build_review_router(
                queue=lambda a=agent: get_runtime(a).ctx.review_queue,
                user_dependency=current_user,
                on_decision=lambda item, decision, a=agent: get_runtime(a).pipeline.on_decision(item, decision),
                prefix=f"/api/{slug}/review",
                agent=agent,
            )
        )
        app.include_router(
            build_ops_router(
                kill_switch=lambda a=agent: get_runtime(a).ctx.kill_switch,
                user_dependency=current_user,
                audit=lambda a=agent: get_runtime(a).ctx.audit,
                poll=lambda a=agent: get_sweeper(a).poll_once(),
                prefix=f"/api/{slug}/ops",
            )
        )
        app.include_router(
            build_events_router(
                slug=slug,
                agent=agent,
                kind=EVENT_KINDS[agent],
                runtime=lambda a=agent: get_runtime(a),
                dispatcher=get_dispatcher,
                auth_dependency=require_push_auth,
            )
        )

    @app.get("/health", tags=["ops"])
    def liveness():
        """Unauthenticated liveness probe (no upstream calls, builds nothing)."""
        return {"status": "ok", "service": "ingredion-factory-api", "version": app.version, "agents": slugs}

    return app


app = create_app()
