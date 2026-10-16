from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from pulseops.backend.persistence.models import AnalysisRun, AgentStep, Opportunity
from pulseops.backend.persistence.service import RunService
from pulseops.backend.schemas.analytics import DateWindows, LifecycleWindows

router = APIRouter(prefix="/api", tags=["product"])

_REDUNDANT_HYPOTHESIS_SUFFIX = re.compile(
    r"\s*(?:[;,:-]\s*)?\(?\s*(?:this\s+is\s+)?unverified\s*\)?[.!]?\s*$",
    re.IGNORECASE,
)


def _polish_hypothesis_copy(value: str) -> str:
    polished = _REDUNDANT_HYPOTHESIS_SUFFIX.sub("", value).rstrip()
    if polished and polished[-1] not in ".!?":
        polished += "."
    return polished


class RunCreate(DateWindows):
    planner_mode: Literal["deterministic", "deepseek"] = "deterministic"
    analysis_type: Literal["CONVERSION", "LIFECYCLE_RISK"] = "CONVERSION"
    post_start: date | None = None
    post_end: date | None = None

    @model_validator(mode="after")
    def validate_profile_windows(self) -> "RunCreate":
        if self.analysis_type == "LIFECYCLE_RISK" and (
            self.post_start is None or self.post_end is None
        ):
            raise ValueError("LIFECYCLE_RISK requires post_start and post_end")
        return self


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_type: str
    baseline_start: date
    baseline_end: date
    target_start: date
    target_end: date
    post_start: date | None
    post_end: date | None
    planner_mode: str
    provider: str | None
    model_identifier: str | None
    detected_signal: str | None
    overall_baseline_rate: float | None
    overall_target_rate: float | None
    overall_delta_pp: float | None
    post_rate: float | None
    target_to_post_delta_pp: float | None
    baseline_to_post_delta_pp: float | None
    recovery_ratio: float | None
    risk_pattern: str | None
    return_timing: dict[str, Any] | None
    affected_segment: str | None
    signal_confidence: str
    root_cause_confidence: str
    stop_reason: str | None
    recommended_status: str | None
    recommended_action_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class StepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    step_order: int
    node: str
    tool_name: str | None
    planner_proposal: dict[str, Any] | None
    planner_rationale: str | None
    guard_status: str | None
    guard_reason: str | None
    tool_input: dict[str, Any]
    tool_output_summary: dict[str, Any]
    decision: str
    decision_reason: str
    hypothesis: str | None
    hypothesis_status: str | None
    remaining_budget: int
    fallback_used: bool
    fallback_reason: str | None
    created_at: datetime


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    title: str
    opportunity_type: str
    affected_segment: str | None
    metric: str
    baseline_rate: float
    target_rate: float
    delta_pp: float
    post_rate: float | None
    target_to_post_delta_pp: float | None
    baseline_to_post_delta_pp: float | None
    recovery_ratio: float | None
    risk_pattern: str | None
    return_timing: dict[str, Any] | None
    segment_analysis: dict[str, Any] | None
    hypothesis_records: list[dict[str, Any]] | None
    signal_confidence: str
    root_cause_confidence: str
    evidence: list[str]
    hypotheses: list[str]
    unknowns: list[str]
    recommended_status: str
    recommended_action_type: str
    recommended_next_action: str | None
    do_not_recommend_yet: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    @field_validator("hypotheses", mode="before")
    @classmethod
    def polish_hypothesis_copy(cls, values: list[str]) -> list[str]:
        return [_polish_hypothesis_copy(value) for value in values]


def get_run_service(request: Request) -> RunService:
    return request.app.state.run_service


@router.post("/runs", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, service: RunService = Depends(get_run_service)) -> AnalysisRun:
    values = payload.model_dump(exclude={"planner_mode", "analysis_type"})
    if payload.analysis_type == "LIFECYCLE_RISK":
        windows = LifecycleWindows.model_validate(values)
    else:
        windows = DateWindows.model_validate(values, extra="ignore")
    return service.execute(windows, payload.planner_mode, payload.analysis_type)


@router.get("/runs", response_model=list[RunRead])
def list_runs(service: RunService = Depends(get_run_service)) -> list[AnalysisRun]:
    return service.list_runs()


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: str, service: RunService = Depends(get_run_service)) -> AnalysisRun:
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run


@router.get("/runs/{run_id}/steps", response_model=list[StepRead])
def get_run_steps(run_id: str, service: RunService = Depends(get_run_service)) -> list[AgentStep]:
    steps = service.get_steps(run_id)
    if steps is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return steps


@router.get("/opportunities", response_model=list[OpportunityRead])
def list_opportunities(service: RunService = Depends(get_run_service)) -> list[Opportunity]:
    return service.list_opportunities()


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityRead)
def get_opportunity(
    opportunity_id: str, service: RunService = Depends(get_run_service)
) -> Opportunity:
    opportunity = service.get_opportunity(opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opportunity
