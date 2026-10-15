from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select

from pulseops.backend.agent.graph import InvestigationAgent
from pulseops.backend.agent.planner import PlannerMode
from pulseops.backend.main import create_app
from pulseops.backend.persistence.database import create_database
from pulseops.backend.persistence.models import AnalysisRun, AgentStep, Opportunity
from pulseops.backend.persistence.runner import DefaultAnalysisRunner, RunExecution
from pulseops.backend.schemas.analytics import DateWindows
from tests.test_agent_router import FixtureTools

CASE_PAYLOAD = {
    "baseline_start": "2020-12-07",
    "baseline_end": "2020-12-13",
    "target_start": "2020-12-21",
    "target_end": "2020-12-27",
    "planner_mode": "deterministic",
}
TEST_DATABASE_DIR = Path("work/m4-test-dbs")


def database_url(label: str) -> str:
    TEST_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(TEST_DATABASE_DIR / f'{label}-{uuid4()}.db').resolve().as_posix()}"


@dataclass
class FixtureRunner:
    tools: FixtureTools

    def run(self, windows: DateWindows, planner_mode: str, run_id: str) -> RunExecution:
        mode = PlannerMode.LLM if planner_mode == "deepseek" else PlannerMode.DETERMINISTIC
        state = InvestigationAgent(self.tools, planner_mode=mode).run(windows, run_id=run_id)
        return RunExecution(state=state)


@pytest.fixture
def api():
    tools = FixtureTools()
    app = create_app(
        database_url=database_url("api"),
        runner=FixtureRunner(tools),
    )
    with TestClient(app) as client:
        yield client, app, tools


def create_case(client: TestClient, **overrides):
    return client.post("/api/runs", json={**CASE_PAYLOAD, **overrides})


def test_database_schema_contains_three_product_tables(api):
    _, app, _ = api
    assert {"analysis_runs", "agent_steps", "opportunities"} <= set(
        inspect(app.state.database_engine).get_table_names()
    )


def test_case_01_persists_analysis_run(api):
    client, _, _ = api
    body = create_case(client).json()
    assert body["detected_signal"] == "View→Cart"
    assert body["overall_baseline_rate"] == 31.6
    assert body["overall_target_rate"] == 22.92
    assert body["overall_delta_pp"] == -8.68
    assert body["affected_segment"] == "new_users"
    assert body["status"] == "COMPLETED"


def test_case_01_persists_complete_ordered_steps(api):
    client, _, _ = api
    run_id = create_case(client).json()["id"]
    steps = client.get(f"/api/runs/{run_id}/steps").json()
    assert [step["step_order"] for step in steps] == list(range(1, 9))
    assert steps[-1]["node"] == "STOP_DRILLDOWN"


def test_case_01_persists_expected_opportunity(api):
    client, _, _ = api
    run_id = create_case(client).json()["id"]
    opportunity = client.get("/api/opportunities").json()[0]
    assert opportunity["run_id"] == run_id
    assert opportunity["metric"] == "View→Cart"
    assert opportunity["affected_segment"] == "new_users"
    assert opportunity["baseline_rate"] == 31.04
    assert opportunity["target_rate"] == 19.48
    assert opportunity["delta_pp"] == -11.56
    assert opportunity["signal_confidence"] == "HIGH"
    assert opportunity["root_cause_confidence"] == "LOW"
    assert opportunity["recommended_status"] == "NEEDS_EVIDENCE"
    assert opportunity["recommended_action_type"] == "EVIDENCE_COLLECTION"
    assert opportunity["status"] == "NEEDS_EVIDENCE"


def test_opportunity_preserves_evidence_discipline_fields(api):
    client, _, _ = api
    create_case(client)
    opportunity = client.get("/api/opportunities").json()[0]
    assert opportunity["evidence"]
    assert any("8.68 percentage points" in item for item in opportunity["evidence"])
    assert opportunity["hypotheses"]
    assert opportunity["unknowns"]
    assert opportunity["do_not_recommend_yet"]
    assert isinstance(opportunity["evidence"], list)


def test_opportunity_persists_metric_rates(api):
    client, _, _ = api
    create_case(client)
    opportunity = client.get("/api/opportunities").json()[0]
    assert opportunity["baseline_rate"] > opportunity["target_rate"]
    assert opportunity["delta_pp"] < 0


def test_persisted_steps_contain_summaries_not_raw_user_counts(api):
    client, _, _ = api
    run_id = create_case(client).json()["id"]
    payload = json.dumps(client.get(f"/api/runs/{run_id}/steps").json())
    assert "converted_users" not in payload
    assert "view_users" not in payload


def test_data_quality_failure_saves_run_without_opportunity():
    tools = FixtureTools(data_quality_passes=False)
    app = create_app(
        database_url=database_url("dq"),
        runner=FixtureRunner(tools),
    )
    with TestClient(app) as client:
        run = create_case(client).json()
        assert run["stop_reason"] == "DATA_QUALITY_FAIL"
        assert client.get("/api/opportunities").json() == []


def test_data_quality_failure_saves_validation_step():
    tools = FixtureTools(data_quality_passes=False)
    app = create_app(
        database_url=database_url("dq-step"),
        runner=FixtureRunner(tools),
    )
    with TestClient(app) as client:
        run_id = create_case(client).json()["id"]
        steps = client.get(f"/api/runs/{run_id}/steps").json()
        assert [step["node"] for step in steps] == ["VALIDATE_DATA"]


