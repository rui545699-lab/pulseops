from __future__ import annotations

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.guard import GuardReason, GuardStatus, PolicyGuard
from pulseops.backend.agent.planner import PlannerProposal, SequencePlanner
from pulseops.backend.agent.state import AgentState
from tests.test_agent_router import DeviceFocusedTools, FixtureTools, WINDOWS


def proposal(action="INVESTIGATE", dimension=None, lifecycle_filter=None, rationale="bounded test"):
    return {
        "action": action,
        "dimension": dimension,
        "lifecycle_filter": lifecycle_filter,
        "rationale": rationale,
    }


def run_llm(outputs, *, tools=None, budget=4):
    return InvestigationAgent(
        tools or FixtureTools(),
        investigation_budget=budget,
        planner_mode="llm",
        planner=SequencePlanner(outputs),
    ).run(WINDOWS, run_id="llm-test")


def planning_steps(state):
    return [step for step in state.agent_steps if step.planner_mode is not None]


def test_deterministic_mode_regression_preserves_milestone_2_behavior():
    state = InvestigationAgent(FixtureTools()).run(WINDOWS, run_id="deterministic")
    assert state.investigated_dimensions == ["lifecycle", "device", "acquisition", "category"]
    assert state.stop_reason == "ALLOWED_DIMENSIONS_EXHAUSTED"
    assert all(step.planner_mode == "deterministic" for step in planning_steps(state))


def test_valid_llm_proposals_are_accepted_and_may_reorder_secondary_dimensions():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="acquisition", lifecycle_filter="new"),
            proposal(dimension="device", lifecycle_filter="new"),
            proposal(dimension="category", lifecycle_filter="new"),
        ]
    )
    assert state.investigated_dimensions == ["lifecycle", "acquisition", "device", "category"]
    assert all(step.guard_status == "ACCEPTED" for step in planning_steps(state))
    assert all(not step.fallback_used for step in planning_steps(state))


def test_browser_dimension_is_rejected_and_falls_back_to_lifecycle():
    state = run_llm([proposal(dimension="browser")])
    first = planning_steps(state)[0]
    assert first.planner_proposal["dimension"] == "browser"
    assert first.guard_status == "REJECTED"
    assert first.guard_reason == "DIMENSION_NOT_ALLOWED"
    assert first.fallback_used is True
    assert first.tool_input["dimension"] == "lifecycle"


def test_duplicate_dimension_is_rejected_and_next_legal_dimension_executes():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="lifecycle"),
        ]
    )
    second = planning_steps(state)[1]
    assert second.guard_reason == "DUPLICATE_DIMENSION"
    assert second.tool_input["dimension"] == "device"


def test_secondary_dimension_before_lifecycle_is_rejected():
    state = run_llm([proposal(dimension="device")])
    first = planning_steps(state)[0]
    assert first.guard_reason == "LIFECYCLE_REQUIRED"
    assert first.tool_input["dimension"] == "lifecycle"


def test_wrong_lifecycle_filter_is_rejected():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="device", lifecycle_filter="returning"),
        ]
    )
    second = planning_steps(state)[1]
    assert second.guard_reason == "FILTER_INCONSISTENT"
    assert second.tool_input["dimension"] == "device"
    assert second.tool_input["lifecycle_filter"] == "new"


def test_guard_rejects_investigation_when_budget_is_exhausted():
    state = AgentState(
        run_id="budget-guard",
        **WINDOWS.model_dump(),
        data_quality_status="PASS",
        detected_signal="View→Cart",
        remaining_investigation_budget=0,
    )
    result = PolicyGuard().validate(
        state,
        PlannerProposal(**proposal(dimension="lifecycle")),
    )
    assert result.status == GuardStatus.REJECTED
    assert result.reason == GuardReason.BUDGET_EXHAUSTED


def test_premature_stop_is_rejected_and_investigation_continues():
    state = run_llm([proposal(action="STOP", rationale="stop now")])
    first = planning_steps(state)[0]
    assert first.guard_reason == "PREMATURE_STOP"
    assert first.tool_input["dimension"] == "lifecycle"


def test_invalid_json_falls_back_to_deterministic_planner():
    state = run_llm(["{not-json"])
    first = planning_steps(state)[0]
    assert first.guard_status == "FALLBACK"
    assert first.fallback_reason == "INVALID_JSON"
    assert first.tool_input["dimension"] == "lifecycle"


