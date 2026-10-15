from __future__ import annotations

from datetime import date

from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.queries.metrics import FUNNEL_PAIRS
from pulseops.backend.schemas.analytics import MetricResult, MetricsScanResult
from pulseops.backend.tools.analyze_funnel import analyze_funnel


def scan_metrics(
    executor: QueryExecutor,
    baseline_start: date,
    baseline_end: date,
    target_start: date,
    target_end: date,
) -> MetricsScanResult:
    metrics: list[MetricResult] = []
    for name, events in FUNNEL_PAIRS:
        result = analyze_funnel(
            executor,
            list(events),
            baseline_start,
            baseline_end,
            target_start,
            target_end,
        )
        metrics.append(
            MetricResult(
                name=name,
                baseline_rate=result.baseline.session_conversion_rate,
                target_rate=result.target.session_conversion_rate,
                delta_pp=result.session_delta_pp,
                baseline_sample_size=result.baseline.view_sessions,
                target_sample_size=result.target.view_sessions,
                needs_investigation=result.needs_investigation,
            )
        )
    return MetricsScanResult(metrics=metrics)

