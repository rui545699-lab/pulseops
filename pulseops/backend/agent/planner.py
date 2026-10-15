from __future__ import annotations

import json
from collections.abc import Sequence
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from pulseops.backend.agent.router import next_dimension
from pulseops.backend.agent.state import AgentState


class PlannerMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class PlannerAction(str, Enum):
    INVESTIGATE = "INVESTIGATE"
    STOP = "STOP"


class PlannerProposal(BaseModel):
    """A proposal only; PolicyGuard decides whether it may execute."""

    model_config = ConfigDict(extra="forbid")

    action: PlannerAction
    dimension: str | None = None
    lifecycle_filter: str | None = None
    rationale: str = Field(min_length=1, max_length=1000)
    hypothesis_code: str | None = Field(default=None, max_length=100)


class PlannerProtocol(Protocol):
    def plan(self, state: AgentState) -> PlannerProposal | dict[str, Any] | str: ...


class DeterministicPlanner:
    def plan(self, state: AgentState) -> PlannerProposal:
        dimension = next_dimension(state)
        if dimension is None:
            return PlannerProposal(
                action=PlannerAction.STOP,
                rationale="Deterministic stop policy found no permitted next investigation.",
            )
        lifecycle_filter = None
        if dimension != "lifecycle" and state.affected_segment == "new_users":
            lifecycle_filter = "new"
        elif dimension != "lifecycle" and state.affected_segment == "returning_users":
            lifecycle_filter = "returning"
        return PlannerProposal(
            action=PlannerAction.INVESTIGATE,
            dimension=dimension,
            lifecycle_filter=lifecycle_filter,
            rationale=f"Select the next permitted uninvestigated dimension: {dimension}.",
        )


class SequencePlanner:
    """Small fake planner for offline tests and deterministic demonstrations."""

    def __init__(self, outputs: Sequence[PlannerProposal | dict[str, Any] | str | Exception]):
        self._outputs = list(outputs)
        self._index = 0

    def plan(self, state: AgentState) -> PlannerProposal | dict[str, Any] | str:
        if self._index >= len(self._outputs):
            raise RuntimeError("fake planner has no remaining output")
        output = self._outputs[self._index]
        self._index += 1
        if isinstance(output, Exception):
            raise output
        return output


def parse_planner_output(raw: PlannerProposal | dict[str, Any] | str) -> PlannerProposal:
    if isinstance(raw, PlannerProposal):
        raw = raw.model_dump()
    if isinstance(raw, str):
        raw = json.loads(raw)
    return PlannerProposal.model_validate(raw)
