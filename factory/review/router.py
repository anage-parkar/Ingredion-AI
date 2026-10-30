"""/api/<agent>/review: list open items, inspect one, record a decision.

The reviewer identity is whatever the injected dependency returns (the service maps
``X-User-Id`` to it today; single sign-on in the client tenant later). ``on_decision``
is the pipeline's resume hook: approve or correct continues the case, reject returns
it to the rework path. The decision is stored before the hook runs, so a failure in
the pipeline never loses a reviewer's decision. Mounted per agent with ``agent`` set,
the router only ever shows and decides that agent's items, although both agents share
one queue collection.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .models import Decision, DecisionKind, ReviewItem
from .queue import AlreadyDecided, ReviewQueue

logger = logging.getLogger("factory.review")


class DecisionRequest(BaseModel):
    kind: DecisionKind
    reason: str = Field(default="", max_length=2000)
    corrections: dict[str, Any] = Field(default_factory=dict)
    confirmed_duplicate: bool = False


def build_review_router(
    *,
    queue: Callable[[], ReviewQueue],
    user_dependency: Callable[..., str],
    on_decision: Callable[[ReviewItem, Decision], Any] | None = None,
    prefix: str = "/api/review",
    agent: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[f"review queue · {agent}" if agent else "review queue"])

    def _visible(item: ReviewItem | None) -> ReviewItem:
        if item is None or (agent is not None and item.agent != agent):
            raise HTTPException(status_code=404, detail="Review item not found")
        return item

    @router.get("/items")
    def list_items(
        status: str | None = Query(default="open"),
        agent_filter: str | None = Query(default=None, alias="agent"),
        owner: str | None = None,
        _: str = Depends(user_dependency),
    ) -> dict[str, Any]:
        items = queue().list(status=None if status in (None, "", "all") else status, agent=agent or agent_filter, owner=owner)
        return {"success": True, "items": [i.to_dict() for i in items]}

    @router.get("/items/{item_id}")
    def get_item(item_id: str, _: str = Depends(user_dependency)) -> dict[str, Any]:
        return {"success": True, "item": _visible(queue().get(item_id)).to_dict()}

    @router.post("/items/{item_id}/decision")
    def decide(item_id: str, body: DecisionRequest, user: str = Depends(user_dependency)) -> dict[str, Any]:
        _visible(queue().get(item_id))
        if body.kind == DecisionKind.REJECT and not body.reason.strip():
            raise HTTPException(status_code=422, detail="A reason is required to reject")
        if body.kind == DecisionKind.CORRECT and not body.corrections:
            raise HTTPException(status_code=422, detail="Corrections are required for a 'correct' decision")
        decision = Decision(
            kind=body.kind,
            reviewer=user,
            reason=body.reason,
            corrections=body.corrections,
            confirmed_duplicate=body.confirmed_duplicate,
        )
        try:
            item = queue().decide(item_id, decision)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Review item not found") from exc
        except AlreadyDecided as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        resume: Any = None
        if on_decision is not None:
            try:
                resume = on_decision(item, decision)
            except Exception as exc:  # the decision is saved; report the pipeline problem
                logger.exception("resume after decision failed for case %s", item.case_id)
                return {"success": True, "item": item.to_dict(), "resume": {"error": str(exc)}}
        return {"success": True, "item": item.to_dict(), "resume": resume}

    return router
