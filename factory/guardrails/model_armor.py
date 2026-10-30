"""Google Cloud Model Armor as the guardrail in front of every model call.

Email and PO text is sent to the Model Armor template's ``sanitizeUserPrompt`` so
prompt injection and jailbreak attempts, sensitive data and malicious URIs inside a
document are detected before Gemini sees it. The call fails **closed**: if Model
Armor cannot be reached, the text is not allowed and the pipeline parks the case.

The template (which filters are on, at which confidence) is Ingredion's to define
and is referenced by its full resource name. Authentication is a bearer token from
the agent's service account (``google.auth`` default credentials) or any callable
passed as ``token_provider``; ``transport`` lets tests inject an ``httpx`` mock.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import GuardResult

_CHUNK = 40_000


def _default_token_provider() -> Callable[[], str]:
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

    def token() -> str:
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token

    return token


class ModelArmorGuard:
    name = "model_armor"

    def __init__(
        self,
        template: str,
        *,
        token_provider: Callable[[], str] | None = None,
        timeout: float = 10.0,
        transport: Any = None,
    ) -> None:
        if "/locations/" not in template or "/templates/" not in template:
            raise ValueError("Model Armor template must be projects/<p>/locations/<l>/templates/<id>")
        self.template = template
        self.location = template.split("/locations/")[1].split("/")[0]
        self.token_provider = token_provider
        self.timeout = timeout
        self.transport = transport

    @property
    def url(self) -> str:
        return f"https://modelarmor.{self.location}.rep.googleapis.com/v1/{self.template}:sanitizeUserPrompt"

    def _headers(self) -> dict[str, str]:
        if self.token_provider is None:
            self.token_provider = _default_token_provider()
        return {"Authorization": f"Bearer {self.token_provider()}", "Content-Type": "application/json"}

    def screen(self, text: str, *, purpose: str = "") -> GuardResult:
        import httpx

        chunks = [text[i : i + _CHUNK] for i in range(0, len(text or ""), _CHUNK)] or [""]
        reasons: list[str] = []
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                for idx, chunk in enumerate(chunks):
                    resp = client.post(self.url, headers=self._headers(), json={"user_prompt_data": {"text": chunk}})
                    if resp.status_code != 200:
                        return GuardResult(False, self.name, [f"model armor unavailable: HTTP {resp.status_code}"])
                    result = resp.json().get("sanitizationResult", {})
                    if result.get("filterMatchState") == "MATCH_FOUND":
                        hits = [name for name, body in (result.get("filterResults") or {}).items() if "MATCH_FOUND" in str(body)]
                        reasons.append(f"chunk {idx}: {', '.join(hits) or 'filter match'}")
        except Exception as exc:  # network, auth, JSON
            return GuardResult(False, self.name, [f"model armor unavailable: {exc.__class__.__name__}"])
        return GuardResult(not reasons, self.name, reasons)
