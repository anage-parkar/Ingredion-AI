"""A1 · Pick up the case.

Salesforce routes each cohort of customers to the agent; the case arrives with the
original email body and attachments. The agent claims it (a status on the case) so
the Existing RPA, which keeps the cohorts not yet moved, and manual staff skip it.
In fallback mode the same step reads an RPA-failed case instead.
"""

from __future__ import annotations

from factory.case import Case, StepResult

from ..context import OrderIntakeContext

STEP = "A1"
CLAIM_STATUS = "agent_in_progress"


def run(case: Case, ctx: OrderIntakeContext) -> StepResult:
    intake = case.data["intake"]
    email = ctx.salesforce.get_email(case.case_id)
    case.data["email"] = email
    origin = f"cohort {intake.cohort}" if intake.cohort else intake.source
    if intake.error_category:
        origin += f"; RPA error: {intake.error_category}: {intake.error_detail}"
    ctx.salesforce.set_status(case.case_id, CLAIM_STATUS, note=f"Claimed by the Order Intake agent ({origin})")
    ctx.log(
        case,
        STEP,
        "case.picked_up",
        source=intake.source,
        cohort=intake.cohort,
        customer=intake.customer,
        record_id=intake.record_id,
        error_category=str(intake.error_category) if intake.error_category else None,
        attachments=[a.name for a in email.attachments],
        body_chars=len(email.body or ""),
    )
    return StepResult.ok()
