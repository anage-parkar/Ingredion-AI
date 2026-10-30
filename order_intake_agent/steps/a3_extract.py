"""A3 · Read the PO with generative AI.

Document Intelligence (or a plain reader) has already turned the attachments into
text; the model returns the fields in a fixed schema with a self-reported
confidence per field. It has no tools and cannot act. A field that later fails
validation triggers one re-read with hints (the pipeline calls ``run`` again).
"""

from __future__ import annotations

from factory.case import Case, StepResult
from factory.guardrails import GuardBlocked
from factory.model_gateway import ExtractionFormatError

from ..context import OrderIntakeContext
from ..models import POExtraction
from ._common import call_model, gather_source_text, truncate

STEP = "A3"
PROMPT = "order_intake/a3_extract"


def run(case: Case, ctx: OrderIntakeContext, *, hints: list[str] | None = None) -> StepResult:
    source = gather_source_text(case, ctx)
    attempt = case.data.get("extraction_attempts", 0) + 1
    case.data["extraction_attempts"] = attempt
    if attempt == 1:
        ctx.keep(case, STEP, "source_text.json", source)  # what the model saw: layout text per attachment, reader, confidence
    inputs = {
        "text": truncate(source["all"], ctx.policy.max_prompt_chars),
        "hints": "; ".join(hints) if hints else "none",
    }
    try:
        result = call_model(ctx, PROMPT, inputs, POExtraction)
    except GuardBlocked as exc:
        case.add_flag("GUARD.BLOCKED", f"extraction input blocked: {exc}")
        ctx.log(case, STEP, "guard.blocked", reasons=exc.result.reasons)
        return StepResult.review("GUARD.BLOCKED")
    except ExtractionFormatError as exc:
        case.add_flag("EXTRACT.FORMAT_ERROR", f"extraction answer unusable: {exc}")
        ctx.log(case, STEP, "model.format_error", error=str(exc), attempt=attempt)
        return StepResult.review("EXTRACT.FORMAT_ERROR")

    extraction = POExtraction.model_validate(result.data)
    case.data["extraction"] = extraction
    ctx.keep_model_call(case, STEP, result)
    ctx.log(
        case,
        STEP,
        "extracted" if attempt == 1 else "re-read",
        model_call=result.audit_fields(),
        attempt=attempt,
        hints=list(hints or []),
        po_number=extraction.po_number,
        lines=len(extraction.lines),
        self_reported_confidence=extraction.confidence,
        layout_mean_confidence=source["mean_confidence"],
    )
    return StepResult.ok()
