from __future__ import annotations

from json import JSONDecodeError
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from pulseops.backend.agent.guard import GuardStatus, PolicyGuard
from pulseops.backend.agent.planner import (
    DeterministicPlanner,
    PlannerAction,
    PlannerMode,
    PlannerProposal,
    PlannerProtocol,
    parse_planner_output,
)
from pulseops.backend.agent.policies import (
    apply_lifecycle_segment_policy,
    apply_segment_policy,
    finalize_lifecycle_needs_evidence,
    finalize_needs_evidence,
    select_signal,
    set_signal_confidence,
)
from pulseops.backend.agent.router import (
    ALLOWED_DIMENSIONS,
    allowed_dimensions,
    continuation_reason,
    next_dimension,
)
from pulseops.backend.agent.state import (
    AgentState,
    AgentStep,
    InvestigationProfile,
    RecommendedActionType,
    StopReason,
)
from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.lifecycle import (
    describe_return_timing,
    has_material_negative_retention,
    retention_data_is_sufficient,
)
from pulseops.backend.analytics.queries.metrics import FUNNEL_PAIRS
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    Confidence,
    DateWindows,
    FunnelComparison,
    MetricsScanResult,
    RecommendedStatus,
    SegmentComparison,
    ValidationResult,
    LifecycleSegmentComparison,
    LifecycleWindows,
    RecoveryAnalysis,
    RetentionComparison,
    RiskPattern,
    ReturnTimingAnalysis,
)
from pulseops.backend.tools.analyze_funnel import analyze_funnel
from pulseops.backend.tools.compare_segments import compare_segments
from pulseops.backend.tools.scan_metrics import scan_metrics
from pulseops.backend.tools.validate_data import validate_data
from pulseops.backend.tools.lifecycle import (
    analyze_recovery as analyze_lifecycle_recovery,
    compare_lifecycle_segments,
    query_return_timing,
    retention_from_timing,
    validate_lifecycle_data,
)


class InvestigationTools(Protocol):
    def validate_data(self, windows: DateWindows) -> ValidationResult: ...

    def scan_metrics(self, windows: DateWindows) -> MetricsScanResult: ...

    def analyze_funnel(self, events: list[str], windows: DateWindows) -> FunnelComparison: ...

    def compare_segments(
        self, dimension: str, windows: DateWindows, lifecycle_filter: str | None
    ) -> SegmentComparison: ...

    def validate_lifecycle_data(self, windows: LifecycleWindows) -> ValidationResult: ...

    def analyze_retention(self, windows: LifecycleWindows) -> RetentionComparison: ...

    def analyze_return_timing(self, windows: LifecycleWindows) -> ReturnTimingAnalysis: ...

    def analyze_recovery(
        self, windows: LifecycleWindows, retention: RetentionComparison
    ) -> RecoveryAnalysis: ...

    def compare_lifecycle_segments(
        self, dimension: str, windows: LifecycleWindows
    ) -> LifecycleSegmentComparison: ...


