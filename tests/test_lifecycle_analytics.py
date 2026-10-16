from __future__ import annotations

from datetime import date

import pytest

from pulseops.backend.analytics.lifecycle import (
    activation_bucket,
    analyze_timing,
    classify_recovery,
    compare_lifecycle_segment_rows,
    compare_retention_periods,
    describe_return_timing,
    eligible_users,
    return_day,
    summarize_return_timing,
)
from pulseops.backend.analytics.queries.lifecycle import build_lifecycle_timing_query
from pulseops.backend.schemas.analytics import RetentionPeriodResult, ReturnTimingPeriod


def test_day_zero_session_does_not_count_as_return():
    first = date(2021, 1, 1)
    assert return_day(first, [first]) is None
    assert return_day(first, [date(2021, 1, 2)]) == 1


def test_right_censored_users_are_excluded():
    users = [
        {"first_visit_date": date(2021, 1, 23)},
        {"first_visit_date": date(2021, 1, 24)},
        {"first_visit_date": date(2021, 1, 25)},
    ]
    assert len(eligible_users(users, date(2021, 1, 31))) == 2


def test_d1_d3_d7_are_cumulative_and_deterministic():
    first = date(2021, 1, 1)
    result = summarize_return_timing(
        [
            {"first_visit_date": first, "session_dates": [date(2021, 1, 2)]},
            {"first_visit_date": first, "session_dates": [date(2021, 1, 4)]},
            {"first_visit_date": first, "session_dates": [date(2021, 1, 8)]},
            {"first_visit_date": first, "session_dates": [date(2021, 1, 9)]},
        ]
    )
    assert (result.returned_users_d1, result.returned_users_d3, result.returned_users_d7) == (1, 2, 3)
    assert (result.return_rate_d1, result.return_rate_d3, result.return_rate_d7) == (25, 50, 75)


def retention_period(rate: float, *, users: int = 60_000) -> RetentionPeriodResult:
    return RetentionPeriodResult(
        eligible_new_users=users,
        returned_users_7d=round(users * rate / 100),
        return_rate_7d=rate,
    )


@pytest.mark.parametrize(
    ("post", "expected"),
    [
        (4.5, "NO_RECOVERY"),
        (5.11, "NO_RECOVERY"),
        (6.9, "PARTIAL_RECOVERY"),
        (8.3, "FULL_RECOVERY"),
        (9.0, "FULL_RECOVERY"),
    ],
)
def test_recovery_classification_uses_statistical_comparisons(post, expected):
    result = classify_recovery(
        retention_period(8.33),
        retention_period(5.11),
        retention_period(post),
    )
    assert result.risk_pattern == expected


def test_baseline_zero_returns_no_relative_change_instead_of_dividing_by_zero():
    baseline = ReturnTimingPeriod(
        eligible_new_users=100,
        returned_users_d1=0,
        return_rate_d1=0,
        returned_users_d3=0,
        return_rate_d3=0,
        returned_users_d7=0,
        return_rate_d7=0,
    )
    target = baseline.model_copy(update={"returned_users_d7": 5, "return_rate_d7": 5})
    result = compare_retention_periods(baseline, target, target)
    assert result.relative_change_pct is None


def test_later_timing_decline_is_not_described_as_beginning_at_d1():
    baseline = ReturnTimingPeriod(
        eligible_new_users=1_000,
        returned_users_d1=100,
        return_rate_d1=10,
        returned_users_d3=180,
        return_rate_d3=18,
        returned_users_d7=250,
        return_rate_d7=25,
    )
    target = ReturnTimingPeriod(
        eligible_new_users=1_000,
        returned_users_d1=100,
        return_rate_d1=10,
        returned_users_d3=130,
        return_rate_d3=13,
        returned_users_d7=180,
        return_rate_d7=18,
    )
    timing = analyze_timing(baseline, target, target)
    assert describe_return_timing(timing).startswith("Return is not lower at D1")


def test_activation_buckets_are_mutually_exclusive_highest_depth():
    assert activation_bucket(["session_start"]) == "SHALLOW"
    assert activation_bucket(["session_start", "view_item"]) == "BROWSE"
    assert activation_bucket(["session_start", "view_item", "add_to_cart"]) == "INTENT"
    assert activation_bucket(["session_start", "purchase"]) == "INTENT"


def test_composition_and_within_segment_effects_are_separate():
    baseline = [
        {"segment": "SHALLOW", "eligible_users": 800, "returned_users": 80},
        {"segment": "INTENT", "eligible_users": 200, "returned_users": 40},
    ]
    target = [
        {"segment": "SHALLOW", "eligible_users": 900, "returned_users": 45},
        {"segment": "INTENT", "eligible_users": 100, "returned_users": 15},
    ]
    result = compare_lifecycle_segment_rows("activation_depth", baseline, target)
    assert result.composition_effect_pp == -1.0
    assert result.within_segment_effect_pp == -5.0
    assert {row.segment for row in result.segments} == {"SHALLOW", "INTENT"}


def test_live_query_enforces_day_zero_exclusion_and_complete_observation_parameter():
    sql = build_lifecycle_timing_query()
    assert "e.event_date > c.first_visit_date" in sql
    assert "DATE_ADD(c.first_visit_date, INTERVAL 7 DAY)" in sql
    assert "@observation_end" in sql
