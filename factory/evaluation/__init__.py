"""Evaluation suite: the scorecards both SOWs gate releases on.

* Order Intake: recovery rate, undetected-error rate and field-level accuracy against
  the final SAP orders (Stage 1 backtest, Stage 4 holdout, every build).
* Pre-bill: catch rate (incl. the Kraft Heinz anchor 4 of 4), false alarms, traceability,
  reviewer agreement, time saved, unattended actions, missing data flagged.

The scorers are pure functions over plain records so they run on fixtures in CI and
on reviewer-labelled production data later without change.
"""

from .order_intake import (
    GATE_THRESHOLDS,
    KEY_FIELDS,
    Answer,
    Prediction,
    Scorecard,
    score_order_intake,
    values_match,
)
from .prebill import CHECKS, PrebillCase, PrebillScorecard, score_prebill

__all__ = [
    "CHECKS",
    "GATE_THRESHOLDS",
    "KEY_FIELDS",
    "Answer",
    "PrebillCase",
    "PrebillScorecard",
    "Prediction",
    "Scorecard",
    "score_order_intake",
    "score_prebill",
    "values_match",
]
