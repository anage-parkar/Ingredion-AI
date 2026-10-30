"""Deterministic decisions: the reason-code catalogue shared by both agents, the rule
engine, and the composite confidence score computed from evidence rather than
asked of the model."""

from .confidence import CompositeConfidence, FieldEvidence, Weights, layout_agreement
from .engine import Rule, RuleResult, RuleSet, Verdict
from .reason_codes import CATALOGUE, ReasonCode, Routing, UnknownReasonCode, get, routing

__all__ = [
    "CATALOGUE",
    "CompositeConfidence",
    "FieldEvidence",
    "ReasonCode",
    "Routing",
    "Rule",
    "RuleResult",
    "RuleSet",
    "UnknownReasonCode",
    "Verdict",
    "Weights",
    "get",
    "layout_agreement",
    "routing",
]
