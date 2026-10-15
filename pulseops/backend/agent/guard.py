from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from pulseops.backend.agent.planner import PlannerAction, PlannerProposal
from pulseops.backend.agent.router import ALLOWED_DIMENSIONS, next_dimension
from pulseops.backend.agent.state import AgentState


class GuardStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FALLBACK = "FALLBACK"


class GuardReason(str, Enum):
    ACCEPTED = "ACCEPTED"
    DIMENSION_NOT_ALLOWED = "DIMENSION_NOT_ALLOWED"
    LIFECYCLE_REQUIRED = "LIFECYCLE_REQUIRED"
    DUPLICATE_DIMENSION = "DUPLICATE_DIMENSION"
    FILTER_INCONSISTENT = "FILTER_INCONSISTENT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    PREMATURE_STOP = "PREMATURE_STOP"
    STOP_ALLOWED = "STOP_ALLOWED"


class GuardResult(BaseModel):
    status: GuardStatus
    reason: GuardReason


class PolicyGuard:
    def validate(self, state: AgentState, proposal: PlannerProposal) -> GuardResult:
        if proposal.action == PlannerAction.STOP:
            if next_dimension(state) is not None:
                return GuardResult(status=GuardStatus.REJECTED, reason=GuardReason.PREMATURE_STOP)
            return GuardResult(status=GuardStatus.ACCEPTED, reason=GuardReason.STOP_ALLOWED)

        dimension = proposal.dimension
        if dimension not in ALLOWED_DIMENSIONS:
            return GuardResult(
                status=GuardStatus.REJECTED,
                reason=GuardReason.DIMENSION_NOT_ALLOWED,
            )
        if state.remaining_investigation_budget <= 0:
            return GuardResult(status=GuardStatus.REJECTED, reason=GuardReason.BUDGET_EXHAUSTED)
        if dimension in state.investigated_dimensions:
            return GuardResult(
                status=GuardStatus.REJECTED,
                reason=GuardReason.DUPLICATE_DIMENSION,
            )
        if "lifecycle" not in state.investigated_dimensions and dimension != "lifecycle":
            return GuardResult(status=GuardStatus.REJECTED, reason=GuardReason.LIFECYCLE_REQUIRED)

        expected_filter = None
        if dimension != "lifecycle" and state.affected_segment == "new_users":
            expected_filter = "new"
        elif dimension != "lifecycle" and state.affected_segment == "returning_users":
            expected_filter = "returning"
        if proposal.lifecycle_filter != expected_filter:
            return GuardResult(
                status=GuardStatus.REJECTED,
                reason=GuardReason.FILTER_INCONSISTENT,
            )
        return GuardResult(status=GuardStatus.ACCEPTED, reason=GuardReason.ACCEPTED)
