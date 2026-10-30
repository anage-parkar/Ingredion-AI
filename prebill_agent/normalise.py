"""B4 helpers: unit-of-measure and currency conversion, and line pairing.

Mass units pivot through pounds; packaging units (BAG, DRUM, PALLET, CASE) need a
per-material factor from the reference data, and ambiguous units ("ton") are never
guessed. Every conversion leaves an evidence record on the document.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from .schema import CanonicalDoc, CanonicalLine, EvidenceRef

MASS_TO_LB: dict[str, float] = {
    "LB": 1.0,
    "LBS": 1.0,
    "POUND": 1.0,
    "CWT": 100.0,
    "KG": 2.20462,
    "KGS": 2.20462,
    "MT": 2204.62,
    "TONNE_METRIC": 2204.62,
    "G": 0.00220462,
}
AMBIGUOUS_UNITS = {"TON", "TONS", "T", "TONNE", "TONNES"}
PACKAGING_UNITS = {"BAG", "BAGS", "DRUM", "DRUMS", "PALLET", "PALLETS", "CASE", "CASES", "TOTE", "TOTES", "EA", "EACH"}


class UnitError(ValueError):
    pass


def _lb_per_unit(uom: str, factors: Mapping[str, float] | None) -> float:
    unit = (uom or "").strip().upper()
    if unit in AMBIGUOUS_UNITS:
        raise UnitError(f"unit {uom!r} is ambiguous (US or metric ton); not converted")
    if unit in MASS_TO_LB:
        return MASS_TO_LB[unit]
    if factors and unit in {k.upper() for k in factors}:
        return float({k.upper(): v for k, v in factors.items()}[unit])
    if unit in PACKAGING_UNITS:
        raise UnitError(f"no per-material weight for unit {uom!r}")
    raise UnitError(f"unknown unit {uom!r}")


def qty_factor(from_uom: str, to_uom: str, factors: Mapping[str, float] | None = None) -> float:
    """Multiply a quantity in ``from_uom`` by this to get ``to_uom``."""
    if (from_uom or "").strip().upper() == (to_uom or "").strip().upper():
        return 1.0
    return _lb_per_unit(from_uom, factors) / _lb_per_unit(to_uom, factors)


def convert_qty(value: float, from_uom: str, to_uom: str, factors: Mapping[str, float] | None = None) -> float:
    return round(value * qty_factor(from_uom, to_uom, factors), 6)


def convert_price(price: float, from_price_uom: str, to_price_uom: str, factors: Mapping[str, float] | None = None) -> float:
    """A price per ``from_price_uom`` expressed per ``to_price_uom`` (47.00/CWT -> 0.47/LB)."""
    return round(price / qty_factor(from_price_uom, to_price_uom, factors), 6)


class FxRates(Protocol):
    def rate(self, from_ccy: str, to_ccy: str, on_date: str | None) -> float: ...


class StaticRates:
    def __init__(self, rates: Mapping[tuple[str, str], float] | None = None) -> None:
        self._rates = {(a.upper(), b.upper()): r for (a, b), r in (rates or {}).items()}

    def rate(self, from_ccy: str, to_ccy: str, on_date: str | None) -> float:
        a, b = from_ccy.upper(), to_ccy.upper()
        if a == b:
            return 1.0
        if (a, b) in self._rates:
            return self._rates[(a, b)]
        if (b, a) in self._rates:
            return 1.0 / self._rates[(b, a)]
        raise UnitError(f"no exchange rate {a}->{b}")


def normalise_doc(
    doc: CanonicalDoc,
    *,
    qty_uom: str,
    price_uom: str,
    currency: str | None,
    on_date: str | None,
    rates: FxRates | None = None,
    factors: Mapping[str, float] | None = None,
) -> CanonicalDoc:
    """Return a copy with quantities, prices and currency in the target units."""
    out = doc.model_copy(deep=True)
    fx = 1.0
    if currency and doc.currency and doc.currency.upper() != currency.upper():
        if rates is None:
            raise UnitError(f"no rate provider to convert {doc.currency} to {currency}")
        fx = rates.rate(doc.currency, currency, on_date)
        out.currency = currency
        out.evidence.append(EvidenceRef(field="currency", system="conversion", record=f"{doc.currency}->{currency} @ {fx} on {on_date}"))
    for line in out.lines:
        if line.qty_uom.upper() != qty_uom.upper():
            converted = convert_qty(line.qty, line.qty_uom, qty_uom, factors)
            out.evidence.append(EvidenceRef(field=f"line{line.line_no}.qty", system="conversion", record=f"{line.qty} {line.qty_uom} -> {converted} {qty_uom}"))
            line.qty, line.qty_uom = converted, qty_uom.upper()
        if line.unit_price is not None:
            source_uom = line.price_uom or line.qty_uom
            price = line.unit_price * fx
            if source_uom.upper() != price_uom.upper():
                price = convert_price(price, source_uom, price_uom, factors)
                out.evidence.append(EvidenceRef(field=f"line{line.line_no}.unit_price", system="conversion", record=f"{line.unit_price}/{source_uom} -> {price}/{price_uom}"))
            line.unit_price, line.price_uom = round(price, 6), price_uom.upper()
    if fx != 1.0:
        for charge in out.charges:
            charge.amount = round(charge.amount * fx, 2)
    return out


def pair_lines(po: CanonicalDoc, invoice: CanonicalDoc) -> list[tuple[CanonicalLine | None, CanonicalLine]]:
    """Each invoice line with its PO line: by material first, then by line number."""
    remaining = list(po.lines)
    pairs: list[tuple[CanonicalLine | None, CanonicalLine]] = []
    for inv in invoice.lines:
        match = next((p for p in remaining if p.material.strip().casefold() == inv.material.strip().casefold()), None)
        if match is None:
            match = next((p for p in remaining if p.line_no == inv.line_no), None)
        if match is not None:
            remaining.remove(match)
        pairs.append((match, inv))
    return pairs