def test_no_signal_saves_run_without_opportunity():
    tools = FixtureTools(significant_signal=False)
    app = create_app(
        database_url=database_url("no-signal"),
        runner=FixtureRunner(tools),
    )
    with TestClient(app) as client:
        run = create_case(client).json()
        assert run["stop_reason"] == "NO_SIGNIFICANT_SIGNAL"
        assert run["recommended_status"] == "NO_OPPORTUNITY"
        assert client.get("/api/opportunities").json() == []


def test_no_signal_saves_preflight_steps_only():
    tools = FixtureTools(significant_signal=False)
    app = create_app(
        database_url=database_url("no-signal-step"),
        runner=FixtureRunner(tools),
    )
    with TestClient(app) as client:
        run_id = create_case(client).json()["id"]
        steps = client.get(f"/api/runs/{run_id}/steps").json()
        assert [step["node"] for step in steps] == ["VALIDATE_DATA", "SCAN_METRICS"]


def test_transaction_rolls_back_all_records_on_opportunity_failure(api, monkeypatch):
    _, app, _ = api
    service = app.state.run_service

    def fail(_state):
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr(service, "_opportunity_from_state", fail)
    windows = DateWindows.model_validate({key: CASE_PAYLOAD[key] for key in CASE_PAYLOAD if key != "planner_mode"})
    with pytest.raises(RuntimeError, match="simulated"):
        service.execute(windows, "deterministic")
    with service.sessions() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 0
        assert session.scalar(select(func.count()).select_from(AgentStep)) == 0
        assert session.scalar(select(func.count()).select_from(Opportunity)) == 0


def test_post_runs_returns_created(api):
    client, _, _ = api
    response = create_case(client)
    assert response.status_code == 201
    assert response.json()["planner_mode"] == "deterministic"


def test_list_runs_endpoint(api):
    client, _, _ = api
    run_id = create_case(client).json()["id"]
    assert [run["id"] for run in client.get("/api/runs").json()] == [run_id]


def test_get_run_endpoint(api):
    client, _, _ = api
    run_id = create_case(client).json()["id"]
    assert client.get(f"/api/runs/{run_id}").json()["id"] == run_id


def test_get_steps_endpoint(api):
    client, _, _ = api
    run_id = create_case(client).json()["id"]
    assert client.get(f"/api/runs/{run_id}/steps").status_code == 200


def test_list_opportunities_endpoint(api):
    client, _, _ = api
    create_case(client)
    assert len(client.get("/api/opportunities").json()) == 1


def test_get_opportunity_endpoint(api):
    client, _, _ = api
    create_case(client)
    item = client.get("/api/opportunities").json()[0]
    assert client.get(f"/api/opportunities/{item['id']}").json() == item


@pytest.mark.parametrize(
    "path",
    ["/api/runs/missing", "/api/runs/missing/steps", "/api/opportunities/missing"],
)
def test_missing_resources_return_404(api, path):
    client, _, _ = api
    assert client.get(path).status_code == 404


def test_deepseek_mode_without_provider_uses_existing_fallback(api):
    client, _, _ = api
    run = create_case(client, planner_mode="deepseek").json()
    steps = client.get(f"/api/runs/{run['id']}/steps").json()
    planned = [step for step in steps if step["guard_status"] == "FALLBACK"]
    assert run["provider"] is None
    assert planned and all(step["fallback_used"] for step in planned)
    assert {step["fallback_reason"] for step in planned} == {"NO_PLANNER_CONFIGURED"}


def test_default_runner_needs_neither_deepseek_nor_bigquery_in_offline_test(
    monkeypatch,
):
    import pulseops.backend.persistence.runner as runner_module

    tools = FixtureTools()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(runner_module, "BigQueryExecutor", lambda project=None: object())
    monkeypatch.setattr(runner_module, "AnalyticsToolset", lambda executor: tools)
    windows = DateWindows.model_validate(
        {key: CASE_PAYLOAD[key] for key in CASE_PAYLOAD if key != "planner_mode"}
    )
    execution = DefaultAnalysisRunner().run(windows, "deepseek", "offline")
    fallback_steps = [step for step in execution.state.agent_steps if step.fallback_used]
    assert execution.provider is None
    assert fallback_steps
    assert {step.fallback_reason for step in fallback_steps} == {"NO_PLANNER_CONFIGURED"}


def test_run_and_opportunity_ids_are_unique(api):
    client, _, _ = api
    first = create_case(client).json()["id"]
    second = create_case(client).json()["id"]
    opportunities = client.get("/api/opportunities").json()
    assert first != second
    assert len({item["id"] for item in opportunities}) == 2


def test_api_payloads_do_not_contain_secret_fields(api):
    client, _, _ = api
    create_case(client)
    payload = json.dumps(
        {
            "runs": client.get("/api/runs").json(),
            "opportunities": client.get("/api/opportunities").json(),
        }
    ).lower()
    assert "api_key" not in payload
    assert "authorization" not in payload


def test_invalid_planner_mode_is_rejected(api):
    client, _, _ = api
    assert create_case(client, planner_mode="unbounded").status_code == 422


def test_invalid_date_window_is_rejected(api):
    client, _, _ = api
    response = create_case(client, baseline_start="2020-12-14", baseline_end="2020-12-13")
    assert response.status_code == 422


def test_database_url_can_be_supplied_by_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url("environment"))
    engine, _ = create_database()
    try:
        assert engine.url.database.endswith(".db")
    finally:
        engine.dispose()
