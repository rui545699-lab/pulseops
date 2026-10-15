from __future__ import annotations

from pulseops.backend.agent.state import AgentState

ALLOWED_DIMENSIONS = ("lifecycle", "device", "acquisition", "category")


def next_dimension(state: AgentState) -> str | None:
    """Choose a permitted, not-yet-investigated dimension within budget."""
    if state.remaining_investigation_budget <= 0:
        return None
    if state.data_quality_status != "PASS" or state.detected_signal is None:
        return None
    if state.supported_hypotheses:
        return None
    investigated = set(state.investigated_dimensions)
    return next((item for item in ALLOWED_DIMENSIONS if item not in investigated), None)


def continuation_reason(state: AgentState, dimension: str | None) -> str:
    if state.supported_hypotheses:
        return "A focused pattern is supported; stop broad drilldown and collect evidence for that hypothesis."
    remaining = [item for item in ALLOWED_DIMENSIONS if item not in state.investigated_dimensions]
    if not remaining:
        return "All permitted dimensions are complete; no confirmed root cause supports further drilldown."
    if state.remaining_investigation_budget <= 0:
        return "Investigation budget exhausted while permitted dimensions remain uninvestigated."
    if dimension is None:
        return "All permitted dimensions are complete; no confirmed root cause supports further drilldown."
    if dimension == "lifecycle":
        return "A material signal exists; identify whether the decline is concentrated by lifecycle."
    if state.affected_segment:
        return f"Root cause remains unconfirmed; investigate {dimension} within {state.affected_segment}."
    return f"Root cause remains unconfirmed; investigate the next permitted dimension: {dimension}."
