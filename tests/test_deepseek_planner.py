from __future__ import annotations

import json
from unittest.mock import patch

from pulseops.backend.agent.providers.deepseek import DeepSeekPlanner, DeepSeekPlannerConfig
from pulseops.backend.agent.state import AgentState, InvestigationProfile
from pulseops.backend.fixtures.lifecycle import CASE_02
from pulseops.backend.schemas.analytics import LifecycleWindows
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


def test_lifecycle_risk_context_makes_remaining_dimensions_and_stop_policy_explicit():
    planner = DeepSeekPlanner("test-only-secret")
    windows = LifecycleWindows.model_validate(CASE_02["windows"])
    state = AgentState(
        run_id="lifecycle-payload",
        **windows.model_dump(),
        investigation_profile=InvestigationProfile.LIFECYCLE_RISK,
        data_quality_status="PASS",
        detected_signal="New-user 7-day Return Rate",
        affected_segment="new_users",
    )
    payload = planner._request_payload(state)
    context = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])

    assert context["remaining_dimensions"] == ["acquisition", "device", "activation_depth"]
    assert context["required_lifecycle_filter"] is None
    assert context["stop_allowed"] is False
    assert context["stop_preconditions"]["no_legal_next_dimension"] is False
    assert context["root_cause_confidence"] == "LOW"
    assert "lifecycle_filter MUST be null" in payload["messages"][0]["content"]


def test_deepseek_adapter_rejects_empty_key():
    try:
        DeepSeekPlanner("   ")
    except ValueError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("empty key should fail")
