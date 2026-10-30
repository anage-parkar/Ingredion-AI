"""Authentication of Pub/Sub push deliveries on ``/events/*``.

In the Ingredion project the push subscription is configured with a service
account and an audience; Pub/Sub signs an OIDC token per delivery and the api
verifies it against Google's keys (``google-auth``), the configured audience and
the expected service-account email. Nothing else may post an event. Without
``PUBSUB_PUSH_AUDIENCE`` (Dev) the service key stands in, so a laptop can post
events with curl.

``set_verifier`` lets tests replace the token verification.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Header, HTTPException

from . import config
from .auth import require_api_key

logger = logging.getLogger("ingredion.push_auth")

Verifier = Callable[[str, str], dict[str, Any]]


def _google_verifier(token: str, audience: str) -> dict[str, Any]:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)


_verifier: Verifier = _google_verifier


def set_verifier(verifier: Verifier | None) -> None:
    """Replace the OIDC verification (tests). ``None`` restores Google's."""
    global _verifier
    _verifier = verifier or _google_verifier


def require_push_auth(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """Returns the caller identity: the push service account's email, or ``api-key`` in Dev."""
    audience = config.PUBSUB_PUSH_AUDIENCE
    if not audience:
        require_api_key(x_api_key)
        return "api-key"
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Pub/Sub push requires a bearer OIDC token")
    try:
        claims = _verifier(token.strip(), audience)
    except Exception as exc:  # expired, wrong audience, bad signature, keys unreachable
        logger.warning("push token rejected: %s", exc.__class__.__name__)
        raise HTTPException(status_code=401, detail="Invalid push token") from exc
    email = str(claims.get("email") or "")
    if not claims.get("email_verified", False) or not email:
        raise HTTPException(status_code=403, detail="Push token carries no verified identity")
    expected = config.PUBSUB_PUSH_SERVICE_ACCOUNT
    if expected and email.lower() != expected.lower():
        raise HTTPException(status_code=403, detail="Push token is not from the subscription's service account")
    return email
