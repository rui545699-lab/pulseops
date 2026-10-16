from __future__ import annotations

from datetime import date

from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.growth import (
    checkout_purchase_rate,
    compare_growth_segment_rows,
    two_proportion_result,
)
from pulseops.backend.analytics.queries.growth import (
    build_growth_segment_query,
    build_growth_validation_query,
    build_growth_weekly_query,
)
from pulseops.backend.tools.analyze_funnel import analyze_funnel
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    GrowthComparison,
    GrowthPeriodResult,
    GrowthWindows,
    OrderValueContext,
    ValidationResult,
    WarningItem,
    GrowthSegmentComparison,
    WeeklyGrowthResult,
)


def _period(executor: QueryExecutor, start: date, end: date) -> GrowthPeriodResult:
    funnel = analyze_funnel(executor, ["begin_checkout", "purchase"], start, end, start, end)
    return checkout_purchase_rate(funnel.baseline.view_sessions, funnel.baseline.converted_sessions)


def validate_growth_data(executor: QueryExecutor, windows: GrowthWindows) -> ValidationResult:
    rows = executor.query(build_growth_validation_query(), windows.model_dump())
    checkout_counts = [int(row["checkout_events"]) for row in rows]
    purchase_counts = [int(row["purchase_events"]) for row in rows]
    warnings: list[WarningItem] = []
    if any(count == 0 for count in checkout_counts):
        warnings.append(WarningItem(code="MISSING_CHECKOUT", message="begin_checkout has zero-volume dates."))
    if any(count == 0 for count in purchase_counts):
        warnings.append(WarningItem(code="MISSING_PURCHASE", message="purchase has zero-volume dates."))
    if checkout_counts:
        median = sorted(checkout_counts)[len(checkout_counts) // 2]
        if median and any(0 < count < median * 0.2 for count in checkout_counts):
            warnings.append(WarningItem(code="CHECKOUT_VOLUME_ANOMALY", message="begin_checkout has a sub-20%-median date."))
    return ValidationResult(status=AnalysisStatus.FAIL if warnings else AnalysisStatus.PASS, analysis_allowed=not warnings, warnings=warnings)


def analyze_growth(executor: QueryExecutor, windows: GrowthWindows) -> GrowthComparison:
    baseline = _period(executor, windows.baseline_start, windows.baseline_end)
    growth = _period(executor, windows.target_start, windows.target_end)
    confirmation = _period(executor, windows.confirmation_start, windows.confirmation_end)
    holdout_1 = _period(executor, windows.holdout_1_start, windows.holdout_1_end)
    holdout_2 = _period(executor, windows.holdout_2_start, windows.holdout_2_end)
    return GrowthComparison(
        baseline=baseline,
        growth=growth,
        confirmation=confirmation,
        holdout_1=holdout_1,
        holdout_2=holdout_2,
        delta_pp=round(growth.conversion_rate - baseline.conversion_rate, 2),
        growth_statistical_result=two_proportion_result(baseline, growth),
        confirmation_statistical_result=two_proportion_result(baseline, confirmation),
        holdout_1_statistical_result=two_proportion_result(baseline, holdout_1),
        holdout_2_statistical_result=two_proportion_result(baseline, holdout_2),
    )


def analyze_weekly_growth(executor: QueryExecutor, windows: GrowthWindows) -> list[WeeklyGrowthResult]:
    rows = executor.query(build_growth_weekly_query(), windows.model_dump())
    return [
        WeeklyGrowthResult(
            cohort_week=str(row["cohort_week"]),
            period=str(row["period"]),
            checkout_sessions=int(row["checkout_sessions"]),
            purchase_after_checkout_sessions=int(row["purchase_after_checkout_sessions"]),
            conversion_rate=round(
                100 * int(row["purchase_after_checkout_sessions"]) / int(row["checkout_sessions"]), 2
            ) if int(row["checkout_sessions"]) else 0.0,
        )
        for row in rows
    ]


def compare_growth_segments(
    executor: QueryExecutor, dimension: str, windows: GrowthWindows, minimum_sample_size: int = 100
) -> GrowthSegmentComparison:
    rows = [dict(row) for row in executor.query(build_growth_segment_query(dimension), windows.model_dump())]
    return compare_growth_segment_rows(
        dimension,
        [row for row in rows if row["period"] == "baseline"],
        [row for row in rows if row["period"] == "growth"],
        minimum_sample_size,
    )


def analyze_order_value(executor: QueryExecutor, windows: GrowthWindows) -> OrderValueContext:
    # Revenue is context only; it cannot determine whether the strict conversion lift is material.
    query = """
SELECT
  CASE WHEN PARSE_DATE('%Y%m%d', event_date) BETWEEN @baseline_start AND @baseline_end THEN 'baseline'
       WHEN PARSE_DATE('%Y%m%d', event_date) BETWEEN @target_start AND @target_end THEN 'growth'
       ELSE 'confirmation' END AS period,
  COUNT(*) AS purchases,
  COALESCE(SUM(ecommerce.purchase_revenue_in_usd), 0) AS revenue_usd
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @baseline_start)
                        AND FORMAT_DATE('%Y%m%d', @confirmation_end)
  AND event_name = 'purchase'
  AND (PARSE_DATE('%Y%m%d', event_date) BETWEEN @baseline_start AND @baseline_end
       OR PARSE_DATE('%Y%m%d', event_date) BETWEEN @target_start AND @target_end
       OR PARSE_DATE('%Y%m%d', event_date) BETWEEN @confirmation_start AND @confirmation_end)
GROUP BY period
"""
    rows = {str(row["period"]): row for row in executor.query(query, windows.model_dump())}
    def values(period: str) -> tuple[float, float]:
        row = rows.get(period, {})
        revenue = float(row.get("revenue_usd", 0))
        purchases = int(row.get("purchases", 0))
        return revenue, round(revenue / purchases, 2) if purchases else 0.0
    baseline, growth, confirmation = (values(name) for name in ("baseline", "growth", "confirmation"))
    return OrderValueContext(
        baseline_revenue_usd=baseline[0], baseline_average_order_value_usd=baseline[1],
        growth_revenue_usd=growth[0], growth_average_order_value_usd=growth[1],
        confirmation_revenue_usd=confirmation[0], confirmation_average_order_value_usd=confirmation[1],
    )