class AnalyticsToolset:
    """Production adapter that composes the existing Analytics Tools unchanged."""

    def __init__(self, executor: QueryExecutor, minimum_sample_size: int = 100) -> None:
        self.executor = executor
        self.minimum_sample_size = minimum_sample_size
        self._lifecycle_timing: dict[tuple, ReturnTimingAnalysis] = {}

    def validate_data(self, windows: DateWindows) -> ValidationResult:
        return validate_data(self.executor, windows, self.minimum_sample_size)

    def scan_metrics(self, windows: DateWindows) -> MetricsScanResult:
        return scan_metrics(self.executor, **windows.model_dump())

    def analyze_funnel(self, events: list[str], windows: DateWindows) -> FunnelComparison:
        return analyze_funnel(self.executor, events, **windows.model_dump())

    def compare_segments(
        self, dimension: str, windows: DateWindows, lifecycle_filter: str | None
    ) -> SegmentComparison:
        return compare_segments(
            self.executor,
            dimension,
            **windows.model_dump(),
            minimum_sample_size=self.minimum_sample_size,
            lifecycle_filter=lifecycle_filter,
        )

    def validate_lifecycle_data(self, windows: LifecycleWindows) -> ValidationResult:
        return validate_lifecycle_data(self.executor, windows)

    def analyze_return_timing(self, windows: LifecycleWindows) -> ReturnTimingAnalysis:
        key = tuple(windows.model_dump().values())
        if key not in self._lifecycle_timing:
            self._lifecycle_timing[key] = query_return_timing(self.executor, windows)
        return self._lifecycle_timing[key]

    def analyze_retention(self, windows: LifecycleWindows) -> RetentionComparison:
        return retention_from_timing(self.analyze_return_timing(windows))

    def analyze_recovery(
        self, windows: LifecycleWindows, retention: RetentionComparison
    ) -> RecoveryAnalysis:
        return analyze_lifecycle_recovery(retention)

    def compare_lifecycle_segments(
        self, dimension: str, windows: LifecycleWindows
    ) -> LifecycleSegmentComparison:
        return compare_lifecycle_segments(
            self.executor, dimension, windows, self.minimum_sample_size
        )


