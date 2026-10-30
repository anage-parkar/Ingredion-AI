"""A7 · Review summary (code): the order summary with doubtful fields flagged, the
SAP candidates, the reason codes and the drafted clarification, as one review item.
Under Phase 1 every case goes to the reviewer from here; in Phase 2 (an Ingredion
decision at Gate 5) a clean, high-confidence case continues to A8."""

from __future__ import annotations

from typing import Any

from factory.case import Case, StepResult
from factory.review import ReviewField, ReviewItem

from .. import AGENT
from ..context import OrderIntakeContext
from ..models import Score
from .a5_score import KEY_FIELDS

STEP = "A7"


def build_review_item(case: Case, ctx: OrderIntakeContext) -> ReviewItem:
    ex = case.data.get("extraction")
    val = case.data.get("validation")
    score: Score | None = case.data.get("score")
    intake = case.data.get("intake")
    conf = score.confidence if score else {}
    low = set(score.low_confidence_fields) if score else set()
    flagged_fields = {f.field for f in case.flags if f.field}
    fields: list[ReviewField] = []
    if ex is not None:
        for name in KEY_FIELDS:
            candidates: list[Any] = []
            if val is not None and name in ("sold_to", "ship_to", "bill_to"):
                match = getattr(val, name)
                candidates = [m.model_dump() for m in val.partner_candidates.get(name, [])] or ([match.model_dump()] if match else [])
            fields.append(ReviewField(name=name, value=getattr(ex, name), confidence=conf.get(name), flagged=name in low or name in flagged_fields, candidates=candidates))
        for line in ex.lines:
            n = line.line_no
            vl = next((v for v in (val.lines if val else []) if v.line_no == n), None)
            fields.append(
                ReviewField(
                    name=f"line{n}.customer_material",
                    value=line.customer_material,
                    confidence=conf.get(f"line{n}.customer_material"),
                    flagged=f"line{n}.customer_material" in low or f"line{n}.sap_material" in flagged_fields,
                    candidates=[m.model_dump() for m in vl.candidates] if vl and vl.candidates else ([vl.sap_material] if vl and vl.sap_material else []),
                    note="SAP material" if vl and vl.sap_material else "",
                )
            )
            converted = f" → {vl.converted_quantity} {vl.converted_uom}" if vl and vl.converted_quantity is not None and vl.converted_uom != vl.uom else ""
            fields.append(ReviewField(name=f"line{n}.quantity", value=f"{line.quantity} {line.uom}{converted}", confidence=conf.get(f"line{n}.quantity"), flagged=f"line{n}.quantity" in low or f"line{n}.uom" in flagged_fields))
            if line.unit_price is not None:
                fields.append(ReviewField(name=f"line{n}.unit_price", value=f"{line.unit_price} / {line.price_uom or line.uom}", confidence=conf.get(f"line{n}.unit_price"), flagged=f"line{n}.unit_price" in low or f"line{n}.unit_price" in flagged_fields))
    codes = sorted({f.code for f in case.flags})
    summary = (
        f"PO {ex.po_number if ex else '?'} · {len(ex.lines) if ex else 0} line(s) · "
        f"{(intake.customer if intake and intake.customer else (ex.sold_to if ex else '?'))} · cohort {intake.cohort if intake and intake.cohort else 'n/a'} · "
        f"{len(case.flags)} flag(s): {', '.join(codes) or 'none'}"
    )
    return ReviewItem(case_id=case.case_id, agent=AGENT, summary=summary, fields=fields, flags=[f.to_dict() for f in case.flags], drafts=dict(case.data.get("drafts", {})), source_ref=ex.po_number if ex else None)


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    score: Score | None = case.data.get("score")
    review_required = ctx.policy.review_every_case or (score.review_required if score else True)
    ctx.log(case, STEP, "summary.built", flags=[f.code for f in case.flags], review_required=review_required)
    if review_required:
        return StepResult.review(*[f.code for f in case.flags])
    return StepResult.ok()
