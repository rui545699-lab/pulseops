from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class AnalysisStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RecommendedStatus(str, Enum):
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    MONITOR = "MONITOR"
    DATA_QUALITY_ALERT = "DATA_QUALITY_ALERT"
    NO_OPPORTUNITY = "NO_OPPORTUNITY"


class DateWindows(BaseModel):
    baseline_start: date
    baseline_end: date
    target_start: date
    target_end: date

    @model_validator(mode="after")
    def validate_ranges(self) -> "DateWindows":
        if self.baseline_start > self.baseline_end:
            raise ValueError("baseline_start must be on or before baseline_end")
        if self.target_start > self.target_end:
            raise ValueError("target_start must be on or before target_end")
        return self


class LifecycleWindows(DateWindows):
    post_start: date
    post_end: date

    @model_validator(mode="after")
    def validate_post_range(self) -> "LifecycleWindows":
        if self.post_start > self.post_end:
            raise ValueError("post_start must be on or before post_end")
        if self.post_start <= self.target_end:
            raise ValueError("post period must start after target_end")
        return self


class WarningItem(BaseModel):
    code: str
    message: str
    period: str | None = None
    event_date: date | None = None


class ValidationResult(BaseModel):
    status: AnalysisStatus
    analysis_allowed: bool
    warnings: list[WarningItem] = Field(default_factory=list)


class PeriodFunnelResult(BaseModel):
    view_sessions: int
    converted_sessions: int
    session_conversion_rate: float
    view_users: int
    converted_users: int
    user_conversion_rate: float


class FunnelComparison(BaseModel):
    entry_event: str
    conversion_event: str
    baseline: PeriodFunnelResult
    target: PeriodFunnelResult
    session_delta_pp: float
    user_delta_pp: float
    needs_investigation: bool


class MetricResult(BaseModel):
    name: str
    baseline_rate: float
    target_rate: float
    delta_pp: float
    baseline_sample_size: int
    target_sample_size: int
    needs_investigation: bool


class MetricsScanResult(BaseModel):
    metrics: list[MetricResult]


class SegmentResult(BaseModel):
    segment: str
    baseline_rate: float | None
    target_rate: float | None
    change_pp: float | None
    baseline_users: int
    target_users: int
    baseline_share: float
    target_share: float
    sample_sufficient: bool


class SegmentComparison(BaseModel):
    dimension: str
    minimum_sample_size: int
    segments: list[SegmentResult]


class OperationalAssessment(BaseModel):
    signal_confidence: Confidence
    root_cause_confidence: Confidence
    recommended_status: RecommendedStatus
    evidence: list[str]
    hypotheses: list[str]
    unknowns: list[str]


class RiskPattern(str, Enum):
    NO_RECOVERY = "NO_RECOVERY"
    PARTIAL_RECOVERY = "PARTIAL_RECOVERY"
    FULL_RECOVERY = "FULL_RECOVERY"


class RetentionPeriodResult(BaseModel):
    eligible_new_users: int
    returned_users_7d: int
    return_rate_7d: float


class RetentionComparison(BaseModel):
    metric_name: str = "New-user 7-day Return Rate"
    baseline: RetentionPeriodResult
    target: RetentionPeriodResult
    post: RetentionPeriodResult
    delta_pp: float
    relative_change_pct: float | None
    target_to_post_delta_pp: float
    baseline_to_post_delta_pp: float


class ReturnTimingPeriod(BaseModel):
    eligible_new_users: int
    returned_users_d1: int
    return_rate_d1: float
    returned_users_d3: int
    return_rate_d3: float
    returned_users_d7: int
    return_rate_d7: float


class ReturnTimingAnalysis(BaseModel):
    baseline: ReturnTimingPeriod
    target: ReturnTimingPeriod
    post: ReturnTimingPeriod
    d1_decline_contribution_pct: float
    d2_3_decline_contribution_pct: float
    d4_7_decline_contribution_pct: float


class RecoveryAnalysis(BaseModel):
    risk_pattern: RiskPattern
    recovery_ratio_pct: float
    target_to_post_delta_pp: float
    baseline_to_post_delta_pp: float


class LifecycleSegmentResult(BaseModel):
    segment: str
    baseline_users: int
    baseline_returned_users: int
    baseline_rate: float
    baseline_share: float
    target_users: int
    target_returned_users: int
    target_rate: float
    target_share: float
    change_pp: float
    share_change_pp: float
    sample_sufficient: bool = True


class LifecycleSegmentComparison(BaseModel):
    dimension: str
    segments: list[LifecycleSegmentResult]
    composition_effect_pp: float
    within_segment_effect_pp: float
    composition_share_of_total_decline_pct: float | None = None
    within_segment_share_of_total_decline_pct: float | None = None