def test_schema_invalid_proposal_falls_back_without_mutating_evidence():
    state = run_llm(
        [
            {
                "action": "INVESTIGATE",
                "dimension": "lifecycle",
                "rationale": "overwrite facts",
                "evidence": ["invented causal fact"],
            }
        ]
    )
    first = planning_steps(state)[0]
    assert first.fallback_reason == "SCHEMA_VALIDATION_FAILURE"
    assert "invented causal fact" not in state.evidence


def test_invalid_action_falls_back_to_deterministic_planner():
    state = run_llm([proposal(action="RUN_SQL", dimension="lifecycle")])
    first = planning_steps(state)[0]
    assert first.fallback_reason == "SCHEMA_VALIDATION_FAILURE"
    assert first.tool_input["dimension"] == "lifecycle"


def test_provider_exception_falls_back_to_deterministic_planner():
    state = run_llm([TimeoutError("provider timeout")])
    first = planning_steps(state)[0]
    assert first.guard_status == "FALLBACK"
    assert first.fallback_reason == "PROVIDER_ERROR:TimeoutError"
    assert first.tool_input["dimension"] == "lifecycle"


def test_missing_planner_configuration_falls_back_without_api_key():
    state = InvestigationAgent(FixtureTools(), planner_mode="llm", planner=None).run(WINDOWS)
    first = planning_steps(state)[0]
    assert first.fallback_reason == "NO_PLANNER_CONFIGURED"
    assert state.investigated_dimensions == ["lifecycle", "device", "acquisition", "category"]


def test_causal_planner_rationale_never_enters_evidence_or_confidence():
    claim = "Mobile UX caused the conversion decline."
    state = run_llm([proposal(dimension="lifecycle", rationale=claim)])
    assert claim not in state.evidence
    assert state.root_cause_confidence == "LOW"
    assert planning_steps(state)[0].planner_rationale == claim


def test_planner_receives_copy_and_cannot_mutate_tool_facts():
    class MutatingPlanner:
        def plan(self, state):
            state.evidence.append("forged metric fact")
            state.signal_confidence = "LOW"
            return proposal(dimension="lifecycle")

    state = InvestigationAgent(
        FixtureTools(), planner_mode="llm", planner=MutatingPlanner()
    ).run(WINDOWS)
    assert "forged metric fact" not in state.evidence
    assert state.signal_confidence == "HIGH"


def test_signal_localization_stops_broad_drilldown_without_claiming_root_cause():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="device", lifecycle_filter="new"),
        ],
        tools=DeviceFocusedTools(),
    )
    assert state.investigated_dimensions == ["lifecycle", "device"]
    assert state.stop_reason == "SIGNAL_LOCALIZED"
    assert state.root_cause_confidence == "LOW"
    assert state.recommended_action_type == "EVIDENCE_COLLECTION"


def test_case_01_llm_mode_retains_deterministic_final_assessment():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="category", lifecycle_filter="new"),
            proposal(dimension="acquisition", lifecycle_filter="new"),
            proposal(dimension="device", lifecycle_filter="new"),
        ]
    )
    assert state.signal_confidence == "HIGH"
    assert state.root_cause_confidence == "LOW"
    assert state.recommended_status == "NEEDS_EVIDENCE"
    assert state.recommended_action_type == "EVIDENCE_COLLECTION"


def test_llm_mode_never_duplicates_investigation():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="lifecycle"),
            proposal(dimension="device", lifecycle_filter="new"),
        ]
    )
    assert len(state.investigated_dimensions) == len(set(state.investigated_dimensions))


def test_llm_mode_respects_investigation_budget():
    state = run_llm(
        [
            proposal(dimension="lifecycle"),
            proposal(dimension="device", lifecycle_filter="new"),
            proposal(dimension="acquisition", lifecycle_filter="new"),
        ],
        budget=2,
    )
    assert state.investigated_dimensions == ["lifecycle", "device"]
    assert state.remaining_investigation_budget == 0
    assert state.stop_reason == "BUDGET_EXHAUSTED"


def test_final_output_contains_no_unsupported_causal_statement():
    state = run_llm(
        [proposal(dimension="lifecycle", rationale="Pricing caused the decline.")]
    )
    final_text = " ".join(state.evidence + state.hypotheses + state.unknowns).lower()
    assert "caused the decline" not in final_text
    assert all("unverified" in item.lower() for item in state.hypotheses)
