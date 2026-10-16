from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from pulseops.backend.agent.graph import AnalyticsToolset, InvestigationAgent
from pulseops.backend.agent.planner import PlannerMode
from pulseops.backend.agent.providers.deepseek import DeepSeekPlanner, DeepSeekPlannerConfig
from pulseops.backend.agent.state import AgentState, InvestigationProfile
from pulseops.backend.analytics.bigquery_client import BigQueryExecutor
from pulseops.backend.schemas.analytics import DateWindows


@dataclass(frozen=True)
class RunExecution:
    state: AgentState
    provider: str | None = None
    model_identifier: str | None = None


class AnalysisRunner(Protocol):
    def run(
        self, windows: DateWindows, planner_mode: str, run_id: str,
        analysis_type: str = "CONVERSION",
    ) -> RunExecution: ...


class DefaultAnalysisRunner:
    """Connects the existing bounded agent to production adapters."""

    def run(
        self, windows: DateWindows, planner_mode: str, run_id: str,
        analysis_type: str = "CONVERSION",
    ) -> RunExecution:
        tools = AnalyticsToolset(BigQueryExecutor(project=os.getenv("GOOGLE_CLOUD_PROJECT")))
        planner = None
        provider = None
        model_identifier = None
        agent_mode = PlannerMode.DETERMINISTIC

        if planner_mode == "deepseek":
            agent_mode = PlannerMode.LLM
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if api_key:
                config = DeepSeekPlannerConfig(
                    model=os.getenv("DEEPSEEK_MODEL", DeepSeekPlannerConfig.model)
                )
                planner = DeepSeekPlanner(api_key, config)
                provider = planner.provider
                model_identifier = planner.model_identifier

        state = InvestigationAgent(
            tools,
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
