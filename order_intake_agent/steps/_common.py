"""Shared helpers for the steps: source text assembly and the guarded model call."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from factory.case import Case
from factory.model_gateway import ExtractionFormatError, StructuredResult, UnsupportedContent

from ..context import OrderIntakeContext


def truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n[truncated]"


def gather_source_text(case: Case, ctx: OrderIntakeContext) -> dict[str, Any]:
    """Email body plus the layout text of every readable attachment, computed once.

    Stored under ``case.data["source_text"]`` with the per-attachment reader and the
    mean Document Intelligence confidence, which feeds the composite score at A5.
    """
    if "source_text" in case.data:
        return case.data["source_text"]
    email = case.data["email"]
    attachments: list[dict[str, Any]] = []
    for att in email.attachments:
        try:
            layout = ctx.layout_reader.read(att.content, att.content_type, filename=att.name)
            attachments.append(
                {
                    "name": att.name,
                    "reader": layout.reader,
                    "text": layout.text,
                    "pages": layout.pages,
                    "mean_confidence": layout.mean_confidence,
                }
            )
        except UnsupportedContent as exc:
            attachments.append({"name": att.name, "reader": None, "text": "", "error": str(exc)})
    attachment_text = "\n\n".join(f"[attachment {a['name']}]\n{a['text']}" for a in attachments if a["text"])
    all_text = f"[email body]\n{email.body or ''}"
    if attachment_text:
        all_text += "\n\n" + attachment_text
    confidences = [a["mean_confidence"] for a in attachments if a.get("mean_confidence") is not None]
    source = {
        "subject": email.subject or "",
        "body": email.body or "",
        "attachments": attachments,
        "attachment_text": attachment_text,
        "all": all_text,
        "mean_confidence": (sum(confidences) / len(confidences)) if confidences else None,
    }
    case.data["source_text"] = source
    return source


def call_model(
    ctx: OrderIntakeContext,
    prompt_name: str,
    inputs: dict[str, Any],
    schema: type[BaseModel],
    *,
    format_retries: int = 1,
) -> StructuredResult:
    """One guarded, schema-checked model call; a malformed answer is retried once.

    ``GuardBlocked`` propagates untouched: blocked text never reaches the model and
    the step routes the case to a reviewer.
    """
    prompt = ctx.prompt(prompt_name)
    attempt = 0
    while True:
        try:
            return ctx.extractor.extract(prompt, inputs, schema)
        except ExtractionFormatError:
            attempt += 1
            if attempt > format_retries:
                raise
