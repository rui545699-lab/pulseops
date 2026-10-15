from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    DateWindows,
    MetricResult,
    MetricsScanResult,
    ValidationResult,
    WarningItem,
)
from pulseops.backend.tools.analyze_funnel import compare_funnel_rows
from pulseops.backend.tools.compare_segments import compare_segment_rows

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "case_01.json").read_text())
WINDOWS = DateWindows(
    baseline_start=date(2020, 12, 7),
    baseline_end=date(2020, 12, 13),
    target_start=date(2020, 12, 21),
    target_end=date(2020, 12, 27),
)


class FixtureTools:
    def __init__(self, *, data_quality_passes: bool = True, significant_signal: bool = True):
        self.data_quality_passes = data_quality_passes
        self.significant_signal = significant_signal
        self.calls: list[tuple] = []

    def validate_data(self, windows):
        self.calls.append(("validate_data",))
        if self.data_quality_passes:
            return ValidationResult(status=AnalysisStatus.PASS, analysis_allowed=True)
        return ValidationResult(
            status=AnalysisStatus.FAIL,
            analysis_allowed=False,
            warnings=[WarningItem(code="DATA_QUALITY_ALERT", message="fixture quality failure")],
        )

    def scan_metrics(self, windows):
        self.calls.append(("scan_metrics",))
        funnel = compare_funnel_rows(
            ["view_item", "add_to_cart"],
            FIXTURE["funnel"]["baseline"],
            FIXTURE["funnel"]["target"],
        )
        return MetricsScanResult(
            metrics=[
                MetricResult(
                    name="View→Cart",
                    baseline_rate=funnel.baseline.session_conversion_rate,
                    target_rate=funnel.target.session_conversion_rate,
                    delta_pp=funnel.session_delta_pp,
                    baseline_sample_size=funnel.baseline.view_sessions,
                    target_sample_size=funnel.target.view_sessions,
                    needs_investigation=self.significant_signal,
                ),
                MetricResult(
                    name="Cart→Checkout",
                    baseline_rate=50,
                    target_rate=50,
                    delta_pp=0,
                    baseline_sample_size=1000,
                    target_sample_size=1000,
                    needs_investigation=False,
                ),
                MetricResult(
                    name="Checkout→Purchase",
                    baseline_rate=60,
                    target_rate=60,
                    delta_pp=0,
                    baseline_sample_size=800,
                    target_sample_size=800,
                    needs_investigation=False,
                ),
            ]
        )

    def analyze_funnel(self, events, windows):
        self.calls.append(("analyze_funnel", tuple(events)))
        return compare_funnel_rows(
            events,
            FIXTURE["funnel"]["baseline"],
            FIXTURE["funnel"]["target"],
        )

    def compare_segments(self, dimension, windows, lifecycle_filter):
        self.calls.append(("compare_segments", dimension, lifecycle_filter))
        values = FIXTURE["segments"][dimension]
        return compare_segment_rows(dimension, values["baseline"], values["target"])


class DeviceFocusedTools(FixtureTools):
    def compare_segments(self, dimension, windows, lifecycle_filter):
        if dimension != "device":
            return super().compare_segments(dimension, windows, lifecycle_filter)
        self.calls.append(("compare_segments", dimension, lifecycle_filter))
        return compare_segment_rows(
            "device",
            [
                {"segment": "desktop", "view_users": 1000, "converted_users": 300},
                {"segment": "mobile", "view_users": 1000, "converted_users": 300},
            ],
            [
                {"segment": "desktop", "view_users": 800, "converted_users": 120},
                {"segment": "mobile", "view_users": 800, "converted_users": 236},
            ],
        )


@pytest.fixture
def case_run():
    tools = FixtureTools()
    state = InvestigationAgent(tools).run(WINDOWS, run_id="case-01")
    return tools, state


def test_case_01_runs_tools_in_evidence_driven_order(case_run):
    tools, state = case_run
    assert [call[0] for call in tools.calls[:3]] == [
        "validate_data",
        "scan_metrics",
        "analyze_funnel",
    ]
    assert state.funnel_result.entry_event == "view_item"
    assert state.funnel_result.conversion_event == "add_to_cart"
    assert state.investigated_dimensions == ["lifecycle", "device", "acquisition", "category"]


def test_case_01_focuses_secondary_dimensions_on_new_users(case_run):
    tools, state = case_run
    assert state.affected_segment == "new_users"
    segment_calls = [call for call in tools.calls if call[0] == "compare_segments"]
    assert segment_calls[0] == ("compare_segments", "lifecycle", None)
    assert all(call[2] == "new" for call in segment_calls[1:])


def test_case_01_rejects_unsupported_root_causes(case_run):
    _, state = case_run
    rejected = {item.code: item.reason for item in state.rejected_hypotheses}
    assert "DEVICE_CONCENTRATION" in rejected
    assert "ACQUISITION_MIX_EXPLANATION" in rejected
    assert not state.supported_hypotheses
    assert [item.code for item in state.insufficient_hypotheses] == ["CATEGORY_CONCENTRATION"]
    assert state.insufficient_hypotheses[0].status == "INSUFFICIENT_EVIDENCE"
    assert any("single category root cause" in item for item in state.unknowns)


