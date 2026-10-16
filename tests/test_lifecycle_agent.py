from __future__ import annotations

import pytest

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.guard import GuardReason, GuardStatus, PolicyGuard
from pulseops.backend.agent.planner import PlannerProposal, SequencePlanner
from pulseops.backend.agent.state import AgentState, InvestigationProfile
from pulseops.backend.analytics.lifecycle import classify_recovery
from pulseops.backend.fixtures.lifecycle import CASE_02, Case02GoldenTools
from pulseops.backend.persistence.service import RunService
from pulseops.backend.schemas.analytics import (
    LifecycleWindows,
    RetentionComparison,
    RetentionPeriodResult,
)


WINDOWS = LifecycleWindows.model_validate(CASE_02["windows"])


def proposal(action="INVESTIGATE", dimension=None, rationale="bounded lifecycle check"):
    return {
        "action": action,
        "dimension": dimension,
        "lifecycle_filter": None,
        "rationale": rationale,
    }


def run_case(*, planner=None):
    return InvestigationAgent(
        Case02GoldenTools(),
        planner_mode="llm" if planner else "deterministic",
        planner=planner,
    ).run(
        WINDOWS,
        run_id="case-02",
        investigation_profile="LIFECYCLE_RISK",
    )


def planning_steps(state):
    return [step for step in state.agent_steps if step.planner_mode is not None]


def retention(rate_baseline: float, rate_target: float, rate_post: float) -> RetentionComparison:
    def period(rate: float) -> RetentionPeriodResult:
        users = 20_000
        return RetentionPeriodResult(
            eligible_new_users=users,
            returned_users_7d=round(users * rate / 100),
            return_rate_7d=rate,
        )

    baseline, target, post = period(rate_baseline), period(rate_target), period(rate_post)
    return RetentionComparison(
        baseline=baseline,
        target=target,
        post=post,
        delta_pp=round(rate_target - rate_baseline, 2),
        relative_change_pct=round(100 * (rate_target - rate_baseline) / rate_baseline, 2) if rate_baseline else None,
        target_to_post_delta_pp=round(rate_post - rate_target, 2),
        baseline_to_post_delta_pp=round(rate_post - rate_baseline, 2),
    )


class RetentionVariantTools(Case02GoldenTools):
    def __init__(self, value: RetentionComparison):
        super().__init__()
        self.value = value

    def analyze_retention(self, windows):
        self.calls.append(("analyze_retention",))
        return self.value

    def analyze_recovery(self, windows, retention_result):
        self.calls.append(("analyze_recovery",))
        return classify_recovery(
            retention_result.baseline,
            retention_result.target,
            retention_result.post,
        )


def run_variant(value: RetentionComparison):
    return InvestigationAgent(RetentionVariantTools(value)).run(
        WINDOWS,
        run_id="lifecycle-variant",
        investigation_profile="LIFECYCLE_RISK",
    )


def test_case_02_runs_fixed_preflight_before_planned_dimensions():
    state = run_case()
    assert [step.node for step in state.agent_steps[:4]] == [
        "VALIDATE_DATA",
        "ANALYZE_RETENTION",
        "CHECK_RETURN_TIMING",
        "CHECK_RECOVERY",
    ]
    assert state.investigated_dimensions == ["acquisition", "device", "activation_depth"]


def test_case_02_golden_result_preserves_evidence_boundary():
    state = run_case()
    assert state.retention_result.delta_pp == -3.22
    assert state.recovery_result.risk_pattern == "PARTIAL_RECOVERY"
    assert state.signal_confidence == "HIGH"
    assert state.root_cause_confidence == "LOW"
    assert state.recommended_status == "NEEDS_EVIDENCE"
    assert state.recommended_action_type == "EVIDENCE_COLLECTION"
    assert state.stop_reason == "ALLOWED_DIMENSIONS_EXHAUSTED"
    rendered = " ".join(state.evidence + state.hypotheses + state.unknowns).lower()
    assert all(term not in rendered for term in ("post-holiday", "christmas", "new year", "holiday"))


def test_case_02_hypotheses_have_expected_statuses():
    state = run_case()
    assert {item.code for item in state.rejected_hypotheses} == {
        "ACQUISITION_MIX_EXPLANATION",
        "DEVICE_CONCENTRATION",
    }
    assert {item.code for item in state.supported_hypotheses} == {"ACTIVATION_DEPTH_SHIFT"}


