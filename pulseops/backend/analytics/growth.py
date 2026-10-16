"""Deterministic calculations for bounded positive-growth investigations.

These functions deliberately accept already queried facts.  They never infer a
mechanism, and provide no path for a planner to alter metrics or confidence.
"""
from __future__ import annotations

from math import erfc, sqrt

from pulseops.backend.schemas.analytics import (
    GrowthSegmentComparison,
    GrowthSegmentResult,
    GrowthPeriodResult,
    Reproducibility,
    StatisticalResult,
)


def checkout_purchase_rate(checkout_sessions: int, purchase_after_checkout_sessions: int) -> GrowthPeriodResult:
    if checkout_sessions < 0 or purchase_after_checkout_sessions < 0:
        raise ValueError("session counts must be non-negative")
    if purchase_after_checkout_sessions > checkout_sessions:
        raise ValueError("purchases after checkout cannot exceed checkout sessions")
    return GrowthPeriodResult(
        checkout_sessions=checkout_sessions,
        purchase_after_checkout_sessions=purchase_after_checkout_sessions,
        conversion_rate=(round(100 * purchase_after_checkout_sessions / checkout_sessions, 2)
                         if checkout_sessions else 0.0),
    )


def two_proportion_result(baseline: GrowthPeriodResult, comparison: GrowthPeriodResult) -> StatisticalResult:
    if baseline.checkout_sessions == 0 or comparison.checkout_sessions == 0:
        return StatisticalResult(delta_pp=0.0, z_score=0.0, p_value=1.0, statistically_significant=False)
    p1 = baseline.purchase_after_checkout_sessions / baseline.checkout_sessions
    p2 = comparison.purchase_after_checkout_sessions / comparison.checkout_sessions
    pooled = ((baseline.purchase_after_checkout_sessions + comparison.purchase_after_checkout_sessions)
              / (baseline.checkout_sessions + comparison.checkout_sessions))
    standard_error = sqrt(pooled * (1 - pooled) * (1 / baseline.checkout_sessions + 1 / comparison.checkout_sessions))
    z_score = (p2 - p1) / standard_error if standard_error else 0.0
    p_value = erfc(abs(z_score) / sqrt(2))
    return StatisticalResult(
        delta_pp=round(100 * (p2 - p1), 4),
        z_score=round(z_score, 4),
        p_value=p_value,
        statistically_significant=p_value < 0.05,
    )


def has_material_positive_growth(
    baseline: GrowthPeriodResult,
    growth: GrowthPeriodResult,
    minimum_sample_size: int = 100,
) -> bool:
    result = two_proportion_result(baseline, growth)
    return (
        baseline.checkout_sessions >= minimum_sample_size
        and growth.checkout_sessions >= minimum_sample_size
        and result.delta_pp > 0
        and result.statistically_significant
    )


def classify_reproducibility(
    baseline: GrowthPeriodResult,
    confirmation: GrowthPeriodResult,
    holdout_1: GrowthPeriodResult,
    holdout_2: GrowthPeriodResult,
    minimum_sample_size: int = 100,
    growth_weeks: list | None = None,
    growth: GrowthPeriodResult | None = None,
) -> Reproducibility:
    """Classify persistence without silently discarding undersized required periods.

    The positive-signal gate validates Baseline and Growth before this function is
    reached.  ``growth`` is accepted here as an additional explicit safeguard for
    callers that have the period available.  REPRODUCED requires every required
    confirmation/holdout comparison to be adequately sampled and positive.
    """
    required_periods = (confirmation, holdout_1, holdout_2)
    checks = [two_proportion_result(baseline, period) for period in required_periods]
    adequately_sampled = [
        period.checkout_sessions >= minimum_sample_size for period in required_periods
    ]
    required_samples_adequate = (
        baseline.checkout_sessions >= minimum_sample_size
        and (growth is None or growth.checkout_sessions >= minimum_sample_size)
        and all(adequately_sampled)
    )
    reproduced = [
        item
        for item, adequate in zip(checks, adequately_sampled, strict=True)
        if adequate and item.delta_pp > 0 and item.statistically_significant
    ]
    weekly_supported = True
    weekly_evidence_present = growth_weeks is not None
    if growth_weeks is not None:
        eligible_weeks = [
            item for item in growth_weeks
            if getattr(item, "period", "GROWTH") == "GROWTH"
            and getattr(item, "checkout_sessions", 0) >= minimum_sample_size
        ]
        weekly_supported = bool(eligible_weeks) and all(
            item.conversion_rate > baseline.conversion_rate for item in eligible_weeks
        )
    if required_samples_adequate and len(reproduced) == len(checks) and weekly_supported:
        return Reproducibility.REPRODUCED
    if reproduced or (weekly_evidence_present and weekly_supported):
        return Reproducibility.PARTIALLY_REPRODUCED
    return Reproducibility.NOT_REPRODUCED


def derive_growth_localization(results: list[GrowthSegmentComparison] | tuple[GrowthSegmentComparison, ...]) -> str:
    """Summarize complete available segment evidence independently of tool order."""
    localizations = {result.localization for result in results if result.localization}
    if not localizations:
        return "UNKNOWN"
    if len(localizations) == 1:
        return localizations.pop()
    return "MIXED"


def compare_growth_segment_rows(
    dimension: str, baseline_rows: list[dict], growth_rows: list[dict], minimum_sample_size: int = 100
) -> GrowthSegmentComparison:
    baseline = {str(row["segment"]): row for row in baseline_rows}
    growth = {str(row["segment"]): row for row in growth_rows}
    baseline_total = sum(int(row["checkout_sessions"]) for row in baseline.values())
    growth_total = sum(int(row["checkout_sessions"]) for row in growth.values())
    rows: list[GrowthSegmentResult] = []
    composition = 0.0
    within = 0.0
    for segment in sorted(set(baseline) | set(growth)):
        before = baseline.get(segment, {})
        after = growth.get(segment, {})
        b_sessions = int(before.get("checkout_sessions", 0))
        b_converted = int(before.get("purchase_after_checkout_sessions", 0))
        g_sessions = int(after.get("checkout_sessions", 0))
        g_converted = int(after.get("purchase_after_checkout_sessions", 0))
        b_rate = 100 * b_converted / b_sessions if b_sessions else 0.0
        g_rate = 100 * g_converted / g_sessions if g_sessions else 0.0
        b_share = 100 * b_sessions / baseline_total if baseline_total else 0.0
        g_share = 100 * g_sessions / growth_total if growth_total else 0.0
        composition += (g_share - b_share) * b_rate / 100
        within += g_share * (g_rate - b_rate) / 100
        rows.append(GrowthSegmentResult(
            segment=segment,
            baseline_sessions=b_sessions,
            baseline_converted_sessions=b_converted,
            baseline_rate=round(b_rate, 2),
            baseline_share=round(b_share, 2),
            growth_sessions=g_sessions,
            growth_converted_sessions=g_converted,
            growth_rate=round(g_rate, 2),
            growth_share=round(g_share, 2),
            change_pp=round(g_rate - b_rate, 2),
            share_change_pp=round(g_share - b_share, 2),
            sample_sufficient=b_sessions >= minimum_sample_size and g_sessions >= minimum_sample_size,
        ))
    material = [row for row in rows if row.sample_sufficient]
    localization = "BROAD" if len(material) >= 2 and all(row.change_pp > 0 for row in material) else "MIXED"
    return GrowthSegmentComparison(
        dimension=dimension,
        segments=rows,
        composition_effect_pp=round(composition, 2),
        within_segment_effect_pp=round(within, 2),
        localization=localization,
    )
