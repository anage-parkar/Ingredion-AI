"""B7 · Route to the owner: one review item per flagged invoice with the gaps, the
evidence, the explanation and the drafts, addressed to the owner the redline v2
names for the outcome. The owner confirms or overrides and acts outside the agent;
no case skips this."""

from __future__ import annotations

from factory.audit import Outcome
from factory.case import Case, StepResult
from factory.review import ReviewField, ReviewItem

from .. import AGENT
from ..context import PrebillContext
from ..rules import outcome_label, owners

STEP = "B7"
OUTCOME_OWNERS = {
    str(Outcome.UPDATED_PO_REQUIRED): "Customer Service or Commercial",
    str(Outcome.INTERNAL_FIX_OR_MISSING_DATA): "Ingredion owner (CBA, Sales, PROS for price)",
}
_DEFAULT_OWNER = "Ingredion owner"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    failed = [r for r in case.data["results"] if not r.passed]
    owner_map = owners(failed)
    primary = OUTCOME_OWNERS.get(case.outcome or "", _DEFAULT_OWNER)
    explanation = case.data["explanation"]
    ref = case.data["invoice_ref"]
    fields = [
        ReviewField(name=r.rule, value=r.message, flagged=True, note=f"{r.verdict} · issue owner: {r.owner or primary}", candidates=[r.evidence])
        for r in failed
    ]
    item = ReviewItem(
        case_id=case.case_id,
        agent=AGENT,
        summary=(
            f"{ref.customer_name} · order {ref.order_ref} · invoice {ref.invoice_ref} · {outcome_label(case.outcome)} · "
            f"{len(failed)} gap(s): {', '.join(r.rule for r in failed)}"
        ),
        fields=fields,
        flags=[f.to_dict() for f in case.flags],
        drafts={
            "summary": "\n".join(f"{k}: {v}" for k, v in explanation.summary_by_category.items()),
            "po_update_request": explanation.draft_request,
            "internal_note": explanation.draft_internal_note,
            "risk": explanation.risk_note,
        },
        owner=primary,
        source_ref=ref.order_ref,
    )
    ctx.review_queue.enqueue(item)
    case.data["review_item_id"] = item.id
    case.data["owners"] = owner_map
    ctx.log(case, STEP, "review.enqueued", item_id=item.id, owner=primary, issue_owners=owner_map, outcome=case.outcome)
    return StepResult.review(*[r.code for r in failed if r.code])
