from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from pulseops.backend.schemas.analytics import (
    LifecycleSegmentComparison,
    LifecycleSegmentResult,
    RecoveryAnalysis,
    RetentionComparison,
    RetentionPeriodResult,
    ReturnTimingAnalysis,
    ReturnTimingPeriod,
    RiskPattern,
)


_Z_95 = 1.959963984540054


def return_day(first_visit_date: date, session_dates: Iterable[date]) -> int | None:
    """Return the earliest eligible return day; Day 0 never counts."""
    eligible = sorted(
        (session_date - first_visit_date).days
        for session_date in session_dates
        if 1 <= (session_date - first_visit_date).days <= 7
    )
    return eligible[0] if eligible else None


def summarize_return_timing(users: Sequence[Mapping[str, Any]]) -> ReturnTimingPeriod:
    eligible = len(users)
    days = [return_day(row["first_visit_date"], row.get("session_dates", [])) for row in users]
    d1 = sum(day == 1 for day in days)
    d3 = sum(day is not None and day <= 3 for day in days)
    d7 = sum(day is not None and day <= 7 for day in days)
    return ReturnTimingPeriod(
        eligible_new_users=eligible,
        returned_users_d1=d1,
        return_rate_d1=_rate(d1, eligible),
        returned_users_d3=d3,
        return_rate_d3=_rate(d3, eligible),
        returned_users_d7=d7,
        return_rate_d7=_rate(d7, eligible),
    )


def compare_retention_periods(
    baseline: ReturnTimingPeriod,
    target: ReturnTimingPeriod,
    post: ReturnTimingPeriod,
) -> RetentionComparison:
    baseline_rate = baseline.return_rate_d7
    target_rate = target.return_rate_d7
    return RetentionComparison(
        baseline=_period(baseline),
        target=_period(target),
        post=_period(post),
        delta_pp=round(target_rate - baseline_rate, 2),
        relative_change_pct=(
            round(100 * (target_rate - baseline_rate) / baseline_rate, 2)
            if baseline_rate
            else None
        ),
        target_to_post_delta_pp=round(post.return_rate_d7 - target_rate, 2),
        baseline_to_post_delta_pp=round(post.return_rate_d7 - baseline_rate, 2),
    )


def analyze_timing(
    baseline: ReturnTimingPeriod,
    target: ReturnTimingPeriod,
    post: ReturnTimingPeriod,
) -> ReturnTimingAnalysis:
    total_gap = baseline.return_rate_d7 - target.return_rate_d7
    d1_gap = baseline.return_rate_d1 - target.return_rate_d1
    d2_3_gap = (
        baseline.return_rate_d3 - baseline.return_rate_d1
        - (target.return_rate_d3 - target.return_rate_d1)
    )
    d4_7_gap = (
        baseline.return_rate_d7 - baseline.return_rate_d3
        - (target.return_rate_d7 - target.return_rate_d3)
    )
    return ReturnTimingAnalysis(
        baseline=baseline,
        target=target,
        post=post,
        d1_decline_contribution_pct=_share(d1_gap, total_gap),
        d2_3_decline_contribution_pct=_share(d2_3_gap, total_gap),
        d4_7_decline_contribution_pct=_share(d4_7_gap, total_gap),
    )


def classify_recovery(
    baseline: RetentionPeriodResult,
    target: RetentionPeriodResult,
    post: RetentionPeriodResult,
) -> RecoveryAnalysis:
    baseline_rate = baseline.return_rate_7d
    target_rate = target.return_rate_7d
    post_rate = post.return_rate_7d
    lost = baseline_rate - target_rate
    recovered = post_rate - target_rate
    ratio = 100 * recovered / lost if lost > 0 else 0.0
    if not is_significantly_higher(post, target):
        pattern = RiskPattern.NO_RECOVERY
    elif is_significantly_lower(post, baseline):
        pattern = RiskPattern.PARTIAL_RECOVERY
    else:
        pattern = RiskPattern.FULL_RECOVERY
    return RecoveryAnalysis(
        risk_pattern=pattern,
        recovery_ratio_pct=round(ratio, 2),
        target_to_post_delta_pp=round(recovered, 2),
        baseline_to_post_delta_pp=round(post_rate - baseline_rate, 2),
    )


def has_material_negative_retention(
    baseline: RetentionPeriodResult, target: RetentionPeriodResult
) -> bool:
    """True only when a two-proportion 95% CI supports a negative change."""
    return (
        target.return_rate_7d < baseline.return_rate_7d
        and is_significantly_lower(target, baseline)
    )


def retention_data_is_sufficient(
    retention: RetentionComparison, *, minimum_cohort_size: int = 100
) -> bool:
    """Reject malformed or too-small cohorts before lifecycle interpretation."""
    periods = (retention.baseline, retention.target, retention.post)
    return all(
        period.eligible_new_users >= minimum_cohort_size
        and 0 <= period.returned_users_7d <= period.eligible_new_users
        for period in periods
    )


def is_significantly_higher(
    candidate: RetentionPeriodResult, reference: RetentionPeriodResult
) -> bool:
    interval = proportion_difference_interval(candidate, reference)
    return interval is not None and interval[0] > 0


def is_significantly_lower(
    candidate: RetentionPeriodResult, reference: RetentionPeriodResult
) -> bool:
    interval = proportion_difference_interval(candidate, reference)
    return interval is not None and interval[1] < 0


