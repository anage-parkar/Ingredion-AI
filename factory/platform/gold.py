"""Reading the gold layer.

The agents read gold tables only, never bronze or silver, and never a source
system's API where a gold copy exists. A connector expresses what it needs as a
:class:`Lookup` (table, equality and range filters, order, limit) rather than SQL,
so the same connector runs on :class:`InMemoryGoldClient` in Dev and the tests and
on :class:`BigQueryGoldClient` in the Ingredion project, and every lookup is checked
against the table registry.

The staleness guard: before a connector reads a table it asks ``ops.freshness`` when
the table was last refreshed; older than the registry's limit raises
:class:`GoldStale`, and the worker retries the case later instead of validating
against old data. The refresh times used are kept for the evidence snapshot.
"""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from .schema import GOLD, REFRESH, UnknownTable


class GoldError(RuntimeError):
    pass


class UnknownColumn(GoldError):
    pass


class GoldStale(GoldError):
    """The table was refreshed too long ago (or never) to validate against."""

    def __init__(self, table: str, refreshed_at: str | None, max_age_minutes: int) -> None:
        super().__init__(f"gold table {table} refreshed at {refreshed_at or 'unknown'}; older than {max_age_minutes} minutes")
        self.table = table
        self.refreshed_at = refreshed_at
        self.max_age_minutes = max_age_minutes


@dataclass(frozen=True)
class Lookup:
    """One read. ``where`` values: a scalar (equality), a list (IN) or ``None`` (IS NULL).
    ``within`` means "the column's value occurs inside this text" (partner names in a
    PO). ``between`` bounds are inclusive; either may be ``None``. ``gt`` is for markers."""

    table: str
    where: dict[str, Any] = field(default_factory=dict)
    within: dict[str, str] = field(default_factory=dict)
    between: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    gt: dict[str, Any] = field(default_factory=dict)
    order_by: tuple[str, ...] = ()  # "-col" for descending
    limit: int | None = None

    def columns(self) -> set[str]:
        cols = set(self.where) | set(self.within) | set(self.between) | set(self.gt)
        cols |= {c[1:] if c.startswith("-") else c for c in self.order_by}
        return cols

    def validate(self) -> None:
        spec = GOLD.table(self.table)
        unknown = sorted(c for c in self.columns() if not spec.has(c))
        if unknown:
            raise UnknownColumn(f"{self.table} has no column(s) {unknown}; registry: {list(spec.columns)}")


@dataclass
class Freshness:
    table: str
    refreshed_at: str | None
    source_ts: str | None = None
    row_count: int | None = None

    def age_minutes(self, now: dt.datetime | None = None) -> float | None:
        when = parse_ts(self.refreshed_at)
        if when is None:
            return None
        now = now or dt.datetime.now(dt.UTC)
        return (now - when).total_seconds() / 60.0


def parse_ts(value: Any) -> dt.datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def iso(value: Any) -> str | None:
    parsed = parse_ts(value)
    return parsed.isoformat() if parsed else (str(value) if value not in (None, "") else None)


class GoldClient(Protocol):
    name: str

    def rows(self, lookup: Lookup) -> list[dict[str, Any]]: ...

    def freshness(self, table: str) -> Freshness: ...


# ── in-memory (Dev and tests) ────────────────────────────────────────────────


