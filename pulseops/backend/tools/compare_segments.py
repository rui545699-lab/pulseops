from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.queries.segments import build_segment_query
from pulseops.backend.schemas.analytics import SegmentComparison, SegmentResult


def _index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row["segment"]): row for row in rows}


def _rate(row: Mapping[str, Any] | None) -> float | None:
    if not row or not int(row.get("view_users", 0)):
        return None
    return round(100 * int(row["converted_users"]) / int(row["view_users"]), 2)


def compare_segment_rows(
    dimension: str,
    baseline_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    minimum_sample_size: int = 100,
) -> SegmentComparison:
    baseline = _index(baseline_rows)
    target = _index(target_rows)
    baseline_total = sum(int(row["view_users"]) for row in baseline_rows)
    target_total = sum(int(row["view_users"]) for row in target_rows)
    output: list[SegmentResult] = []

    for segment in sorted(set(baseline) | set(target)):
        b_row, t_row = baseline.get(segment), target.get(segment)
        b_users = int(b_row.get("view_users", 0)) if b_row else 0
        t_users = int(t_row.get("view_users", 0)) if t_row else 0
        sufficient = b_users >= minimum_sample_size and t_users >= minimum_sample_size
        b_rate, t_rate = _rate(b_row), _rate(t_row)
        change = round(t_rate - b_rate, 2) if sufficient and b_rate is not None and t_rate is not None else None
        output.append(
            SegmentResult(
                segment=segment,
                baseline_rate=b_rate if sufficient else None,
                target_rate=t_rate if sufficient else None,
                change_pp=change,
                baseline_users=b_users,
                target_users=t_users,
                baseline_share=round(100 * b_users / baseline_total, 2) if baseline_total else 0.0,
                target_share=round(100 * t_users / target_total, 2) if target_total else 0.0,
                sample_sufficient=sufficient,
            )
        )
    output.sort(key=lambda row: row.baseline_users, reverse=True)
    return SegmentComparison(
        dimension=dimension,
        minimum_sample_size=minimum_sample_size,
        segments=output,
    )


def compare_segments(
    executor: QueryExecutor,
    dimension: str,
    baseline_start: date,
    baseline_end: date,
    target_start: date,
    target_end: date,
    minimum_sample_size: int = 100,
    lifecycle_filter: str | None = None,
) -> SegmentComparison:
    sql = build_segment_query(dimension, lifecycle_filter=lifecycle_filter)
    baseline = executor.query(
        sql, {"start_date": baseline_start, "end_date": baseline_end}
    )
    target = executor.query(sql, {"start_date": target_start, "end_date": target_end})
    return compare_segment_rows(dimension, baseline, target, minimum_sample_size)

