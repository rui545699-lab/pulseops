from __future__ import annotations

import pytest

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.guard import GuardReason, GuardStatus, PolicyGuard
from pulseops.backend.agent.planner import PlannerProposal, SequencePlanner
from pulseops.backend.agent.state import AgentState, InvestigationProfile
from pulseops.backend.fixtures.growth import CASE_03, Case03GoldenTools
from pulseops.backend.persistence.service import RunService
from pulseops.backend.schemas.analytics import GrowthComparison, GrowthPeriodResult, GrowthWindows


WINDOWS = GrowthWindows.model_validate(CASE_03["windows"])


def proposal(action="INVESTIGATE", dimension=None, rationale="bounded observational growth check"):
    return {
        "action": action,
        "dimension": dimension,
        "lifecycle_filter": None,
        "rationale": rationale,
    }


def run_case(*, planner=None, tools=None, investigation_budget=4):
    return InvestigationAgent(
        tools or Case03GoldenTools(),
        investigation_budget=investigation_budget,
        planner_mode="llm" if planner else "deterministic",
        planner=planner,
    ).run(WINDOWS, run_id="case-03", investigation_profile="POSITIVE_GROWTH")


def planning_steps(state):
    return [step for step in state.agent_steps if step.planner_mode is not None]


def test_case_03_runs_deterministic_preflight_before_planned_dimensions():
    state = run_case()
    assert [step.node for step in state.agent_steps[:5]] == [
        "VALIDATE_DATA", "ANALYZE_GROWTH", "CHECK_WEEKLY_PERSISTENCE",
        "CHECK_CONFIRMATION", "CHECK_HOLDOUT",
    ]
    assert state.investigated_dimensions == ["lifecycle", "device", "acquisition"]


def test_case_03_golden_result_is_ready_for_bounded_replication():
    state = run_case()
    assert state.growth_result is not None
    assert state.growth_result.baseline.conversion_rate == 40.35
    assert state.growth_result.growth.conversion_rate == 51.14
    assert state.growth_result.delta_pp == 10.78
    assert state.growth_result.confirmation.conversion_rate == 55.07
    assert state.growth_result.holdout_1.conversion_rate == 48.74
    assert state.growth_result.holdout_2.conversion_rate == 55.13
    assert state.growth_signal_confidence == "HIGH"
    assert state.reproducibility == "REPRODUCED"
    assert state.reproducibility_confidence == "HIGH"
    assert state.root_cause_confidence == "LOW"
    assert state.recommended_status == "READY_FOR_REPLICATION_TEST"
    assert state.recommended_action_type == "REPLICATION_TEST"
    assert state.stop_reason == "ALLOWED_DIMENSIONS_EXHAUSTED"
    assert state.order_value_context is not None
    assert state.order_value_context.growth_average_order_value_usd == 71.07
    assert state.growth_segment_results["lifecycle"].within_segment_effect_pp == 7.33
    assert state.growth_segment_results["device"].within_segment_effect_pp == 10.80
    assert state.growth_segment_results["acquisition"].within_segment_effect_pp == 10.13
    evidence = " ".join(state.evidence)
    assert "Both Growth weeks improved" in evidence
    assert "Both Confirmation weeks remained above" in evidence
    assert "Holdout periods measured 48.74% and 55.13%" in evidence
    assert "Average order value did not show an obvious collapse" in evidence
    assert all("causes" not in item.lower() for item in state.evidence + state.hypotheses)


def test_growth_planner_may_select_a_legal_non_default_order():
    state = run_case(planner=SequencePlanner([
        proposal(dimension="device"), proposal(dimension="acquisition"), proposal(dimension="lifecycle"),
    ]))
    assert state.investigated_dimensions == ["device", "acquisition", "lifecycle"]
    assert all(step.guard_status == "ACCEPTED" for step in planning_steps(state))


