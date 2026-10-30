"""The pre-bill pipeline: B1 to B8 with the state machine, the human gate and the
recheck loop that runs when the updated PO arrives. Matched invoices go straight
from B5 to B8: no model call, no reviewer."""

from __future__ import annotations

from typing import Any

from factory.audit import Outcome
from factory.case import Case
from factory.intake import PB, PREBILL, IllegalTransition, RawCase
from factory.review import Decision, ReviewItem

from . import AGENT
from .connectors import DraftInvoiceRef
from .context import PrebillContext
from .schema import CanonicalDoc
from .steps import (
    b1_pickup,
    b2_evidence,
    b3_read_po,
    b4_normalise,
    b5_compare,
    b6_explain,
    b7_route,
    b8_record,
)


class KillSwitchEngaged(RuntimeError):
    pass


class InMemoryCaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}

    def save(self, case: Case) -> None:
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def in_state(self, state: str) -> list[Case]:
        return [c for c in self._cases.values() if c.state == state]


class PrebillPipeline:
    def __init__(self, ctx: PrebillContext, case_store: Any = None) -> None:
        self.ctx = ctx
        self.store = case_store or InMemoryCaseStore()
        self.sm = PREBILL

    def process(self, ref: DraftInvoiceRef) -> Case:
        if self.ctx.kill_switch is not None and self.ctx.kill_switch.is_engaged():
            raise KillSwitchEngaged("kill switch engaged: no new invoices are taken")
        case = Case(case_id=ref.order_ref, agent=AGENT)
        case.data["invoice_ref"] = ref
        self.sm.start(case, "draft invoice ready in SAP")
        self.store.save(case)
        b1_pickup.run(case, self.ctx)
        return self._run(case)

    def process_raw(self, raw: RawCase) -> Case:
        return self.process(DraftInvoiceRef.model_validate(raw.payload))

    def resume(self, case: Case | str, decision: Decision) -> Case:
        """The owner confirmed or overrode the verdict; record it. Action happens outside."""
        if isinstance(case, str):
            found = self.store.get(case)
            if found is None:
                raise KeyError(case)
            case = found
        if case.state != PB.IN_REVIEW:
            raise IllegalTransition(f"case {case.case_id} is in {case.state!r}, not in review")
        case.data["decision"] = decision
        item_id = case.data.get("review_item_id")
        if item_id:
            item = self.ctx.review_queue.get(item_id)
            if item is not None and item.status == "open":
                self.ctx.review_queue.decide(item_id, decision)
        self.ctx.log(case, "gate", "review.decided", actor=decision.reviewer, kind=str(decision.kind), reason=decision.reason, corrections=decision.corrections)
        self.sm.move(case, PB.DECIDED, str(decision.kind))
        b8_record.run(case, self.ctx)
        self.sm.move(case, PB.RECORDED, "B8 done")
        self.store.save(case)
        return case

    def recheck(self, case: Case | str, updated_po: CanonicalDoc | None = None) -> Case:
        """The updated PO (or an internal fix) arrived: run again from B2; close when aligned."""
        if isinstance(case, str):
            found = self.store.get(case)
            if found is None:
                raise KeyError(case)
            case = found
        self.sm.move(case, PB.EVIDENCE_ASSEMBLED, "recheck: updated PO or internal fix arrived")
        case.data["recheck_count"] = case.data.get("recheck_count", 0) + 1
        case.flags = []
        case.outcome = None
        if updated_po is not None:
            case.data["po_override"] = updated_po
        self.ctx.log(case, "B8", "recheck.started", with_updated_po=updated_po is not None, recheck_count=case.data["recheck_count"])
        return self._run(case, recheck=True)

    def on_decision(self, item: ReviewItem, decision: Decision) -> dict[str, Any]:
        case = self.resume(item.case_id, decision)
        return {"case_id": case.case_id, "state": case.state, "outcome": case.outcome}

    # ── internals ────────────────────────────────────────────────────────────
    def _run(self, case: Case, *, recheck: bool = False) -> Case:
        b2_evidence.run(case, self.ctx)
        if not recheck:
            self.sm.move(case, PB.EVIDENCE_ASSEMBLED, "B2 done")
        b3_read_po.run(case, self.ctx)
        self.sm.move(case, PB.PO_READ, "B3 done")
        b4_normalise.run(case, self.ctx)
        self.sm.move(case, PB.NORMALISED, "B4 done")
        b5_compare.run(case, self.ctx)
        self.sm.move(case, PB.COMPARED, "B5 done")
        self.store.save(case)

        if case.outcome == str(Outcome.MATCHED):
            b8_record.run(case, self.ctx)
            self.sm.move(case, PB.RECORDED, "matched: recorded only")
            if recheck:
                self.sm.move(case, PB.CLOSED, "aligned after the recheck")
            self.store.save(case)
            return case

        b6_explain.run(case, self.ctx)
        self.sm.move(case, PB.EXPLAINED, "B6 done")
        result = b7_route.run(case, self.ctx)
        case.add_codes(*result.codes)
        self.sm.move(case, PB.IN_REVIEW, "B7: waiting for the owner")
        self.store.save(case)
        return case
