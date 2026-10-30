"""The gold layer as the agents see it: the table registry (the contract), lookups on
the in-memory client, the SQL the BigQuery client renders, the staleness guard, and
files by pointer and hash."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from factory.platform import (
    GOLD,
    BigQueryGoldClient,
    GcsFileStore,
    GoldReader,
    GoldStale,
    InMemoryFileStore,
    InMemoryGoldClient,
    IntegrityError,
    LocalFileStore,
    Lookup,
    UnknownColumn,
    UnknownTable,
    fetch_verified,
    sha256_hex,
)

CUSTOMERS = [
    {"customer_id": "100123", "role": "sold_to", "name": "Kraft Heinz Foods", "blocked": False, "valid_from": "2020-01-01", "valid_to": "9999-12-31", "_gold_refresh_ts": "2026-10-30T08:00:00+00:00"},
    {"customer_id": "100124", "role": "sold_to", "name": "Kraft Heinz Canada", "blocked": False, "valid_from": "2020-01-01", "valid_to": "9999-12-31", "_gold_refresh_ts": "2026-10-30T08:00:00+00:00"},
    {"customer_id": "200456", "role": "ship_to", "name": "Kraft Heinz Plant Champaign", "blocked": True, "valid_from": "2020-01-01", "valid_to": "2025-12-31", "_gold_refresh_ts": "2026-10-30T08:00:00+00:00"},
]


# ── registry ─────────────────────────────────────────────────────────────────


def test_registry_is_the_contract_with_the_data_team():
    names = GOLD.names()
    assert {"gold_cases.email_order_case", "gold_sales.customer", "gold_pricing.condition", "gold_billing.invoice_ready_order", "gold_procurement.ariba_po", "gold_ar.dispute", "ops.freshness"} <= set(names)
    for table in GOLD.tables():
        assert table.name == f"{table.dataset}.{table.table}"
        if table.dataset != "ops":
            assert "_gold_refresh_ts" in table.columns and table.max_age_minutes > 0
        assert set(table.keys) <= set(table.columns)
    assert {t.name for t in GOLD.for_agent("prebill")} >= {"gold_billing.billing_document", "gold_pricing.pros_agreement", "gold_sales.delivery"}
    assert {t.name for t in GOLD.for_agent("order_intake")} >= {"gold_cases.email_order_case", "gold_sales.customer_material"}
    with pytest.raises(UnknownTable):
        GOLD.table("silver_sales.customer")
    with pytest.raises(UnknownColumn):
        Lookup("gold_sales.customer", where={"customer_name": "x"}).validate()


# ── in-memory client ─────────────────────────────────────────────────────────


def test_in_memory_lookups_cover_what_the_connectors_ask():
    client = InMemoryGoldClient({"gold_sales.customer": CUSTOMERS})
    rows = client.rows(Lookup("gold_sales.customer", where={"role": "sold_to"}, within={"name": "Sold-to: KRAFT HEINZ FOODS, Chicago"}))
    assert [r["customer_id"] for r in rows] == ["100123"]
    assert [r["customer_id"] for r in client.rows(Lookup("gold_sales.customer", where={"customer_id": ["100124", "200456"]}, order_by=("-customer_id",)))] == ["200456", "100124"]
    assert [r["customer_id"] for r in client.rows(Lookup("gold_sales.customer", between={"valid_from": (None, dt.date(2026, 10, 1)), "valid_to": (dt.date(2026, 10, 1), None)}))] == ["100123", "100124"]
    assert len(client.rows(Lookup("gold_sales.customer", where={"blocked": False}, limit=1))) == 1
    assert client.rows(Lookup("gold_sales.customer", gt={"valid_from": "2021-01-01"})) == []
    client.add("gold_pricing.pros_agreement", {"agreement_ref": "KH-2026", "sold_to": "KH-001", "material_id": None, "payment_terms_days": 120})
    assert client.rows(Lookup("gold_pricing.pros_agreement", where={"sold_to": "KH-001", "material_id": None}))[0]["payment_terms_days"] == 120
    assert client.freshness("gold_sales.customer").refreshed_at == "2026-10-30T08:00:00+00:00"
    assert client.queries[-1].table == "gold_pricing.pros_agreement"


# ── BigQuery client ──────────────────────────────────────────────────────────


class FakeBigQuery:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls: list[tuple[str, object]] = []

    def query(self, sql, job_config=None):
        self.calls.append((sql, job_config))
        return SimpleNamespace(result=lambda: list(self.rows))


def test_bigquery_client_renders_parameterised_sql_over_the_suffixed_dataset():
    fake = FakeBigQuery(rows=[{"customer_id": "100123", "name": "Kraft Heinz Foods"}])
    client = BigQueryGoldClient("ingredion-dev", dataset_suffix="_dev", client=fake)
    lookup = Lookup(
        "gold_sales.customer",
        where={"role": "sold_to", "customer_id": ["100123", "100124"], "parent_sold_to": None},
        within={"name": "KRAFT HEINZ FOODS"},
        between={"valid_from": (None, dt.date(2026, 10, 30)), "valid_to": (dt.date(2026, 10, 30), None)},
        gt={"_gold_refresh_ts": dt.datetime(2026, 10, 30, 8, tzinfo=dt.UTC)},
        order_by=("-valid_from", "customer_id"),
        limit=5,
    )
    sql, params = client.compile(lookup)
    assert sql == (
        "SELECT * FROM `ingredion-dev.gold_sales_dev.customer` WHERE `role` = @p0 AND `customer_id` IN UNNEST(@p1) AND `parent_sold_to` IS NULL "
        "AND STRPOS(LOWER(@p2), LOWER(CAST(`name` AS STRING))) > 0 AND `valid_from` <= @p3 AND `valid_to` >= @p4 AND `_gold_refresh_ts` > @p5 "
        "ORDER BY `valid_from` DESC, `customer_id` LIMIT 5"
    )
    assert [(n, t) for n, t, _ in params] == [("p0", "STRING"), ("p1", "ARRAY<STRING>"), ("p2", "STRING"), ("p3", "DATE"), ("p4", "DATE"), ("p5", "TIMESTAMP")]
    assert client.rows(lookup)[0]["customer_id"] == "100123" and fake.calls[-1][0] == sql
    with pytest.raises(UnknownColumn):
        client.compile(Lookup("gold_sales.customer", where={"nope": 1}))

    fake.rows = [{"table_name": "gold_sales.customer", "refreshed_at": dt.datetime(2026, 10, 30, 8, 5, tzinfo=dt.UTC), "source_ts": None, "row_count": 3}]
    fresh = client.freshness("gold_sales.customer")
    assert fresh.refreshed_at == "2026-10-30T08:05:00+00:00" and fresh.row_count == 3
    assert "`ingredion-dev.ops_dev.freshness`" in fake.calls[-1][0]
    fake.rows = []
    assert client.freshness("gold_sales.customer").refreshed_at is None


# ── staleness guard ──────────────────────────────────────────────────────────


def test_readers_refuse_stale_tables_and_remember_the_refresh_they_used():
    now = dt.datetime(2026, 10, 30, 9, 0, tzinfo=dt.UTC)
    client = InMemoryGoldClient({"gold_sales.customer": CUSTOMERS}, now=lambda: now)
    clock = [0.0]
    reader = GoldReader(client, clock=lambda: clock[0], now=lambda: now, check_every_seconds=60)
    assert len(reader.rows("gold_sales.customer", where={"role": "sold_to"})) == 2  # refreshed 08:00, limit 60 min
    assert reader.refresh_used == {"gold_sales.customer": "2026-10-30T08:00:00+00:00"}

    client.set_freshness("gold_sales.customer", "2026-10-30T07:30:00+00:00")  # 90 minutes old
    assert len(reader.rows("gold_sales.customer", where={"role": "sold_to"})) == 2  # cached check within the minute
    clock[0] = 61.0
    with pytest.raises(GoldStale) as exc:
        reader.rows("gold_sales.customer", where={"role": "sold_to"})
    assert exc.value.table == "gold_sales.customer" and exc.value.max_age_minutes == 60

    client.set_freshness("gold_sales.customer", None)  # unknown freshness fails closed
    with pytest.raises(GoldStale):
        GoldReader(client, now=lambda: now).rows("gold_sales.customer")
    assert GoldReader(client, now=lambda: now, max_age_minutes=0).rows("gold_sales.customer")  # 0 = guard off (tests only)


# ── files ────────────────────────────────────────────────────────────────────


def test_files_are_fetched_by_pointer_and_verified_by_hash(tmp_path):
    content = b"%PDF-1.4 purchase order"
    store = InMemoryFileStore({"gs://ingredion-files-dev/cases/CASE-1/po.pdf": content})
    assert fetch_verified(store, "gs://ingredion-files-dev/cases/CASE-1/po.pdf", sha256_hex(content)) == content
    with pytest.raises(IntegrityError):
        fetch_verified(store, "gs://ingredion-files-dev/cases/CASE-1/po.pdf", "00" * 32)

    (tmp_path / "po.txt").write_bytes(b"PO 1")
    assert LocalFileStore(tmp_path).get("po.txt") == b"PO 1"

    class Blob:
        def __init__(self, path):
            self.path = path

        def download_as_bytes(self):
            assert self.path == "cases/CASE-1/po.pdf"
            return content

    class Bucket:
        def __init__(self, name):
            assert name == "ingredion-files-dev"

        def blob(self, path):
            return Blob(path)

    gcs = GcsFileStore(client=SimpleNamespace(bucket=Bucket))
    assert gcs.get("gs://ingredion-files-dev/cases/CASE-1/po.pdf") == content
