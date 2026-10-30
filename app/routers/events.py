"""/events/<agent>/<kind>: where the data platform's change signals arrive.

``gold.cases.changed`` pushes to ``/events/order-intake/cases`` and
``gold.orders.invoice_ready`` to ``/events/prebill/invoices``. The handler does four
things and returns 204 in well under a second: verify the push identity, refuse
while the kill switch is engaged (503, so Pub/Sub retries later), claim the case
once (a redelivery is acknowledged without a second run), and hand the run to the
worker through the dispatcher. If the hand-over fails the claim is released and the
answer is 503, so the event comes back.

Pub/Sub treats 2xx as an acknowledgement and anything else as a retry; a malformed
event therefore answers 400 and ends in the subscription's dead-letter topic.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from factory.dispatch import Dispatcher, WorkItem

logger = logging.getLogger("ingredion.events")


class PushMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    data: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    message_id: str | None = Field(default=None, alias="messageId")
    publish_time: str | None = Field(default=None, alias="publishTime")


class PushEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: PushMessage
    subscription: str | None = None

    def payload(self) -> dict[str, Any]:
        if not self.message.data:
            return {}
        decoded = base64.b64decode(self.message.data, validate=True)
        body = json.loads(decoded)
        if not isinstance(body, dict):
            raise ValueError("event body must be a JSON object")
        return body


def build_events_router(
    *,
    slug: str,
    agent: str,
    kind: str,
    runtime: Callable[[], Any],
    dispatcher: Callable[[], Dispatcher],
    auth_dependency: Callable[..., str],
) -> APIRouter:
    router = APIRouter(prefix=f"/events/{slug}", tags=[f"events · {slug}"])

    @router.post(f"/{kind}", status_code=204, response_class=Response)
    def on_event(envelope: PushEnvelope, caller: str = Depends(auth_dependency)) -> Response:
        rt = runtime()
        try:
            payload = envelope.payload()
        except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"message data is not base64 JSON: {exc.__class__.__name__}") from exc
        if rt.ctx.kill_switch is not None and rt.ctx.kill_switch.is_engaged():
            raise HTTPException(status_code=503, detail="kill switch engaged; the event will be retried")
        try:
            raw = rt.raw_from_event(payload, envelope.message.attributes)
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"event does not describe a {kind}: {exc.__class__.__name__}") from exc

        message_id = envelope.message.message_id
        ingress = {"message_id": message_id, "subscription": envelope.subscription, "marker": raw.marker, "caller": caller}
        if not rt.ctx.claims.claim(raw.source_ref, owner=f"{agent}:event"):
            rt.ctx.audit.append(raw.source_ref, agent, "ingress", "event.duplicate", actor=caller, data=ingress)
            return Response(status_code=204)
        rt.ctx.audit.append(raw.source_ref, agent, "ingress", "event.accepted", actor=caller, data=ingress)

        item = WorkItem.from_raw(agent, raw, subscription=envelope.subscription or "")
        item.message_id = message_id
        try:
            delivery = dispatcher().submit(item)
        except Exception as exc:
            rt.ctx.claims.release(raw.source_ref)
            rt.ctx.audit.append(raw.source_ref, agent, "ingress", "event.dispatch_failed", actor=caller, data={**ingress, "error": f"{type(exc).__name__}: {exc}"})
            logger.exception("dispatch failed for %s %s", agent, raw.source_ref)
            raise HTTPException(status_code=503, detail="could not hand the case to the worker; the event will be retried") from exc
        rt.ctx.audit.append(raw.source_ref, agent, "ingress", "event.dispatched", actor=caller, data={**ingress, "delivery": delivery})
        return Response(status_code=204)

    return router


__all__ = ["PushEnvelope", "PushMessage", "build_events_router"]
