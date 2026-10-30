"""B6 · Explain the gaps and draft the request, on Gemini behind the guardrails.

The model writes words only: a summary per failed check, the draft PO-update
request and the internal fix note. It never changes a verdict, a number or an
owner. If the model is unavailable or its answer does not fit the schema, a plain
template says the same things less elegantly; the case is never held up on prose.
"""

from __future__ import annotations

import json

from factory.case import Case, StepResult
from factory.guardrails import GuardBlocked
from factory.model_gateway import ExtractionFormatError, ModelUnavailable
from factory.rules import RuleResult, Verdict

from ..context import PrebillContext
from ..schema import GapExplanation

STEP = "B6"
PROMPT = "prebill/b6_explain"


def template_explanation(case: Case, failed: list[RuleResult]) -> GapExplanation:
    ref = case.data["invoice_ref"]
    summary = {r.rule: f"{r.message}. Verdict: {r.verdict}. Evidence: {json.dumps(r.evidence, default=str)}" for r in failed}
    updates = [r for r in failed if r.verdict == Verdict.UPDATED_PO_REQUIRED]
    fixes = [r for r in failed if r.verdict in (Verdict.INTERNAL_FIX, Verdict.MISSING_DATA)]
    request = ""
    if updates:
        request = (
            f"Subject: Updated purchase order needed for order {ref.order_ref}\n\nHello,\n\n"
            f"Before we invoice order {ref.order_ref}, we need an updated purchase order covering:\n"
            + "\n".join(f"- {r.message}" for r in updates)
            + "\n\nCould you send a revised PO? Kind regards,\nIngredion"
        )
    note = ""
    if fixes:
        note = f"Internal fix needed before invoice {ref.invoice_ref} is released:\n" + "\n".join(
            f"- {r.rule}: {r.message} (owner: {r.owner or 'to assign'})" for r in fixes
        )
    risk = ""
    if any(r.code == "QTY.OVER" for r in failed):
        risk = "The customer portal hard-blocks over-quantity invoices; sent as is, this invoice will be rejected."
    elif any(r.rule == "unit_price" for r in failed):
        risk = "The portal three-way match will fail on price; expect a short-pay or a dispute."
    return GapExplanation(summary_by_category=summary, draft_request=request, draft_internal_note=note, risk_note=risk)


def run(case: Case, ctx: PrebillContext) -> StepResult:
    failed = [r for r in case.data["results"] if not r.passed]
    ref = case.data["invoice_ref"]
    explanation: GapExplanation | None = None
    model_call = None
    source = "template"
    if ctx.policy.explain_with_model:
        context = {"order_ref": ref.order_ref, "invoice_ref": ref.invoice_ref, "customer": ref.customer_name, "sold_to": ref.sold_to, "billing_date": ref.billing_date, "outcome": case.outcome}
        try:
            result = ctx.extractor.extract(
                ctx.prompt(PROMPT),
                {"context": json.dumps(context), "gaps": json.dumps([r.to_dict() for r in failed], default=str)},
                GapExplanation,
            )
            explanation, model_call, source = GapExplanation.model_validate(result.data), result.audit_fields(), "model"
            ctx.keep_model_call(case, STEP, result)
        except GuardBlocked as exc:
            case.add_flag("GUARD.BLOCKED", f"explanation input blocked: {exc}")
        except (ExtractionFormatError, ModelUnavailable, LookupError) as exc:
            ctx.log(case, STEP, "model.unavailable", error=str(exc))
    if explanation is None:
        explanation = template_explanation(case, failed)
    case.data["explanation"] = explanation
    ctx.log(case, STEP, "explained", model_call=model_call, source=source, categories=list(explanation.summary_by_category), has_request=bool(explanation.draft_request), has_note=bool(explanation.draft_internal_note))
    return StepResult.ok()
