"""A6 · Exceptions (Vertex AI + Microsoft Graph).

For the flags that need the customer (price, contract, availability, an ambiguous
unit, a doubtful field) the model drafts the clarification email; the draft is saved
in the shared Outlook mailbox through Microsoft Graph so the reviewer can send it,
or not. The agent never sends anything and never changes a value. If the model is
unavailable a plain template drafts the same email. A case with nothing usable to
read at all (no PO number, no lines, after the re-read) cannot be clarified and goes
to the manual queue.
"""

from __future__ import annotations

import json

from factory.case import Case, Flag, StepResult
from factory.guardrails import GuardBlocked
from factory.model_gateway import ExtractionFormatError, ModelUnavailable

from ..context import OrderIntakeContext
from ..models import ClarificationDraft
from ._common import call_model

STEP = "A6"
PROMPT = "order_intake/a6_exceptions"
CLARIFY_PREFIXES = ("PRICE.", "CONTRACT.", "ATP.", "UOM.AMBIGUOUS", "UOM.NO_CONVERSION", "UOM.INVALID", "EXTRACT.LOW_CONFIDENCE")


def flags_for_customer(case: Case) -> list[Flag]:
    return [f for f in case.flags if f.code.startswith(CLARIFY_PREFIXES)]


def template_draft(case: Case, flags: list[Flag]) -> ClarificationDraft:
    ex = case.data["extraction"]
    email = case.data["email"]
    lines = [
        "Hello,",
        "",
        f"Thank you for your purchase order {ex.po_number or ''}. Before we enter it, we need to confirm the following with you:".replace("  ", " "),
        "",
    ]
    for flag in flags:
        e = flag.evidence
        if flag.code == "PRICE.PO_VS_SAP":
            lines.append(f"- Line {e.get('line_no')}: your PO shows {e.get('po_price_in_sap_uom')} per {e.get('sap_price_uom')}; our current price is {e.get('sap_price')} per {e.get('sap_price_uom')}.")
        elif flag.code == "ATP.SHORT":
            lines.append(f"- Line {e.get('line_no', '')}: {flag.message}.")
        else:
            lines.append(f"- {flag.message}.")
    lines += ["", "Could you confirm, or send an updated purchase order?", "", "Kind regards,", "Ingredion Customer Service"]
    return ClarificationDraft(
        to=[email.sender] if email.sender else [],
        subject=f"Purchase order {ex.po_number or '(number pending)'}: confirmation needed",
        body="\n".join(lines),
        reasons=sorted({f.code for f in flags}),
    )


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    ex = case.data["extraction"]
    email = case.data["email"]
    intake = case.data["intake"]
    if not ex.po_number and not ex.lines:
        case.add_flag("FORMAT.UNREADABLE", "no PO number and no order lines could be read after two attempts")
        ctx.log(case, STEP, "exception.unresolved", reason="nothing usable extracted")
        return StepResult.exit("EXCEPTION.UNRESOLVED", note="nothing usable could be read from the email or its attachments")

    flags = flags_for_customer(case)
    if not flags:
        case.data["drafts"] = {}
        ctx.log(case, STEP, "no_exceptions")
        return StepResult.ok()

    draft: ClarificationDraft | None = None
    model_call = None
    source = "template"
    if ctx.policy.draft_clarification_with_model:
        context = {
            "customer": intake.customer or ex.sold_to,
            "po_number": ex.po_number,
            "buyer_email": email.sender,
            "case_id": case.case_id,
            "requested_delivery_date": ex.requested_delivery_date,
        }
        try:
            result = call_model(ctx, PROMPT, {"context": json.dumps(context), "flags": json.dumps([f.to_dict() for f in flags], default=str)}, ClarificationDraft)
            draft, model_call, source = ClarificationDraft.model_validate(result.data), result.audit_fields(), "model"
            ctx.keep_model_call(case, STEP, result)
        except GuardBlocked as exc:
            case.add_flag("GUARD.BLOCKED", f"clarification input blocked: {exc}")
        except (ExtractionFormatError, ModelUnavailable, LookupError) as exc:
            ctx.log(case, STEP, "model.unavailable", error=str(exc))
    if draft is None:
        draft = template_draft(case, flags)
    if not draft.to and email.sender:
        draft.to = [email.sender]

    drafts = {"clarification_email": f"To: {', '.join(draft.to) or '(buyer address missing)'}\nSubject: {draft.subject}\n\n{draft.body}"}
    if ctx.graph is not None and ctx.policy.create_outlook_drafts:
        try:
            drafts["outlook_draft_id"] = ctx.graph.create_draft(ctx.draft_mailbox, draft.to, draft.subject, draft.body, case_ref=case.case_id)
        except Exception as exc:  # the draft text is still on the review item
            ctx.log(case, STEP, "graph.draft_failed", error=str(exc))
    case.data["drafts"] = drafts
    case.data["clarification"] = draft
    ctx.log(case, STEP, "clarification.drafted", model_call=model_call, source=source, reasons=[f.code for f in flags], to=draft.to, outlook_draft=drafts.get("outlook_draft_id"))
    return StepResult.ok()
