"""/api/ops: kill switch and runtime health. The authentication dependency is
injected by the service so this package never imports ``app``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..audit.trail import AuditTrail
from .kill_switch import KillSwitch, ReadOnlyKillSwitch


class KillSwitchRequest(BaseModel):
    engaged: bool
    reason: str = Field(default="", max_length=500)


def build_ops_router(
    *,
    kill_switch: Callable[[], KillSwitch],
    user_dependency: Callable[..., str],
    audit: Callable[[], AuditTrail] | None = None,
    poll: Callable[[], Any] | None = None,
    prefix: str = "/api/ops",
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["operations"])

    @router.get("/kill-switch")
    def kill_switch_status(_: str = Depends(user_dependency)) -> dict[str, Any]:
        return {"success": True, "kill_switch": kill_switch().status().to_dict()}

    @router.post("/kill-switch")
    def set_kill_switch(body: KillSwitchRequest, user: str = Depends(user_dependency)) -> dict[str, Any]:
        switch = kill_switch()
        if body.engaged and not body.reason.strip():
            raise HTTPException(status_code=422, detail="A reason is required to engage the kill switch")
        try:
            state = switch.engage(user, body.reason) if body.engaged else switch.release(user, body.reason)
        except ReadOnlyKillSwitch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if audit is not None:
            audit().append(
                case_id="-",
                agent="factory",
                step="ops",
                event="kill_switch.engaged" if body.engaged else "kill_switch.released",
                actor=user,
                data={"reason": body.reason, "state": state.to_dict()},
            )
        return {"success": True, "kill_switch": state.to_dict()}

    if poll is not None:

        @router.post("/poll")
        def sweep(user: str = Depends(user_dependency)) -> dict[str, Any]:
            """One pass over the intake source (gold or stub): claims and dispatches anything
            the change signal missed. Honours the kill switch."""
            report = poll()
            return {"success": True, "poll": asdict(report) if hasattr(report, "__dataclass_fields__") else report}

    @router.get("/health")
    def runtime_health(_: str = Depends(user_dependency)) -> dict[str, Any]:
        out: dict[str, Any] = {"success": True, "kill_switch": kill_switch().status().to_dict()}
        if audit is not None:
            out["audit_records"] = audit().count()
        return out

    return router
