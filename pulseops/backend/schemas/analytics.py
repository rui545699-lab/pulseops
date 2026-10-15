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

