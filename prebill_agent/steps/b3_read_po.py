"""B3 · Read the PO, tiered: Ariba (structured) first, then the PO captured on the
Salesforce order, and only then a PDF from the mailbox read through Document
Intelligence and the model behind the guardrails. No PO anywhere is a missing-data
outcome, never a guess."""

from __future__ import annotations

from factory.case import Case, StepResult
from factory.guardrails import GuardBlocked
from factory.model_gateway import ExtractionFormatError, ModelUnavailable, UnsupportedContent

from ..context import PrebillContext
from ..schema import CanonicalDoc, DocType

STEP = "B3"
PROMPT = "prebill/b3_read_po"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    ref = case.data["invoice_ref"]
    order = case.data.get("order") or {}
    override = case.data.pop("po_override", None)
    if override is not None:  # an updated PO handed in for a recheck
        case.data["po"], case.data["po_source"] = override, "updated_po"
        ctx.log(case, STEP, "po.read", source="updated_po", lines=len(override.lines))
        return StepResult.ok()

    po_ref = order.get("po_ref") or ref.po_ref
    po: CanonicalDoc | None = None
    source: str | None = None
    model_call = None

    if po_ref:
        po = ctx.ariba.purchase_order(po_ref)
        source = "ariba" if po else None
    if po is None and order.get("captured_po") is not None:
        po, source = order["captured_po"], "salesforce"
    if po is None and ctx.mailbox is not None:
        found = ctx.mailbox.find_po_pdf(ref.order_ref, po_ref)
        if found:
            content, content_type = found
            try:
                layout = ctx.layout_reader.read(content, content_type, filename=f"{po_ref or ref.order_ref}.pdf")
                text = layout.text[: ctx.policy.max_prompt_chars]
                result = ctx.extractor.extract(ctx.prompt(PROMPT), {"text": text}, CanonicalDoc)
                po = CanonicalDoc.model_validate(result.data)
                po.doc_type, po.source = DocType.PO, "pdf"
                source, model_call = "pdf", result.audit_fields()
                ctx.keep_model_call(case, STEP, result)
            except GuardBlocked as exc:
                case.add_flag("GUARD.BLOCKED", f"PO attachment blocked by the guardrails: {exc}", "po")
            except (UnsupportedContent, ExtractionFormatError, ModelUnavailable, LookupError) as exc:
                case.add_flag("PO.NOT_FOUND", f"PO attachment could not be read: {exc}", "po", po_ref=po_ref)

    if po is None and not case.has_flag("PO.NOT_FOUND") and not case.has_flag("GUARD.BLOCKED"):
        case.add_flag("PO.NOT_FOUND", "no purchase order in Ariba, on the Salesforce order or in the mailbox", "po", po_ref=po_ref)

    case.data["po"], case.data["po_source"] = po, source
    if po is not None:
        ctx.keep(case, STEP, f"po_{source}.json", po)
    ctx.log(case, STEP, "po.read", model_call=model_call, source=source, po_ref=po_ref, lines=len(po.lines) if po else 0)
    return StepResult.ok()
