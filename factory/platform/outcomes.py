"""Outcome rows: what the SOW scorecards and the dashboards read.

Each agent writes one row per finished case (and per pre-bill version) into its own
BigQuery dataset (``agent_a_outcomes.case_outcome``, ``agent_b_outcomes.prebill_outcome``).
The append-only audit trail stays the record; these rows are the queryable
projection of it. A failed write is logged and alerted, never allowed to fail the
case: the audit record already exists and the row can be rebuilt from it.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from ..case import Case, now_iso


class OutcomeWriteFailed(RuntimeError):
    pass


class OutcomeSink(Protocol):
    name: str

    def record(self, table: str, row: dict[str, Any]) -> None: ...


def json_text(value: Any) -> str:
    """Nested structures travel as JSON strings (a STRING/JSON column), lists of scalars as REPEATED."""

    def default(v: Any) -> Any:
        if hasattr(v, "model_dump"):
            return v.model_dump(mode="json")
        if hasattr(v, "to_dict"):
            return v.to_dict()
        return str(v)

    return json.dumps(value, default=default, ensure_ascii=False)


def base_row(case: Case, agent: str) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "agent": agent,
        "run_id": case.run_id,
        "recorded_at": now_iso(),
        "outcome": case.outcome,
        "state": case.state,
        "reason_codes": list(case.reason_codes),
        "flags": [f.code for f in case.flags],
        "case_created_at": case.created_at,
    }


class InMemoryOutcomeSink:
    name = "memory"

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {}

    def record(self, table: str, row: dict[str, Any]) -> None:
        self.rows.setdefault(table, []).append(dict(row))

    def last(self, table: str) -> dict[str, Any] | None:
        rows = self.rows.get(table) or []
        return rows[-1] if rows else None


class BigQueryOutcomeSink:
    """Streaming inserts into ``<project>.<dataset>.<table>``; ``client`` is injectable."""

    name = "bigquery"

    def __init__(self, project: str, dataset: str, *, client: Any = None) -> None:
        if not project or not dataset:
            raise ValueError("BigQueryOutcomeSink needs a project and a dataset")
        self.project = project
        self.dataset = dataset
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project)
        return self._client

    def record(self, table: str, row: dict[str, Any]) -> None:
        errors = self._get_client().insert_rows_json(f"{self.project}.{self.dataset}.{table}", [row])
        if errors:
            raise OutcomeWriteFailed(f"{self.dataset}.{table}: {errors}")


__all__ = ["BigQueryOutcomeSink", "InMemoryOutcomeSink", "OutcomeSink", "OutcomeWriteFailed", "base_row", "json_text"]
