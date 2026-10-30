"""Pre-bill policy: which checks are switched on (rollout by release), tolerances,
and whether the model or a template writes the explanation."""

from __future__ import annotations

from dataclasses import dataclass

from .rules import ALL_CHECKS


@dataclass
class PrebillPolicy:
    # Rollout: release 1 = price, freight, fuel surcharge; then quantity; then payment
    # terms. The backtest runs all five so the Kraft Heinz anchor is scored 4 of 4.
    checks: tuple[str, ...] = ALL_CHECKS
    price_tolerance: float = 0.005  # in price units after conversion (exact in practice)
    qty_default_tolerance_pct: float | None = None  # a PO with no printed tolerance means exact
    explain_with_model: bool = True  # B6 on Vertex AI; a template is the fallback, never silence
    max_prompt_chars: int = 60_000