def _cmp(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def _matches(row: dict[str, Any], lookup: Lookup) -> bool:
    for col, expected in lookup.where.items():
        actual = row.get(col)
        if expected is None:
            if actual is not None:
                return False
        elif isinstance(expected, (list, tuple, set)):
            if _cmp(actual) not in {_cmp(e) for e in expected}:
                return False
        elif _cmp(actual) != _cmp(expected):
            if str(_cmp(actual)) != str(_cmp(expected)):
                return False
    for col, text in lookup.within.items():
        actual = row.get(col)
        if not actual or str(actual).casefold() not in (text or "").casefold():
            return False
    for col, (lo, hi) in lookup.between.items():
        actual = row.get(col)
        if lo is not None and (actual is None or str(_cmp(actual)) < str(_cmp(lo))):
            return False
        if hi is not None and actual is not None and str(_cmp(actual)) > str(_cmp(hi)):
            return False
    for col, bound in lookup.gt.items():
        actual = row.get(col)
        if actual is None or str(_cmp(actual)) <= str(_cmp(bound)):
            return False
    return True


class InMemoryGoldClient:
    """Tables as lists of dicts, keyed by the registry's logical names. Freshness is
    taken from ``_gold_refresh_ts`` on the rows unless registered explicitly; a table
    with neither counts as refreshed now (the fake platform is always current)."""

    name = "memory"

    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None, *, freshness: dict[str, str | None] | None = None, now: Callable[[], dt.datetime] | None = None) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        for name, rows in (tables or {}).items():
            self.add(name, *rows)
        self._freshness: dict[str, str | None] = dict(freshness or {})
        self._now = now or (lambda: dt.datetime.now(dt.UTC))
        self.queries: list[Lookup] = []

    def add(self, table: str, *rows: dict[str, Any]) -> None:
        GOLD.table(table)
        self.tables.setdefault(table, []).extend(dict(r) for r in rows)

    def set_freshness(self, table: str, refreshed_at: str | None) -> None:
        self._freshness[table] = refreshed_at

    def rows(self, lookup: Lookup) -> list[dict[str, Any]]:
        lookup.validate()
        self.queries.append(lookup)
        out = [dict(r) for r in self.tables.get(lookup.table, []) if _matches(r, lookup)]
        for key in reversed(lookup.order_by):
            desc = key.startswith("-")
            col = key[1:] if desc else key
            out.sort(key=lambda r: str(_cmp(r.get(col))), reverse=desc)
        if lookup.limit is not None:
            out = out[: lookup.limit]
        return out

    def freshness(self, table: str) -> Freshness:
        GOLD.table(table)
        rows = self.tables.get(table, [])
        if table in self._freshness:
            ts = self._freshness[table]
        else:
            stamps = [r.get(REFRESH) for r in rows if r.get(REFRESH)]
            ts = max(stamps) if stamps else self._now().isoformat()
        return Freshness(table, iso(ts), row_count=len(rows))


# ── BigQuery ─────────────────────────────────────────────────────────────────


def _bq_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    if isinstance(value, dt.datetime):
        return "TIMESTAMP"
    if isinstance(value, dt.date):
        return "DATE"
    return "STRING"