def test_lifecycle_guard_rejects_unsupported_dimension_and_falls_back():
    state = run_case(planner=SequencePlanner([proposal(dimension="category")]))
    first = planning_steps(state)[0]
    assert first.guard_reason == "DIMENSION_NOT_ALLOWED"
    assert first.tool_input["dimension"] == "acquisition"


def test_lifecycle_guard_rejects_duplicate_proposal():
    state = run_case(
        planner=SequencePlanner([
            proposal(dimension="acquisition"),
            proposal(dimension="acquisition"),
        ])
    )
    second = planning_steps(state)[1]
    assert second.guard_reason == "DUPLICATE_DIMENSION"
    assert second.tool_input["dimension"] == "device"


def test_lifecycle_guard_accepts_null_filter_and_rejects_new_filter():
    accepted = run_case(planner=SequencePlanner([proposal(dimension="device")]))
    assert planning_steps(accepted)[0].guard_reason == "ACCEPTED"

    rejected = run_case(
        planner=SequencePlanner([
            {**proposal(dimension="device"), "lifecycle_filter": "new"},
        ])
    )
    first = planning_steps(rejected)[0]
    assert first.guard_reason == "FILTER_INCONSISTENT"
    assert first.tool_input["dimension"] == "acquisition"


def test_lifecycle_stop_requires_no_remaining_legal_dimension_even_with_low_confidence():
    state = AgentState(
        run_id="lifecycle-stop",
        **WINDOWS.model_dump(),
        investigation_profile=InvestigationProfile.LIFECYCLE_RISK,
        data_quality_status="PASS",
        detected_signal="New-user 7-day Return Rate",
    )
    result = PolicyGuard().validate(
        state,
        PlannerProposal(**proposal(action="STOP", rationale="root cause remains unknown")),
    )
    assert result.status == GuardStatus.REJECTED
    assert result.reason == GuardReason.PREMATURE_STOP

    state.investigated_dimensions = ["acquisition", "device", "activation_depth"]
    allowed = PolicyGuard().validate(
        state,
        PlannerProposal(**proposal(action="STOP", rationale="root cause remains unknown")),
    )
    assert allowed.status == GuardStatus.ACCEPTED
    assert allowed.reason == GuardReason.STOP_ALLOWED


def test_lifecycle_guard_rejects_premature_stop_and_causal_claim():
    premature = run_case(planner=SequencePlanner([proposal(action="STOP")]))
    assert planning_steps(premature)[0].guard_reason == "PREMATURE_STOP"
    causal = run_case(
        planner=SequencePlanner([
            proposal(dimension="acquisition", rationale="Calendar timing caused the decline.")
        ])
    )
    assert planning_steps(causal)[0].guard_reason == "UNSUPPORTED_CAUSAL_CLAIM"
    assert causal.root_cause_confidence == "LOW"


def test_lifecycle_guard_allows_cautious_root_cause_wording_but_rejects_affirmative_claim():
    cautious = run_case(
        planner=SequencePlanner([
            proposal(dimension="acquisition", rationale="The root cause remains unknown."),
        ])
    )
    assert planning_steps(cautious)[0].guard_reason == "ACCEPTED"

    causal = run_case(
        planner=SequencePlanner([
            proposal(dimension="acquisition", rationale="Device causes the decline."),
        ])
    )
    assert planning_steps(causal)[0].guard_reason == "UNSUPPORTED_CAUSAL_CLAIM"


def test_lifecycle_provider_failure_uses_deterministic_fallback():
    state = run_case(planner=SequencePlanner([TimeoutError("provider timeout")]))
    first = planning_steps(state)[0]
    assert first.guard_status == "FALLBACK"
    assert first.fallback_reason == "PROVIDER_ERROR:TimeoutError"
    assert first.tool_input["dimension"] == "acquisition"


