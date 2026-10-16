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
    LifecycleSegmentComparison,
    GrowthSegmentComparison,
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


def apply_lifecycle_segment_policy(
    state: AgentState, result: LifecycleSegmentComparison
) -> HypothesisRecord:
    if result.dimension == "acquisition":
        material = [segment for segment in result.segments if segment.sample_sufficient]
        rejected = bool(material) and all(segment.change_pp < 0 for segment in material) and abs(
            result.composition_effect_pp
        ) < 0.5
        record = HypothesisRecord(
            code="ACQUISITION_MIX_EXPLANATION",
            reason=(
                "composition was stable while material sources declined within-source"
                if rejected
                else "acquisition evidence does not isolate a stable mix explanation"
            ),
            status=(HypothesisStatus.REJECTED if rejected else HypothesisStatus.INSUFFICIENT_EVIDENCE),
        )
        (state.rejected_hypotheses if rejected else state.insufficient_hypotheses).append(record)
        if rejected:
            state.evidence.append("Acquisition mix stayed stable while major sources declined within-source.")
        return record
    if result.dimension == "device":
        material = [segment for segment in result.segments if segment.sample_sufficient]
        rejected = len(material) >= 2 and all(segment.change_pp < 0 for segment in material) and abs(
            result.composition_effect_pp
        ) < 0.5
        record = HypothesisRecord(
            code="DEVICE_CONCENTRATION",
            reason=(
                "material device segments declined in parallel while device mix stayed stable"
                if rejected
                else "device evidence does not establish a concentrated explanation"
            ),
            status=(HypothesisStatus.REJECTED if rejected else HypothesisStatus.INSUFFICIENT_EVIDENCE),
        )
        (state.rejected_hypotheses if rejected else state.insufficient_hypotheses).append(record)
        if rejected:
            state.evidence.append("Material device segments declined in parallel while device mix stayed stable.")
        return record
    if result.dimension == "activation_depth":
        by_segment = {segment.segment: segment for segment in result.segments}
        shallow = by_segment.get("SHALLOW")
        intent = by_segment.get("INTENT")
        supported = (
            shallow is not None
            and intent is not None
            and shallow.share_change_pp > 0
            and intent.share_change_pp < 0
            and result.composition_effect_pp < 0
        )
        record = HypothesisRecord(
            code="ACTIVATION_DEPTH_SHIFT",
            reason=(
                "the observed first-session composition shifted toward SHALLOW users"
                if supported
                else "activation-depth evidence does not establish a directional composition shift"
            ),
            status=(HypothesisStatus.SUPPORTED if supported else HypothesisStatus.INSUFFICIENT_EVIDENCE),
        )
        (state.supported_hypotheses if supported else state.insufficient_hypotheses).append(record)
        if supported:
            state.evidence.append(
                f"SHALLOW share increased {shallow.share_change_pp:.2f}pp and INTENT share "
                f"decreased {abs(intent.share_change_pp):.2f}pp; composition explains about "
                f"{result.composition_share_of_total_decline_pct:.2f}% of the decline while "
                f"within-segment decline explains {result.within_segment_share_of_total_decline_pct:.2f}%."
            )
        return record
    raise ValueError(f"unsupported lifecycle investigation dimension: {result.dimension}")


def finalize_lifecycle_needs_evidence(state: AgentState) -> None:
    state.root_cause_confidence = Confidence.LOW
    state.recommended_status = RecommendedStatus.NEEDS_EVIDENCE
    state.recommended_action_type = RecommendedActionType.EVIDENCE_COLLECTION
    state.hypotheses = [
        "First-session activation becoming shallower may contribute to part of the decline.",
        "Calendar seasonality may contribute to the temporary component.",
        "Broader period-specific factors may affect return behavior.",
    ]
    state.unknowns = [
        "Whether calendar or period-specific effects contributed to the change is unknown.",
        "Why return declined inside every activation bucket is unknown.",
        "Campaign, pricing, inventory, UX, performance, consent, and identity-resolution changes are unknown.",
        "Longer-window retention and year-over-year behavior are unknown.",
    ]
    state.recommended_next_action = (
        "Collect campaign, merchandising, UX, performance, consent, and identity evidence "
        "before selecting a lifecycle intervention."
    )
    state.do_not_recommend_yet = [
        "Do not launch a coupon blast or broad reactivation campaign.",
        "Do not send notification spam or a full-audience promotion.",
        "Do not redesign the UX before the within-segment decline is explained.",
    ]


def apply_growth_segment_policy(
    state: AgentState, result: GrowthSegmentComparison
) -> HypothesisRecord:
    """Record observational breadth without turning it into a causal explanation."""
    material = [segment for segment in result.segments if segment.sample_sufficient]
    broad = len(material) >= 2 and all(segment.change_pp > 0 for segment in material)
    code = f"{result.dimension.upper()}_GROWTH_CONCENTRATION"
    record = HypothesisRecord(
        code=code,
        reason=(
            f"the observed lift is broad across material {result.dimension} segments"
            if broad
            else f"{result.dimension} evidence does not isolate a single growth mechanism"
        ),
        status=(HypothesisStatus.SUPPORTED if broad else HypothesisStatus.INSUFFICIENT_EVIDENCE),
    )
    (state.supported_hypotheses if broad else state.insufficient_hypotheses).append(record)
    if broad:
        state.evidence.append(
            f"The checkout-to-purchase lift was observed across material {result.dimension} segments."
        )
        if abs(result.within_segment_effect_pp) > abs(result.composition_effect_pp):
            state.evidence.append(
                f"Within-segment improvement ({result.within_segment_effect_pp:+.2f}pp) exceeded "
                f"composition effect ({result.composition_effect_pp:+.2f}pp) for {result.dimension}."
            )
    else:
        state.unknowns.append(
            f"{result.dimension.capitalize()} results do not establish a single growth mechanism."
        )
    return record


def finalize_positive_growth(state: AgentState) -> None:
    state.root_cause_confidence = Confidence.LOW
    state.recommended_status = RecommendedStatus.READY_FOR_REPLICATION_TEST
    state.recommended_action_type = RecommendedActionType.REPLICATION_TEST
    state.hypotheses = [
        "Pricing or promotion context may contribute to the observed lift.",
        "Checkout UX, payment experience, merchandising, inventory, or calendar context may contribute to the observed lift.",
        "The validated lift may be repeatable, but its mechanism remains unproven.",
    ]
    state.unknowns = [
        *state.unknowns,
        "Exact promotion configuration, pricing, UX or payment, merchandising, and inventory changes are unknown.",
        "A validated lift does not establish a causal mechanism or justify a broad rollout.",
        "Whether the observed lift can be intentionally recreated remains unknown.",
    ]
    state.recommended_next_action = (
        "Design a bounded replication test with documented context and pre-specified success criteria."
    )
    state.do_not_recommend_yet = [
        "Do not scale to all users before a bounded replication test.",
        "Do not increase budget or roll out globally without causal evidence.",
        "Do not attribute the lift to a single segment or intervention."
    ]
