"""Gemini on Vertex AI as the structured extractor (the approved model endpoint in
Ingredion's Google Cloud project).

Controlled generation: the Pydantic schema is sent as ``response_schema`` so the
model can only answer in that shape. Gemini's schema dialect is a subset of JSON
Schema (no ``$ref``, no ``additionalProperties``), so the schema is translated
first; if the API still rejects it, the call is retried in plain JSON mode with the
schema spelled out in the prompt, and the answer is validated by Pydantic either
way. Temperature is 0, no tools are attached, and nothing is streamed.

SDK: ``google-genai`` (``genai.Client(vertexai=True, ...)``), imported lazily. Tests
inject a fake client through ``client``.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from pydantic import BaseModel

from .. import settings
from .errors import ModelUnavailable
from .prompts import Prompt
from .structured import StructuredResult, parse_to_schema


class VertexUnavailable(ModelUnavailable):
    """Vertex AI is not configured or the SDK/credentials are missing."""


_UNSUPPORTED_KEYS = {"additionalProperties", "title", "default", "examples", "$schema", "const", "pattern", "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "format"}


def gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Translate a Pydantic JSON schema into the subset Gemini accepts.

    ``$ref`` entries are inlined from ``$defs``; free-form dictionaries (which Pydantic
    expresses with ``additionalProperties``) become plain objects; ``anyOf`` with null
    becomes ``nullable``.
    """
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return walk(copy.deepcopy(defs[name]))
        out: dict[str, Any] = {}
        if "anyOf" in node:
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            nullable = len(options) != len(node["anyOf"])
            if len(options) == 1:
                out = walk(copy.deepcopy(options[0]))
                if nullable:
                    out["nullable"] = True
                for key in ("description",):
                    if key in node and key not in out:
                        out[key] = node[key]
                return out
            out["anyOf"] = [walk(o) for o in options]
            if nullable:
                out["nullable"] = True
            return out
        for key, value in node.items():
            if key in _UNSUPPORTED_KEYS or key == "$defs":
                continue
            if key == "properties":
                out[key] = {k: walk(v) for k, v in value.items()}
            elif key == "items":
                out[key] = walk(value)
            else:
                out[key] = value
        if out.get("type") == "object" and "properties" not in out:
            out.pop("required", None)  # a free-form dict: Gemini accepts an open object
        return out

    return walk(copy.deepcopy(schema))


class VertexStructuredExtractor:
    name = "vertex"

    def __init__(
        self,
        *,
        project: str | None = None,
        location: str | None = None,
        model: str | None = None,
        controlled_generation: bool | None = None,
        client: Any = None,
        max_output_tokens: int = 8192,
    ) -> None:
        env_project, env_location = settings.gcp()
        self.project = project or env_project
        self.location = location or env_location
        self.model = model or settings.vertex_model()
        self.controlled = settings.vertex_controlled_generation() if controlled_generation is None else controlled_generation
        self.max_output_tokens = max_output_tokens
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.project:
            raise VertexUnavailable("Vertex AI is not configured: set GOOGLE_CLOUD_PROJECT (and GOOGLE_CLOUD_LOCATION).")
        try:
            from google import genai
        except ImportError as exc:
            raise VertexUnavailable("google-genai is not installed in this runtime.") from exc
        try:
            self._client = genai.Client(vertexai=True, project=self.project, location=self.location)
        except Exception as exc:  # credentials, project
            raise VertexUnavailable(f"Could not initialise the Vertex AI client: {exc}") from exc
        return self._client

    def _config(self, schema: dict[str, Any] | None) -> Any:
        try:
            from google.genai import types
        except ImportError:  # fake client in tests: a plain dict is enough
            return {"response_mime_type": "application/json", "response_schema": schema, "temperature": 0, "max_output_tokens": self.max_output_tokens}
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
            max_output_tokens=self.max_output_tokens,
        )

    def extract(self, prompt: Prompt, inputs: dict[str, Any], schema: type[BaseModel]) -> StructuredResult:
        client = self._get_client()
        json_schema = schema.model_json_schema()
        message = prompt.render(**inputs)
        started = time.perf_counter()
        response = None
        used_schema = False
        if self.controlled:
            try:
                response = client.models.generate_content(model=self.model, contents=message, config=self._config(gemini_schema(json_schema)))
                used_schema = True
            except Exception as exc:  # schema rejected (INVALID_ARGUMENT) or transient: fall back to JSON mode
                if "INVALID_ARGUMENT" not in str(exc) and "schema" not in str(exc).lower():
                    raise
        if response is None:
            message_with_schema = message + "\n\nAnswer with one JSON object only, matching this JSON schema:\n" + json.dumps(json_schema, separators=(",", ":"))
            response = client.models.generate_content(model=self.model, contents=message_with_schema, config=self._config(None))
        text = getattr(response, "text", None) or ""
        data = parse_to_schema(text, schema)
        usage = getattr(response, "usage_metadata", None)
        tokens = {
            "prompt": getattr(usage, "prompt_token_count", 0) or 0,
            "completion": getattr(usage, "candidates_token_count", 0) or 0,
            "total": getattr(usage, "total_token_count", 0) or 0,
        }
        return StructuredResult(
            data=data,
            model=f"vertex:{self.model}" + (":schema" if used_schema else ":json"),
            prompt_ref=prompt.ref,
            prompt_sha256=prompt.sha256,
            usage=tokens,
            raw=text,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
