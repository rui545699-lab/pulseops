from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.queries.validate_data import build_validation_query
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    DateWindows,
    ValidationResult,
    WarningItem,
)

REQUIRED_EVENTS = {"view_item", "add_to_cart", "begin_checkout", "purchase"}


def _dates(start: date, end: date) -> set[date]:
    return {start + timedelta(days=i) for i in range((end - start).days + 1)}


def evaluate_validation_rows(
    rows_by_period: Mapping[str, Sequence[Mapping[str, Any]]],
    windows: DateWindows,
    minimum_view_sessions: int = 100,
) -> ValidationResult:
    warnings: list[WarningItem] = []
    periods = {
        "baseline": (windows.baseline_start, windows.baseline_end),
        "target": (windows.target_start, windows.target_end),
    }

    for period, (start, end) in periods.items():
        rows = rows_by_period.get(period, [])
        seen_events = {str(row["event_name"]) for row in rows}
        missing_events = sorted(REQUIRED_EVENTS - seen_events)
        if missing_events:
            warnings.append(
                WarningItem(
                    code="MISSING_FUNNEL_EVENTS",
                    period=period,
                    message=f"Missing required events: {', '.join(missing_events)}",
                )
            )

        observed_dates = {row["event_date"] for row in rows}
        missing_dates = _dates(start, end) - observed_dates
        if missing_dates:
            warnings.append(
                WarningItem(
                    code="INCOMPLETE_OBSERVATION_WINDOW",
                    period=period,
                    message=f"No funnel events on {len(missing_dates)} day(s)",
                )
            )

        view_sessions = sum(
            int(row.get("sessions", 0))
            for row in rows
            if row["event_name"] == "view_item"
        )
        if view_sessions < minimum_view_sessions:
            warnings.append(
                WarningItem(
                    code="INSUFFICIENT_SAMPLE",
                    period=period,
                    message=(
                        f"Only {view_sessions} view_item sessions; "
                        f"minimum is {minimum_view_sessions}"
                    ),
                )
            )

        daily: dict[date, dict[str, Mapping[str, Any]]] = defaultdict(dict)
        for row in rows:
            daily[row["event_date"]][str(row["event_name"])] = row
        for event_date, events in daily.items():
            cart_users = int(events.get("add_to_cart", {}).get("users", 0))
            checkout_users = int(events.get("begin_checkout", {}).get("users", 0))
            if checkout_users > 100 and cart_users <= max(2, round(checkout_users * 0.02)):
                warnings.append(
                    WarningItem(
                        code="DATA_QUALITY_ALERT",
                        period=period,
                        event_date=event_date,
                        message=(
                            "add_to_cart users are near zero while begin_checkout "
                            "users exceed 100; likely event collection instability"
                        ),
                    )
                )

    return ValidationResult(
        status=AnalysisStatus.FAIL if warnings else AnalysisStatus.PASS,
        analysis_allowed=not warnings,
        warnings=warnings,
    )


def validate_data(
    executor: QueryExecutor,
    windows: DateWindows,
    minimum_view_sessions: int = 100,
) -> ValidationResult:
    sql = build_validation_query()
    rows = {
        "baseline": executor.query(
            sql,
            {"start_date": windows.baseline_start, "end_date": windows.baseline_end},
        ),
        "target": executor.query(
            sql,
            {"start_date": windows.target_start, "end_date": windows.target_end},
        ),
    }
    return evaluate_validation_rows(rows, windows, minimum_view_sessions)

