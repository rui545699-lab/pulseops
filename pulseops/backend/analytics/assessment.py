from __future__ import annotations

from pulseops.backend.schemas.analytics import (
    Confidence,
    FunnelComparison,
    OperationalAssessment,
    RecommendedStatus,
    SegmentComparison,
)


def _segments(comparison: SegmentComparison) -> dict[str, object]:
    return {segment.segment.lower(): segment for segment in comparison.segments}


def assess_case(
    funnel: FunnelComparison,
    comparisons: dict[str, SegmentComparison],
) -> OperationalAssessment:
    evidence: list[str] = []
    unknowns: list[str] = []

    signal_high = (
        funnel.session_delta_pp <= -5
        and funnel.baseline.view_sessions >= 1000
        and funnel.target.view_sessions >= 1000
    )
    if signal_high:
        evidence.append("Strict session View→Cart conversion declined materially.")

    lifecycle = _segments(comparisons["lifecycle"])
    new = lifecycle.get("new")
    returning = lifecycle.get("returning")
    if new and new.change_pp is not None and new.change_pp <= -5:
        evidence.append("The decline is concentrated in New Users.")
    if returning and returning.change_pp is not None and abs(returning.change_pp) < 2:
        evidence.append("Returning Users remained broadly stable.")

    device = [s for s in comparisons["device"].segments if s.sample_sufficient]
    major_devices = [s for s in device if s.baseline_share >= 10]
    if len(major_devices) >= 2 and all((s.change_pp or 0) < -5 for s in major_devices):
        evidence.append("Desktop and Mobile both declined; device is not a primary explanation.")

    acquisition = [s for s in comparisons["acquisition"].segments if s.sample_sufficient]
    major_sources = [s for s in acquisition if s.baseline_share >= 5]
    mix_stable = major_sources and all(abs(s.target_share - s.baseline_share) < 8 for s in major_sources)
    sources_declined = major_sources and all((s.change_pp or 0) < -3 for s in major_sources)
    if mix_stable and sources_declined:
        evidence.append("Major acquisition sources declined within-source while mix stayed broadly stable.")

    category = [s for s in comparisons["category"].segments if s.sample_sufficient]
    category_changes = [s.change_pp for s in category if s.change_pp is not None]
    if category_changes and min(category_changes) < 0 < max(category_changes):
        unknowns.append("Category movements are mixed and do not establish a single category root cause.")
    else:
        unknowns.append("Available category evidence does not establish a single root cause.")

    unknowns.append("A causal mechanism requires additional product, instrumentation, or experiment evidence.")
    return OperationalAssessment(
        signal_confidence=Confidence.HIGH if signal_high else Confidence.MEDIUM,
        root_cause_confidence=Confidence.LOW,
        recommended_status=RecommendedStatus.NEEDS_EVIDENCE,
        evidence=evidence,
        hypotheses=[],
        unknowns=unknowns,
    )