def test_case_01_stops_with_separate_confidence_and_safe_action(case_run):
    _, state = case_run
    assert state.signal_confidence == "HIGH"
    assert state.root_cause_confidence == "LOW"
    assert state.recommended_status == "NEEDS_EVIDENCE"
    assert state.recommended_action_type == "EVIDENCE_COLLECTION"
    assert state.agent_steps[-1].node == "STOP_DRILLDOWN"
    assert state.agent_steps[-1].decision == "STOP"
    assert state.remaining_investigation_budget == 0
    assert state.stop_reason == "ALLOWED_DIMENSIONS_EXHAUSTED"
    assert "all permitted dimensions are complete" in state.agent_steps[-1].decision_reason.lower()


def test_case_01_preserves_evidence_hypothesis_unknown_boundaries(case_run):
    _, state = case_run
    assert all("unverified" not in item.lower() for item in state.evidence)
    assert state.hypotheses and all("unverified" in item.lower() for item in state.hypotheses)
    assert any("pricing" in item.lower() for item in state.unknowns)
    assert state.do_not_recommend_yet
    unsupported = ("caused", "导致了", "is the root cause")
    assert not any(term in item.lower() for item in state.evidence for term in unsupported)


def test_case_01_log_is_complete_bounded_and_summarized(case_run):
    _, state = case_run
    assert [step.step_order for step in state.agent_steps] == list(range(1, 9))
    assert [step.node for step in state.agent_steps] == [
        "VALIDATE_DATA",
        "SCAN_METRICS",
        "ANALYZE_FUNNEL",
        "COMPARE_SEGMENTS_LIFECYCLE",
        "COMPARE_SEGMENTS_DEVICE",
        "COMPARE_SEGMENTS_ACQUISITION",
        "COMPARE_SEGMENTS_CATEGORY",
        "STOP_DRILLDOWN",
    ]
    assert len(state.investigated_dimensions) == len(set(state.investigated_dimensions))
    serialized = json.dumps([step.model_dump(mode="json") for step in state.agent_steps])
    assert "converted_users" not in serialized
    assert "view_users" not in serialized


def test_data_quality_failure_stops_before_metric_or_segment_work():
    tools = FixtureTools(data_quality_passes=False)
    state = InvestigationAgent(tools).run(WINDOWS, run_id="dq-fail")
    assert tools.calls == [("validate_data",)]
    assert state.recommended_status == "DATA_QUALITY_ALERT"
    assert state.recommended_action_type == "NONE"
    assert state.stop_reason == "DATA_QUALITY_FAIL"
    assert state.investigated_dimensions == []
    assert state.agent_steps[-1].decision == "STOP"


def test_no_significant_signal_creates_no_opportunity():
    tools = FixtureTools(significant_signal=False)
    state = InvestigationAgent(tools).run(WINDOWS, run_id="no-signal")
    assert tools.calls == [("validate_data",), ("scan_metrics",)]
    assert state.detected_signal is None
    assert state.recommended_status == "NO_OPPORTUNITY"
    assert state.recommended_action_type == "NONE"
    assert state.stop_reason == "NO_SIGNIFICANT_SIGNAL"
    assert state.investigated_dimensions == []


def test_budget_exhaustion_stops_without_duplicate_or_forbidden_dimensions():
    tools = FixtureTools()
    state = InvestigationAgent(tools, investigation_budget=2).run(WINDOWS, run_id="budget")
    assert state.investigated_dimensions == ["lifecycle", "device"]
    assert state.remaining_investigation_budget == 0
    assert len(state.investigated_dimensions) == len(set(state.investigated_dimensions))
    assert set(state.investigated_dimensions) <= {"lifecycle", "device", "acquisition", "category"}
    assert state.agent_steps[-1].node == "STOP_DRILLDOWN"
    assert "budget exhausted" in state.agent_steps[-1].decision_reason.lower()
    assert state.stop_reason == "BUDGET_EXHAUSTED"


def test_budget_cannot_exceed_v01_dimension_limit():
    with pytest.raises(ValueError, match="between 0 and 4"):
        InvestigationAgent(FixtureTools(), investigation_budget=5)


def test_supported_focused_pattern_stops_broad_dimension_sweep():
    tools = DeviceFocusedTools()
    state = InvestigationAgent(tools).run(WINDOWS, run_id="focused-device")
    assert state.investigated_dimensions == ["lifecycle", "device"]
    assert [item.code for item in state.supported_hypotheses] == ["DEVICE_CONCENTRATION"]
    assert "focused pattern" in state.agent_steps[-1].decision_reason.lower()
    assert state.stop_reason == "SIGNAL_LOCALIZED"
    assert state.root_cause_confidence == "LOW"
    assert state.recommended_action_type == "EVIDENCE_COLLECTION"