class MixedLocalizationTools(Case03GoldenTools):
    localizations = {
        "lifecycle": "SEGMENT_CONCENTRATED",
        "device": "MIX_DRIVEN",
        "acquisition": "BROAD",
    }

    def compare_growth_segments(self, dimension, windows):
        result = super().compare_growth_segments(dimension, windows)
        return result.model_copy(update={"localization": self.localizations[dimension]})


@pytest.mark.parametrize(
    "dimensions",
    [
        ["lifecycle", "device", "acquisition"],
        ["device", "acquisition", "lifecycle"],
        ["acquisition", "lifecycle", "device"],
    ],
)
def test_growth_localization_is_independent_of_legal_planner_order(dimensions):
    state = run_case(
        tools=MixedLocalizationTools(),
        planner=SequencePlanner([proposal(dimension=dimension) for dimension in dimensions]),
    )
    assert state.investigated_dimensions == dimensions
    assert state.growth_localization == "MIXED"


def test_growth_guard_rejects_filter_duplicate_premature_stop_and_broad_scale():
    unsupported = run_case(planner=SequencePlanner([proposal(dimension="category")]))
    assert planning_steps(unsupported)[0].guard_reason == "DIMENSION_NOT_ALLOWED"

    invalid_filter = run_case(planner=SequencePlanner([proposal(dimension="device") | {"lifecycle_filter": "new"}]))
    assert planning_steps(invalid_filter)[0].guard_reason == "FILTER_INCONSISTENT"

    duplicate = run_case(planner=SequencePlanner([proposal(dimension="device"), proposal(dimension="device")]))
    assert planning_steps(duplicate)[1].guard_reason == "DUPLICATE_DIMENSION"

    premature = run_case(planner=SequencePlanner([proposal(action="STOP")]))
    assert planning_steps(premature)[0].guard_reason == "PREMATURE_STOP"

    scaled = run_case(planner=SequencePlanner([proposal(dimension="device", rationale="Scale to all users now.")]))
    assert planning_steps(scaled)[0].guard_reason == "INTERVENTION_NOT_ALLOWED"

    causal = run_case(planner=SequencePlanner([proposal(dimension="device", rationale="Device causes the observed lift.")]))
    assert planning_steps(causal)[0].guard_reason == "UNSUPPORTED_CAUSAL_CLAIM"


@pytest.mark.parametrize(
    "rationale",
    [
        "Scale broadly now.",
        "Scale this broadly now.",
        "Rollout to everyone now.",
        "Roll out to everyone now.",
        "Increase spend now.",
        "Increase budget now.",
        "Expand to all users now.",
        "Expand across all users now.",
        "Scale to all users now.",
        "Copy to all segments now.",
        "Deploy globally now.",
        "Roll out globally now.",
        "SCALE_TO_ALL_USERS",
        "ROLL_OUT_GLOBALLY",
        "INCREASE_BUDGET",
        "BROAD_CAMPAIGN_SCALE",
        "COPY_TO_ALL_SEGMENTS",
    ],
)
def test_growth_guard_rejects_broad_scale_recommendation_variants(rationale):
    state = AgentState(
        run_id="growth-guard", **WINDOWS.model_dump(),
        investigation_profile=InvestigationProfile.POSITIVE_GROWTH,
        data_quality_status="PASS", detected_signal="Checkout→Purchase",
    )
    result = PolicyGuard().validate(
        state, PlannerProposal(**proposal(dimension="lifecycle", rationale=rationale))
    )
    assert result.status == GuardStatus.REJECTED
    assert result.reason == GuardReason.INTERVENTION_NOT_ALLOWED


@pytest.mark.parametrize(
    "rationale",
    ["Measure the scale of the observed growth.", "Evaluate expansion patterns by device."],
)
def test_growth_guard_allows_non_recommendation_scale_language(rationale):
    state = AgentState(
        run_id="growth-guard-benign", **WINDOWS.model_dump(),
        investigation_profile=InvestigationProfile.POSITIVE_GROWTH,
        data_quality_status="PASS", detected_signal="Checkout→Purchase",
    )
    assert PolicyGuard().validate(
        state, PlannerProposal(**proposal(dimension="lifecycle", rationale=rationale))
    ).status == GuardStatus.ACCEPTED


