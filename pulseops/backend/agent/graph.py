from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from pulseops.backend.agent.policies import (
    apply_segment_policy,
    finalize_needs_evidence,
    select_signal,
    set_signal_confidence,
)
from pulseops.backend.agent.router import ALLOWED_DIMENSIONS, continuation_reason, next_dimension
from pulseops.backend.agent.state import (
    AgentState,
    AgentStep,
    RecommendedActionType,
    StopReason,
)
from pulseops.backend.analytics.bigquery_client import QueryExecutor
from pulseops.backend.analytics.queries.metrics import FUNNEL_PAIRS
from pulseops.backend.schemas.analytics import (
    Confidence,
    DateWindows,
    FunnelComparison,
    MetricsScanResult,
    RecommendedStatus,
    SegmentComparison,
    ValidationResult,
)
from pulseops.backend.tools.analyze_funnel import analyze_funnel
from pulseops.backend.tools.compare_segments import compare_segments
from pulseops.backend.tools.scan_metrics import scan_metrics
from pulseops.backend.tools.validate_data import validate_data


class InvestigationTools(Protocol):
    def validate_data(self, windows: DateWindows) -> ValidationResult: ...

    def scan_metrics(self, windows: DateWindows) -> MetricsScanResult: ...

    def analyze_funnel(self, events: list[str], windows: DateWindows) -> FunnelComparison: ...

    def compare_segments(
        self, dimension: str, windows: DateWindows, lifecycle_filter: str | None
    ) -> SegmentComparison: ...


class AnalyticsToolset:
    """Production adapter that composes the existing Analytics Tools unchanged."""

    def __init__(self, executor: QueryExecutor, minimum_sample_size: int = 100) -> None:
        self.executor = executor
        self.minimum_sample_size = minimum_sample_size

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


class InvestigationAgent:
    def __init__(self, tools: InvestigationTools, investigation_budget: int = 4) -> None:
        if not 0 <= investigation_budget <= len(ALLOWED_DIMENSIONS):
            raise ValueError("investigation_budget must be between 0 and 4")
        self.tools = tools
        self.investigation_budget = investigation_budget

    def run(self, windows: DateWindows, run_id: str | None = None) -> AgentState:
        state = AgentState(
            run_id=run_id or str(uuid4()),
            **windows.model_dump(),
            remaining_investigation_budget=self.investigation_budget,
        )
        self._validate(state, windows)
        if state.data_quality_status != "PASS":
            return state

        signal = self._scan(state, windows)
        if signal is None:
            return state

        events = next(list(pair) for name, pair in FUNNEL_PAIRS if name == signal.name)
        self._analyze_signal(state, windows, events)

        while (dimension := next_dimension(state)) is not None:
            self._investigate_dimension(state, windows, dimension)

        finalize_needs_evidence(state)
        state.stop_reason = _investigation_stop_reason(state)
        reason = continuation_reason(state, None)
        self._log(state, "STOP_DRILLDOWN", None, {}, {}, "STOP", reason)
        return state

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
        self, state: AgentState, windows: DateWindows, dimension: str
    ) -> None:
        lifecycle_filter = "new" if dimension != "lifecycle" and state.affected_segment == "new_users" else None
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
            )
        )


def _window_input(windows: DateWindows) -> dict[str, str]:
    return {name: value.isoformat() for name, value in windows.model_dump().items()}


def _investigation_stop_reason(state: AgentState) -> StopReason:
    if state.supported_hypotheses:
        return StopReason.SIGNAL_LOCALIZED
    if set(state.investigated_dimensions) == set(ALLOWED_DIMENSIONS):
        return StopReason.ALLOWED_DIMENSIONS_EXHAUSTED
    if state.remaining_investigation_budget <= 0:
        return StopReason.BUDGET_EXHAUSTED
    return StopReason.ALLOWED_DIMENSIONS_EXHAUSTED
