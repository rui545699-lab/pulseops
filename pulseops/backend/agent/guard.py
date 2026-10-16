from __future__ import annotations

from enum import Enum
import re

from pydantic import BaseModel

from pulseops.backend.agent.planner import PlannerAction, PlannerProposal
from pulseops.backend.agent.router import allowed_dimensions, next_dimension
from pulseops.backend.agent.state import AgentState, InvestigationProfile


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
    UNSUPPORTED_CAUSAL_CLAIM = "UNSUPPORTED_CAUSAL_CLAIM"
    INTERVENTION_NOT_ALLOWED = "INTERVENTION_NOT_ALLOWED"


class GuardResult(BaseModel):
    status: GuardStatus
    reason: GuardReason


class PolicyGuard:
    def validate(self, state: AgentState, proposal: PlannerProposal) -> GuardResult:
        rationale = proposal.rationale
        if any(
            pattern.search(rationale)
            for pattern in (
                re.compile(
                    r"\bcauses?\s+(?:the\s+)?(?:observed\s+)?(?:decline|drop|change|risk)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\bcaused\s+(?:the\s+)?(?:observed\s+)?(?:decline|drop|change|risk)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(?:decline|drop|change|risk)\s+(?:was|is)\s+caused\s+by\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\bis the root cause\b", re.IGNORECASE),
                re.compile(r"\bproves that\b", re.IGNORECASE),
                re.compile(
                    r"\bdrives?\s+(?:the\s+)?(?:observed\s+)?(?:decline|drop|change|risk)\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\bexplains?\s+(?:the\s+)?(?:observed\s+)?(?:decline|drop|change|risk)\b",
                    re.IGNORECASE,
                ),
                re.compile(r"\bis the reason for\b", re.IGNORECASE),
            )
        ):
            return GuardResult(
                status=GuardStatus.REJECTED,
                reason=GuardReason.UNSUPPORTED_CAUSAL_CLAIM,
            )
        if any(
            pattern.search(rationale)
            for pattern in (
                re.compile(r"\blaunch (?:a )?coupon", re.IGNORECASE),
                re.compile(r"\bsend coupons?\b", re.IGNORECASE),
                re.compile(r"\boffer discounts?\b", re.IGNORECASE),
                re.compile(r"\bsend push notifications?\b", re.IGNORECASE),
                re.compile(r"\blaunch (?:a )?promotion\b", re.IGNORECASE),
                re.compile(r"\breactivation campaign\b", re.IGNORECASE),
                re.compile(r"\bnotification spam\b", re.IGNORECASE),
                re.compile(r"\bredesign the ux\b", re.IGNORECASE),
                re.compile(r"\bfull-audience promotion\b", re.IGNORECASE),
            )
        ):
            return GuardResult(
                status=GuardStatus.REJECTED,
                reason=GuardReason.INTERVENTION_NOT_ALLOWED,
            )
        if proposal.action == PlannerAction.STOP:
            if next_dimension(state) is not None:
                return GuardResult(status=GuardStatus.REJECTED, reason=GuardReason.PREMATURE_STOP)
            return GuardResult(status=GuardStatus.ACCEPTED, reason=GuardReason.STOP_ALLOWED)

        dimension = proposal.dimension
        if dimension not in allowed_dimensions(state):
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
        if (
            state.investigation_profile == InvestigationProfile.CONVERSION
            and "lifecycle" not in state.investigated_dimensions
            and dimension != "lifecycle"
        ):
            return GuardResult(status=GuardStatus.REJECTED, reason=GuardReason.LIFECYCLE_REQUIRED)

        expected_filter = None
        if (
            state.investigation_profile == InvestigationProfile.CONVERSION
            and dimension != "lifecycle"
            and state.affected_segment == "new_users"
        ):
            expected_filter = "new"
        elif (
            state.investigation_profile == InvestigationProfile.CONVERSION
            and dimension != "lifecycle"
            and state.affected_segment == "returning_users"
        ):
            expected_filter = "returning"
        if proposal.lifecycle_filter != expected_filter:
            return GuardResult(
                status=GuardStatus.REJECTED,
                reason=GuardReason.FILTER_INCONSISTENT,
            )
        return GuardResult(status=GuardStatus.ACCEPTED, reason=GuardReason.ACCEPTED)
