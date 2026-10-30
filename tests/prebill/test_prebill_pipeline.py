"""Pre-bill pipeline on the Kraft Heinz anchor and its variations."""

from __future__ import annotations

from factory.evaluation import PrebillCase, score_prebill
from factory.intake import PB
from factory.review import Decision, DecisionKind
from factory.rules import Verdict
from prebill_agent.fixtures import (
    B6_ANSWER,
    MATERIAL,
    PO_REF,
    build,
    clean_world,
    converted_units_world,
    kraft_heinz_world,
    missing_po_world,
)
from prebill_agent.normalise import StaticRates, UnitError, convert_price, convert_qty, qty_factor
from prebill_agent.policy import PrebillPolicy
from prebill_agent.rules import RELEASE_CHECKS
from prebill_agent.schema import CanonicalDoc, CanonicalLine, Charge, DocType


def _failed(case):
    return {r.rule: r for r in case.data["results"] if not r.passed}


def test_kraft_heinz_anchor_is_caught_four_of_four_with_the_right_verdicts():
    h = build(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    case = h.pipeline.process(h.world.ref)

    failed = _failed(case)
    assert set(failed) == {"unit_price", "fuel_surcharge", "quantity", "payment_terms"}
    assert failed["unit_price"].verdict == Verdict.UPDATED_PO_REQUIRED and failed["unit_price"].code == "PRICE.PO_STALE"
    assert failed["unit_price"].evidence["po_price"] == 40.14 and failed["unit_price"].evidence["invoice_price"] == 47.0
    assert failed["fuel_surcharge"].verdict == Verdict.UPDATED_PO_REQUIRED and failed["fuel_surcharge"].evidence["invoice_amount"] == 300.0
    assert failed["quantity"].verdict == Verdict.UPDATED_PO_REQUIRED and failed["quantity"].evidence["difference"] == 250
    assert failed["payment_terms"].verdict == Verdict.INTERNAL_FIX and failed["payment_terms"].code == "TERMS.SAP_WRONG"
    assert case.outcome == "INTERNAL_FIX_OR_MISSING_DATA"
    assert case.data["owners"] == {
        "unit_price": "Pricing & Billing",
        "fuel_surcharge": "Pricing & Billing",
        "quantity": "Customer Service",
        "payment_terms": "AR & Collections",
    }
    assert all(r.evidence for r in failed.values())  # traceability: every flag carries its evidence

    assert case.state == PB.IN_REVIEW and h.review.count("open") == 1
    item = h.review.list()[0]
    assert item.owner == "Ingredion owner (CBA, Sales, PROS for price)" and item.source_ref == "809-6862"
    assert "Fix our side or decide" in item.summary
    assert "updated PO" in item.drafts["po_update_request"] and "Net 120" in item.drafts["internal_note"]
    assert [c["prompt"] for c in h.fake.calls] == ["prebill/b6_explain@v1"]  # the one model call
    assert "explained" in h.audit.events("809-6862") and h.audit.model_calls("809-6862")[0].model_call["prompt"] == "prebill/b6_explain@v1"


def test_matched_invoice_is_recorded_without_a_model_call_or_a_reviewer():
    h = build(clean_world())
    case = h.pipeline.process(h.world.ref)
    assert case.outcome == "MATCHED" and case.state == PB.RECORDED
    assert case.flags == [] and h.review.count() == 0 and h.fake.calls == []
    assert h.audit.events("809-6862")[-1] == "recorded"


def test_units_are_normalised_before_the_rules_run():
    assert qty_factor("CWT", "LB") == 100.0
    assert convert_qty(3_405, "BAG", "LB", {"BAG": 50.0}) == 170_250
    assert convert_price(47.0, "CWT", "LB") == 0.47
    assert StaticRates({("CAD", "USD"): 0.73}).rate("USD", "CAD", None) == 1 / 0.73
    try:
        convert_qty(2, "TON", "LB")
    except UnitError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("ton must not be converted")

    h = build(converted_units_world())
    case = h.pipeline.process(h.world.ref)
    assert case.outcome == "MATCHED"
    assert any("BAG -> 170250" in r for r in [e.record for e in case.data["po_n"].evidence])


def test_missing_po_is_missing_data_routed_to_the_data_owners():
    h = build(missing_po_world())
    case = h.pipeline.process(h.world.ref)
    assert case.has_flag("PO.NOT_FOUND") and case.outcome == "INTERNAL_FIX_OR_MISSING_DATA"
    # redline v2: "Fix our side or decide" goes to the Ingredion owner; the data gap stays named on the item
    assert case.state == PB.IN_REVIEW and h.review.list()[0].owner == "Ingredion owner (CBA, Sales, PROS for price)"
    assert "PO.NOT_FOUND" in {f["code"] for f in h.review.list()[0].flags}


def test_explanation_falls_back_to_the_template_when_the_model_has_no_answer():
    h = build(kraft_heinz_world())  # no B6 answer configured: the fake raises LookupError
    case = h.pipeline.process(h.world.ref)
    explanation = case.data["explanation"]
    assert set(explanation.summary_by_category) == {"unit_price", "fuel_surcharge", "quantity", "payment_terms"}
    assert "Updated purchase order needed" in explanation.draft_request and "AR & Collections" in explanation.draft_internal_note
    assert "over-quantity" in explanation.risk_note
    recorded = [r for r in h.audit.for_case("809-6862") if r.event == "explained"][0]
    assert recorded.data["source"] == "template"


def test_first_release_runs_all_four_checks_and_a_subset_policy_still_works():
    assert RELEASE_CHECKS[1] == ("unit_price", "freight", "fuel_surcharge", "quantity", "payment_terms")
    h = build(kraft_heinz_world(), policy=PrebillPolicy(checks=("unit_price", "freight", "fuel_surcharge")))
    case = h.pipeline.process(h.world.ref)
    assert set(_failed(case)) == {"unit_price", "fuel_surcharge"}
    assert case.outcome == "UPDATED_PO_REQUIRED" and h.review.list()[0].owner == "Customer Service or Commercial"


def test_owner_decision_then_recheck_with_the_updated_po_closes_the_case():
    h = build(kraft_heinz_world(), b6_answers=[B6_ANSWER])
    case = h.pipeline.process(h.world.ref)
    case = h.pipeline.resume(case, Decision(kind=DecisionKind.APPROVE, reviewer="pricing-lead", reason="confirmed; PO update requested"))
    assert case.state == PB.RECORDED and h.review.count("open") == 0

    # the customer sends the updated PO and AR fixes the terms in SAP
    updated_po = CanonicalDoc(
        doc_type=DocType.PO, order_ref=PO_REF, source="ariba", currency="USD", payment_terms_days=120,
        lines=[CanonicalLine(line_no=1, material=MATERIAL, qty=170_250, qty_uom="LB", unit_price=47.0, price_uom="CWT")],
        charges=[Charge(type="fuel_surcharge", amount=300.0)],
    )
    h.world.sap.invoices["809-6862"].payment_terms_days = 120
    case = h.pipeline.recheck(case, updated_po)
    assert case.outcome == "MATCHED" and case.state == PB.CLOSED and case.flags == []
    assert case.data["recheck_count"] == 1 and "recheck.started" in h.audit.events("809-6862")


def test_the_pipeline_has_no_way_to_write_to_an_ingredion_system():
    h = build(kraft_heinz_world())
    for connector in (h.ctx.sap, h.ctx.pros, h.ctx.salesforce, h.ctx.ariba, h.ctx.termsync, h.ctx.rate_files, h.ctx.mailbox):
        for method in ("create_order", "complete", "set_status", "return_case", "update", "write", "post", "release_invoice", "send_email"):
            assert not hasattr(connector, method), f"{type(connector).__name__}.{method}"


def test_scorecard_from_pipeline_results_passes_the_anchor():
    cases = []
    for world in (kraft_heinz_world(), clean_world()):
        h = build(world)
        case = h.pipeline.process(world.ref)
        failed = _failed(case)
        cases.append(PrebillCase(order_ref=world.ref.order_ref if world.expected_flags else "clean", expected_flags=set(world.expected_flags), predicted_flags=set(failed), traceable=all(r.evidence for r in failed.values())))
    card = score_prebill(cases)
    assert card.anchor_caught == "4/4" and card.catch_rate == 1.0 and card.false_alarm_rate == 0.0
    assert card.verdicts["catch_rate"] == "scale_up" and card.verdicts["unattended_actions"] == "scale_up"
