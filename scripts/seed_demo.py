from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.planner import PlannerMode
from pulseops.backend.agent.providers.deepseek import DeepSeekPlanner, DeepSeekPlannerConfig
from pulseops.backend.agent.state import InvestigationProfile
from pulseops.backend.fixtures.lifecycle import CASE_02, Case02GoldenTools
from pulseops.backend.fixtures.growth import CASE_03, Case03GoldenTools
from pulseops.backend.persistence.database import create_database, init_database
from pulseops.backend.persistence.runner import RunExecution
from pulseops.backend.persistence.service import RunService
from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    DateWindows,
    LifecycleWindows,
    GrowthWindows,
    ValidationResult,
    WarningItem,
)
from scripts.verify_live_planner import Case01FixtureTools, ROOT, WINDOWS, _env_value

DEFAULT_DATABASE_PATH = ROOT / "work" / "pulseops-demo.db"
LIFECYCLE_WINDOWS = LifecycleWindows.model_validate(CASE_02["windows"])
GROWTH_WINDOWS = GrowthWindows.model_validate(CASE_03["windows"])


class DemoFixtureTools(Case01FixtureTools):
    """Verified analytics fixture variants used only by the local portfolio demo."""

    def __init__(
        self,
        *,
        data_quality_passes: bool = True,
        significant_signal: bool = True,
    ) -> None:
        super().__init__()
        self.data_quality_passes = data_quality_passes
        self.significant_signal = significant_signal

    def validate_data(self, windows: DateWindows) -> ValidationResult:
        if self.data_quality_passes:
            return super().validate_data(windows)
        return ValidationResult(
            status=AnalysisStatus.FAIL,
            analysis_allowed=False,
            warnings=[
                WarningItem(
                    code="DATA_QUALITY_ALERT",
                    message="Demo fixture data-quality checks did not pass.",
                )
            ],
        )

    def scan_metrics(self, windows: DateWindows):
        result = super().scan_metrics(windows)
        if self.significant_signal:
            return result
        return result.model_copy(
            update={
                "metrics": [
                    metric.model_copy(update={"needs_investigation": False})
                    for metric in result.metrics
                ]
            }
        )


@dataclass
class DemoRunner:
    tools: Any
    api_key: str | None = None

    def run(
        self,
        windows: DateWindows,
        planner_mode: str,
        run_id: str,
        analysis_type: str = "CONVERSION",
    ) -> RunExecution:
        planner = None
        provider = None
        model_identifier = None
        agent_mode = PlannerMode.DETERMINISTIC

        if planner_mode == "deepseek":
            agent_mode = PlannerMode.LLM
            if self.api_key:
                planner = DeepSeekPlanner(
                    self.api_key,
                    DeepSeekPlannerConfig(
                        model=_env_value("DEEPSEEK_MODEL") or DeepSeekPlannerConfig.model,
                        base_url=_env_value("DEEPSEEK_BASE_URL")
                        or DeepSeekPlannerConfig.base_url,
                        timeout_seconds=float(
                            _env_value("DEEPSEEK_TIMEOUT_SECONDS")
                            or DeepSeekPlannerConfig.timeout_seconds
                        ),
                    ),
                )
                provider = planner.provider
                model_identifier = planner.model_identifier

        state = InvestigationAgent(
            self.tools,
            planner_mode=agent_mode,
            planner=planner,
        ).run(
            windows,
            run_id=run_id,
            investigation_profile=InvestigationProfile(analysis_type),
        )
        if planner is not None:
            model_identifier = planner.model_identifier
        return RunExecution(state, provider, model_identifier)


