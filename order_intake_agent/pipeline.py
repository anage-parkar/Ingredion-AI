"""The Order Intake pipeline (redline v2): sequences A1 to A10, owns the state
machine, parks cases at the human gate and resumes them on a decision, returns
cases to the manual queue with their reason codes, and reconciles anything left in
``submitting`` after a restart. Steps never call each other; the order lives here.
"""

from __future__ import annotations

from typing import Any

from factory.audit import Outcome
from factory.case import Case, Disposition, StepResult
from factory.intake import OI, ORDER_INTAKE, IllegalTransition, RawCase
from factory.review import Decision, DecisionKind, ReviewItem

from . import AGENT
from .case_store import CaseStore, InMemoryCaseStore
from .context import OrderIntakeContext
from .models import IntakeCase
from .steps import (
    a1_pickup,
    a2_classify,
    a3_extract,
    a4_validate,
    a5_score,
    a6_exceptions,
    a7_review_summary,
    a8_build_payload,
    a9_create_order,
    a10_update_case,
)


class KillSwitchEngaged(RuntimeError):
    pass


def apply_corrections(case: Case, corrections: dict[str, Any]) -> None:
    """Reviewer corrections onto the case.

    Top-level fields change the extraction; ``sold_to_id`` / ``ship_to_id`` /
    ``bill_to_id`` pin an SAP partner; ``line<N>.sap_material`` and
    ``line<N>.sales_uom`` pin the CMIR choice; ``line<N>.quantity`` / ``.uom`` /
    ``.unit_price`` change the line. A4 rebuilds the validation afterwards.
    """
    ex = case.data["extraction"]
    overrides = case.data.setdefault("overrides", {"lines": {}})
    overrides.setdefault("lines", {})
    for key, value in corrections.items():
        if key in ("po_number", "sold_to", "ship_to", "bill_to", "requested_delivery_date", "currency"):
            setattr(ex, key, value)
        elif key in ("sold_to_id", "ship_to_id", "bill_to_id"):
            overrides[key] = value
        elif key.startswith("line") and "." in key:
            head, _, attr = key.partition(".")
            line_no = int(head[4:])
            if attr in ("sap_material", "sales_uom"):
                overrides["lines"].setdefault(str(line_no), {})[attr] = value
            elif attr in ("quantity", "uom", "unit_price", "price_uom", "customer_material", "line_total"):
                for line in ex.lines:
                    if line.line_no == line_no:
                        setattr(line, attr, value)
            else:
                raise KeyError(f"unknown line correction {key!r}")
        else:
            raise KeyError(f"unknown correction field {key!r}")


