"""Request authentication for the review and operations routes.

Two headers, both mandatory on every ``/api`` route:

* ``X-API-Key``  — the shared service secret (constant-time compared).
* ``X-User-Id``  — the reviewer or operator on whose behalf the client calls; it is
  what the audit trail records as the actor. Single sign-on in the Ingredion
  tenant maps onto it (Stage 2); until then the client application is responsible
  for setting it truthfully, which is why the API key must stay server-side.

Keys are accepted in headers only, never in the query string. The ``/events``
routes use ``push_auth`` (a Google-signed OIDC token from Pub/Sub) instead.
"""

import hmac

from fastapi import Depends, Header, HTTPException

from . import config

_MAX_USER_ID = 128


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or not hmac.compare_digest(x_api_key, config.INGREDION_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    _: None = Depends(require_api_key),
) -> str:
    user_id = (x_user_id or "").strip()
    if not user_id or len(user_id) > _MAX_USER_ID:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    return user_id
