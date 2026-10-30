"""B5 · Compare: the rules decide, one result per check, with evidence and a verdict.
Code only. The outcome is Matched, Updated PO required, or Internal fix or missing
data; a matched invoice is recorded and never waits for a model or a person."""

from __future__ import annotations

from factory.case import Case, StepResult
from factory.rules import RuleResult, Verdict

from ..context import PrebillContext
from ..rules import MatchContext, build_ruleset, overall_outcome

STEP = "B5"


def run(case: Case, ctx: PrebillContext) -> StepResult:
    po_n = case.data.get("po_n")
    invoice_n = case.data["invoice_n"]
    reference = case.data["reference"]
    pairs = case.data.get("pairs", [])
    checks = tuple(ctx.policy.checks)
    results: list[RuleResult] = []

    if po_n is None:
        results.append(RuleResult("po", False, "PO.NOT_FOUND", "no purchase order to compare the draft invoice against", "po", Verdict.MISSING_DATA))
    else:
        if case.data.get("normalisation_failed"):
            for check in checks:
                if check in ("unit_price", "quantity"):
                    results.append(RuleResult(check, False, "UOM.AMBIGUOUS", "units could not be normalised; not compared", check, Verdict.MISSING_DATA))
            checks = tuple(c for c in checks if c not in ("unit_price", "quantity"))
        mctx = MatchContext(po_n, invoice_n, reference, pairs, ctx.policy.price_tolerance, ctx.policy.qty_default_tolerance_pct)
        results.extend(build_ruleset(checks).run(mctx))
    if any(f.code == "DATA.MISSING" for f in case.flags):
        results.append(RuleResult("evidence", False, "DATA.MISSING", "evidence missing from the draft invoice", "evidence", Verdict.MISSING_DATA))

    outcome = overall_outcome(results)
    case.outcome = str(outcome)
    case.data["results"] = results
    for r in results:
        if not r.passed and r.code and not case.has_flag(r.code):
            case.add_flag(r.code, r.message, r.field, verdict=r.verdict, owner=r.owner, **r.evidence)
    ctx.log(case, STEP, "compared", outcome=str(outcome), checks=list(ctx.policy.checks), results=[r.to_dict() for r in results])
    return StepResult.ok()