class BigQueryGoldClient:
    """Parameterised SELECTs over the gold datasets; the SQL is built from the lookup,
    never from caller strings. ``client`` is injectable (tests pass a fake whose
    ``query(sql, job_config)`` returns rows)."""

    name = "bigquery"

    def __init__(self, project: str, *, dataset_suffix: str = "", client: Any = None, location: str | None = None) -> None:
        if not project:
            raise GoldError("BigQueryGoldClient needs a project (GOLD_PROJECT or GOOGLE_CLOUD_PROJECT)")
        self.project = project
        self.suffix = dataset_suffix or ""
        self.location = location
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project, location=self.location)
        return self._client

    def table_ref(self, table: str) -> str:
        spec = GOLD.table(table)
        return f"`{self.project}.{spec.dataset}{self.suffix}.{spec.table}`"

    def compile(self, lookup: Lookup) -> tuple[str, list[tuple[str, str, Any]]]:
        lookup.validate()
        params: list[tuple[str, str, Any]] = []
        clauses: list[str] = []

        def p(value: Any) -> str:
            name = f"p{len(params)}"
            params.append((name, _bq_type(value), value))
            return f"@{name}"

        for col, val in lookup.where.items():
            if val is None:
                clauses.append(f"`{col}` IS NULL")
            elif isinstance(val, (list, tuple, set)):
                values = list(val)
                name = f"p{len(params)}"
                params.append((name, f"ARRAY<{_bq_type(values[0]) if values else 'STRING'}>", values))
                clauses.append(f"`{col}` IN UNNEST(@{name})")
            else:
                clauses.append(f"`{col}` = {p(val)}")
        for col, text in lookup.within.items():
            clauses.append(f"STRPOS(LOWER({p(text)}), LOWER(CAST(`{col}` AS STRING))) > 0")
        for col, (lo, hi) in lookup.between.items():
            if lo is not None:
                clauses.append(f"`{col}` >= {p(lo)}")
            if hi is not None:
                clauses.append(f"`{col}` <= {p(hi)}")
        for col, bound in lookup.gt.items():
            clauses.append(f"`{col}` > {p(bound)}")
        sql = f"SELECT * FROM {self.table_ref(lookup.table)}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if lookup.order_by:
            sql += " ORDER BY " + ", ".join(f"`{c[1:]}` DESC" if c.startswith("-") else f"`{c}`" for c in lookup.order_by)
        if lookup.limit is not None:
            sql += f" LIMIT {int(lookup.limit)}"
        return sql, params

    def _run(self, sql: str, params: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
        client = self._get_client()
        try:
            from google.cloud import bigquery

            query_parameters = [
                bigquery.ArrayQueryParameter(name, type_[6:-1], value) if type_.startswith("ARRAY<") else bigquery.ScalarQueryParameter(name, type_, value)
                for name, type_, value in params
            ]
            job_config: Any = bigquery.QueryJobConfig(query_parameters=query_parameters)
        except ImportError:  # fake client in tests
            job_config = {"query_parameters": params}
        result = client.query(sql, job_config=job_config).result()
        return [row if isinstance(row, dict) else dict(row) for row in result]

    def rows(self, lookup: Lookup) -> list[dict[str, Any]]:
        sql, params = self.compile(lookup)
        return self._run(sql, params)

    def freshness(self, table: str) -> Freshness:
        spec = GOLD.table(table)
        sql = f"SELECT table_name, refreshed_at, source_ts, row_count FROM `{self.project}.ops{self.suffix}.freshness` WHERE `table_name` = @p0"
        rows = self._run(sql, [("p0", "STRING", f"{spec.dataset}.{spec.table}")])
        if not rows:
            return Freshness(table, None)
        row = rows[0]
        return Freshness(table, iso(row.get("refreshed_at")), iso(row.get("source_ts")), row.get("row_count"))


# ── what connectors build on ─────────────────────────────────────────────────


class GoldReader:
    """Base for the connector implementations: validated lookups, the staleness guard
    (checked at most every ``check_every_seconds`` per table) and the refresh times
    used, which go into the evidence snapshot."""

    def __init__(
        self,
        client: GoldClient,
        *,
        max_age_minutes: int | None = None,
        check_every_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.client = client
        self.max_age_minutes = max_age_minutes
        self.check_every_seconds = check_every_seconds
        self._clock = clock
        self._now = now or (lambda: dt.datetime.now(dt.UTC))
        self._checked: dict[str, tuple[float, Freshness]] = {}
        self.refresh_used: dict[str, str | None] = {}

    def guard(self, table: str) -> Freshness:
        spec = GOLD.table(table)
        cached = self._checked.get(table)
        if cached is not None and self._clock() - cached[0] < self.check_every_seconds:
            return cached[1]
        fresh = self.client.freshness(table)
        self._checked[table] = (self._clock(), fresh)
        self.refresh_used[table] = fresh.refreshed_at
        limit = self.max_age_minutes if self.max_age_minutes is not None else spec.max_age_minutes
        if limit:
            age = fresh.age_minutes(self._now())
            if age is None or age > limit:
                self._checked.pop(table, None)
                raise GoldStale(table, fresh.refreshed_at, limit)
        return fresh

    def rows(self, table: str, **spec: Any) -> list[dict[str, Any]]:
        self.guard(table)
        return self.client.rows(Lookup(table, **spec))

    def one(self, table: str, **spec: Any) -> dict[str, Any] | None:
        found = self.rows(table, **{**spec, "limit": 1})
        return found[0] if found else None


def refresh_snapshot(*readers: Any) -> dict[str, str | None]:
    """Merge the refresh times every gold-backed connector used (for the evidence)."""
    out: dict[str, str | None] = {}
    for reader in readers:
        used = getattr(reader, "refresh_used", None)
        if isinstance(used, dict):
            out.update(used)
    return out


__all__ = [
    "BigQueryGoldClient",
    "Freshness",
    "GoldClient",
    "GoldError",
    "GoldReader",
    "GoldStale",
    "InMemoryGoldClient",
    "Lookup",
    "UnknownColumn",
    "UnknownTable",
    "iso",
    "parse_ts",
    "refresh_snapshot",
]
