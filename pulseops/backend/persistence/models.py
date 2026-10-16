from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False, default="CONVERSION")
    baseline_start: Mapped[date] = mapped_column(Date, nullable=False)
    baseline_end: Mapped[date] = mapped_column(Date, nullable=False)
    target_start: Mapped[date] = mapped_column(Date, nullable=False)
    target_end: Mapped[date] = mapped_column(Date, nullable=False)
    post_start: Mapped[date | None] = mapped_column(Date)
    post_end: Mapped[date | None] = mapped_column(Date)
    planner_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64))
    model_identifier: Mapped[str | None] = mapped_column(String(128))
    detected_signal: Mapped[str | None] = mapped_column(String(128))
    overall_baseline_rate: Mapped[float | None] = mapped_column(Float)
    overall_target_rate: Mapped[float | None] = mapped_column(Float)
    overall_delta_pp: Mapped[float | None] = mapped_column(Float)
    post_rate: Mapped[float | None] = mapped_column(Float)
    target_to_post_delta_pp: Mapped[float | None] = mapped_column(Float)
    baseline_to_post_delta_pp: Mapped[float | None] = mapped_column(Float)
    recovery_ratio: Mapped[float | None] = mapped_column(Float)
    risk_pattern: Mapped[str | None] = mapped_column(String(64))
    return_timing: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    affected_segment: Mapped[str | None] = mapped_column(String(128))
    signal_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    root_cause_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(String(64))
    recommended_status: Mapped[str | None] = mapped_column(String(64))
    recommended_action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    steps: Mapped[list[AgentStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.step_order"
    )
    opportunity: Mapped[Opportunity | None] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_order", name="uq_step_run_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(128))
    planner_proposal: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    planner_rationale: Mapped[str | None] = mapped_column(Text)
    guard_status: Mapped[str | None] = mapped_column(String(32))
    guard_reason: Mapped[str | None] = mapped_column(String(128))
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    tool_output_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    decision: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(String(128))
    hypothesis_status: Mapped[str | None] = mapped_column(String(64))
    remaining_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="steps")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_segment: Mapped[str | None] = mapped_column(String(128))
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    baseline_rate: Mapped[float] = mapped_column(Float, nullable=False)
    target_rate: Mapped[float] = mapped_column(Float, nullable=False)
    delta_pp: Mapped[float] = mapped_column(Float, nullable=False)
    post_rate: Mapped[float | None] = mapped_column(Float)
    target_to_post_delta_pp: Mapped[float | None] = mapped_column(Float)
    baseline_to_post_delta_pp: Mapped[float | None] = mapped_column(Float)
    recovery_ratio: Mapped[float | None] = mapped_column(Float)
    risk_pattern: Mapped[str | None] = mapped_column(String(64))
    return_timing: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    segment_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    hypothesis_records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    signal_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    root_cause_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    hypotheses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    unknowns: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    recommended_status: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_next_action: Mapped[str | None] = mapped_column(Text)
    do_not_recommend_yet: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="opportunity")
