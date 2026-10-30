"""Guardrails: screened before every model call, so text inside an email or a PO
cannot steer the model. Production uses Google Cloud Model Armor (redline v2); the
pattern guard is a development stand-in that stays in the chain."""

from .. import settings
from .base import Guard, GuardBlocked, GuardResult
from .chain import GuardChain
from .model_armor import ModelArmorGuard
from .pattern_guard import PatternGuard


def default_chain() -> GuardChain:
    """Pattern guard always; Model Armor when a template is configured (always, outside Dev)."""
    guards: list[Guard] = [PatternGuard()]
    template = settings.model_armor_template()
    if template:
        guards.append(ModelArmorGuard(template))
    return GuardChain(guards)


__all__ = [
    "Guard",
    "GuardBlocked",
    "GuardChain",
    "GuardResult",
    "ModelArmorGuard",
    "PatternGuard",
    "default_chain",
]
