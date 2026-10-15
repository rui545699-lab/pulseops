from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class QueryExecutor(Protocol):
    def query(self, sql: str, params: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        """Execute a parameterized query and return dictionary-like rows."""


class BigQueryExecutor:
    """Small adapter around ADC-authenticated google-cloud-bigquery.

    Importing this module does not require the BigQuery package, which keeps the
    deterministic unit-test path lightweight.
    """

    def __init__(self, project: str | None = None) -> None:
        try:
            from google.cloud import bigquery
        except ImportError as exc:  # pragma: no cover - exercised only in live use
            raise RuntimeError(
                "Install google-cloud-bigquery to run live queries"
            ) from exc
        self._bigquery = bigquery
        self._client = bigquery.Client(project=project)

    def query(self, sql: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        scalar_params = [
            self._bigquery.ScalarQueryParameter(name, _bq_type(value), value)
            for name, value in params.items()
        ]
        job_config = self._bigquery.QueryJobConfig(query_parameters=scalar_params)
        return [dict(row.items()) for row in self._client.query(sql, job_config=job_config)]


def _bq_type(value: Any) -> str:
    from datetime import date, datetime

    if isinstance(value, datetime):
        return "TIMESTAMP"
    if isinstance(value, date):
        return "DATE"
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT64"
    if isinstance(value, float):
        return "FLOAT64"
    return "STRING"

