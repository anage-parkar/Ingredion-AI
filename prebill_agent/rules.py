"""B5 · The five checks and the "which source wins" verdict.

Rules compare the normalised PO with the normalised draft invoice and consult the
reference evidence (contract or PROS price, contract terms, freight and surcharge
terms) to say who is right:

* invoice == reference, PO differs  → ``UPDATED_PO_REQUIRED`` (the PO is stale)
* invoice != reference               → ``INTERNAL_FIX`` (SAP or PROS is wrong)
* no reference                       → ``MISSING_DATA`` (never treated as matched)

Over-shipments are checked before under-shipments; a PO with no printed tolerance
means exact; any charge not on the PO is flagged even when the contract allows it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from factory.audit import Outcome
from factory.rules import Rule, RuleResult, RuleSet, Verdict

from .schema import CanonicalDoc, CanonicalLine, ReferenceData

ALL_CHECKS: tuple[str, ...] = ("unit_price", "freight", "fuel_surcharge", "quantity", "payment_terms")
# Redline v2 (20 Oct 2026): all four checks (price; freight and surcharge; quantity;
# payment terms) are in the first release, and the Kraft Heinz anchor must be caught 4 of 4.
RELEASE_CHECKS: dict[int, tuple[str, ...]] = {1: ALL_CHECKS}

OUTCOME_LABELS = {
    "MATCHED": "Matched",
    "UPDATED_PO_REQUIRED": "Updated PO required",
    "INTERNAL_FIX_OR_MISSING_DATA": "Fix our side or decide",
}


def outcome_label(outcome: str | None) -> str:
    """The redline v2 wording for an outcome code."""
    return OUTCOME_LABELS.get(str(outcome or ""), str(outcome or "undecided"))


@dataclass
class MatchContext:
    po: CanonicalDoc
    invoice: CanonicalDoc
    reference: ReferenceData
    pairs: list[tuple[CanonicalLine | None, CanonicalLine]]
    price_tolerance: float = 0.005  # in price units after conversion
    qty_default_tolerance_pct: float | None = None  # None: exact when the PO prints none
    notes: list[str] = field(default_factory=list)


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


class UnitPriceRule(Rule):
    name = "unit_price"

    def evaluate(self, ctx: MatchContext) -> list[RuleResult]:
        out: list[RuleResult] = []
        for po_line, inv in ctx.pairs:
            fld = f"line{inv.line_no}.unit_price"
            if po_line is None:
                out.append(RuleResult(self.name, False, "LINE.UNPAIRED", f"invoice line {inv.line_no} ({inv.material}) has no PO line", fld, Verdict.MISSING_DATA, evidence={"material": inv.material}))
                continue
            if inv.unit_price is None or po_line.unit_price is None:
                out.append(RuleResult(self.name, False, "DATA.MISSING", f"line {inv.line_no}: a unit price is missing", fld, Verdict.MISSING_DATA, evidence={"po_price": po_line.unit_price, "invoice_price": inv.unit_price}))
                continue
            evidence: dict[str, Any] = {
                "po_price": po_line.unit_price, "invoice_price": inv.unit_price, "price_uom": inv.price_uom,
                "difference": round(inv.unit_price - po_line.unit_price, 4), "currency": ctx.invoice.currency,
            }
            if _close(po_line.unit_price, inv.unit_price, ctx.price_tolerance):
                out.append(Rule.ok(self.name, f"line {inv.line_no}: price {inv.unit_price}/{inv.price_uom} matches", **evidence))
                continue
            ref = ctx.reference.contract_prices.get(inv.line_no)
            if ref is None:
                out.append(RuleResult(self.name, False, "PRICE.MISSING_SAP", f"line {inv.line_no}: PO {po_line.unit_price} vs invoice {inv.unit_price} per {inv.price_uom}; no contract or SAP price to judge", fld, Verdict.MISSING_DATA, evidence=evidence))
                continue
            evidence.update({"contract_price": ref.price, "contract_source": ref.source, "contract_record": ref.record})
            if _close(inv.unit_price, ref.price, ctx.price_tolerance):
                out.append(RuleResult(self.name, False, "PRICE.PO_STALE", f"line {inv.line_no}: invoice {inv.unit_price} equals the {ref.source} price; PO shows {po_line.unit_price} per {inv.price_uom}", fld, Verdict.UPDATED_PO_REQUIRED, evidence=evidence))
            else:
                out.append(RuleResult(self.name, False, "PRICE.SAP_WRONG", f"line {inv.line_no}: invoice {inv.unit_price} differs from the {ref.source} price {ref.price}; SAP side to fix", fld, Verdict.INTERNAL_FIX, evidence=evidence))
        return out


class _ChargeRule(Rule):
    charge_kind = ""
    code_prefix = ""

    def _terms(self, ctx: MatchContext):
        return ctx.reference.freight_terms if self.charge_kind == "freight" else ctx.reference.surcharge_terms

    def evaluate(self, ctx: MatchContext) -> list[RuleResult]:
        inv_total = ctx.invoice.charge_total(self.charge_kind)
        po_total = ctx.po.charge_total(self.charge_kind)
        evidence: dict[str, Any] = {"invoice_amount": inv_total, "po_amount": po_total, "currency": ctx.invoice.currency}
        if inv_total <= po_total + 0.005:
            return [Rule.ok(self.name, f"{self.charge_kind} {inv_total} covered by the PO", **evidence)]
        terms = self._terms(ctx)
        label = self.charge_kind.replace("_", " ")
        if terms is None:
            return [RuleResult(self.name, False, f"{self.code_prefix}.NO_TERMS", f"{label} {inv_total} charged, not on the PO, and no terms found to judge it", self.charge_kind, Verdict.MISSING_DATA, evidence=evidence)]
        evidence.update({"terms_apply": terms.applies, "terms_amount": terms.amount, "terms_basis": terms.basis, "terms_source": terms.source, "terms_record": terms.record})
        if terms.applies:
            return [RuleResult(self.name, False, f"{self.code_prefix}.NOT_ON_PO", f"{label} {inv_total} is in the agreement ({terms.record}) but not on the PO", self.charge_kind, Verdict.UPDATED_PO_REQUIRED, evidence=evidence)]
        return [RuleResult(self.name, False, f"{self.code_prefix}.SAP_WRONG", f"{label} {inv_total} charged although the agreement does not provide for it", self.charge_kind, Verdict.INTERNAL_FIX, evidence=evidence)]


class FreightRule(_ChargeRule):
    name = "freight"
    charge_kind = "freight"
    code_prefix = "FREIGHT"


class FuelSurchargeRule(_ChargeRule):
    name = "fuel_surcharge"
    charge_kind = "fuel_surcharge"
    code_prefix = "SURCHARGE"


class QuantityRule(Rule):
    name = "quantity"

    def evaluate(self, ctx: MatchContext) -> list[RuleResult]:
        out: list[RuleResult] = []
        for po_line, inv in ctx.pairs:
            if po_line is None:
                continue  # reported by the price rule as LINE.UNPAIRED
            tol = po_line.tolerance_pct if po_line.tolerance_pct is not None else ctx.qty_default_tolerance_pct
            upper = po_line.qty * (1 + (tol or 0) / 100)
            lower = po_line.qty * (1 - (tol or 0) / 100)
            evidence = {"po_qty": po_line.qty, "shipped_qty": inv.qty, "uom": inv.qty_uom, "tolerance_pct": tol, "difference": round(inv.qty - po_line.qty, 6)}
            fld = f"line{inv.line_no}.qty"
            if inv.qty > upper + 1e-9:
                out.append(RuleResult(self.name, False, "QTY.OVER", f"line {inv.line_no}: shipped {inv.qty} {inv.qty_uom} against PO {po_line.qty} ({'no tolerance' if tol is None else f'+/-{tol}%'})", fld, Verdict.UPDATED_PO_REQUIRED, evidence=evidence))
            elif inv.qty < lower - 1e-9:
                out.append(RuleResult(self.name, False, "QTY.UNDER", f"line {inv.line_no}: shipped {inv.qty} {inv.qty_uom} below PO {po_line.qty}", fld, Verdict.UPDATED_PO_REQUIRED, evidence=evidence))
            else:
                out.append(Rule.ok(self.name, f"line {inv.line_no}: {inv.qty} {inv.qty_uom} within the PO range", **evidence))
        return out


class PaymentTermsRule(Rule):
    name = "payment_terms"

    def evaluate(self, ctx: MatchContext) -> list[RuleResult]:
        po_days, inv_days = ctx.po.payment_terms_days, ctx.invoice.payment_terms_days
        evidence: dict[str, Any] = {"po_terms_days": po_days, "invoice_terms_days": inv_days}
        if inv_days is None:
            return [RuleResult(self.name, False, "TERMS.MISSING", "the draft invoice carries no payment terms", "payment_terms", Verdict.MISSING_DATA, evidence=evidence)]
        if po_days is None:
            return [Rule.ok(self.name, "PO prints no payment terms; nothing to match", **evidence)]
        if po_days == inv_days:
            return [Rule.ok(self.name, f"payment terms {inv_days} days match", **evidence)]
        contract = ctx.reference.contract_terms_days
        evidence.update({"contract_terms_days": contract, "terms_source": ctx.reference.terms_source, "terms_record": ctx.reference.terms_record})
        if contract is None:
            return [RuleResult(self.name, False, "TERMS.MISSING", f"PO {po_days} vs invoice {inv_days} days; no contract terms to judge", "payment_terms", Verdict.MISSING_DATA, evidence=evidence)]
        if contract == inv_days:
            return [RuleResult(self.name, False, "TERMS.PO_STALE", f"invoice terms {inv_days} days equal the contract; the PO shows {po_days}", "payment_terms", Verdict.UPDATED_PO_REQUIRED, evidence=evidence)]
        return [RuleResult(self.name, False, "TERMS.SAP_WRONG", f"invoice terms {inv_days} days differ from the contract ({contract}); PO shows {po_days}", "payment_terms", Verdict.INTERNAL_FIX, evidence=evidence)]


_RULES: dict[str, type[Rule]] = {
    "unit_price": UnitPriceRule,
    "freight": FreightRule,
    "fuel_surcharge": FuelSurchargeRule,
    "quantity": QuantityRule,
    "payment_terms": PaymentTermsRule,
}


def build_ruleset(checks: Iterable[str] = ALL_CHECKS) -> RuleSet:
    unknown = [c for c in checks if c not in _RULES]
    if unknown:
        raise KeyError(f"unknown checks {unknown}")
    return RuleSet(_RULES[c]() for c in checks)


def overall_outcome(results: Iterable[RuleResult]) -> Outcome:
    verdicts = {r.verdict for r in results if not r.passed}
    if Verdict.INTERNAL_FIX in verdicts or Verdict.MISSING_DATA in verdicts:
        return Outcome.INTERNAL_FIX_OR_MISSING_DATA
    if Verdict.UPDATED_PO_REQUIRED in verdicts:
        return Outcome.UPDATED_PO_REQUIRED
    return Outcome.MATCHED


def owners(results: Iterable[RuleResult]) -> dict[str, str]:
    """Proposed owner per failed check (from the reason-code catalogue / RACI)."""
    return {r.rule: r.owner for r in results if not r.passed and r.owner}
