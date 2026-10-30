"""A10 · Update the Salesforce case: order number, status, an audit note, the outcome
marker (Agent-created, Agent-assisted) and the incompletion follow-ups from SAP.
Retried independently of A9 by the pipeline, so a Salesforce failure can never
cause a second SAP order."""

from __future__ import annotations

from factory.audit import Outcome
from factory.case import Case, StepResult
from factory.review import DecisionKind

from ..context import OrderIntakeContext

STEP = "A10"


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    order = case.data["order"]
    decision = case.data.get("decision")
    outcome = Outcome.AGENT_ASSISTED if decision is not None and decision.kind == DecisionKind.CORRECT else Outcome.AGENT_CREATED
    reviewer = decision.reviewer if decision is not None else "n/a"
    follow_ups = [f"{item.field}: {item.message}" + (f" (item {item.item})" if item.item else "") for item in case.data.get("incompletion", [])]
    note = (
        f"Processed by: Agent · {outcome} · SAP order {order['order_number']} · reviewer: {reviewer} · "
        f"reason codes: {', '.join(case.reason_codes) or 'none'}"
        + (f" · incompletion follow-ups: {len(follow_ups)}" if follow_ups else "")
    )
    ctx.salesforce.complete(case.case_id, [order["order_number"]], str(outcome), note, follow_ups=follow_ups)
    case.outcome = str(outcome)
    ctx.log(case, STEP, "case.completed", outcome=str(outcome), order_number=order["order_number"], reviewer=reviewer, follow_ups=follow_ups)
    return StepResult.done()
