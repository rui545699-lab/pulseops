from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.lifecycle import (
    analyze_timing,
    classify_recovery,
    compare_lifecycle_segment_rows,
)
from pulseops.backend.analytics.queries.lifecycle import (
    build_lifecycle_segment_query,
    build_lifecycle_timing_query,
    build_lifecycle_validation_query,
)
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    LifecycleSegmentComparison,
    LifecycleWindows,
    RecoveryAnalysis,
    RetentionComparison,
    RetentionPeriodResult,
    ReturnTimingAnalysis,
    ReturnTimingPeriod,
    ValidationResult,
    WarningItem,
)


def lifecycle_params(windows: LifecycleWindows) -> dict[str, Any]:
    return {
        **windows.model_dump(),
        "observation_end": windows.post_end + timedelta(days=7),
    }


def validate_lifecycle_data(
    executor: QueryExecutor, windows: LifecycleWindows
) -> ValidationResult:
    rows = executor.query(build_lifecycle_validation_query(), lifecycle_params(windows))
    warnings: list[WarningItem] = []
    if any(int(row["first_visit_events"]) == 0 for row in rows):
        warnings.append(WarningItem(code="MISSING_FIRST_VISIT", message="first_visit has zero-volume dates"))
    if any(int(row["session_start_events"]) == 0 for row in rows):
        warnings.append(WarningItem(code="MISSING_SESSION_START", message="session_start has zero-volume dates"))
    activation_dates = [
        row for row in rows
        if windows.baseline_start <= row["day"] <= windows.target_end
    ]
    if any(int(row["add_to_cart_events"]) == 0 for row in activation_dates):
        warnings.append(WarningItem(code="ACTIVATION_EVENT_GAP", message="add_to_cart is unstable in analysis windows"))
    return ValidationResult(
        status=AnalysisStatus.FAIL if warnings else AnalysisStatus.PASS,
        analysis_allowed=not warnings,
        warnings=warnings,
    )


def query_return_timing(
    executor: QueryExecutor, windows: LifecycleWindows
) -> ReturnTimingAnalysis:
    rows = executor.query(build_lifecycle_timing_query(), lifecycle_params(windows))
    periods = {str(row["period"]): _timing_period(row) for row in rows}
    return analyze_timing(periods["baseline"], periods["target"], periods["post"])


def retention_from_timing(timing: ReturnTimingAnalysis) -> RetentionComparison:
    baseline = _retention_period(timing.baseline)
    target = _retention_period(timing.target)
    post = _retention_period(timing.post)
    return RetentionComparison(
        baseline=baseline,
        target=target,
        post=post,
        delta_pp=round(target.return_rate_7d - baseline.return_rate_7d, 2),
        relative_change_pct=(
            round(
                100 * (target.return_rate_7d - baseline.return_rate_7d) / baseline.return_rate_7d,
                2,
            )
            if baseline.return_rate_7d
            else None
        ),
        target_to_post_delta_pp=round(post.return_rate_7d - target.return_rate_7d, 2),
        baseline_to_post_delta_pp=round(post.return_rate_7d - baseline.return_rate_7d, 2),
    )


def analyze_recovery(retention: RetentionComparison) -> RecoveryAnalysis:
    return classify_recovery(
        retention.baseline,
        retention.target,
        retention.post,
    )


def compare_lifecycle_segments(
    executor: QueryExecutor,
    dimension: str,
    windows: LifecycleWindows,
    minimum_sample_size: int = 100,
) -> LifecycleSegmentComparison:
    rows = executor.query(build_lifecycle_segment_query(dimension), lifecycle_params(windows))
    baseline = [row for row in rows if row["period"] == "baseline"]
    target = [row for row in rows if row["period"] == "target"]
    return compare_lifecycle_segment_rows(
        dimension, baseline, target, minimum_sample_size=minimum_sample_size
    )


def _timing_period(row: Mapping[str, Any]) -> ReturnTimingPeriod:
    eligible = int(row["eligible_new_users"])
    d1 = int(row["returned_users_d1"])
    d3 = int(row["returned_users_d3"])
    d7 = int(row["returned_users_d7"])
    return ReturnTimingPeriod(
        eligible_new_users=eligible,
        returned_users_d1=d1,
        return_rate_d1=_rate(d1, eligible),
        returned_users_d3=d3,
        return_rate_d3=_rate(d3, eligible),
        returned_users_d7=d7,
        return_rate_d7=_rate(d7, eligible),
    )


def _retention_period(timing: ReturnTimingPeriod) -> RetentionPeriodResult:
    return RetentionPeriodResult(
        eligible_new_users=timing.eligible_new_users,
        returned_users_7d=timing.returned_users_d7,
        return_rate_7d=timing.return_rate_d7,
    )


def _rate(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0
