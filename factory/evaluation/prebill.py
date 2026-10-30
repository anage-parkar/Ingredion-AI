"""Pre-bill scorecard (business briefing, slide "How we measure success").

| Measure                         | Scale up                 | Extend if | Stop if                 |
| Catch rate (incl. KH 4/4)       | ≥ 95%                    | 85–95%    | < 85%                   |
| False alarms on clean invoices  | ≤ 10%                    | 10–20%    | > 20%                   |
| Traceability                    | 100%                     | ≥ 95%     | < 95%                   |
| Reviewer agreement              | ≥ 85%                    | 70–85%    | < 70%                   |
| Time saved per case             | ≥ 30%                    | 15–30%    | < 15%                   |
| Actions without a person        | 0                        | —         | any                     |
| Missing data flagged            | 100%, in ≤ 15% of cases  | 15–25%    | any missed or > 25%     |
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

CHECKS: tuple[str, ...] = ("unit_price", "freight", "fuel_surcharge", "quantity", "payment_terms")
ANCHOR_ORDER = "809-6862"  # Kraft Heinz; all four checks must be caught


@dataclass
class PrebillCase:
    order_ref: str
    expected_flags: set[str] = field(default_factory=set)  # checks that truly fail (labels)
    predicted_flags: set[str] = field(default_factory=set)  # checks the agent flagged
    traceable: bool = True  # every flag points at a source record and a rule
    reviewer_agreed: bool | None = None  # None = not reviewed (matched, or not yet)
    missing_data_expected: bool = False
    missing_data_flagged: bool = False
    unattended_action: bool = False  # must always be False by construction
    seconds_manual: float | None = None
    seconds_agent: float | None = None


@dataclass
class PrebillScorecard:
    n_cases: int
    catch_rate: float
    catch_by_check: dict[str, float]
    anchor_caught: str  # "4/4", "3/4", "n/a"
    false_alarm_rate: float
    traceability: float
    reviewer_agreement: float | None
    time_saved_pct: float | None
    unattended_actions: int
    missing_data_flag_rate: float | None
    missing_data_share: float
    verdicts: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _rate(num: float, den: float) -> float:
    return round(num / den, 4) if den else 0.0


def _band(value: float | None, scale: float, extend: float, *, higher_is_better: bool = True) -> str:
    if value is None:
        return "n/a"
    if higher_is_better:
        return "scale_up" if value >= scale else "extend" if value >= extend else "stop"
    return "scale_up" if value <= scale else "extend" if value <= extend else "stop"


def score_prebill(cases: Iterable[PrebillCase]) -> PrebillScorecard:
    items = list(cases)
    true_total = 0
    caught_total = 0
    by_check_true: dict[str, int] = dict.fromkeys(CHECKS, 0)
    by_check_caught: dict[str, int] = dict.fromkeys(CHECKS, 0)
    clean = flagged_clean = 0
    flagged_cases = traceable_cases = 0
    reviewed = agreed = 0
    md_expected = md_caught = md_flagged = 0
    manual = agent = 0.0
    timed = 0
    unattended = 0
    anchor = "n/a"

    for c in items:
        true_total += len(c.expected_flags)
        caught = c.expected_flags & c.predicted_flags
        caught_total += len(caught)
        for check in c.expected_flags:
            by_check_true[check] = by_check_true.get(check, 0) + 1
        for check in caught:
            by_check_caught[check] = by_check_caught.get(check, 0) + 1
        if not c.expected_flags and not c.missing_data_expected:
            clean += 1
            if c.predicted_flags or c.missing_data_flagged:
                flagged_clean += 1
        if c.predicted_flags or c.missing_data_flagged:
            flagged_cases += 1
            traceable_cases += int(c.traceable)
        if c.reviewer_agreed is not None:
            reviewed += 1
            agreed += int(c.reviewer_agreed)
        if c.missing_data_expected:
            md_expected += 1
            md_caught += int(c.missing_data_flagged)
        md_flagged += int(c.missing_data_flagged)
        if c.seconds_manual and c.seconds_agent is not None:
            manual += c.seconds_manual
            agent += c.seconds_agent
            timed += 1
        unattended += int(c.unattended_action)
        if c.order_ref == ANCHOR_ORDER:
            anchor = f"{len(caught)}/{len(c.expected_flags)}"

    catch_rate = _rate(caught_total, true_total)
    false_alarms = _rate(flagged_clean, clean)
    traceability = _rate(traceable_cases, flagged_cases) if flagged_cases else 1.0
    reviewer_agreement = _rate(agreed, reviewed) if reviewed else None
    time_saved = round(1 - agent / manual, 4) if timed and manual else None
    md_flag_rate = _rate(md_caught, md_expected) if md_expected else None
    md_share = _rate(md_flagged, len(items))

    anchor_ok = anchor in ("n/a", "4/4")
    verdicts = {
        "catch_rate": "stop" if not anchor_ok else _band(catch_rate, 0.95, 0.85),
        "false_alarms": _band(false_alarms, 0.10, 0.20, higher_is_better=False),
        "traceability": _band(traceability, 1.0, 0.95),
        "reviewer_agreement": _band(reviewer_agreement, 0.85, 0.70),
        "time_saved": _band(time_saved, 0.30, 0.15),
        "unattended_actions": "scale_up" if unattended == 0 else "stop",
        "missing_data": (
            "n/a"
            if md_flag_rate is None
            else "stop"
            if md_flag_rate < 1.0 or md_share > 0.25
            else "scale_up"
            if md_share <= 0.15
            else "extend"
        ),
    }
    return PrebillScorecard(
        n_cases=len(items),
        catch_rate=catch_rate,
        catch_by_check={k: _rate(by_check_caught.get(k, 0), v) for k, v in by_check_true.items() if v},
        anchor_caught=anchor,
        false_alarm_rate=false_alarms,
        traceability=traceability,
        reviewer_agreement=reviewer_agreement,
        time_saved_pct=time_saved,
        unattended_actions=unattended,
        missing_data_flag_rate=md_flag_rate,
        missing_data_share=md_share,
        verdicts=verdicts,
    )
