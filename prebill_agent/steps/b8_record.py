"""B8 · Record: the decision, the reason and the evidence per order, in the
append-only audit trail, and one row in ``agent_b_outcomes`` for the scorecard."""

from __future__ import annotations

from factory.case import Case, StepResult

from ..context import PrebillContext

STEP = "B8"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    decision = case.data.get("decision")
    results = case.data.get("results", [])
    ctx.log(
        case, STEP, "recorded",
        actor=decision.reviewer if decision else "agent",
        outcome=case.outcome,
        failed_checks=[r.rule for r in results if not r.passed],
        reason_codes=list(case.reason_codes),
        owners=case.data.get("owners", {}),
        decision=decision.to_dict() if decision else None,
        recheck_count=case.data.get("recheck_count", 0),
    )
    ctx.record_outcome(case)
    return StepResult.done()
