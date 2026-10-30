"""Read-only connectors over the extract landing (Cloud Storage bucket or a local
folder with the same layout) for the two sources that have no read interface and
arrive as scheduled CSV extracts until the data team promotes them to gold: the
freight and fuel-surcharge schedules with the packaging factors, and the TermSync
dispute history. When configured they take precedence over gold and the stubs.

Layout: ``<source>/<anything>.csv``, newest object per source wins.

* ``freight_terms`` and ``fuel_surcharge``: sold_to, applies, amount, basis, currency,
  valid_from, valid_to, record
* ``material_factors``: material, uom, lb_per_unit
* ``disputes``: sold_to, invoice, code, date, amount, status
"""

from __future__ import annotations

from typing import Any

from ..schema import ChargeTerms
from .extracts import ExtractLanding

_TRUE = {"1", "true", "yes", "y", "t"}


def _bool(value: Any) -> bool:
    return str(value or "").strip().lower() in _TRUE


def _float(value: Any) -> float | None:
    text = str(value or "").strip()
    return float(text) if text else None


def _valid_on(row: dict[str, str], on_date: str) -> bool:
    start, end = (row.get("valid_from") or "").strip(), (row.get("valid_to") or "").strip()
    return (not start or start[:10] <= on_date[:10]) and (not end or end[:10] >= on_date[:10])


class LandingRateFiles:
    name = "landing_rate_files"

    def __init__(self, landing: ExtractLanding, *, freight_source: str = "freight_terms", surcharge_source: str = "fuel_surcharge", factors_source: str = "material_factors") -> None:
        self.landing = landing
        self.freight_source = freight_source
        self.surcharge_source = surcharge_source
        self.factors_source = factors_source

    def _terms(self, source: str, sold_to: str, on_date: str) -> ChargeTerms | None:
        rows = [r for r in self.landing.latest(source) if (r.get("sold_to") or "").strip() == sold_to and _valid_on(r, on_date)]
        if not rows:
            return None
        row = max(rows, key=lambda r: (r.get("valid_from") or ""))
        return ChargeTerms(
            applies=_bool(row.get("applies")),
            amount=_float(row.get("amount")),
            basis=(row.get("basis") or "").strip() or None,
            source=f"extract:{source}",
            record=(row.get("record") or "").strip() or f"{source} extract, sold-to {sold_to}",
        )

    def freight_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None:
        return self._terms(self.freight_source, sold_to, on_date)

    def surcharge_terms(self, sold_to: str, on_date: str) -> ChargeTerms | None:
        return self._terms(self.surcharge_source, sold_to, on_date)

    def material_factors(self, material: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for row in self.landing.latest(self.factors_source):
            if (row.get("material") or "").strip() == material and _float(row.get("lb_per_unit")) is not None:
                out[(row.get("uom") or "").strip().upper()] = float(row["lb_per_unit"])
        return out


class LandingTermSync:
    name = "landing_termsync"

    def __init__(self, landing: ExtractLanding, *, source: str = "disputes") -> None:
        self.landing = landing
        self.source = source

    def dispute_history(self, sold_to: str) -> list[dict[str, Any]]:
        return [
            {"invoice": (r.get("invoice") or "").strip(), "code": (r.get("code") or "").strip(), "date": (r.get("date") or "").strip(), "amount": _float(r.get("amount")), "status": (r.get("status") or "").strip() or None}
            for r in self.landing.latest(self.source)
            if (r.get("sold_to") or "").strip() == sold_to
        ]


__all__ = ["LandingRateFiles", "LandingTermSync"]