def test_lifecycle_planner_cannot_change_metrics_confidence_or_risk_pattern():
    state = run_case(
        planner=SequencePlanner([
            {
                **proposal(dimension="acquisition"),
                "delta_pp": 4.0,
                "signal_confidence": "LOW",
                "risk_pattern": "FULL_RECOVERY",
            }
        ])
    )
    first = planning_steps(state)[0]
    assert first.fallback_reason == "SCHEMA_VALIDATION_FAILURE"
    assert state.retention_result.delta_pp == -3.22
    assert state.signal_confidence == "HIGH"
    assert state.recovery_result.risk_pattern == "PARTIAL_RECOVERY"


def test_lifecycle_guard_rejects_direct_intervention_recommendation():
    state = run_case(
        planner=SequencePlanner([
            proposal(dimension="activation_depth", rationale="Launch a coupon blast now.")
        ])
    )
    assert planning_steps(state)[0].guard_reason == "INTERVENTION_NOT_ALLOWED"
    assert state.recommended_action_type == "EVIDENCE_COLLECTION"


@pytest.mark.parametrize(
    ("rationale", "reason"),
    [
        ("Activation depth causes the decline.", "UNSUPPORTED_CAUSAL_CLAIM"),
        ("Activation depth drives the decline.", "UNSUPPORTED_CAUSAL_CLAIM"),
        ("Offer discounts now.", "INTERVENTION_NOT_ALLOWED"),
        ("Send push notifications now.", "INTERVENTION_NOT_ALLOWED"),
        ("Launch promotion now.", "INTERVENTION_NOT_ALLOWED"),
    ],
)
def test_lifecycle_guard_rejects_obvious_causal_and_intervention_variants(rationale, reason):
    state = run_case(
        planner=SequencePlanner([proposal(dimension="acquisition", rationale=rationale)])
    )
    assert planning_steps(state)[0].guard_reason == reason


def test_lifecycle_planner_can_execute_a_legal_non_default_order_without_fallback():
    state = run_case(
        planner=SequencePlanner(
            [
                proposal(dimension="device"),
                proposal(dimension="activation_depth"),
                proposal(dimension="acquisition"),
            ]
        )
    )
    planned = planning_steps(state)
    assert state.investigated_dimensions == ["device", "activation_depth", "acquisition"]
    assert all(step.guard_reason == "ACCEPTED" for step in planned)
    assert not any(step.fallback_used for step in planned)


@pytest.mark.parametrize("rates", [(8.0, 8.0, 8.0), (8.0, 9.0, 9.0)])
def test_stable_or_improving_retention_creates_no_lifecycle_opportunity(rates):
    state = run_variant(retention(*rates))
    assert state.stop_reason == "NO_SIGNIFICANT_SIGNAL"
    assert state.detected_signal is None
    assert state.investigated_dimensions == []
    assert RunService._opportunity_from_state(state) is None


def test_insufficient_lifecycle_cohorts_stop_as_data_quality_failure():
    value = retention(8.0, 4.0, 6.0).model_copy(
        update={
            "baseline": RetentionPeriodResult(
                eligible_new_users=99,
                returned_users_7d=8,
                return_rate_7d=8.08,
            )
        }
    )
    state = run_variant(value)
    assert state.stop_reason == "DATA_QUALITY_FAIL"
    assert state.detected_signal is None
    assert RunService._opportunity_from_state(state) is None


@pytest.mark.parametrize(
    ("post_rate", "expected_title"),
    [
        (5.0, "New-user 7-day return risk with no observed recovery"),
        (8.3, "New-user 7-day return risk with full recovery"),
    ],
)
def test_lifecycle_opportunity_title_is_derived_from_recovery_pattern(post_rate, expected_title):
    state = run_variant(retention(8.33, 5.11, post_rate))
    opportunity = RunService._opportunity_from_state(state)
    assert opportunity is not None
    assert opportunity.title == expected_title


def test_lifecycle_budget_is_bounded():
    state = InvestigationAgent(
        Case02GoldenTools(), investigation_budget=2
    ).run(
        WINDOWS,
        run_id="case-02-budget",
        investigation_profile="LIFECYCLE_RISK",
    )
    assert state.investigated_dimensions == ["acquisition", "device"]
    assert state.remaining_investigation_budget == 0
    assert state.stop_reason == "BUDGET_EXHAUSTED"
    assert state.agent_steps[-1].decision_reason == "Investigation budget exhausted while permitted dimensions remain uninvestigated."
