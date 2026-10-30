"""The gold tables the agents read: the contract with the data team.

One entry per table, with the columns the connectors use, the lookup keys, which
agent reads it, and how old the table may be before the staleness guard refuses to
validate against it. Every lookup a connector issues is checked against this
registry (an unknown table or column raises), so when the data team's DDL arrives
the diff is made here and the contract tests say what else has to move.

Dataset names are the ones proposed on 29 October 2026 (``gold_cases``,
``gold_sales``, ``gold_pricing``, ``gold_billing``, ``gold_ar``, ``gold_reference``,
``gold_procurement``, ``ops``); the per-environment suffix comes from settings.
Every gold row carries ``_gold_refresh_ts``; ``ops.freshness`` holds the last refresh
per table.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import AGENT_ORDER_INTAKE, AGENT_PREBILL

A = AGENT_ORDER_INTAKE
B = AGENT_PREBILL
REFRESH = "_gold_refresh_ts"


@dataclass(frozen=True)
class GoldTable:
    name: str  # logical name "<dataset>.<table>", what connectors and the in-memory client use
    dataset: str
    table: str
    columns: tuple[str, ...]
    keys: tuple[str, ...]
    max_age_minutes: int
    readers: tuple[str, ...]

    def has(self, column: str) -> bool:
        return column in self.columns


def _t(dataset: str, table: str, columns: str, keys: str, max_age_minutes: int, *readers: str) -> GoldTable:
    cols = tuple(c.strip() for c in columns.split(",") if c.strip())
    if REFRESH not in cols and dataset != "ops":
        cols = (*cols, REFRESH)
    return GoldTable(f"{dataset}.{table}", dataset, table, cols, tuple(k.strip() for k in keys.split(",")), max_age_minutes, readers)


_TABLES: tuple[GoldTable, ...] = (
    # ── cases (Salesforce) ──────────────────────────────────────────────────
    _t("gold_cases", "email_order_case",
       "case_id, case_number, status, routed_to, cohort, customer_id, customer_name, subject, body, sender, "
       "received_at, updated_at, po_ref, order_ref, source_system",
       "case_id", 15, A),
    _t("gold_cases", "case_attachment",
       "attachment_id, case_id, order_ref, po_ref, kind, name, content_type, file_uri, sha256, size_bytes, received_at",
       "attachment_id", 15, A, B),
    # ── sales (SAP SD) ──────────────────────────────────────────────────────
    _t("gold_sales", "customer",
       "customer_id, role, name, search_name, parent_sold_to, country, payment_terms_days, payment_terms_code, "
       "currency, blocked, valid_from, valid_to",
       "customer_id, role", 60, A, B),
    _t("gold_sales", "material",
       "material_id, description, base_uom, sales_uom, status",
       "material_id", 60, A),
    _t("gold_sales", "material_uom",
       "material_id, uom, base_uom, factor, lb_per_unit",
       "material_id, uom", 60, A, B),
    _t("gold_sales", "customer_material",
       "sold_to, customer_material, material_id, description, sales_uom, valid_from, valid_to",
       "sold_to, customer_material", 60, A),
    _t("gold_sales", "sales_order",
       "order_ref, sold_to, ship_to, bill_to, po_ref, po_source, order_date, requested_delivery_date, status, "
       "agent_reference, captured_po_json, salesforce_case_id, created_at, updated_at",
       "order_ref", 30, A, B),
    _t("gold_sales", "sales_order_item",
       "order_ref, line_no, material_id, quantity, uom, net_price, price_uom, requested_date",
       "order_ref, line_no", 30, A),
    _t("gold_sales", "delivery",
       "delivery_ref, order_ref, line_no, ship_date, shipped_qty, uom, carrier",
       "delivery_ref", 30, B),
    # ── pricing ─────────────────────────────────────────────────────────────
    _t("gold_pricing", "condition",
       "condition_type, sold_to, material_id, rate, price_uom, currency, valid_from, valid_to, record",
       "condition_type, sold_to, material_id, valid_from", 240, A, B),
    _t("gold_pricing", "contract",
       "contract_ref, sold_to, material_id, valid_from, valid_to, remaining_quantity, quantity_uom, price, "
       "price_uom, currency",
       "contract_ref", 240, A),
    _t("gold_pricing", "pros_agreement",
       "agreement_ref, sold_to, material_id, price, price_uom, currency, payment_terms_days, valid_from, valid_to, record",
       "agreement_ref", 240, B),
    _t("gold_pricing", "freight_charge",
       "sold_to, applies, amount, basis, currency, valid_from, valid_to, record",
       "sold_to, valid_from", 1440, B),
    _t("gold_pricing", "fuel_rate",
       "sold_to, applies, amount, basis, currency, valid_from, valid_to, record",
       "sold_to, valid_from", 1440, B),
    # ── billing ─────────────────────────────────────────────────────────────
    _t("gold_billing", "invoice_ready_order",
       "order_ref, invoice_ref, sold_to, customer_name, billing_date, po_ref, ready_at",
       "order_ref, invoice_ref", 30, B),
    _t("gold_billing", "billing_document",
       "invoice_ref, order_ref, line_no, line_type, material_id, quantity, uom, unit_price, price_uom, price_date, "
       "description, charge_type, amount, currency, payment_terms_days, price_record, terms_record",
       "invoice_ref, line_no", 30, B),
    # ── accounts receivable ─────────────────────────────────────────────────
    _t("gold_ar", "dispute",
       "dispute_ref, sold_to, invoice_ref, code, amount, opened_at, status",
       "dispute_ref", 240, B),
    # ── procurement (customer portals) ──────────────────────────────────────
    _t("gold_procurement", "ariba_po",
       "po_ref, order_ref, sold_to, line_no, line_type, material_id, customer_material, quantity, uom, tolerance_pct, "
       "unit_price, price_uom, price_date, currency, payment_terms_days, charge_type, charge_amount, description",
       "po_ref, line_no", 60, B),
    # ── reference ───────────────────────────────────────────────────────────
    _t("gold_reference", "uom_conversion",
       "from_uom, to_uom, factor",
       "from_uom, to_uom", 1440, A, B),
    _t("gold_reference", "contract_document",
       "document_id, sold_to, kind, file_uri, sha256, valid_from, valid_to",
       "document_id", 1440, B),
    # ── operations ──────────────────────────────────────────────────────────
    _t("ops", "freshness",
       "table_name, refreshed_at, source_ts, row_count",
       "table_name", 0),
)


class GoldRegistry:
    def __init__(self, tables: tuple[GoldTable, ...]) -> None:
        self._by_name = {t.name: t for t in tables}

    def table(self, name: str) -> GoldTable:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownTable(f"{name!r} is not a gold table the agents read; see factory/platform/schema.py") from None

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def tables(self) -> list[GoldTable]:
        return [self._by_name[n] for n in self.names()]

    def for_agent(self, agent: str) -> list[GoldTable]:
        return [t for t in self.tables() if agent in t.readers]


class UnknownTable(KeyError):
    pass


GOLD = GoldRegistry(_TABLES)

__all__ = ["A", "B", "GOLD", "REFRESH", "GoldRegistry", "GoldTable", "UnknownTable"]
