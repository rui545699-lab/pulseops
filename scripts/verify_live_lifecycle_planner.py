"""Run bounded live DeepSeek planning against Case 02's offline Golden analytics."""

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
from pulseops.backend.fixtures.lifecycle import CASE_02, Case02GoldenTools
from pulseops.backend.schemas.analytics import LifecycleWindows


DEFAULT_JSON = ROOT / "outputs" / "v0_2_live_llm_verification.json"
DEFAULT_MARKDOWN = ROOT / "outputs" / "v0_2_live_llm_verification.md"
WINDOWS = LifecycleWindows.model_validate(CASE_02["windows"])
EXPECTED_FACTS = {
    "baseline_rate": 8.33,
    "target_rate": 5.11,
    "delta_pp": -3.22,
    "post_rate": 6.90,
    "recovery_ratio": 55.73,
    "risk_pattern": "PARTIAL_RECOVERY",
    "signal_confidence": "HIGH",
    "root_cause_confidence": "LOW",
    "recommended_status": "NEEDS_EVIDENCE",
    "recommended_action_type": "EVIDENCE_COLLECTION",
    "stop_reason": "ALLOWED_DIMENSIONS_EXHAUSTED",
}
CAUSAL_PATTERNS = (
    re.compile(r"\bcauses?\s+(?:the\s+)?(?:decline|drop|change|risk)\b", re.IGNORECASE),
    re.compile(r"\bcaused\s+(?:the\s+)?(?:decline|drop|change|risk)\b", re.IGNORECASE),
    re.compile(r"\b(?:decline|drop|change|risk)\s+(?:was|is)\s+caused\s+by\b", re.IGNORECASE),
    re.compile(r"\bis the root cause\b", re.IGNORECASE),
    re.compile(r"\bdrives?\s+(?:the\s+)?(?:decline|drop|change|risk)\b", re.IGNORECASE),
    re.compile(r"\bexplains?\s+(?:the\s+)?(?:decline|drop|change|risk)\b", re.IGNORECASE),
    re.compile(r"\bis the reason for\b", re.IGNORECASE),
)
CAUTIOUS_ROOT_CAUSE_PATTERNS = (
    re.compile(r"\broot[- ]cause remains unknown\b", re.IGNORECASE),
    re.compile(r"\bno causal evidence\b", re.IGNORECASE),
    re.compile(r"\bavoid inventing a root cause\b", re.IGNORECASE),
    re.compile(r"\broot[- ]cause confidence is low\b", re.IGNORECASE),
)
INTERVENTION_PATTERNS = (
    re.compile(r"\b(?:coupon|discount|promotion|reactivation|push notification)", re.IGNORECASE),
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
        "root_cause_confidence": state.root_cause_confidence.value,
    }


class AuditingPlanner:
    """Records the exact Planner-visible state while delegating all planning to DeepSeek."""

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