class OrderIntakePipeline:
    _PLAN = (
        ("A1", a1_pickup.run, None),
        ("A2", a2_classify.run, OI.CLASSIFIED),
        ("A3", a3_extract.run, OI.EXTRACTED),
        ("A4", a4_validate.run, OI.VALIDATED),
        ("A5", a5_score.run, OI.SCORED),
        ("A6", a6_exceptions.run, OI.EXCEPTIONS),
        ("A7", a7_review_summary.run, None),
    )

    def __init__(self, ctx: OrderIntakeContext, case_store: CaseStore | None = None) -> None:
        self.ctx = ctx
        self.store: CaseStore = case_store or InMemoryCaseStore()
        self.sm = ORDER_INTAKE

    # ── entry points ─────────────────────────────────────────────────────────
    def process(self, intake: IntakeCase) -> Case:
        if self.ctx.kill_switch is not None and self.ctx.kill_switch.is_engaged():
            raise KillSwitchEngaged("kill switch engaged: no new cases are taken")
        case = Case(case_id=intake.case_id, agent=AGENT)
        case.data["intake"] = intake
        self.sm.start(case, f"case taken from {intake.source}")
        self._save(case)
        self.ctx.log(case, "pipeline", "case.started", source=intake.source, cohort=intake.cohort, mode=self.ctx.policy.mode)
        return self._run_intake(case)

    def process_raw(self, raw: RawCase) -> Case:
        return self.process(IntakeCase.model_validate(raw.payload))

    def resume(self, case: Case | str, decision: Decision) -> Case:
        """After the human gate. Approve or correct continues; reject goes to the manual queue."""
        if isinstance(case, str):
            found = self.store.get(case)
            if found is None:
                raise KeyError(case)
            case = found
        if case.state != OI.IN_REVIEW:
            raise IllegalTransition(f"case {case.case_id} is in {case.state!r}, not in review")
        case.data["decision"] = decision
        item_id = case.data.get("review_item_id")
        if item_id:  # keep the queue consistent whichever way the decision arrived
            item = self.ctx.review_queue.get(item_id)
            if item is not None and item.status == "open":
                self.ctx.review_queue.decide(item_id, decision)
        self.ctx.log(case, "gate", "review.decided", actor=decision.reviewer, kind=str(decision.kind), reason=decision.reason, corrections=decision.corrections, confirmed_duplicate=decision.confirmed_duplicate)
        if decision.confirmed_duplicate:
            case.add_codes("DUP.CONFIRMED")
            case.outcome = str(Outcome.DUPLICATE)
            self.sm.move(case, OI.DUPLICATE_CLOSED, "reviewer confirmed the duplicate")
            self.ctx.salesforce.complete(case.case_id, [], str(Outcome.DUPLICATE), f"Duplicate confirmed by {decision.reviewer}: {decision.reason}")
            self.ctx.log(case, "gate", "case.closed_duplicate", actor=decision.reviewer)
            self._save(case)
            self.ctx.record_outcome(case)
            return case
        if decision.kind == DecisionKind.REJECT:
            return self._return(case, ["REVIEW.REJECTED"], "gate", decision.reason)
        if decision.kind == DecisionKind.CORRECT:
            apply_corrections(case, decision.corrections)
            case.add_codes("REVIEW.CORRECTED")
        self.sm.move(case, OI.APPROVED, str(decision.kind))
        self._save(case)
        if decision.kind == DecisionKind.CORRECT:
            r4 = a4_validate.run(case, self.ctx, recheck=True)
            if r4.disposition == Disposition.EXIT:
                return self._return(case, r4.codes, "A4", r4.note)
            if self.ctx.policy.revalidate_after_correction:
                r5 = a5_score.run(case, self.ctx, recheck=True)
                if r5.disposition == Disposition.REVIEW:
                    return self._park(case, ["REVIEW.RECHECK_FLAGGED", *r5.codes], "A5", "new flag after correction")
        return self._create(case)

    def on_decision(self, item: ReviewItem, decision: Decision) -> dict[str, Any]:
        """Hook for the review router."""
        case = self.resume(item.case_id, decision)
        return {"case_id": case.case_id, "state": case.state, "outcome": case.outcome, "reason_codes": list(case.reason_codes)}

    def retry_case_update(self, case: Case) -> Case:
        if case.state != OI.CREATED:
            raise IllegalTransition(f"case {case.case_id} is in {case.state!r}, not created")
        return self._update_case(case)

    def reconcile_in_flight(self) -> list[Case]:
        """On start-up: any case left in ``submitting`` is looked up in SAP before anything else."""
        out: list[Case] = []
        for case in self.store.in_state(OI.SUBMITTING):
            self.ctx.log(case, "A9", "sap.reconcile_on_restart", idempotency_key=case.idempotency_key)
            out.append(self._submit(case))
        return out

    # ── internals ────────────────────────────────────────────────────────────
    def _save(self, case: Case) -> None:
        self.store.save(case)

    def _run_intake(self, case: Case) -> Case:
        index = 0
        while index < len(self._PLAN):
            name, step, next_state = self._PLAN[index]
            result: StepResult = step(case, self.ctx)
            if result.disposition == Disposition.RETRY:  # A4 asked for one re-read
                reread = a3_extract.run(case, self.ctx, hints=case.data.get("reread_hints", []))
                if reread.disposition != Disposition.CONTINUE:
                    return self._dispatch(case, reread, "A3")
                self.sm.move(case, OI.EXTRACTED, "PO re-read once")
                self._save(case)
                continue  # A4 again
            if result.disposition != Disposition.CONTINUE:
                return self._dispatch(case, result, name)
            if next_state:
                self.sm.move(case, next_state, f"{name} done")
            self._save(case)
            index += 1
        return self._create(case)  # A7 found no reason to review (Phase 2 only)

    def _dispatch(self, case: Case, result: StepResult, step: str) -> Case:
        if result.disposition == Disposition.EXIT:
            return self._return(case, result.codes, step, result.note)
        if result.disposition == Disposition.REVIEW:
            return self._park(case, result.codes, step, result.note)
        if result.disposition == Disposition.DONE:
            return case
        raise RuntimeError(f"unexpected disposition {result.disposition} from {step}")

    def _park(self, case: Case, codes: list[str], step: str, note: str = "") -> Case:
        case.add_codes(*codes)
        if case.state != OI.IN_REVIEW:
            self.sm.move(case, OI.IN_REVIEW, f"{step}: {', '.join(codes) or 'every case is reviewed in Phase 1'}")
        item = a7_review_summary.build_review_item(case, self.ctx)
        self.ctx.review_queue.enqueue(item)
        case.data["review_item_id"] = item.id
        case.data["reviewed_codes"] = [f.code for f in case.flags]
        self.ctx.log(case, step, "review.enqueued", item_id=item.id, codes=codes, note=note)
        self._save(case)
        return case

    def _return(self, case: Case, codes: list[str], step: str, note: str = "") -> Case:
        case.add_codes(*codes)
        case.outcome = str(Outcome.RETURNED)
        self.sm.move(case, OI.RETURNED, f"{step}: {', '.join(codes)}")
        self.ctx.salesforce.return_case(case.case_id, list(case.reason_codes), f"To the manual queue from the Order Intake agent at {step}: {', '.join(codes)}. {note}".strip())
        self.ctx.log(case, step, "case.returned", codes=codes, note=note, all_reason_codes=list(case.reason_codes))
        self._save(case)
        self.ctx.record_outcome(case)
        return case

    def _create(self, case: Case) -> Case:
        r8 = a8_build_payload.run(case, self.ctx)
        if r8.disposition != Disposition.CONTINUE:
            return self._dispatch(case, r8, "A8")
        self.sm.move(case, OI.PAYLOAD_BUILT, "A8 done")
        self.sm.move(case, OI.SUBMITTING, "write-ahead before the SAP call")
        self.ctx.log(case, "A9", "sap.submitting", idempotency_key=case.idempotency_key)
        self._save(case)
        return self._submit(case)

    def _submit(self, case: Case) -> Case:
        r9 = a9_create_order.run(case, self.ctx)
        if r9.disposition == Disposition.EXIT:
            return self._return(case, r9.codes, "A9", r9.note)
        self.sm.move(case, OI.CREATED, "SAP order created")
        self._save(case)
        return self._update_case(case)

    def _update_case(self, case: Case) -> Case:
        try:
            a10_update_case.run(case, self.ctx)
        except Exception as exc:  # Salesforce problem: never re-trigger A9
            case.data["case_update_pending"] = True
            self.ctx.log(case, "A10", "salesforce.update_failed", error=str(exc))
            self.ctx.alert("salesforce_update_failed", f"case {case.case_id}: {exc}", case_id=case.case_id)
            self._save(case)
            return case
        case.data.pop("case_update_pending", None)
        self.sm.move(case, OI.CASE_UPDATED, "A10 done")
        self._save(case)
        self.ctx.record_outcome(case)
        return case
