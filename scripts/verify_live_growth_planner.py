"""Run bounded live DeepSeek planning against Case 03's offline Golden analytics."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.providers.deepseek import DeepSeekPlanner, DeepSeekPlannerConfig
from pulseops.backend.agent.router import allowed_dimensions, next_dimension
from pulseops.backend.agent.state import InvestigationProfile
from pulseops.backend.fixtures.growth import CASE_03, Case03GoldenTools
from pulseops.backend.schemas.analytics import GrowthWindows


DEFAULT_JSON = ROOT / "outputs" / "v0_3_live_llm_verification.json"
DEFAULT_MARKDOWN = ROOT / "outputs" / "v0_3_live_llm_verification.md"
WINDOWS = GrowthWindows.model_validate(CASE_03["windows"])
EXPECTED_FACTS = {
    "baseline_rate": 40.35,
    "baseline_counts": (1_046, 2_592),
    "growth_rate": 51.14,
    "growth_counts": (1_304, 2_550),
    "delta_pp": 10.78,
    "confirmation_rate": 55.07,
    "confirmation_counts": (369, 670),
    "holdout_1_rate": 48.74,
    "holdout_1_counts": (386, 792),
    "holdout_2_rate": 55.13,
    "holdout_2_counts": (666, 1_208),
    "localization": "BROAD",
    "reproducibility": "REPRODUCED",
    "growth_signal_confidence": "HIGH",
    "reproducibility_confidence": "HIGH",
    "recommended_status": "READY_FOR_REPLICATION_TEST",
    "recommended_action_type": "REPLICATION_TEST",
    "stop_reason": "ALLOWED_DIMENSIONS_EXHAUSTED",
}
CAUSAL_PATTERNS = (
    re.compile(r"\bcauses?\s+(?:the\s+)?(?:observed\s+)?(?:lift|growth|increase)\b", re.IGNORECASE),
    re.compile(r"\b(?:campaign|ux|pricing|promotion)\s+(?:caused|drove|explains?)\b", re.IGNORECASE),
    re.compile(r"\b(?:lift|growth|increase)\s+(?:was|is)\s+caused\s+by\b", re.IGNORECASE),
    re.compile(r"\bis the root cause\b", re.IGNORECASE),
    re.compile(r"\bproves that\b", re.IGNORECASE),
)
SCALE_PATTERNS = (
    re.compile(r"\bscale(?: this)? broadly\b", re.IGNORECASE),
    re.compile(r"\bscale to all users\b", re.IGNORECASE),
    re.compile(r"\broll ?out to everyone\b", re.IGNORECASE),
    re.compile(r"\bincrease (?:spend|budget)\b", re.IGNORECASE),
    re.compile(r"\bexpand (?:to|across) all users\b", re.IGNORECASE),
    re.compile(r"\b(?:deploy|roll out) globally\b", re.IGNORECASE),
    re.compile(r"\bcopy (?:the )?(?:experience )?to all segments\b", re.IGNORECASE),
    re.compile(r"\bbroad campaign scale\b", re.IGNORECASE),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args()


def env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    env_path = ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^\s*{re.escape(name)}\s*=\s*(.*?)\s*$", line)
        if match:
            candidate = match.group(1).strip().strip("\"'")
            return candidate or None
    return None


def text_has(patterns: tuple[re.Pattern[str], ...], texts: list[str]) -> bool:
    return any(pattern.search(text) for pattern in patterns for text in texts)


def state_snapshot(state) -> dict[str, Any]:
    remaining = [
        dimension for dimension in allowed_dimensions(state)
        if dimension not in state.investigated_dimensions
    ]
    return {
        "investigated_dimensions": list(state.investigated_dimensions),
        "remaining_dimensions": remaining,
        "remaining_budget": state.remaining_investigation_budget,
        "stop_allowed": next_dimension(state) is None,
        "growth_signal_confidence": (
            state.growth_signal_confidence.value if state.growth_signal_confidence else None
        ),
        "reproducibility": state.reproducibility.value if state.reproducibility else None,
        "localization": state.growth_localization,
    }


class AuditingPlanner:
    """Records Planner-visible state while delegating each proposal to DeepSeek."""

    def __init__(self, delegate: DeepSeekPlanner) -> None:
        self.delegate = delegate
        self._snapshots: dict[str, list[dict[str, Any]]] = {}

    def plan(self, state):
        self._snapshots.setdefault(state.run_id, []).append(state_snapshot(state))
        return self.delegate.plan(state)

    def snapshots_for(self, run_id: str) -> list[dict[str, Any]]:
        return self._snapshots.get(run_id, [])


def proposal_log(state, before_snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    planning_steps = [item for item in state.agent_steps if item.planner_mode == "llm"]
    for index, step in enumerate(planning_steps):
        proposal = step.planner_proposal or {}
        entries.append(
            {
                "step_order": step.step_order,
                "proposed_action": proposal.get("action"),
                "proposed_dimension": proposal.get("dimension"),
                "proposed_lifecycle_filter": proposal.get("lifecycle_filter"),
                "proposed_hypothesis_code": proposal.get("hypothesis_code"),
                "rationale": step.planner_rationale,
                "guard_status": step.guard_status,
                "guard_reason": step.guard_reason,
                "executed_tool": step.tool_name,
                "executed_dimension": step.tool_input.get("dimension"),
                "executed_lifecycle_filter": step.tool_input.get("lifecycle_filter"),
                "fallback_used": step.fallback_used,
                "fallback_reason": step.fallback_reason,
                "state_before": before_snapshots[index] if index < len(before_snapshots) else None,
                "state_after": (
                    before_snapshots[index + 1]
                    if index + 1 < len(before_snapshots)
                    else state_snapshot(state)
                ),
            }
        )
    return entries


def final_facts(state) -> dict[str, Any]:
    result = state.growth_result
    if result is None:
        raise ValueError("Growth verification requires deterministic GrowthComparison facts")
    return {
        "baseline_rate": result.baseline.conversion_rate,
        "baseline_counts": (result.baseline.purchase_after_checkout_sessions, result.baseline.checkout_sessions),
        "growth_rate": result.growth.conversion_rate,
        "growth_counts": (result.growth.purchase_after_checkout_sessions, result.growth.checkout_sessions),
        "delta_pp": result.delta_pp,
        "confirmation_rate": result.confirmation.conversion_rate,
        "confirmation_counts": (result.confirmation.purchase_after_checkout_sessions, result.confirmation.checkout_sessions),
        "holdout_1_rate": result.holdout_1.conversion_rate,
        "holdout_1_counts": (result.holdout_1.purchase_after_checkout_sessions, result.holdout_1.checkout_sessions),
        "holdout_2_rate": result.holdout_2.conversion_rate,
        "holdout_2_counts": (result.holdout_2.purchase_after_checkout_sessions, result.holdout_2.checkout_sessions),
        "localization": state.growth_localization,
        "reproducibility": state.reproducibility.value if state.reproducibility else None,
        "growth_signal_confidence": (
            state.growth_signal_confidence.value if state.growth_signal_confidence else None
        ),
        "reproducibility_confidence": (
            state.reproducibility_confidence.value if state.reproducibility_confidence else None
        ),
        "recommended_status": state.recommended_status.value if state.recommended_status else None,
        "recommended_action_type": state.recommended_action_type.value,
        "stop_reason": state.stop_reason.value if state.stop_reason else None,
    }


def summarize_run(state, run_id: str, before_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    steps = proposal_log(state, before_snapshots)
    guard_reasons = Counter(item["guard_reason"] for item in steps if item["guard_reason"])
    fallback_reasons = Counter(item["fallback_reason"] for item in steps if item["fallback_reason"])
    proposal_text = [item["rationale"] or "" for item in steps]
    facts = final_facts(state)
    evidence_text = " ".join(state.evidence)
    hypotheses_text = " ".join(state.hypotheses)
    unknowns_text = " ".join(state.unknowns)
    provider_causal_claim = text_has(CAUSAL_PATTERNS, proposal_text)
    provider_scale_recommendation = text_has(SCALE_PATTERNS, proposal_text)
    evidence_semantics = all(
        fragment in evidence_text
        for fragment in (
            "Strict Checkout→Purchase conversion increased",
            "Both Growth weeks improved",
            "Both Confirmation weeks remained above",
            "Holdout periods measured",
            "Within-segment improvement",
            "Average order value did not show an obvious collapse",
        )
    )
    hypothesis_semantics = all(
        fragment in hypotheses_text
        for fragment in ("Pricing or promotion", "Checkout UX", "payment experience", "merchandising", "calendar context")
    )
    unknown_semantics = all(
        fragment in unknowns_text
        for fragment in ("promotion configuration", "UX or payment", "inventory", "causal mechanism", "intentionally recreated")
    )
    accepted = sum(item["guard_status"] == "ACCEPTED" for item in steps)
    rejected = sum(item["guard_status"] == "REJECTED" for item in steps)
    fallback_count = sum(item["fallback_used"] for item in steps)
    legal_dimensions = {"lifecycle", "device", "acquisition"}
    preflight = [step.node for step in state.agent_steps[:5]]
    final_intervention_boundary_violation = (
        facts["recommended_action_type"] != "REPLICATION_TEST"
        or facts["recommended_status"] != "READY_FOR_REPLICATION_TEST"
    )
    passed = (
        preflight
        == [
            "VALIDATE_DATA",
            "ANALYZE_GROWTH",
            "CHECK_WEEKLY_PERSISTENCE",
            "CHECK_CONFIRMATION",
            "CHECK_HOLDOUT",
        ]
        and facts == EXPECTED_FACTS
        and len(state.investigated_dimensions) == len(set(state.investigated_dimensions))
        and set(state.investigated_dimensions) == legal_dimensions
        and all(item["proposed_lifecycle_filter"] is None for item in steps)
        and all(item["executed_lifecycle_filter"] is None for item in steps)
        and accepted == len(legal_dimensions)
        and rejected == 0
        and fallback_count == 0
        and not provider_causal_claim
        and not provider_scale_recommendation
        and not final_intervention_boundary_violation
        and evidence_semantics
        and hypothesis_semantics
        and unknown_semantics
    )
    return {
        "run_id": run_id,
        "preflight": preflight,
        "planner_sequence": [item["proposed_dimension"] for item in steps],
        "proposed_filters": [item["proposed_lifecycle_filter"] for item in steps],
        "investigation_order": list(state.investigated_dimensions),
        "planner_guard_log": steps,
        "proposal_count": len(steps),
        "accepted": accepted,
        "rejected": rejected,
        "fallback_count": fallback_count,
        "fallback_reasons": dict(fallback_reasons),
        "illegal_proposals": sum(
            guard_reasons[reason]
            for reason in ("DIMENSION_NOT_ALLOWED", "BUDGET_EXHAUSTED")
        ),
        "filter_inconsistent": guard_reasons["FILTER_INCONSISTENT"],
        "duplicate_proposals": guard_reasons["DUPLICATE_DIMENSION"],
        "premature_stops": guard_reasons["PREMATURE_STOP"],
        "unsupported_causal_claims": guard_reasons["UNSUPPORTED_CAUSAL_CLAIM"],
        "broad_scale_violations": guard_reasons["INTERVENTION_NOT_ALLOWED"],
        "intervention_boundary_violations": int(final_intervention_boundary_violation),
        "provider_rationale_causal_claim": provider_causal_claim,
        "provider_rationale_scale_recommendation": provider_scale_recommendation,
        "evidence_semantics_preserved": evidence_semantics,
        "hypothesis_semantics_preserved": hypothesis_semantics,
        "unknown_semantics_preserved": unknown_semantics,
        "final_facts": facts,
        "passed": passed,
    }


def build_report(api_key: str, runs: int) -> dict[str, Any]:
    model = env_value("DEEPSEEK_MODEL") or DeepSeekPlannerConfig.model
    planner = DeepSeekPlanner(
        api_key,
        DeepSeekPlannerConfig(
            model=model,
            base_url=env_value("DEEPSEEK_BASE_URL") or DeepSeekPlannerConfig.base_url,
            timeout_seconds=float(env_value("DEEPSEEK_TIMEOUT_SECONDS") or "45"),
        ),
    )
    auditing_planner = AuditingPlanner(planner)
    results = []
    for index in range(1, runs + 1):
        run_id = f"case-03-live-{index}"
        state = InvestigationAgent(
            Case03GoldenTools(), planner_mode="llm", planner=auditing_planner
        ).run(WINDOWS, run_id=run_id, investigation_profile=InvestigationProfile.POSITIVE_GROWTH)
        results.append(summarize_run(state, run_id, auditing_planner.snapshots_for(run_id)))

    summary = {
        "run_count": len(results),
        "total_proposals": sum(item["proposal_count"] for item in results),
        "accepted_proposals": sum(item["accepted"] for item in results),
        "rejected_proposals": sum(item["rejected"] for item in results),
        "fallback_count": sum(item["fallback_count"] for item in results),
        "fallback_reasons": dict(
            Counter(reason for item in results for reason, count in item["fallback_reasons"].items() for _ in range(count))
        ),
        "illegal_proposals": sum(item["illegal_proposals"] for item in results),
        "filter_inconsistent": sum(item["filter_inconsistent"] for item in results),
        "duplicate_proposals": sum(item["duplicate_proposals"] for item in results),
        "premature_stops": sum(item["premature_stops"] for item in results),
        "unsupported_causal_claims": sum(item["unsupported_causal_claims"] for item in results),
        "broad_scale_violations": sum(item["broad_scale_violations"] for item in results),
        "intervention_boundary_violations": sum(item["intervention_boundary_violations"] for item in results),
        "final_state_consistent": len(
            {json.dumps(item["final_facts"], sort_keys=True) for item in results}
        ) == 1,
        "overall_result": "PASS" if all(item["passed"] for item in results) else "FAIL",
    }
    return {
        "verification": "V0.3 Positive Growth Live DeepSeek Planner Verification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": planner.provider,
        "configured_model": model,
        "response_model_identifier": planner.model_identifier,
        "analytics_source": CASE_03["provenance"],
        "windows": WINDOWS.model_dump(mode="json"),
        "runs": results,
        "summary": summary,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# V0.3 Positive Growth Live DeepSeek Planner Verification",
        "",
        f"- Provider: `{report['provider']}`",
        f"- Model: `{report['response_model_identifier']}`",
        "- Analytics input: Case 03 verified Golden Fixture; live provider used only for bounded planning.",
        f"- Overall result: **{summary['overall_result']}**",
        "",
        "## Aggregate",
        "",
        f"- Runs: {summary['run_count']}",
        f"- Proposals / accepted / rejected: {summary['total_proposals']} / {summary['accepted_proposals']} / {summary['rejected_proposals']}",
        f"- Fallbacks: {summary['fallback_count']} ({json.dumps(summary['fallback_reasons'])})",
        f"- Illegal / filter / duplicate / premature STOP: {summary['illegal_proposals']} / {summary['filter_inconsistent']} / {summary['duplicate_proposals']} / {summary['premature_stops']}",
        f"- Unsupported causal / broad-scale / intervention boundary: {summary['unsupported_causal_claims']} / {summary['broad_scale_violations']} / {summary['intervention_boundary_violations']}",
        "",
        "## Runs",
        "",
        "| Run | Planner sequence | Accepted | Rejected | Fallbacks | Stop | Passed |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for item in report["runs"]:
        lines.append(
            f"| {item['run_id']} | {' → '.join(str(value) for value in item['planner_sequence'])} | "
            f"{item['accepted']} | {item['rejected']} | {item['fallback_count']} | "
            f"{item['final_facts']['stop_reason']} | {item['passed']} |"
        )
    lines.extend(
        [
            "",
            "## Complete Planner → Guard → Executed Tool Log: Run 1",
            "",
            "```json",
            json.dumps(report["runs"][0]["planner_guard_log"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.runs != 3:
        print("Positive Growth live verification requires exactly 3 runs.", file=sys.stderr)
        return 2
    api_key = env_value("DEEPSEEK_API_KEY")
    if not api_key:
        print("Live verification not run: DEEPSEEK_API_KEY is not configured.", file=sys.stderr)
        return 2
    report = build_report(api_key, args.runs)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["overall_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