def summarize_run(state, run_id: str, before_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    steps = proposal_log(state, before_snapshots)
    guard_reasons = Counter(item["guard_reason"] for item in steps if item["guard_reason"])
    fallback_reasons = Counter(item["fallback_reason"] for item in steps if item["fallback_reason"])
    final_text = state.evidence + state.hypotheses + state.unknowns
    proposal_text = [item["rationale"] or "" for item in steps]
    causal = text_has(CAUSAL_PATTERNS, final_text)
    interventions = text_has(INTERVENTION_PATTERNS, final_text)
    facts = {
        "baseline_rate": state.retention_result.baseline.return_rate_7d,
        "target_rate": state.retention_result.target.return_rate_7d,
        "delta_pp": state.retention_result.delta_pp,
        "post_rate": state.retention_result.post.return_rate_7d,
        "recovery_ratio": state.recovery_result.recovery_ratio_pct,
        "risk_pattern": state.recovery_result.risk_pattern.value,
        "signal_confidence": state.signal_confidence.value,
        "root_cause_confidence": state.root_cause_confidence.value,
        "recommended_status": state.recommended_status.value,
        "recommended_action_type": state.recommended_action_type.value,
        "stop_reason": state.stop_reason.value,
    }
    preflight = [step.node for step in state.agent_steps[:4]]
    accepted = sum(item["guard_status"] == "ACCEPTED" for item in steps)
    rejected = sum(item["guard_status"] == "REJECTED" for item in steps)
    fallback_count = sum(item["fallback_used"] for item in steps)
    illegal_reasons = {
        "DIMENSION_NOT_ALLOWED",
        "FILTER_INCONSISTENT",
        "BUDGET_EXHAUSTED",
        "UNSUPPORTED_CAUSAL_CLAIM",
        "INTERVENTION_NOT_ALLOWED",
    }
    passed = (
        preflight
        == ["VALIDATE_DATA", "ANALYZE_RETENTION", "CHECK_RETURN_TIMING", "CHECK_RECOVERY"]
        and facts == EXPECTED_FACTS
        and len(state.investigated_dimensions) == len(set(state.investigated_dimensions))
        and set(state.investigated_dimensions) <= {"acquisition", "device", "activation_depth"}
        and all(item["executed_lifecycle_filter"] is None for item in steps)
        and not causal
        and not interventions
        and accepted > 0
        and rejected == 0
    )
    return {
        "run_id": run_id,
        "preflight": preflight,
        "planner_sequence": [item["proposed_dimension"] for item in steps],
        "investigation_order": state.investigated_dimensions,
        "planner_guard_log": steps,
        "proposal_count": len(steps),
        "accepted": accepted,
        "rejected": rejected,
        "fallback_count": fallback_count,
        "fallback_reasons": dict(fallback_reasons),
        "illegal_proposals": sum(guard_reasons[reason] for reason in illegal_reasons),
        "duplicate_proposals": guard_reasons["DUPLICATE_DIMENSION"],
        "premature_stops": guard_reasons["PREMATURE_STOP"],
        "unsupported_causal_claims": guard_reasons["UNSUPPORTED_CAUSAL_CLAIM"],
        "intervention_boundary_violations": guard_reasons["INTERVENTION_NOT_ALLOWED"],
        "filter_inconsistent": guard_reasons["FILTER_INCONSISTENT"],
        "guard_false_positives": sum(
            item["guard_reason"] == "UNSUPPORTED_CAUSAL_CLAIM"
            and text_has(CAUTIOUS_ROOT_CAUSE_PATTERNS, [item["rationale"] or ""])
            for item in steps
        ),
        "provider_rationale_causal_claim": text_has(CAUSAL_PATTERNS, proposal_text),
        "final_content_causal_claim": causal,
        "final_content_intervention_recommendation": interventions,
        "final_facts": facts,
        "evidence": state.evidence,
        "hypotheses": state.hypotheses,
        "unknowns": state.unknowns,
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
        run_id = f"case-02-live-{index}"
        state = InvestigationAgent(
            Case02GoldenTools(), planner_mode="llm", planner=auditing_planner
        ).run(WINDOWS, run_id=run_id, investigation_profile=InvestigationProfile.LIFECYCLE_RISK)
        results.append(summarize_run(state, run_id, auditing_planner.snapshots_for(run_id)))

    summary = {
        "run_count": len(results),
        "total_proposals": sum(item["proposal_count"] for item in results),
        "accepted_proposals": sum(item["accepted"] for item in results),
        "rejected_proposals": sum(item["rejected"] for item in results),
        "fallback_count": sum(item["fallback_count"] for item in results),
        "illegal_proposals": sum(item["illegal_proposals"] for item in results),
        "duplicate_proposals": sum(item["duplicate_proposals"] for item in results),
        "premature_stops": sum(item["premature_stops"] for item in results),
        "unsupported_causal_claims": sum(item["unsupported_causal_claims"] for item in results),
        "intervention_boundary_violations": sum(
            item["intervention_boundary_violations"] for item in results
        ),
        "filter_inconsistent": sum(item["filter_inconsistent"] for item in results),
        "guard_false_positives": sum(item["guard_false_positives"] for item in results),
        "final_state_consistent": len({tuple(item["final_facts"].items()) for item in results}) == 1,
        "overall_result": "PASS" if all(item["passed"] for item in results) else "FAIL",
    }
    return {
        "verification": "V0.2 Lifecycle Risk Live DeepSeek Planner Verification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": planner.provider,
        "configured_model": model,
        "response_model_identifier": planner.model_identifier,
        "analytics_source": CASE_02["provenance"],
        "windows": WINDOWS.model_dump(mode="json"),
        "runs": results,
        "summary": summary,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# V0.2 Lifecycle Risk Live DeepSeek Planner Verification",
        "",
        f"- Provider: `{report['provider']}`",
        f"- Model: `{report['response_model_identifier']}`",
        "- Analytics input: Case 02 verified Golden Fixture; live provider used only for bounded planning.",
        f"- Overall result: **{summary['overall_result']}**",
        "",
        "## Aggregate",
        "",
        f"- Runs: {summary['run_count']}",
        f"- Proposals / accepted / rejected: {summary['total_proposals']} / {summary['accepted_proposals']} / {summary['rejected_proposals']}",
        f"- Fallbacks: {summary['fallback_count']}",
        f"- Illegal / duplicate / premature STOP: {summary['illegal_proposals']} / {summary['duplicate_proposals']} / {summary['premature_stops']}",
        f"- Filter inconsistent / Guard false positives: {summary['filter_inconsistent']} / {summary['guard_false_positives']}",
        f"- Unsupported causal claims / intervention boundary violations: {summary['unsupported_causal_claims']} / {summary['intervention_boundary_violations']}",
        "",
        "## Runs",
        "",
        "| Run | Planner sequence | Executed order | Accepted | Rejected | Fallbacks | Stop | Passed |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for item in report["runs"]:
        lines.append(
            f"| {item['run_id']} | {' → '.join(str(value) for value in item['planner_sequence'])} | "
            f"{' → '.join(item['investigation_order'])} | {item['accepted']} | {item['rejected']} | "
            f"{item['fallback_count']} | {item['final_facts']['stop_reason']} | {item['passed']} |"
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
        print("Lifecycle live verification requires exactly 3 runs.", file=sys.stderr)
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
