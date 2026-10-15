from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from pulseops.backend.agent.planner import PlannerProtocol
from pulseops.backend.agent.prompts import PLANNER_SYSTEM_PROMPT
from pulseops.backend.agent.state import AgentState


@dataclass(frozen=True)
class DeepSeekPlannerConfig:
    model: str = "deepseek-flash"
    base_url: str = "https://api.deepseek.com"
    timeout_seconds: float = 45.0
    max_tokens: int = 400


class DeepSeekPlanner(PlannerProtocol):
    """Provider adapter that proposes actions but never executes tools."""

    provider = "deepseek"

    def __init__(self, api_key: str, config: DeepSeekPlannerConfig | None = None) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API key is required")
        self._api_key = api_key
        self.config = config or DeepSeekPlannerConfig()
        self.last_response_model: str | None = None

    @property
    def model_identifier(self) -> str:
        return self.last_response_model or self.config.model

    def plan(self, state: AgentState) -> str:
        payload = self._request_payload(state)
        request = Request(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.config.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        self.last_response_model = body.get("model")
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("DeepSeek returned an empty planner proposal")
        return content

    def _request_payload(self, state: AgentState) -> dict[str, Any]:
        system = (
            PLANNER_SYSTEM_PROMPT
            + "\nReturn one JSON object with exactly these fields: action, dimension, "
            "lifecycle_filter, rationale, hypothesis_code. Example JSON: "
            '{"action":"INVESTIGATE","dimension":"lifecycle",'
            '"lifecycle_filter":null,"rationale":"Investigate lifecycle first.",'
            '"hypothesis_code":null}'
            "\nLifecycle filter rules: use null when dimension is lifecycle. For secondary "
            "dimensions, if affected_segment is new_users use exactly \"new\"; if it is "
            "returning_users use exactly \"returning\"; otherwise use null. Never use "
            "new_users or returning_users as lifecycle_filter values."
        )
        planner_state = {
            "run_id": state.run_id,
            "detected_signal": state.detected_signal,
            "affected_segment": state.affected_segment,
            "investigated_dimensions": state.investigated_dimensions,
            "remaining_investigation_budget": state.remaining_investigation_budget,
            "evidence": state.evidence,
            "rejected_hypotheses": [item.model_dump(mode="json") for item in state.rejected_hypotheses],
            "supported_hypotheses": [item.model_dump(mode="json") for item in state.supported_hypotheses],
            "insufficient_hypotheses": [
                item.model_dump(mode="json") for item in state.insufficient_hypotheses
            ],
            "unknowns": state.unknowns,
        }
        return {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": "Current bounded investigation state JSON:\n"
                    + json.dumps(planner_state, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "reasoning_effort": "none",
            "temperature": 0.2,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
