from __future__ import annotations

import json
from unittest.mock import patch

from pulseops.backend.agent.providers.deepseek import DeepSeekPlanner, DeepSeekPlannerConfig
from pulseops.backend.agent.state import AgentState
from tests.test_agent_router import WINDOWS


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(
            {
                "model": "provider-model-id",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "action": "INVESTIGATE",
                                    "dimension": "lifecycle",
                                    "lifecycle_filter": None,
                                    "rationale": "Investigate lifecycle first.",
                                    "hypothesis_code": None,
                                }
                            )
                        }
                    }
                ],
            }
        ).encode()


def test_deepseek_adapter_returns_provider_content_without_executing_tools():
    planner = DeepSeekPlanner(
        "test-only-secret",
        DeepSeekPlannerConfig(model="configured-model", base_url="https://example.invalid"),
    )
    state = AgentState(run_id="adapter-test", **WINDOWS.model_dump())
    with patch("pulseops.backend.agent.providers.deepseek.urlopen", return_value=FakeResponse()):
        content = planner.plan(state)
    assert json.loads(content)["dimension"] == "lifecycle"
    assert planner.model_identifier == "provider-model-id"


def test_deepseek_request_uses_json_mode_and_contains_no_tool_authority():
    planner = DeepSeekPlanner("test-only-secret")
    state = AgentState(run_id="payload-test", **WINDOWS.model_dump())
    payload = planner._request_payload(state)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["model"] == "deepseek-flash"
    rendered = json.dumps(payload)
    assert "DEEPSEEK_API_KEY" not in rendered
    assert "test-only-secret" not in rendered
    assert "execute_sql" not in rendered


def test_deepseek_adapter_rejects_empty_key():
    try:
        DeepSeekPlanner("   ")
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("empty key should fail")
