from __future__ import annotations

from datetime import datetime, timezone
from inspect import signature
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from pulseops.backend.agent.state import AgentState
from pulseops.backend.persistence.models import AnalysisRun, AgentStep, Opportunity
from pulseops.backend.persistence.runner import AnalysisRunner
from pulseops.backend.schemas.analytics import DateWindows


def _value(value):
    return value.value if hasattr(value, "value") else value


class RunService:
    def __init__(self, sessions: sessionmaker[Session], runner: AnalysisRunner) -> None:
        self.sessions = sessions
        self.runner = runner

    def execute(
        self,
        windows: DateWindows,
        planner_mode: str,
        analysis_type: str = "CONVERSION",
    ) -> AnalysisRun:
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        if "analysis_type" in signature(self.runner.run).parameters:
            execution = self.runner.run(windows, planner_mode, run_id, analysis_type)
        else:  # Backward-compatible adapter boundary for existing local runners.
            execution = self.runner.run(windows, planner_mode, run_id)
        completed_at = datetime.now(timezone.utc)

        run = self._run_from_state(
            execution.state,
            planner_mode,
            execution.provider,
            execution.model_identifier,
            started_at,
            completed_at,
        )
        with self.sessions() as session, session.begin():
            session.add(run)
            session.add_all(self._steps_from_state(execution.state))
            opportunity = self._opportunity_from_state(execution.state)
            if opportunity is not None:
                session.add(opportunity)
        return self.get_run(run_id)

    def list_runs(self) -> list[AnalysisRun]:
        with self.sessions() as session:
            return list(session.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc())))

    def get_run(self, run_id: str) -> AnalysisRun | None:
        with self.sessions() as session:
            statement = (
                select(AnalysisRun)
                .where(AnalysisRun.id == run_id)
                .options(selectinload(AnalysisRun.steps), selectinload(AnalysisRun.opportunity))
            )
            return session.scalar(statement)

    def get_steps(self, run_id: str) -> list[AgentStep] | None:
        with self.sessions() as session:
            if session.get(AnalysisRun, run_id) is None:
                return None
            statement = (
                select(AgentStep)
                .where(AgentStep.run_id == run_id)
                .order_by(AgentStep.step_order)
            )
            return list(session.scalars(statement))

    def list_opportunities(self) -> list[Opportunity]:
        with self.sessions() as session:
            return list(session.scalars(select(Opportunity).order_by(Opportunity.created_at.desc())))

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        with self.sessions() as session:
            return session.get(Opportunity, opportunity_id)

    @staticmethod
    def _run_from_state(
        state: AgentState,
        planner_mode: str,
        provider: str | None,
        model_identifier: str | None,
        started_at: datetime,
        completed_at: datetime,
    ) -> AnalysisRun:
        funnel = state.funnel_result
        retention = state.retention_result
        growth = state.growth_result
        recovery = state.recovery_result
        if retention is not None:
            overall_baseline_rate = retention.baseline.return_rate_7d
            overall_target_rate = retention.target.return_rate_7d
            overall_delta_pp = retention.delta_pp
        elif growth is not None:
            overall_baseline_rate = growth.baseline.conversion_rate
            overall_target_rate = growth.growth.conversion_rate
            overall_delta_pp = growth.delta_pp
        else:
            overall_baseline_rate = funnel.baseline.session_conversion_rate if funnel else None
            overall_target_rate = funnel.target.session_conversion_rate if funnel else None
            overall_delta_pp = funnel.session_delta_pp if funnel else None
        return AnalysisRun(
            id=state.run_id,
            analysis_type=_value(state.investigation_profile),
            baseline_start=state.baseline_start,
            baseline_end=state.baseline_end,
            target_start=state.target_start,
            target_end=state.target_end,
            post_start=state.post_start,
            post_end=state.post_end,
            confirmation_start=state.confirmation_start,
            confirmation_end=state.confirmation_end,
            holdout_1_start=state.holdout_1_start,
            holdout_1_end=state.holdout_1_end,
            holdout_2_start=state.holdout_2_start,
            holdout_2_end=state.holdout_2_end,
            planner_mode=planner_mode,
            provider=provider,
            model_identifier=model_identifier,
            detected_signal=state.detected_signal,
            overall_baseline_rate=overall_baseline_rate,
            overall_target_rate=overall_target_rate,
            overall_delta_pp=overall_delta_pp,
            post_rate=(retention.post.return_rate_7d if retention else None),
            target_to_post_delta_pp=(retention.target_to_post_delta_pp if retention else None),
            baseline_to_post_delta_pp=(retention.baseline_to_post_delta_pp if retention else None),
            recovery_ratio=(recovery.recovery_ratio_pct if recovery else None),
            risk_pattern=(_value(recovery.risk_pattern) if recovery else None),
            return_timing=(
                state.return_timing_result.model_dump(mode="json")
                if state.return_timing_result else None
            ),
            growth_analysis=(growth.model_dump(mode="json") if growth else None),
            reproducibility=_value(state.reproducibility),
            growth_signal_confidence=_value(state.growth_signal_confidence),
            reproducibility_confidence=_value(state.reproducibility_confidence),
            growth_localization=state.growth_localization,
            affected_segment=state.affected_segment,
            signal_confidence=_value(state.signal_confidence),
            root_cause_confidence=_value(state.root_cause_confidence),
            stop_reason=_value(state.stop_reason),
            recommended_status=_value(state.recommended_status),
            recommended_action_type=_value(state.recommended_action_type),
            status="COMPLETED",
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _steps_from_state(state: AgentState) -> list[AgentStep]:
        rows = []
        for step in state.agent_steps:
            data = step.model_dump(mode="json")
            rows.append(
                AgentStep(
                    id=str(uuid4()),
                    run_id=state.run_id,
                    step_order=data["step_order"],
                    node=data["node"],
                    tool_name=data["tool_name"],
                    planner_proposal=data["planner_proposal"],
                    planner_rationale=data["planner_rationale"],
                    guard_status=data["guard_status"],
                    guard_reason=data["guard_reason"],
                    tool_input=data["tool_input"],
                    tool_output_summary=data["tool_output_summary"],
                    decision=data["decision"],
                    decision_reason=data["decision_reason"],
                    hypothesis=data["hypothesis"],
                    hypothesis_status=data["hypothesis_status"],
                    remaining_budget=data["remaining_budget"],
                    fallback_used=data["fallback_used"],
                    fallback_reason=data["fallback_reason"],
                )
            )
        return rows

    @staticmethod
    def _opportunity_from_state(state: AgentState) -> Opportunity | None:
        if state.detected_signal is None or (
            state.funnel_result is None
            and state.retention_result is None
            and state.growth_result is None
        ):
            return None
        baseline_rate, target_rate, delta_pp = _opportunity_rates(state)
        lifecycle = state.retention_result is not None
        positive_growth = state.growth_result is not None
        recovery = state.recovery_result
        hypothesis_records = [
            item.model_dump(mode="json")
            for item in (
                state.rejected_hypotheses
                + state.supported_hypotheses
                + state.insufficient_hypotheses
            )
        ]
        return Opportunity(
            id=str(uuid4()),
            run_id=state.run_id,
            title=(
                _lifecycle_opportunity_title(_value(recovery.risk_pattern) if recovery else None)
                if lifecycle
                else _positive_growth_opportunity_title(state.growth_localization)
                if positive_growth
                else f"{state.detected_signal} decline for {state.affected_segment or 'all users'}"
            ),
            opportunity_type=state.opportunity_type,
            affected_segment=state.affected_segment,
            metric=state.detected_signal,
            baseline_rate=baseline_rate,
            target_rate=target_rate,
            delta_pp=delta_pp,
            post_rate=(state.retention_result.post.return_rate_7d if lifecycle else None),
            target_to_post_delta_pp=(
                state.retention_result.target_to_post_delta_pp if lifecycle else None
            ),
            baseline_to_post_delta_pp=(
                state.retention_result.baseline_to_post_delta_pp if lifecycle else None
            ),
            recovery_ratio=(recovery.recovery_ratio_pct if recovery else None),
            risk_pattern=(_value(recovery.risk_pattern) if recovery else None),
            return_timing=(
                state.return_timing_result.model_dump(mode="json")
                if state.return_timing_result else None
            ),
            baseline_period=(
                state.growth_result.baseline.model_dump(mode="json")
                if positive_growth else None
            ),
            growth_period=(
                state.growth_result.growth.model_dump(mode="json") if positive_growth else None
            ),
            confirmation_period=(
                state.growth_result.confirmation.model_dump(mode="json") if positive_growth else None
            ),
            holdout_results=(
                {
                    "holdout_1": state.growth_result.holdout_1.model_dump(mode="json"),
                    "holdout_2": state.growth_result.holdout_2.model_dump(mode="json"),
                }
                if positive_growth else None
            ),
            reproducibility=_value(state.reproducibility),
            growth_signal_confidence=_value(state.growth_signal_confidence),
            reproducibility_confidence=_value(state.reproducibility_confidence),
            growth_localization=state.growth_localization,
            order_value_context=(
                state.order_value_context.model_dump(mode="json")
                if state.order_value_context else None
            ),
            segment_analysis=(
                {
                    name: result.model_dump(mode="json")
                    for name, result in state.lifecycle_segment_results.items()
                }
                if lifecycle else {
                    name: result.model_dump(mode="json")
                    for name, result in state.growth_segment_results.items()
                }
                if positive_growth else None
            ),
            hypothesis_records=hypothesis_records or None,
            signal_confidence=_value(state.signal_confidence),
            root_cause_confidence=_value(state.root_cause_confidence),
            evidence=list(state.evidence),
            hypotheses=list(state.hypotheses),
            unknowns=list(state.unknowns),
            recommended_status=_value(state.recommended_status),
            recommended_action_type=_value(state.recommended_action_type),
            recommended_next_action=state.recommended_next_action,
            do_not_recommend_yet=list(state.do_not_recommend_yet),
            status=_value(state.recommended_status),
        )


def _opportunity_rates(state: AgentState) -> tuple[float, float, float]:
    """Use localized lifecycle rates when the Agent identified an affected segment."""
    if state.retention_result is not None:
        return (
            state.retention_result.baseline.return_rate_7d,
            state.retention_result.target.return_rate_7d,
            state.retention_result.delta_pp,
        )

    if state.growth_result is not None:
        return (
            state.growth_result.baseline.conversion_rate,
            state.growth_result.growth.conversion_rate,
            state.growth_result.delta_pp,
        )

    lifecycle_segment = {
        "new_users": "new",
        "returning_users": "returning",
    }.get(state.affected_segment)
    lifecycle = state.segment_results.get("lifecycle")
    if lifecycle_segment is not None and lifecycle is not None:
        for segment in lifecycle.segments:
            if (
                segment.segment == lifecycle_segment
                and segment.sample_sufficient
                and segment.baseline_rate is not None
                and segment.target_rate is not None
                and segment.change_pp is not None
            ):
                return segment.baseline_rate, segment.target_rate, segment.change_pp

    funnel = state.funnel_result
    if funnel is None:  # guarded by the opportunity creation condition
        raise ValueError("material signal opportunity requires a funnel result")
    return (
        funnel.baseline.session_conversion_rate,
        funnel.target.session_conversion_rate,
        funnel.session_delta_pp,
    )


def _lifecycle_opportunity_title(risk_pattern: str | None) -> str:
    if risk_pattern is None:
        return "New-user 7-day return risk"
    recovery = risk_pattern.lower().replace("_", " ")
    if recovery == "no recovery":
        recovery = "no observed recovery"
    return f"New-user 7-day return risk with {recovery}"


def _positive_growth_opportunity_title(localization: str | None) -> str:
    titles = {
        "BROAD": "Broad Checkout→Purchase lift ready for replication test",
        "SEGMENT_CONCENTRATED": "Segment-concentrated Checkout→Purchase lift ready for replication test",
        "MIX_DRIVEN": "Mix-driven Checkout→Purchase lift ready for replication test",
        "MIXED": "Mixed Checkout→Purchase lift ready for replication test",
    }
    return titles.get(localization or "", "Checkout→Purchase Growth Opportunity")