class InvestigationAgent:
    def __init__(
        self,
        tools: InvestigationTools,
        investigation_budget: int = 4,
        planner_mode: PlannerMode | str = PlannerMode.DETERMINISTIC,
        planner: PlannerProtocol | None = None,
    ) -> None:
        if not 0 <= investigation_budget <= len(ALLOWED_DIMENSIONS):
            raise ValueError("investigation_budget must be between 0 and 4")
        self.tools = tools
        self.investigation_budget = investigation_budget
        self.planner_mode = PlannerMode(planner_mode)
        self.planner = planner
        self.deterministic_planner = DeterministicPlanner()
        self.guard = PolicyGuard()

    def run(
        self,
        windows: DateWindows,
        run_id: str | None = None,
        investigation_profile: InvestigationProfile | str = InvestigationProfile.CONVERSION,
    ) -> AgentState:
        profile = InvestigationProfile(investigation_profile)
        state = AgentState(
            run_id=run_id or str(uuid4()),
            **windows.model_dump(),
            remaining_investigation_budget=self.investigation_budget,
            investigation_profile=profile,
            opportunity_type=("LIFECYCLE_RISK" if profile == InvestigationProfile.LIFECYCLE_RISK else "CONVERSION_DECLINE"),
        )
        if profile == InvestigationProfile.LIFECYCLE_RISK:
            if not isinstance(windows, LifecycleWindows):
                raise ValueError("LIFECYCLE_RISK requires post_start and post_end")
            return self._run_lifecycle(state, windows)
        self._validate(state, windows)
        if state.data_quality_status != "PASS":
            return state

        signal = self._scan(state, windows)
        if signal is None:
            return state

        events = next(list(pair) for name, pair in FUNNEL_PAIRS if name == signal.name)
        self._analyze_signal(state, windows, events)

        while next_dimension(state) is not None:
            proposal, planning = self._planning_decision(state)
            if proposal.action == PlannerAction.STOP:
                break
            self._investigate_dimension(
                state,
                windows,
                proposal.dimension,
                proposal.lifecycle_filter,
                planning,
            )

        finalize_needs_evidence(state)
        state.stop_reason = _investigation_stop_reason(state)
        reason = continuation_reason(state, None)
        self._log(state, "STOP_DRILLDOWN", None, {}, {}, "STOP", reason)
        return state

    def _run_lifecycle(
        self, state: AgentState, windows: LifecycleWindows
    ) -> AgentState:
        self._validate_lifecycle(state, windows)
        if state.data_quality_status != "PASS":
            return state
        if not self._analyze_retention(state, windows):
            return state
        self._analyze_return_timing(state, windows)
        self._analyze_recovery(state, windows)

        while next_dimension(state) is not None:
            proposal, planning = self._planning_decision(state)
            if proposal.action == PlannerAction.STOP:
                break
            self._investigate_lifecycle_dimension(
                state, windows, proposal.dimension, planning
            )

        finalize_lifecycle_needs_evidence(state)
        state.stop_reason = _investigation_stop_reason(state)
        self._log(
            state,
            "STOP_DRILLDOWN",
            None,
            {},
            {},
            "STOP",
            continuation_reason(state, None),
        )
        return state

    def _validate_lifecycle(self, state: AgentState, windows: LifecycleWindows) -> None:
        result = self.tools.validate_lifecycle_data(windows)
        state.validation_result = result
        state.data_quality_status = result.status
        if result.analysis_allowed:
            decision = "CONTINUE"
            reason = "Lifecycle source events are stable and all cohorts have complete D7 windows."
        else:
            state.stop_reason = StopReason.DATA_QUALITY_FAIL
            state.recommended_status = RecommendedStatus.DATA_QUALITY_ALERT
            state.recommended_action_type = RecommendedActionType.NONE
            state.recommended_next_action = "Resolve lifecycle data-quality warnings before investigating return behavior."
            state.unknowns = ["Lifecycle signal validity is unknown until data quality is restored."]
            decision = "STOP"
            reason = "Lifecycle data quality failed; stop immediately."
        self._log(
            state,
            "VALIDATE_DATA",
            "validate_lifecycle_data",
            _window_input(windows),
            {"status": result.status.value, "warning_codes": [item.code for item in result.warnings]},
            decision,
            reason,
        )

    def _analyze_retention(self, state: AgentState, windows: LifecycleWindows) -> bool:
        result = self.tools.analyze_retention(windows)
        state.retention_result = result
        state.metric_name = result.metric_name
        if not retention_data_is_sufficient(result):
            state.data_quality_status = AnalysisStatus.FAIL
            state.stop_reason = StopReason.DATA_QUALITY_FAIL
            state.recommended_status = RecommendedStatus.DATA_QUALITY_ALERT
            state.recommended_action_type = RecommendedActionType.NONE
            state.recommended_next_action = (
                "Resolve insufficient or invalid lifecycle cohort data before investigating return behavior."
            )
            state.unknowns = ["Lifecycle signal validity is unknown until cohort data is sufficient."]
            self._log(
                state,
                "ANALYZE_RETENTION",
                "analyze_retention",
                _window_input(windows),
                result.model_dump(mode="json"),
                "STOP",
                "Lifecycle cohort data is insufficient for a reliable return-rate comparison.",
            )
            return False

        if not has_material_negative_retention(result.baseline, result.target):
            state.stop_reason = StopReason.NO_SIGNIFICANT_SIGNAL
            state.signal_confidence = Confidence.LOW
            state.root_cause_confidence = Confidence.LOW
            state.recommended_status = RecommendedStatus.NO_OPPORTUNITY
            state.recommended_action_type = RecommendedActionType.NONE
            state.recommended_next_action = "No material negative lifecycle signal requires investigation."
            state.unknowns = [
                "A statistically supported negative new-user return change was not observed."
            ]
            self._log(
                state,
                "ANALYZE_RETENTION",
                "analyze_retention",
                _window_input(windows),
                result.model_dump(mode="json"),
                "STOP",
                "No statistically supported negative D7 return-rate change was detected.",
            )
            return False

        state.detected_signal = result.metric_name
        state.affected_segment = "new_users"
        state.signal_confidence = Confidence.HIGH
        state.evidence.append(
            f"D7 Return Rate declined from {result.baseline.return_rate_7d:.2f}% "
            f"to {result.target.return_rate_7d:.2f}% ({result.delta_pp:.2f}pp)."
        )
        self._log(
            state,
            "ANALYZE_RETENTION",
            "analyze_retention",
            _window_input(windows),
            result.model_dump(mode="json"),
            "CONTINUE",
            "A statistically supported negative lifecycle signal is present; inspect return timing.",
        )
        return True

    def _analyze_return_timing(self, state: AgentState, windows: LifecycleWindows) -> None:
        result = self.tools.analyze_return_timing(windows)
        state.return_timing_result = result
        conclusion = describe_return_timing(result)
        state.evidence.append(conclusion)
        self._log(
            state,
            "CHECK_RETURN_TIMING",
            "analyze_return_timing",
            _window_input(windows),
            {**result.model_dump(mode="json"), "conclusion": conclusion},
            "CONTINUE",
            "Timing evidence is established without assigning a causal explanation.",
        )

    def _analyze_recovery(self, state: AgentState, windows: LifecycleWindows) -> None:
        if state.retention_result is None:
            raise ValueError("retention analysis must precede recovery analysis")
        result = self.tools.analyze_recovery(windows, state.retention_result)
        state.recovery_result = result
        recovery_evidence = _recovery_evidence(state.retention_result, result)
        state.evidence.append(recovery_evidence)
        self._log(
            state,
            "CHECK_RECOVERY",
            "analyze_recovery",
            _window_input(windows),
            {
                **result.model_dump(mode="json"),
                "baseline_rate": state.retention_result.baseline.return_rate_7d,
                "target_rate": state.retention_result.target.return_rate_7d,
                "post_rate": state.retention_result.post.return_rate_7d,
            },
            "CONTINUE",
            "Recovery is deterministically classified; bounded segment investigation may begin.",
        )

    def _investigate_lifecycle_dimension(
        self,
        state: AgentState,
        windows: LifecycleWindows,
        dimension: str | None,
        planning: dict,
    ) -> None:
        if dimension is None:
            raise ValueError("accepted INVESTIGATE proposal requires a dimension")
        result = self.tools.compare_lifecycle_segments(dimension, windows)
        state.lifecycle_segment_results[dimension] = result
        state.investigated_dimensions.append(dimension)
        state.remaining_investigation_budget -= 1
        hypothesis = apply_lifecycle_segment_policy(state, result)
        following = next_dimension(state)
        self._log(
            state,
            f"CHECK_{dimension.upper()}",
            "compare_lifecycle_segments",
            {**_window_input(windows), "dimension": dimension},
            result.model_dump(mode="json"),
            "CONTINUE" if following is not None else "STOP_DRILLDOWN",
            continuation_reason(state, following),
            hypothesis.code,
            hypothesis.status,
            **planning,
        )

    def _planning_decision(self, state: AgentState) -> tuple[PlannerProposal, dict]:
        if self.planner_mode == PlannerMode.DETERMINISTIC:
            proposal = self.deterministic_planner.plan(state)
            return proposal, {
                "planner_mode": self.planner_mode.value,
                "planner_proposal": _proposal_summary(proposal),
                "planner_rationale": proposal.rationale,
                "guard_status": GuardStatus.ACCEPTED.value,
                "guard_reason": "DETERMINISTIC_POLICY",
                "fallback_used": False,
                "fallback_reason": None,
            }

        fallback = self.deterministic_planner.plan(state)
        if self.planner is None:
            return fallback, _fallback_trace(
                self.planner_mode, None, "NO_PLANNER_CONFIGURED"
            )
        try:
            raw = self.planner.plan(state.model_copy(deep=True))
        except Exception as exc:  # provider boundary must never crash the investigation
            return fallback, _fallback_trace(
                self.planner_mode,
                None,
                f"PROVIDER_ERROR:{type(exc).__name__}",
            )

        raw_summary = _raw_proposal_summary(raw)
        try:
            proposal = parse_planner_output(raw)
        except JSONDecodeError:
            return fallback, _fallback_trace(
                self.planner_mode, raw_summary, "INVALID_JSON"
            )
        except (ValidationError, TypeError, ValueError):
            return fallback, _fallback_trace(
                self.planner_mode, raw_summary, "SCHEMA_VALIDATION_FAILURE"
            )

        guard = self.guard.validate(state, proposal)
        if guard.status == GuardStatus.REJECTED:
            return fallback, {
                "planner_mode": self.planner_mode.value,
                "planner_proposal": _proposal_summary(proposal),
                "planner_rationale": proposal.rationale,
                "guard_status": guard.status.value,
                "guard_reason": guard.reason.value,
                "fallback_used": True,
                "fallback_reason": guard.reason.value,
            }
        return proposal, {
            "planner_mode": self.planner_mode.value,
            "planner_proposal": _proposal_summary(proposal),
            "planner_rationale": proposal.rationale,
            "guard_status": guard.status.value,
            "guard_reason": guard.reason.value,
            "fallback_used": False,
            "fallback_reason": None,
        }

    def _validate(self, state: AgentState, windows: DateWindows) -> None:
        result = self.tools.validate_data(windows)
        state.validation_result = result
        state.data_quality_status = result.status
        if not result.analysis_allowed:
            state.stop_reason = StopReason.DATA_QUALITY_FAIL
            state.recommended_status = RecommendedStatus.DATA_QUALITY_ALERT
            state.recommended_action_type = RecommendedActionType.NONE
            state.recommended_next_action = "Resolve data-quality warnings before investigating behavior."
            state.do_not_recommend_yet = [
                "Do not infer an opportunity or recommend an intervention from failed data validation."
            ]
            state.unknowns = ["Behavioral signal validity is unknown until data quality is restored."]
            decision, reason = "STOP", "Data quality failed; stop immediately."
        else:
            decision, reason = "CONTINUE", "Data quality passed; scan metrics for a material signal."
        self._log(
            state,
            "VALIDATE_DATA",
            "validate_data",
            _window_input(windows),
            {"status": result.status.value, "warning_codes": [item.code for item in result.warnings]},
            decision,
            reason,
        )

    def _scan(self, state: AgentState, windows: DateWindows):
        result = self.tools.scan_metrics(windows)
        state.metrics_result = result
        signal = select_signal(result.metrics)
        if signal is None:
            state.stop_reason = StopReason.NO_SIGNIFICANT_SIGNAL
            state.signal_confidence = Confidence.LOW
            state.root_cause_confidence = Confidence.LOW
            state.recommended_status = RecommendedStatus.NO_OPPORTUNITY
            state.recommended_action_type = RecommendedActionType.NONE
            state.recommended_next_action = "Continue routine monitoring."
            state.do_not_recommend_yet = [
                "Do not create an opportunity or intervention without a significant signal."
            ]
            decision, reason = "STOP", "No metric crossed its investigation threshold."
        else:
            state.detected_signal = signal.name
            decision, reason = "CONTINUE", f"{signal.name} requires strict-funnel verification."
        self._log(
            state,
            "SCAN_METRICS",
            "scan_metrics",
            _window_input(windows),
            {
                "metrics": [
                    {"name": item.name, "delta_pp": item.delta_pp, "needs_investigation": item.needs_investigation}
                    for item in result.metrics
                ]
            },
            decision,
            reason,
        )
        return signal

    def _analyze_signal(self, state: AgentState, windows: DateWindows, events: list[str]) -> None:
        result = self.tools.analyze_funnel(events, windows)
        state.funnel_result = result
        set_signal_confidence(state, result)
        self._log(
            state,
            "ANALYZE_FUNNEL",
            "analyze_funnel",
            {**_window_input(windows), "events": events},
            {
                "entry_event": result.entry_event,
                "conversion_event": result.conversion_event,
                "baseline_rate": result.baseline.session_conversion_rate,
                "target_rate": result.target.session_conversion_rate,
                "delta_pp": result.session_delta_pp,
                "strict_identity_session_order": True,
            },
            "CONTINUE",
            continuation_reason(state, "lifecycle"),
        )

    def _investigate_dimension(
        self,
        state: AgentState,
        windows: DateWindows,
        dimension: str | None,
        lifecycle_filter: str | None,
        planning: dict,
    ) -> None:
        if dimension is None:
            raise ValueError("accepted INVESTIGATE proposal requires a dimension")
        result = self.tools.compare_segments(dimension, windows, lifecycle_filter)
        state.segment_results[dimension] = result
        state.investigated_dimensions.append(dimension)
        state.remaining_investigation_budget -= 1
        hypothesis = apply_segment_policy(state, result)
        following = next_dimension(state)
        decision = "CONTINUE" if following is not None else "STOP_DRILLDOWN"
        reason = continuation_reason(state, following)
        self._log(
            state,
            f"COMPARE_SEGMENTS_{dimension.upper()}",
            "compare_segments",
            {
                **_window_input(windows),
                "dimension": dimension,
                "lifecycle_filter": lifecycle_filter,
            },
            {
                "dimension": dimension,
                "segments": [
                    {
                        "segment": row.segment,
                        "change_pp": row.change_pp,
                        "baseline_share": row.baseline_share,
                        "target_share": row.target_share,
                        "sample_sufficient": row.sample_sufficient,
                    }
                    for row in result.segments
                ],
            },
            decision,
            reason,
            hypothesis.code if hypothesis else None,
            hypothesis.status if hypothesis else None,
            **planning,
        )

    @staticmethod
    def _log(
        state: AgentState,
        node: str,
        tool_name: str | None,
        tool_input: dict,
        output: dict,
        decision: str,
        reason: str,
        hypothesis: str | None = None,
        hypothesis_status=None,
        planner_mode: str | None = None,
        planner_proposal: dict | None = None,
        planner_rationale: str | None = None,
        guard_status: str | None = None,
        guard_reason: str | None = None,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        state.agent_steps.append(
            AgentStep(
                step_order=len(state.agent_steps) + 1,
                node=node,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output_summary=output,
                decision=decision,
                decision_reason=reason,
                hypothesis=hypothesis,
                hypothesis_status=hypothesis_status,
                remaining_budget=state.remaining_investigation_budget,
                planner_mode=planner_mode,
                planner_proposal=planner_proposal,
                planner_rationale=planner_rationale,
                guard_status=guard_status,
                guard_reason=guard_reason,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
            )
        )


def _window_input(windows: DateWindows) -> dict[str, str]:
    return {name: value.isoformat() for name, value in windows.model_dump().items()}


def _proposal_summary(proposal: PlannerProposal) -> dict:
    return proposal.model_dump(mode="json")


def _raw_proposal_summary(raw) -> dict | None:
    if isinstance(raw, PlannerProposal):
        return _proposal_summary(raw)
    if not isinstance(raw, dict):
        return None
    allowed = {"action", "dimension", "lifecycle_filter", "rationale", "hypothesis_code"}
    return {key: raw[key] for key in allowed if key in raw}


def _fallback_trace(
    mode: PlannerMode,
    proposed: dict | None,
    reason: str,
) -> dict:
    return {
        "planner_mode": mode.value,
        "planner_proposal": proposed,
        "planner_rationale": proposed.get("rationale") if proposed else None,
        "guard_status": GuardStatus.FALLBACK.value,
        "guard_reason": reason,
        "fallback_used": True,
        "fallback_reason": reason,
    }


def _recovery_evidence(
    retention: RetentionComparison, recovery: RecoveryAnalysis
) -> str:
    post_rate = retention.post.return_rate_7d
    if recovery.risk_pattern == RiskPattern.NO_RECOVERY:
        return (
            f"Post-period D7 Return was {post_rate:.2f}% and did not show a statistically "
            "supported improvement over Target."
        )
    if recovery.risk_pattern == RiskPattern.FULL_RECOVERY:
        return (
            f"Post-period D7 Return improved to {post_rate:.2f}% and is no longer "
            "statistically below Baseline."
        )
    return (
        f"Post-period D7 Return improved to {post_rate:.2f}% and remained statistically "
        "below Baseline."
    )


def _investigation_stop_reason(state: AgentState) -> StopReason:
    if (
        state.supported_hypotheses
        and state.investigation_profile == InvestigationProfile.CONVERSION
    ):
        return StopReason.SIGNAL_LOCALIZED
    if set(state.investigated_dimensions) == set(allowed_dimensions(state)):
        return StopReason.ALLOWED_DIMENSIONS_EXHAUSTED
    if state.remaining_investigation_budget <= 0:
        return StopReason.BUDGET_EXHAUSTED
    return StopReason.ALLOWED_DIMENSIONS_EXHAUSTED
