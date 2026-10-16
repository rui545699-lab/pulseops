from __future__ import annotations

from pulseops.backend.analytics.growth import (
    checkout_purchase_rate,
    compare_growth_segment_rows,
    classify_reproducibility,
    derive_growth_localization,
    has_material_positive_growth,
    two_proportion_result,
)
import pytest
from pulseops.backend.analytics.queries.growth import (
    build_growth_segment_query,
    build_growth_validation_query,
    build_growth_weekly_query,
)
from pulseops.backend.schemas.analytics import WeeklyGrowthResult
from pulseops.backend.fixtures.growth import CASE_03


def period(total: int, rate: float):
    return checkout_purchase_rate(total, round(total * rate / 100))


def test_material_positive_growth_requires_positive_statistically_supported_lift():
    baseline = period(2_592, 40.35)
    growth = period(2_550, 51.14)
    assert has_material_positive_growth(baseline, growth)
    assert two_proportion_result(baseline, growth).statistically_significant
    assert not has_material_positive_growth(baseline, period(2_550, 40.35))
    assert not has_material_positive_growth(baseline, period(2_550, 35.0))


def test_reproducibility_enum_is_deterministic():
    baseline = period(2_592, 40.35)
    assert classify_reproducibility(
        baseline, period(670, 55.07), period(792, 48.74), period(1_208, 55.13)
    ) == "REPRODUCED"
    assert classify_reproducibility(
        baseline, period(670, 55.07), period(792, 40.35), period(1_208, 55.13)
    ) == "PARTIALLY_REPRODUCED"
    assert classify_reproducibility(
        baseline, period(670, 40.35), period(792, 40.35), period(1_208, 40.35)
    ) == "NOT_REPRODUCED"


def test_reproducibility_requires_constituent_growth_week_persistence_when_supplied():
    baseline = period(2_592, 40.35)
    weeks = [
        WeeklyGrowthResult(cohort_week="2020-12-07", period="GROWTH", checkout_sessions=1_000, purchase_after_checkout_sessions=500, conversion_rate=50.0),
        WeeklyGrowthResult(cohort_week="2020-12-14", period="GROWTH", checkout_sessions=1_000, purchase_after_checkout_sessions=350, conversion_rate=35.0),
    ]
    assert classify_reproducibility(
        baseline, period(670, 55.07), period(792, 48.74), period(1_208, 55.13), growth_weeks=weeks
    ) == "PARTIALLY_REPRODUCED"


@pytest.mark.parametrize(
    ("growth_sessions", "confirmation_sessions", "holdout_1_sessions", "holdout_2_sessions", "confirmation_rate", "expected"),
    [
        (99, 670, 792, 1_208, 55.07, "PARTIALLY_REPRODUCED"),
        (2_550, 99, 792, 1_208, 55.07, "PARTIALLY_REPRODUCED"),
        (2_550, 670, 99, 1_208, 55.07, "PARTIALLY_REPRODUCED"),
        (2_550, 670, 792, 99, 55.07, "PARTIALLY_REPRODUCED"),
        (2_550, 670, 792, 1_208, 55.07, "REPRODUCED"),
        (2_550, 670, 792, 1_208, 40.35, "PARTIALLY_REPRODUCED"),
    ],
)
def test_reproducibility_requires_adequate_confirmation_and_holdout_periods(
    growth_sessions, confirmation_sessions, holdout_1_sessions, holdout_2_sessions, confirmation_rate, expected
):
    baseline = period(2_592, 40.35)
    assert classify_reproducibility(
        baseline,
        period(confirmation_sessions, confirmation_rate),
        period(holdout_1_sessions, 48.74),
        period(holdout_2_sessions, 55.13),
        growth=period(growth_sessions, 51.14),
    ) == expected


def test_live_growth_queries_enforce_strict_checkout_order_and_full_observation_coverage():
    validation = build_growth_validation_query()
    assert "GENERATE_DATE_ARRAY(@baseline_start, @holdout_2_end)" in validation
    assert "begin_checkout" in validation and "purchase" in validation
    segments = build_growth_segment_query("device")
    assert "purchase_ts > checkout_ts" in segments
    assert "GROUP BY period, user_pseudo_id, session_id" in segments
    assert "MIN(IF(event_name = 'begin_checkout'" in segments
    assert "@baseline_start" in segments and "@target_end" in segments
    assert "WEEK(MONDAY)" in build_growth_weekly_query()


def test_case_03_segment_decomposition_keeps_composition_and_within_effects_separate():
    fixture = CASE_03["segments"]["lifecycle"]["segments"]
    result = compare_growth_segment_rows(
        "lifecycle",
        [
            {"segment": row["segment"], "checkout_sessions": row["baseline_sessions"], "purchase_after_checkout_sessions": row["baseline_converted_sessions"]}
            for row in fixture
        ],
        [
            {"segment": row["segment"], "checkout_sessions": row["growth_sessions"], "purchase_after_checkout_sessions": row["growth_converted_sessions"]}
            for row in fixture
        ],
    )
    assert result.localization == "BROAD"
    assert result.within_segment_effect_pp > result.composition_effect_pp


def test_growth_localization_requires_consistent_complete_segment_evidence():
    broad = compare_growth_segment_rows(
        "lifecycle",
        [
            {"segment": "new", "checkout_sessions": 200, "purchase_after_checkout_sessions": 80},
            {"segment": "returning", "checkout_sessions": 200, "purchase_after_checkout_sessions": 120},
        ],
        [
            {"segment": "new", "checkout_sessions": 200, "purchase_after_checkout_sessions": 100},
            {"segment": "returning", "checkout_sessions": 200, "purchase_after_checkout_sessions": 140},
        ],
    )
    concentrated = broad.model_copy(update={"localization": "SEGMENT_CONCENTRATED"})
    assert derive_growth_localization([]) == "UNKNOWN"
    assert derive_growth_localization([broad, broad]) == "BROAD"
    assert derive_growth_localization([broad, concentrated]) == "MIXED"
