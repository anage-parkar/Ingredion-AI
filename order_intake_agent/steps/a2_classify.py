"""A2 · Classify the email (Vertex AI).

The model answers narrow questions on the text: new order, revised PO, duplicate or
not an order; how many POs; which language; handwritten? Model Armor screens the
text first (inside the extractor). Non-orders and unsupported formats go to the
manual queue; revised and duplicate submissions continue with a flag the reviewer
sees; an email with several POs is flagged for splitting.

In fallback mode (RPA failure record as intake) the recorded RPA error is routed
in code first, so no model call is spent on a category Release 1 does not attempt.
"""

from __future__ import annotations

from factory.case import Case, StepResult
from factory.guardrails import GuardBlocked
from factory.model_gateway import ExtractionFormatError

from ..context import OrderIntakeContext
from ..models import Classification, ErrorCategory, Intent
from ..policy import OrderIntakePolicy
from ._common import call_model, gather_source_text, truncate

STEP = "A2"
PROMPT = "order_intake/a2_classify"  # the registry serves the latest version (v2)

_EXIT_CODES = {
    Intent.CHANGE: "NOT_ORDER.CHANGE",
    Intent.CANCELLATION: "NOT_ORDER.CANCELLATION",
    Intent.INQUIRY: "NOT_ORDER.INQUIRY",
    Intent.CREDIT_MEMO: "NOT_ORDER.CREDIT_MEMO",
    Intent.OTHER: "NOT_ORDER.OTHER",
}


def route_rpa_error(category: ErrorCategory | None, policy: OrderIntakePolicy) -> str | None:
    """Fallback mode only: reason code for categories Release 1 does not attempt."""
    if category == ErrorCategory.SAP and not policy.attempt_sap_failures:
        return "RPA.SAP_CAUSE"
    if category == ErrorCategory.MAX_LOAD and not policy.attempt_max_load_failures:
        return "RPA.MAX_LOAD"
    if category == ErrorCategory.MAPPING_DATA and not policy.attempt_mapping_data_failures:
        return "RPA.MAPPING_EXCLUDED"
    return None


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    intake = case.data["intake"]
    if ctx.policy.mode == "fallback":
        code = route_rpa_error(intake.error_category, ctx.policy)
        if code:
            ctx.log(case, STEP, "routed_on_rpa_error", code=code, error_category=str(intake.error_category))
            return StepResult.exit(code, note="routed on the recorded RPA error; no model call")

    source = gather_source_text(case, ctx)
    email = case.data["email"]
    limit = ctx.policy.max_prompt_chars
    context_line = (
        f"{intake.error_category}: {intake.error_detail}"
        if intake.error_category
        else f"cohort {intake.cohort or 'n/a'}; source {intake.source}; customer {intake.customer or 'unknown'}"
    )
    inputs = {
        "subject": email.subject or "",
        "body": truncate(email.body or "", limit // 2),
        "attachment_text": truncate(source["attachment_text"], limit // 2),
        "rpa_error": context_line,
    }
    try:
        result = call_model(ctx, PROMPT, inputs, Classification)
    except GuardBlocked as exc:
        case.add_flag("GUARD.BLOCKED", f"classification input blocked: {exc}")
        ctx.log(case, STEP, "guard.blocked", reasons=exc.result.reasons)
        return StepResult.review("GUARD.BLOCKED")
    except ExtractionFormatError as exc:
        case.add_flag("EXTRACT.FORMAT_ERROR", f"classification answer unusable: {exc}")
        ctx.log(case, STEP, "model.format_error", error=str(exc))
        return StepResult.review("EXTRACT.FORMAT_ERROR")

    cls = Classification.model_validate(result.data)
    case.data["classification"] = cls
    ctx.keep_model_call(case, STEP, result)
    ctx.log(case, STEP, "classified", model_call=result.audit_fields(), **cls.model_dump(mode="json"))

    if cls.intent in _EXIT_CODES or (not cls.is_new_order and cls.intent not in (Intent.DUPLICATE, Intent.REVISED_PO, Intent.NEW_ORDER)):
        return StepResult.exit(_EXIT_CODES.get(cls.intent, "NOT_ORDER.OTHER"), note="; ".join(cls.reasons))
    if cls.language.lower() not in ctx.policy.supported_languages:
        return StepResult.exit("FORMAT.NON_ENGLISH", note=f"language={cls.language}")
    if cls.handwritten:
        return StepResult.exit("FORMAT.HANDWRITTEN", note="; ".join(cls.reasons))
    if cls.intent == Intent.REVISED_PO:
        case.add_flag("EMAIL.REVISED_PO", "revised copy of a PO already received; reviewer confirms replace or new", po_numbers=cls.po_numbers)
    if cls.intent == Intent.DUPLICATE:
        case.add_flag("EMAIL.DUPLICATE_SUBMISSION", "the same PO was received again; reviewer confirms before any order", po_numbers=cls.po_numbers)
    po_count = max(cls.po_count, len(cls.po_numbers))
    if po_count > 1:
        case.add_flag("EMAIL.MULTI_PO", f"{po_count} purchase orders in one email; split into separate orders", po_count=po_count, po_numbers=cls.po_numbers)
    return StepResult.ok()
