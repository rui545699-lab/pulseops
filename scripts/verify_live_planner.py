from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.providers.deepseek import DeepSeekPlanner, DeepSeekPlannerConfig
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    DateWindows,
    MetricResult,
    MetricsScanResult,
    ValidationResult,
)
from pulseops.backend.tools.analyze_funnel import compare_funnel_rows
from pulseops.backend.tools.compare_segments import compare_segment_rows

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "case_01.json"
DEFAULT_JSON = ROOT / "outputs" / "m3_5_live_llm_verification.json"
DEFAULT_MARKDOWN = ROOT / "outputs" / "m3_5_live_llm_verification.md"
WINDOWS = DateWindows(
    baseline_start=date(2020, 12, 7),
    baseline_end=date(2020, 12, 13),
    target_start=date(2020, 12, 21),
    target_end=date(2020, 12, 27),
)
CAUSAL_PATTERNS = (
    re.compile(r"\bcaused the\b", re.IGNORECASE),
    re.compile(r"\bis the root cause\b", re.IGNORECASE),
    re.compile(r"\bresponsible for the decline\b", re.IGNORECASE),
    re.compile(r"导致了|根因是"),
)


class Case01FixtureTools:
    """Verified offline analytics facts; only planning is live."""

    def __init__(self) -> None:
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def validate_data(self, windows: DateWindows) -> ValidationResult:
        return ValidationResult(status=AnalysisStatus.PASS, analysis_allowed=True)

    def scan_metrics(self, windows: DateWindows) -> MetricsScanResult:
        funnel = self._funnel(["view_item", "add_to_cart"])
        return MetricsScanResult(
            metrics=[
                MetricResult(
                    name="View→Cart",
                    baseline_rate=funnel.baseline.session_conversion_rate,
                    target_rate=funnel.target.session_conversion_rate,
                    delta_pp=funnel.session_delta_pp,
                    baseline_sample_size=funnel.baseline.view_sessions,
                    target_sample_size=funnel.target.view_sessions,
                    needs_investigation=True,
                ),
                MetricResult(
                    name="Cart→Checkout",
                    baseline_rate=50,
                    target_rate=50,
                    delta_pp=0,
                    baseline_sample_size=1000,
                    target_sample_size=1000,
                    needs_investigation=False,
                ),
                MetricResult(
                    name="Checkout→Purchase",
                    baseline_rate=60,
                    target_rate=60,
                    delta_pp=0,
                    baseline_sample_size=800,
                    target_sample_size=800,
                    needs_investigation=False,
                ),
            ]
        )

    def analyze_funnel(self, events: list[str], windows: DateWindows):
        return self._funnel(events)

    def compare_segments(self, dimension: str, windows: DateWindows, lifecycle_filter: str | None):
        values = self.fixture["segments"][dimension]
        return compare_segment_rows(dimension, values["baseline"], values["target"])

    def _funnel(self, events: list[str]):
        return compare_funnel_rows(
            events,
            self.fixture["funnel"]["baseline"],
            self.fixture["funnel"]["target"],
        )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run five live DeepSeek planner verifications.")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args()


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    env_path = ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^\s*{re.escape(name)}\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        candidate = match.group(1).strip()
        if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in "\"'":
            candidate = candidate[1:-1]
        return candidate or None
    return None


def _has_unsupported_claim(texts: list[str]) -> bool:
    return any(pattern.search(text) for text in texts for pattern in CAUSAL_PATTERNS)


def _run_summary(state, run_id: str) -> dict[str, Any]:
    planning_steps = [step for step in state.agent_steps if step.planner_mode == "llm"]
    guard_reasons = Counter(step.guard_reason for step in planning_steps if step.guard_reason)
    fallback_reasons = Counter(step.fallback_reason for step in planning_steps if step.fallback_reason)
    proposal_text = [step.planner_rationale or "" for step in planning_steps]
    final_text = state.evidence + state.hypotheses + state.unknowns
    unsupported = _has_unsupported_claim(proposal_text + final_text)
    live_proposal_accepted = any(step.guard_status == "ACCEPTED" for step in planning_steps)
    log = []
    for step in planning_steps:
        log.append(
            {
                "step_order": step.step_order,
                "planner_proposal": step.planner_proposal,
                "planner_rationale": step.planner_rationale,
                "guard_status": step.guard_status,
                "guard_reason": step.guard_reason,
                "fallback_used": step.fallback_used,
                "fallback_reason": step.fallback_reason,
                "executed_action": {
                    "tool_name": step.tool_name,
                    "dimension": step.tool_input.get("dimension"),
                    "lifecycle_filter": step.tool_input.get("lifecycle_filter"),
                },
            }
        )
    order = list(state.investigated_dimensions)
    filters_valid = all(
        item["executed_action"]["lifecycle_filter"] == (None if index == 0 else "new")
        for index, item in enumerate(log)
    )
    run_passed = all(
        (
            bool(order) and order[0] == "lifecycle",
            len(order) == len(set(order)),
            len(order) <= 4,
            filters_valid,
            state.root_cause_confidence == "LOW",
            state.recommended_status == "NEEDS_EVIDENCE",
            state.recommended_action_type == "EVIDENCE_COLLECTION",
            not unsupported,
            live_proposal_accepted,
        )
    )
    return {
        "run_id": run_id,
        "planner_guard_log": log,
        "proposal_count": len(planning_steps),
        "guard_accepted_count": sum(step.guard_status == "ACCEPTED" for step in planning_steps),
        "guard_rejected_count": sum(step.guard_status == "REJECTED" for step in planning_steps),
        "fallback_count": sum(step.fallback_used for step in planning_steps),
        "fallback_reasons": dict(fallback_reasons),
        "illegal_proposal_count": guard_reasons["DIMENSION_NOT_ALLOWED"],
        "duplicate_proposal_count": guard_reasons["DUPLICATE_DIMENSION"],
        "premature_stop_count": guard_reasons["PREMATURE_STOP"],
        "investigation_order": order,
        "stop_reason": state.stop_reason.value,
        "signal_confidence": state.signal_confidence.value,
        "root_cause_confidence": state.root_cause_confidence.value,
        "recommended_status": state.recommended_status.value,
        "recommended_action_type": state.recommended_action_type.value,
        "unsupported_causal_claim": unsupported,
        "live_proposal_accepted": live_proposal_accepted,
        "run_passed": run_passed,
        "final_output": {
            "evidence": state.evidence,
            "hypotheses": state.hypotheses,
            "unknowns": state.unknowns,
        },
    }