def test_growth_provider_failure_uses_deterministic_fallback():
    state = run_case(planner=SequencePlanner([TimeoutError("provider timeout")]))
    first = planning_steps(state)[0]
    assert first.guard_status == "FALLBACK"
    assert first.fallback_reason == "PROVIDER_ERROR:TimeoutError"
    assert first.tool_input["dimension"] == "lifecycle"


def test_growth_guard_only_allows_stop_after_every_registered_dimension():
    state = AgentState(
        run_id="growth-stop", **WINDOWS.model_dump(),
        investigation_profile=InvestigationProfile.POSITIVE_GROWTH,
        data_quality_status="PASS", detected_signal="Checkout→Purchase",
    )
    result = PolicyGuard().validate(state, PlannerProposal(**proposal(action="STOP", rationale="mechanism remains unknown")))
    assert result.status == GuardStatus.REJECTED
    assert result.reason == GuardReason.PREMATURE_STOP
    state.investigated_dimensions = ["lifecycle", "device", "acquisition"]
    assert PolicyGuard().validate(state, PlannerProposal(**proposal(action="STOP", rationale="mechanism remains unknown"))).status == GuardStatus.ACCEPTED


class NoGrowthTools(Case03GoldenTools):
    def analyze_growth(self, windows):
        value = super().analyze_growth(windows)
        unchanged = GrowthPeriodResult(
            checkout_sessions=value.growth.checkout_sessions,
            purchase_after_checkout_sessions=round(value.growth.checkout_sessions * value.baseline.conversion_rate / 100),
            conversion_rate=value.baseline.conversion_rate,
        )
        return value.model_copy(update={"growth": unchanged, "delta_pp": 0.0})


def test_stable_growth_metric_creates_no_opportunity():
    state = InvestigationAgent(NoGrowthTools()).run(WINDOWS, run_id="no-growth", investigation_profile="POSITIVE_GROWTH")
    assert state.stop_reason == "NO_SIGNIFICANT_SIGNAL"
    assert state.detected_signal is None
    assert RunService._opportunity_from_state(state) is None


def test_growth_planner_cannot_overwrite_deterministic_facts():
    state = run_case(planner=SequencePlanner([
        proposal(dimension="lifecycle") | {
            "growth_rate": 99.0, "reproducibility": "NOT_REPRODUCED", "signal_confidence": "LOW"
        }
    ]))
    first = planning_steps(state)[0]
    assert first.fallback_reason == "SCHEMA_VALIDATION_FAILURE"
    assert state.growth_result is not None and state.growth_result.growth.conversion_rate == 51.14
    assert state.reproducibility == "REPRODUCED"
    assert state.growth_signal_confidence == "HIGH"


def test_growth_budget_exhaustion_has_a_budget_stop_reason_and_copy():
    state = run_case(investigation_budget=1)
    assert state.stop_reason == "BUDGET_EXHAUSTED"
    assert state.agent_steps[-1].node == "STOP_DRILLDOWN"
    assert state.agent_steps[-1].decision_reason == (
        "Investigation budget exhausted while permitted dimensions remain uninvestigated."
    )


class UnavailableAOVTools(Case03GoldenTools):
    def analyze_order_value(self, windows):
        raise RuntimeError("AOV unavailable")


def test_growth_continues_when_aov_context_is_unavailable():
    state = run_case(tools=UnavailableAOVTools())
    assert state.order_value_context is None
    assert "Order-value context was unavailable for this bounded investigation." in state.unknowns
    assert state.recommended_action_type == "REPLICATION_TEST"
    assert "Whether the observed lift can be intentionally recreated remains unknown." in state.unknowns
