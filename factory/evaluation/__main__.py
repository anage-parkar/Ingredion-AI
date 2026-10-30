"""Run the scorecards from the command line.

    python -m factory.evaluation prebill        # anchor + clean worlds through the pipeline
    python -m factory.evaluation order-intake   # how the Stage 1 backtest is scored

"Automated evaluation passes in Dev" (Gate 3) is this command returning the
expected verdicts; CI runs the same code through the test suite.
"""

from __future__ import annotations

import argparse
import json
import sys

from .prebill import PrebillCase, score_prebill


def run_prebill() -> dict:
    from prebill_agent.fixtures import (
        B6_ANSWER,
        build,
        clean_world,
        converted_units_world,
        kraft_heinz_world,
    )

    cases: list[PrebillCase] = []
    for world in (kraft_heinz_world(), clean_world(), converted_units_world()):
        h = build(world, b6_answers=[B6_ANSWER])
        case = h.pipeline.process(world.ref)
        failed = [r for r in case.data["results"] if not r.passed]
        cases.append(
            PrebillCase(
                order_ref=f"{world.ref.order_ref}:{world.ref.invoice_ref}" if cases else world.ref.order_ref,
                expected_flags=set(world.expected_flags),
                predicted_flags={r.rule for r in failed},
                traceable=all(bool(r.evidence) for r in failed),
                reviewer_agreed=None,
                unattended_action=False,
            )
        )
    card = score_prebill(cases)
    return card.to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory.evaluation")
    parser.add_argument("agent", nargs="?", default="prebill", choices=["prebill", "order-intake"])
    args = parser.parse_args(argv)
    if args.agent == "prebill":
        card = run_prebill()
        print(json.dumps(card, indent=2))
        return 0 if card["anchor_caught"] == "4/4" and card["false_alarm_rate"] == 0.0 else 1
    print(
        "Order Intake is scored with factory.evaluation.score_order_intake over the Stage 1 backtest: "
        "500 past email POs including RPA-failed POs (SOW No. 07, 8.2(b)); a Prediction per case from the "
        "pipeline's extraction + composite confidence against the final SAP orders (Answer per case). "
        "The scorecard thresholds (2.7) are set at Gate 1 from this backtest; the earlier proposal "
        "(recovery >= 50% at Gate 1, >= 70% at Gate 4, >= 80% before Phase 2; undetected errors <= 2% of key "
        "fields, <= 0.5% before Phase 2) is Parkar's starting point. The sample is Ingredion's to provide within "
        "5 working days of the start (8.1(c)); its RPA failure labels come from order_intake_agent.rpa_errors. "
        "Until then the unit tests exercise the scorer."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
