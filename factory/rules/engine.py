"""A small rule engine: pure code, unit-tested, no model.

A rule inspects a context object the agent builds and returns zero or more
results; each failed result carries a reason code, evidence (which record, which
system) and, for pre-bill, a verdict that says who is right.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from enum import StrEnum
from typing import Any

from .reason_codes import get as get_code


class Verdict(StrEnum):
    MATCHED = "MATCHED"
    UPDATED_PO_REQUIRED = "UPDATED_PO_REQUIRED"  # SAP is right, the PO is stale
    INTERNAL_FIX = "INTERNAL_FIX"  # SAP (or PROS) is wrong; Ingredion fixes its side
    MISSING_DATA = "MISSING_DATA"  # cannot judge; never treated as matched


@dataclass
class RuleResult:
    rule: str
    passed: bool
    code: str | None = None
    message: str = ""
    field: str | None = None
    verdict: str | None = None
    owner: str | None = None
    evidence: dict[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code:
            rc = get_code(self.code)  # unknown codes fail fast
            if self.owner is None:
                self.owner = rc.owner

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Rule(ABC):
    name: str = "rule"

    def applies(self, ctx: Any) -> bool:  # noqa: ARG002  (subclasses use ctx)
        return True

    @abstractmethod
    def evaluate(self, ctx: Any) -> list[RuleResult]: ...

    @staticmethod
    def ok(name: str, message: str = "", **evidence: Any) -> RuleResult:
        return RuleResult(rule=name, passed=True, message=message, verdict=Verdict.MATCHED, evidence=evidence)


class RuleSet:
    def __init__(self, rules: Iterable[Rule]) -> None:
        self.rules = list(rules)

    def run(self, ctx: Any) -> list[RuleResult]:
        results: list[RuleResult] = []
        for rule in self.rules:
            if rule.applies(ctx):
                results.extend(rule.evaluate(ctx))
        return results

    @staticmethod
    def failures(results: Iterable[RuleResult]) -> list[RuleResult]:
        return [r for r in results if not r.passed]

    @staticmethod
    def all_passed(results: Iterable[RuleResult]) -> bool:
        return all(r.passed for r in results)