def seed_demo(database_path: Path, *, api_key: str | None) -> dict[str, Any]:
    database_path = _safe_demo_path(database_path)
    _reset_sqlite_files(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{database_path.as_posix()}"
    engine, sessions = create_database(database_url)
    init_database(engine)
    try:
        material_service = RunService(
            sessions,
            DemoRunner(DemoFixtureTools(), api_key=api_key),
        )
        material = material_service.execute(WINDOWS, "deepseek")

        lifecycle_service = RunService(sessions, DemoRunner(Case02GoldenTools()))
        lifecycle = lifecycle_service.execute(
            LIFECYCLE_WINDOWS,
            "deterministic",
            "LIFECYCLE_RISK",
        )

        growth_service = RunService(sessions, DemoRunner(Case03GoldenTools()))
        growth = growth_service.execute(
            GROWTH_WINDOWS,
            "deterministic",
            "POSITIVE_GROWTH",
        )

        data_quality_service = RunService(
            sessions,
            DemoRunner(DemoFixtureTools(data_quality_passes=False)),
        )
        data_quality = data_quality_service.execute(WINDOWS, "deterministic")

        no_signal_service = RunService(
            sessions,
            DemoRunner(DemoFixtureTools(significant_signal=False)),
        )
        no_signal = no_signal_service.execute(WINDOWS, "deterministic")

        runs = material_service.list_runs()
        opportunities = material_service.list_opportunities()
        material_steps = material_service.get_steps(material.id) or []
        planner_steps = [step for step in material_steps if step.planner_proposal is not None]
        fallback_steps = [step for step in material_steps if step.fallback_used]

        return {
            "database_path": str(database_path),
            "counts": {
                "active_opportunities": sum(item.status != "CLOSED" for item in opportunities),
                "completed_runs": sum(item.status == "COMPLETED" for item in runs),
                "needs_evidence": sum(item.status == "NEEDS_EVIDENCE" for item in opportunities),
                "high_confidence_signals": sum(
                    item.signal_confidence == "HIGH" and item.detected_signal is not None
                    for item in runs
                ),
            },
            "runs": [
                _run_summary(material, "material_signal"),
                _run_summary(lifecycle, "lifecycle_risk"),
                _run_summary(growth, "positive_growth"),
                _run_summary(data_quality, "data_quality_alert"),
                _run_summary(no_signal, "no_significant_signal"),
            ],
            "opportunity_count": len(opportunities),
            "material_opportunity_id": (
                material.opportunity.id if material.opportunity is not None else None
            ),
            "lifecycle_opportunity_id": (
                lifecycle.opportunity.id if lifecycle.opportunity is not None else None
            ),
            "growth_opportunity_id": (
                growth.opportunity.id if growth.opportunity is not None else None
            ),
            "planner": {
                "provider": material.provider,
                "model_identifier": material.model_identifier,
                "real_proposal_count": len(planner_steps),
                "fallback_count": len(fallback_steps),
                "used_real_planner": bool(api_key and planner_steps),
                "fallback_reasons": sorted(
                    {
                        step.fallback_reason
                        for step in fallback_steps
                        if step.fallback_reason is not None
                    }
                ),
            },
        }
    finally:
        engine.dispose()


def _run_summary(run, scenario: str) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "run_id": run.id,
        "planner_mode": run.planner_mode,
        "status": run.status,
        "recommended_status": run.recommended_status,
        "stop_reason": run.stop_reason,
        "opportunity_created": run.opportunity is not None,
    }


def _safe_demo_path(database_path: Path) -> Path:
    resolved = database_path.resolve()
    allowed_root = (ROOT / "work").resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as error:
        raise ValueError(f"Demo database must be inside {allowed_root}") from error
    if resolved.suffix.lower() != ".db":
        raise ValueError("Demo database must use a .db filename")
    return resolved


def _reset_sqlite_files(database_path: Path) -> None:
    for candidate in (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ):
        if candidate.exists():
            candidate.unlink()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely reset and seed the local PulseOps portfolio demo database."
    )
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DATABASE_PATH)
    return parser.parse_args()


def main() -> int:
    args = _args()
    result = seed_demo(args.database_path, api_key=_env_value("DEEPSEEK_API_KEY"))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
