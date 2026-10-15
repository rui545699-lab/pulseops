from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from pulseops.backend.analytics.assessment import assess_case
from pulseops.backend.analytics.queries.funnel import build_funnel_query
from pulseops.backend.schemas.analytics import DateWindows
from pulseops.backend.tools.analyze_funnel import compare_funnel_rows
from pulseops.backend.tools.compare_segments import compare_segment_rows
from pulseops.backend.tools.validate_data import evaluate_validation_rows

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "case_01.json").read_text())


@pytest.fixture
def case_results():
    funnel = compare_funnel_rows(
        ["view_item", "add_to_cart"],
        FIXTURE["funnel"]["baseline"],
        FIXTURE["funnel"]["target"],
    )
    segments = {
        dimension: compare_segment_rows(
            dimension, values["baseline"], values["target"], minimum_sample_size=100
        )
        for dimension, values in FIXTURE["segments"].items()
    }
    return funnel, segments, assess_case(funnel, segments)


def test_detects_material_view_to_cart_decline(case_results):
    funnel, _, _ = case_results
    assert funnel.baseline.session_conversion_rate == pytest.approx(31.6, abs=0.01)
    assert funnel.target.session_conversion_rate == pytest.approx(22.92, abs=0.01)
    assert funnel.session_delta_pp == pytest.approx(-8.68, abs=0.01)
    assert funnel.needs_investigation is True


def test_new_users_are_primary_affected_segment(case_results):
    _, segments, _ = case_results
    lifecycle = {row.segment: row for row in segments["lifecycle"].segments}
    assert lifecycle["new"].change_pp == pytest.approx(-11.56, abs=0.02)
    assert lifecycle["new"].change_pp < lifecycle["returning"].change_pp


def test_returning_users_are_stable(case_results):
    _, segments, _ = case_results
    returning = next(row for row in segments["lifecycle"].segments if row.segment == "returning")
    assert returning.change_pp == pytest.approx(-0.57, abs=0.02)


def test_device_is_not_a_primary_explanation(case_results):
    _, segments, assessment = case_results
    devices = {row.segment: row for row in segments["device"].segments}
    assert devices["desktop"].change_pp < -10
    assert devices["mobile"].change_pp < -10
    assert any("device is not a primary explanation" in item for item in assessment.evidence)
    assert segments["device"].segments[-1].sample_sufficient is False
    assert segments["device"].segments[-1].change_pp is None


def test_acquisition_mix_is_insufficient_explanation(case_results):
    _, _, assessment = case_results
    assert any("acquisition sources" in item for item in assessment.evidence)


def test_category_does_not_establish_single_root_cause(case_results):
    _, _, assessment = case_results
    assert any("Category movements are mixed" in item for item in assessment.unknowns)


def test_final_assessment_preserves_evidence_boundary(case_results):
    _, _, assessment = case_results
    assert assessment.signal_confidence == "HIGH"
    assert assessment.root_cause_confidence == "LOW"
    assert assessment.recommended_status == "NEEDS_EVIDENCE"
    assert assessment.hypotheses == []


def _period_rows(start: date, cart_users: int = 80, checkout_users: int = 60):
    rows = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        for event, users, sessions in (
            ("view_item", 200, 220),
            ("add_to_cart", cart_users, 90),
            ("begin_checkout", checkout_users, 70),
            ("purchase", 40, 45),
        ):
            rows.append(
                {"event_date": day, "event_name": event, "users": users, "sessions": sessions}
            )
    return rows


def test_data_quality_alert_blocks_analysis():
    windows = DateWindows(
        baseline_start=date(2020, 11, 1),
        baseline_end=date(2020, 11, 7),
        target_start=date(2020, 12, 21),
        target_end=date(2020, 12, 27),
    )
    result = evaluate_validation_rows(
        {
            "baseline": _period_rows(date(2020, 11, 1), cart_users=1, checkout_users=150),
            "target": _period_rows(date(2020, 12, 21)),
        },
        windows,
    )
    assert result.analysis_allowed is False
    assert result.status == "FAIL"
    assert any(warning.code == "DATA_QUALITY_ALERT" for warning in result.warnings)


def test_strict_funnel_sql_enforces_identity_session_and_order():
    sql = build_funnel_query(["view_item", "add_to_cart"])
    assert "e.user_pseudo_id = p.user_pseudo_id" in sql
    assert "e.session_id = p.session_id" in sql
    assert "e.event_timestamp > p.step_1_ts" in sql