def proportion_difference_interval(
    candidate: RetentionPeriodResult, reference: RetentionPeriodResult
) -> tuple[float, float] | None:
    """95% normal-approximation CI for candidate minus reference rates in proportions."""
    if candidate.eligible_new_users <= 0 or reference.eligible_new_users <= 0:
        return None
    candidate_rate = candidate.returned_users_7d / candidate.eligible_new_users
    reference_rate = reference.returned_users_7d / reference.eligible_new_users
    difference = candidate_rate - reference_rate
    variance = (
        candidate_rate * (1 - candidate_rate) / candidate.eligible_new_users
        + reference_rate * (1 - reference_rate) / reference.eligible_new_users
    )
    margin = _Z_95 * variance**0.5
    return difference - margin, difference + margin


def describe_return_timing(timing: ReturnTimingAnalysis) -> str:
    """Describe the first interval with a deterministic cumulative timing decline."""
    baseline = timing.baseline
    target = timing.target
    d1_gap = baseline.return_rate_d1 - target.return_rate_d1
    d2_3_gap = (
        baseline.return_rate_d3 - baseline.return_rate_d1
        - (target.return_rate_d3 - target.return_rate_d1)
    )
    d4_7_gap = (
        baseline.return_rate_d7 - baseline.return_rate_d3
        - (target.return_rate_d7 - target.return_rate_d3)
    )
    if d1_gap > 0:
        return "The decline begins at D1 and persists through D7."
    if d2_3_gap > 0:
        return "Return is not lower at D1; the decline emerges during D2–3 and persists through D7."
    if d4_7_gap > 0:
        return "Return is not lower through D3; the decline emerges during D4–7."
    return "Return timing does not show a clear cumulative decline through D7."


def activation_bucket(event_names: Iterable[str]) -> str:
    events = set(event_names)
    if "add_to_cart" in events or "begin_checkout" in events or "purchase" in events:
        return "INTENT"
    if "view_item" in events:
        return "BROWSE"
    if "session_start" in events:
        return "SHALLOW"
    return "UNCLASSIFIED"


def compare_lifecycle_segment_rows(
    dimension: str,
    baseline_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    *,
    minimum_sample_size: int = 100,
) -> LifecycleSegmentComparison:
    baseline = {str(row["segment"]): row for row in baseline_rows}
    target = {str(row["segment"]): row for row in target_rows}
    baseline_total = sum(int(row["eligible_users"]) for row in baseline_rows)
    target_total = sum(int(row["eligible_users"]) for row in target_rows)
    segments: list[LifecycleSegmentResult] = []
    for name in sorted(set(baseline) | set(target)):
        b = baseline.get(name, {})
        t = target.get(name, {})
        b_users = int(b.get("eligible_users", 0))
        t_users = int(t.get("eligible_users", 0))
        b_returned = int(b.get("returned_users", 0))
        t_returned = int(t.get("returned_users", 0))
        b_rate = _rate(b_returned, b_users)
        t_rate = _rate(t_returned, t_users)
        b_share = _rate(b_users, baseline_total)
        t_share = _rate(t_users, target_total)
        segments.append(
            LifecycleSegmentResult(
                segment=name,
                baseline_users=b_users,
                baseline_returned_users=b_returned,
                baseline_rate=b_rate,
                baseline_share=b_share,
                target_users=t_users,
                target_returned_users=t_returned,
                target_rate=t_rate,
                target_share=t_share,
                change_pp=round(t_rate - b_rate, 2),
                share_change_pp=round(t_share - b_share, 2),
                sample_sufficient=b_users >= minimum_sample_size and t_users >= minimum_sample_size,
            )
        )
    usable = [row for row in segments if row.sample_sufficient]
    usable_b_total = sum(row.baseline_users for row in usable)
    usable_t_total = sum(row.target_users for row in usable)
    baseline_rate = _rate(sum(row.baseline_returned_users for row in usable), usable_b_total)
    target_rate = _rate(sum(row.target_returned_users for row in usable), usable_t_total)
    counterfactual = sum(
        row.target_users / usable_t_total * row.baseline_rate for row in usable
    ) if usable_t_total else 0.0
    composition = round(counterfactual - baseline_rate, 2)
    within = round(target_rate - counterfactual, 2)
    total = target_rate - baseline_rate
    return LifecycleSegmentComparison(
        dimension=dimension,
        segments=segments,
        composition_effect_pp=composition,
        within_segment_effect_pp=within,
        composition_share_of_total_decline_pct=_share(composition, total) if total else None,
        within_segment_share_of_total_decline_pct=_share(within, total) if total else None,
    )


def eligible_users(
    users: Sequence[Mapping[str, Any]], observation_end: date
) -> list[Mapping[str, Any]]:
    """Exclude cohorts that do not have all seven follow-up days observable."""
    return [row for row in users if (observation_end - row["first_visit_date"]).days >= 7]


def _period(value: ReturnTimingPeriod) -> RetentionPeriodResult:
    return RetentionPeriodResult(
        eligible_new_users=value.eligible_new_users,
        returned_users_7d=value.returned_users_d7,
        return_rate_7d=value.return_rate_d7,
    )


def _rate(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 4) if denominator else 0.0


def _share(part: float, total: float) -> float:
    return round(100 * part / total, 2) if total else 0.0
