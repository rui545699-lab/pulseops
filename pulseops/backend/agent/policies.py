from __future__ import annotations

from pulseops.backend.agent.prompts import (
    DO_NOT_RECOMMEND,
    ROOT_CAUSE_UNKNOWNS,
    UNVERIFIED_HYPOTHESES,
)
from pulseops.backend.agent.state import (
    AgentState,
    HypothesisRecord,
    HypothesisStatus,
    RecommendedActionType,
)
from pulseops.backend.schemas.analytics import (
    Confidence,
    FunnelComparison,
    MetricResult,
    RecommendedStatus,
    SegmentComparison,
)


def select_signal(metrics: list[MetricResult]) -> MetricResult | None:
    candidates = [metric for metric in metrics if metric.needs_investigation]
    return min(candidates, key=lambda metric: metric.delta_pp) if candidates else None


def set_signal_confidence(state: AgentState, funnel: FunnelComparison) -> None:
    if (
        funnel.session_delta_pp <= -5
        and funnel.baseline.view_sessions >= 1000
        and funnel.target.view_sessions >= 1000
    ):
        state.signal_confidence = Confidence.HIGH
    else:
        state.signal_confidence = Confidence.MEDIUM
    state.evidence.append(
        f"Strict session {funnel.entry_event}→{funnel.conversion_event} conversion declined "
        f"by {abs(funnel.session_delta_pp):.2f} percentage points."
    )


def apply_segment_policy(state: AgentState, result: SegmentComparison) -> HypothesisRecord | None:
    sufficient = [row for row in result.segments if row.sample_sufficient and row.change_pp is not None]
    if result.dimension == "lifecycle":
        return _apply_lifecycle(state, sufficient)
    if result.dimension == "device":
        return _apply_device(state, sufficient)
    if result.dimension == "acquisition":
        return _apply_acquisition(state, sufficient)
    if result.dimension == "category":
        return _apply_category(state, sufficient)
    raise ValueError(f"unsupported investigation dimension: {result.dimension}")


def _apply_lifecycle(state: AgentState, rows: list) -> HypothesisRecord | None:
    indexed = {row.segment.lower(): row for row in rows}
    new = indexed.get("new")
    returning = indexed.get("returning")
    if new and returning and new.change_pp <= -5 and abs(returning.change_pp) < 2:
        state.affected_segment = "new_users"
        state.evidence.extend(
            [
                "The decline is concentrated in New Users.",
                "Returning Users remained broadly stable.",
            ]
        )
    elif rows:
        worst = min(rows, key=lambda row: row.change_pp)
        if worst.change_pp <= -5:
            state.affected_segment = f"{worst.segment.lower()}_users"
            state.evidence.append(
                f"The largest lifecycle decline was observed for {worst.segment} users."
            )
    return None


def _apply_device(state: AgentState, rows: list) -> HypothesisRecord | None:
    major = [row for row in rows if row.baseline_share >= 10]
    if len(major) >= 2 and all(row.change_pp <= -5 for row in major):
        state.evidence.append("Major device types declined in parallel.")
        record = HypothesisRecord(
            code="DEVICE_CONCENTRATION",
            reason="decline is broad across major device types",
            status=HypothesisStatus.REJECTED,
        )
        state.rejected_hypotheses.append(record)
        return record
    declining = [row for row in major if row.change_pp <= -5]
    stable = [row for row in major if abs(row.change_pp) < 2]
    if len(declining) == 1 and stable:
        segment = declining[0].segment
        state.evidence.append(f"The decline is concentrated in the {segment} device segment.")
        record = HypothesisRecord(
            code="DEVICE_CONCENTRATION",
            reason=f"{segment} declined materially while another major device segment stayed stable",
            status=HypothesisStatus.SUPPORTED,
        )
        state.supported_hypotheses.append(record)
        return record
    return None


def _apply_acquisition(state: AgentState, rows: list) -> HypothesisRecord | None:
    major = [row for row in rows if row.baseline_share >= 5]
    mix_stable = bool(major) and all(abs(row.target_share - row.baseline_share) < 8 for row in major)
    sources_declined = bool(major) and all(row.change_pp <= -3 for row in major)
    if mix_stable and sources_declined:
        state.evidence.append(
            "Major acquisition sources declined within-source while channel mix stayed broadly stable."
        )
        record = HypothesisRecord(
            code="ACQUISITION_MIX_EXPLANATION",
            reason="major sources declined within-source while acquisition shares stayed broadly stable",
            status=HypothesisStatus.REJECTED,
        )
        state.rejected_hypotheses.append(record)
        return record
    return None


def _apply_category(state: AgentState, rows: list) -> HypothesisRecord | None:
    changes = [row.change_pp for row in rows]
    if changes and min(changes) < 0 < max(changes):
        state.evidence.append("Category effects were mixed across sufficiently sampled categories.")
        state.unknowns.append(
            "Mixed category movements do not establish a single category root cause."
        )
    else:
        state.unknowns.append("Available category evidence does not establish a single root cause.")
    record = HypothesisRecord(
        code="CATEGORY_CONCENTRATION",
        reason="category results do not provide sufficient evidence for a concentrated explanation",
        status=HypothesisStatus.INSUFFICIENT_EVIDENCE,
    )
    state.insufficient_hypotheses.append(record)
    return record


def finalize_needs_evidence(state: AgentState) -> None:
    state.root_cause_confidence = Confidence.LOW
    state.recommended_status = RecommendedStatus.NEEDS_EVIDENCE
    state.recommended_action_type = RecommendedActionType.EVIDENCE_COLLECTION
    state.hypotheses = list(UNVERIFIED_HYPOTHESES)
    for item in ROOT_CAUSE_UNKNOWNS:
        if item not in state.unknowns:
            state.unknowns.append(item)
    state.recommended_next_action = (
        "Collect landing-page and page-version history, promotion and pricing configuration, "
        "inventory, performance telemetry, and user feedback before choosing an intervention."
    )
    state.do_not_recommend_yet = list(DO_NOT_RECOMMEND)
