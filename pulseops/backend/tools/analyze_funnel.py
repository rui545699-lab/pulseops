from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.queries.funnel import build_funnel_query
from pulseops.backend.schemas.analytics import FunnelComparison, PeriodFunnelResult


def _rate(converted: int, entrants: int) -> float:
    return round(100.0 * converted / entrants, 2) if entrants else 0.0


def interpret_funnel_row(row: Mapping[str, Any]) -> PeriodFunnelResult:
    sessions = int(row["view_sessions"])
    converted_sessions = int(row["converted_sessions"])
    users = int(row["view_users"])
    converted_users = int(row["converted_users"])
    return PeriodFunnelResult(
        view_sessions=sessions,
        converted_sessions=converted_sessions,
        session_conversion_rate=_rate(converted_sessions, sessions),
        view_users=users,
        converted_users=converted_users,
        user_conversion_rate=_rate(converted_users, users),
    )


def compare_funnel_rows(
    events: Sequence[str],
    baseline_row: Mapping[str, Any],
    target_row: Mapping[str, Any],
    investigation_threshold_pp: float = 3.0,
) -> FunnelComparison:
    baseline = interpret_funnel_row(baseline_row)
    target = interpret_funnel_row(target_row)
    session_delta = round(target.session_conversion_rate - baseline.session_conversion_rate, 2)
    user_delta = round(target.user_conversion_rate - baseline.user_conversion_rate, 2)
    return FunnelComparison(
        entry_event=events[0],
        conversion_event=events[-1],
        baseline=baseline,
        target=target,
        session_delta_pp=session_delta,
        user_delta_pp=user_delta,
        needs_investigation=session_delta <= -abs(investigation_threshold_pp),
    )


def analyze_funnel(
    executor: QueryExecutor,
    events: list[str],
    baseline_start: date,
    baseline_end: date,
    target_start: date,
    target_end: date,
) -> FunnelComparison:
    sql = build_funnel_query(events)
    baseline_rows = executor.query(
        sql, {"start_date": baseline_start, "end_date": baseline_end}
    )
    target_rows = executor.query(
        sql, {"start_date": target_start, "end_date": target_end}
    )
    if len(baseline_rows) != 1 or len(target_rows) != 1:
        raise ValueError("funnel query must return exactly one row per period")
    return compare_funnel_rows(events, baseline_rows[0], target_rows[0])