def build_report(api_key: str, runs: int) -> dict[str, Any]:
    model = _env_value("DEEPSEEK_MODEL") or "deepseek-flash"
    base_url = _env_value("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    timeout = float(_env_value("DEEPSEEK_TIMEOUT_SECONDS") or "45")
    planner = DeepSeekPlanner(
        api_key,
        DeepSeekPlannerConfig(model=model, base_url=base_url, timeout_seconds=timeout),
    )
    results = []
    for index in range(1, runs + 1):
        run_id = f"case-01-live-{index}"
        state = InvestigationAgent(
            Case01FixtureTools(), planner_mode="llm", planner=planner
        ).run(WINDOWS, run_id=run_id)
        results.append(_run_summary(state, run_id))

    final_signatures = {
        (
            item["signal_confidence"],
            item["root_cause_confidence"],
            item["recommended_status"],
            item["recommended_action_type"],
        )
        for item in results
    }
    fallback_reasons = Counter()
    for item in results:
        fallback_reasons.update(item["fallback_reasons"])
    summary = {
        "run_count": len(results),
        "investigation_paths": [item["investigation_order"] for item in results],
        "proposal_count": sum(item["proposal_count"] for item in results),
        "guard_accepted_count": sum(item["guard_accepted_count"] for item in results),
        "guard_rejected_count": sum(item["guard_rejected_count"] for item in results),
        "fallback_count": sum(item["fallback_count"] for item in results),
        "fallback_reasons": dict(fallback_reasons),
        "illegal_proposal_count": sum(item["illegal_proposal_count"] for item in results),
        "duplicate_proposal_count": sum(item["duplicate_proposal_count"] for item in results),
        "premature_stop_count": sum(item["premature_stop_count"] for item in results),
        "final_status_consistent": len(final_signatures) == 1,
        "unsupported_causal_claim_count": sum(item["unsupported_causal_claim"] for item in results),
        "overall_verification_result": (
            "PASS" if all(item["run_passed"] for item in results) else "FAIL"
        ),
    }
    return {
        "verification": "Milestone 3.5 Live LLM Planner Verification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": planner.provider,
        "configured_model": model,
        "response_model_identifier": planner.model_identifier,
        "case": "Golden Case 01",
        "windows": WINDOWS.model_dump(mode="json"),
        "runs": results,
        "summary": summary,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Milestone 3.5 Live LLM Planner Verification",
        "",
        f"- Provider: `{report['provider']}`",
        f"- Configured model: `{report['configured_model']}`",
        f"- Response model identifier: `{report['response_model_identifier']}`",
        f"- Overall result: **{summary['overall_verification_result']}**",
        "",
        "## Summary",
        "",
        f"- Runs: {summary['run_count']}",
        f"- Proposals: {summary['proposal_count']}",
        f"- Guard accepted / rejected: {summary['guard_accepted_count']} / {summary['guard_rejected_count']}",
        f"- Fallbacks: {summary['fallback_count']}",
        f"- Fallback reasons: `{json.dumps(summary['fallback_reasons'], ensure_ascii=False)}`",
        f"- Illegal / duplicate / premature STOP: {summary['illegal_proposal_count']} / "
        f"{summary['duplicate_proposal_count']} / {summary['premature_stop_count']}",
        f"- Final status consistent: {summary['final_status_consistent']}",
        f"- Unsupported causal claims: {summary['unsupported_causal_claim_count']}",
        "",
        "## Runs",
        "",
        "| Run | Investigation path | Accepted | Rejected | Fallbacks | Stop reason | Passed |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for item in report["runs"]:
        path = " → ".join(item["investigation_order"])
        lines.append(
            f"| {item['run_id']} | {path} | {item['guard_accepted_count']} | "
            f"{item['guard_rejected_count']} | {item['fallback_count']} | "
            f"{item['stop_reason']} | {item['run_passed']} |"
        )
    lines.extend(
        [
            "",
            "## Complete Planner → Guard → Executed Tool Log (Run 1)",
            "",
            "```json",
            json.dumps(report["runs"][0]["planner_guard_log"], indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = _args()
    if args.runs != 5:
        print("Live verification requires exactly 5 runs.", file=sys.stderr)
        return 2
    api_key = _env_value("DEEPSEEK_API_KEY")
    if not api_key:
        print("Live verification not run: DEEPSEEK_API_KEY is not configured.", file=sys.stderr)
        return 2
    report = build_report(api_key, args.runs)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0 if report["summary"]["overall_verification_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
