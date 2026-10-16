from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    Confidence,
    FunnelComparison,
    MetricsScanResult,
    RecommendedStatus,
    SegmentComparison,
    ValidationResult,
    LifecycleSegmentComparison,
    GrowthComparison,
    GrowthSegmentComparison,
    OrderValueContext,
    Reproducibility,
    WeeklyGrowthResult,
    RecoveryAnalysis,
    RetentionComparison,
    ReturnTimingAnalysis,
    RiskPattern,
)


class InvestigationProfile(str, Enum):
    CONVERSION = "CONVERSION"
    LIFECYCLE_RISK = "LIFECYCLE_RISK"
    POSITIVE_GROWTH = "POSITIVE_GROWTH"


class RecommendedActionType(str, Enum):
    EVIDENCE_COLLECTION = "EVIDENCE_COLLECTION"
    INTERVENTION = "INTERVENTION"
    NONE = "NONE"
    REPLICATION_TEST = "REPLICATION_TEST"


class StopReason(str, Enum):
    DATA_QUALITY_FAIL = "DATA_QUALITY_FAIL"
    NO_SIGNIFICANT_SIGNAL = "NO_SIGNIFICANT_SIGNAL"
    SIGNAL_LOCALIZED = "SIGNAL_LOCALIZED"
    ALLOWED_DIMENSIONS_EXHAUSTED = "ALLOWED_DIMENSIONS_EXHAUSTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class HypothesisStatus(str, Enum):
    REJECTED = "REJECTED"
    SUPPORTED = "SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNVERIFIED = "UNVERIFIED"


class HypothesisRecord(BaseModel):
    code: str
    reason: str
    status: HypothesisStatus


class AgentStep(BaseModel):
    step_order: int
    node: str
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output_summary: dict[str, Any] = Field(default_factory=dict)
    decision: str
    decision_reason: str
    hypothesis: str | None = None
    hypothesis_status: HypothesisStatus | None = None
    remaining_budget: int
    planner_mode: str | None = None
    planner_proposal: dict[str, Any] | None = None
    planner_rationale: str | None = None
    guard_status: str | None = None
    guard_reason: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


class AgentState(BaseModel):
    run_id: str
    baseline_start: date
    baseline_end: date
    target_start: date
    target_end: date
    post_start: date | None = None
    post_end: date | None = None
    confirmation_start: date | None = None
    confirmation_end: date | None = None
    holdout_1_start: date | None = None
    holdout_1_end: date | None = None
    holdout_2_start: date | None = None
    holdout_2_end: date | None = None
    investigation_profile: InvestigationProfile = InvestigationProfile.CONVERSION
    opportunity_type: str = "CONVERSION_DECLINE"
    metric_name: str | None = None

    data_quality_status: AnalysisStatus | None = None
    detected_signal: str | None = None
    affected_segment: str | None = None
    investigated_dimensions: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[HypothesisRecord] = Field(default_factory=list)
    supported_hypotheses: list[HypothesisRecord] = Field(default_factory=list)
    insufficient_hypotheses: list[HypothesisRecord] = Field(default_factory=list)
    remaining_investigation_budget: int = 4
    signal_confidence: Confidence = Confidence.LOW
    root_cause_confidence: Confidence = Confidence.LOW
    evidence: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    recommended_status: RecommendedStatus | None = None
    stop_reason: StopReason | None = None
    recommended_action_type: RecommendedActionType = RecommendedActionType.NONE
    recommended_next_action: str | None = None
    do_not_recommend_yet: list[str] = Field(default_factory=list)
    agent_steps: list[AgentStep] = Field(default_factory=list)

    validation_result: ValidationResult | None = Field(default=None, exclude=True)
    metrics_result: MetricsScanResult | None = Field(default=None, exclude=True)
    funnel_result: FunnelComparison | None = Field(default=None, exclude=True)
    segment_results: dict[str, SegmentComparison] = Field(default_factory=dict, exclude=True)
    retention_result: RetentionComparison | None = Field(default=None, exclude=True)
    return_timing_result: ReturnTimingAnalysis | None = Field(default=None, exclude=True)
    recovery_result: RecoveryAnalysis | None = Field(default=None, exclude=True)
    lifecycle_segment_results: dict[str, LifecycleSegmentComparison] = Field(
        default_factory=dict, exclude=True
    )
    growth_result: GrowthComparison | None = Field(default=None, exclude=True)
    weekly_growth_results: list[WeeklyGrowthResult] = Field(default_factory=list, exclude=True)
    growth_segment_results: dict[str, GrowthSegmentComparison] = Field(
        default_factory=dict, exclude=True
    )
    order_value_context: OrderValueContext | None = Field(default=None, exclude=True)
    reproducibility: Reproducibility | None = None
    growth_signal_confidence: Confidence | None = None
    reproducibility_confidence: Confidence | None = None
    growth_localization: str | None = None
