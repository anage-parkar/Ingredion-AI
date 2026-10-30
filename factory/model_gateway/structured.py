"""Structured model calls: a prompt, inputs, and a Pydantic schema the answer must fit.

The model can only return fields; it has no tools and no way to act. The schema is
sent with the prompt and enforced on the way back, so a malformed answer is an
:class:`ExtractionFormatError` the caller may retry once, never data.

* :class:`VertexStructuredExtractor` (``vertex.py``) is the production extractor:
  Gemini on Vertex AI with controlled generation.
* :class:`FakeStructuredExtractor` serves canned answers in tests and backtests, still
  validated through the schema so fixtures cannot drift from the contract.
* :class:`GuardedExtractor` wraps any extractor: every string input is screened by the
  guard chain first, the call is traced, and the result carries the guard verdicts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from ..guardrails import GuardChain
from ..observability.tracing import span
from .prompts import Prompt

_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


class ExtractionFormatError(RuntimeError):
    """The model's answer was not valid JSON for the schema."""


@dataclass
class StructuredResult:
    data: dict[str, Any]
    model: str
    prompt_ref: str
    prompt_sha256: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: str = ""
    latency_ms: int = 0
    guard: list[dict[str, Any]] = field(default_factory=list)

    def audit_fields(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt_ref,
            "prompt_sha256": self.prompt_sha256,
            "model": self.model,
            "tokens": dict(self.usage),
            "latency_ms": self.latency_ms,
            "guard": list(self.guard),
        }

    def evidence(self) -> dict[str, Any]:
        """What the evidence store keeps for the call: the raw answer and the audit fields."""
        return {**self.audit_fields(), "raw": self.raw, "data": self.data}


class StructuredExtractor(Protocol):
    name: str

    def extract(self, prompt: Prompt, inputs: dict[str, Any], schema: type[BaseModel]) -> StructuredResult: ...


def parse_to_schema(raw: str, schema: type[BaseModel]) -> dict[str, Any]:
    match = _JSON_OBJECT.search(raw or "")
    if not match:
        raise ExtractionFormatError("no JSON object in the model answer")
    try:
        model = schema.model_validate_json(match.group(0))
    except ValidationError as exc:
        raise ExtractionFormatError(f"answer does not match {schema.__name__}: {exc.errors()[:3]}") from exc
    return model.model_dump(mode="json")


class FakeStructuredExtractor:
    """Canned answers keyed by prompt name; each is validated through the schema."""

    name = "fake"

    def __init__(self, responses: dict[str, list[dict[str, Any]] | Callable[[dict[str, Any]], dict[str, Any]]] | None = None) -> None:
        self.responses: dict[str, Any] = dict(responses or {})
        self.calls: list[dict[str, Any]] = []

    def queue(self, prompt_name: str, *answers: dict[str, Any]) -> None:
        self.responses.setdefault(prompt_name, [])
        if callable(self.responses[prompt_name]):
            raise ValueError("cannot queue answers on a callable responder")
        self.responses[prompt_name].extend(answers)

    def extract(self, prompt: Prompt, inputs: dict[str, Any], schema: type[BaseModel]) -> StructuredResult:
        self.calls.append({"prompt": prompt.ref, "inputs": sorted(inputs)})
        responder = self.responses.get(prompt.name)
        if responder is None:
            raise LookupError(f"FakeStructuredExtractor has no answer for {prompt.name}")
        answer = responder(inputs) if callable(responder) else (responder.pop(0) if responder else None)
        if answer is None:
            raise LookupError(f"FakeStructuredExtractor ran out of answers for {prompt.name}")
        data = parse_to_schema(json.dumps(answer), schema)
        return StructuredResult(data=data, model="fake", prompt_ref=prompt.ref, prompt_sha256=prompt.sha256, raw=json.dumps(answer))


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


class GuardedExtractor:
    """Screen every string input, trace the call, attach guard verdicts to the result."""

    def __init__(self, inner: StructuredExtractor, guards: GuardChain) -> None:
        self.inner = inner
        self.guards = guards
        self.name = f"guarded({inner.name})"

    def extract(self, prompt: Prompt, inputs: dict[str, Any], schema: type[BaseModel]) -> StructuredResult:
        verdicts = [r.to_dict() for r in self.guards.require_all(_strings(inputs), purpose=prompt.ref)]
        with span("model_gateway.extract", prompt=prompt.ref, extractor=self.inner.name) as sp:
            result = self.inner.extract(prompt, inputs, schema)
            sp.set("model", result.model)
            sp.set("tokens_total", result.usage.get("total", 0))
            sp.set("latency_ms", result.latency_ms)
        result.guard = verdicts
        return result
