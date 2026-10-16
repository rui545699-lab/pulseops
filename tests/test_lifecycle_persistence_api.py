from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from pulseops.backend.main import create_app
from pulseops.backend.fixtures.lifecycle import Case02GoldenTools
from scripts.seed_demo import DemoRunner
from pulseops.backend.persistence.database import init_database


def database_url() -> str:
    path = (Path("work/m4-test-dbs") / f"lifecycle-{uuid4()}.db").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


PAYLOAD = {
    "analysis_type": "LIFECYCLE_RISK",
    "baseline_start": "2020-11-30",
    "baseline_end": "2020-12-13",
    "target_start": "2020-12-21",
    "target_end": "2021-01-03",
    "post_start": "2021-01-04",
    "post_end": "2021-01-24",
    "planner_mode": "deterministic",
}


def test_case_02_persistence_and_api_round_trip():
    app = create_app(
        database_url=database_url(),
        runner=DemoRunner(Case02GoldenTools()),
    )
    with TestClient(app) as client:
        response = client.post("/api/runs", json=PAYLOAD)
        assert response.status_code == 201
        run = response.json()
        assert run["analysis_type"] == "LIFECYCLE_RISK"
        assert run["overall_baseline_rate"] == 8.33
        assert run["overall_target_rate"] == 5.11
        assert run["overall_delta_pp"] == -3.22
        assert run["post_rate"] == 6.9
        assert run["risk_pattern"] == "PARTIAL_RECOVERY"
        assert run["recovery_ratio"] == 55.73

        opportunity = client.get("/api/opportunities").json()[0]
        assert opportunity["opportunity_type"] == "LIFECYCLE_RISK"
        assert opportunity["title"] == "New-user 7-day return risk with partial recovery"
        assert opportunity["metric"] == "New-user 7-day Return Rate"
        assert opportunity["baseline_rate"] == 8.33
        assert opportunity["target_rate"] == 5.11
        assert opportunity["delta_pp"] == -3.22
        assert opportunity["post_rate"] == 6.9
        assert opportunity["risk_pattern"] == "PARTIAL_RECOVERY"
        assert opportunity["signal_confidence"] == "HIGH"
        assert opportunity["root_cause_confidence"] == "LOW"
        assert opportunity["recommended_action_type"] == "EVIDENCE_COLLECTION"
        assert opportunity["return_timing"]["target"]["return_rate_d1"] == 2.9
        assert opportunity["segment_analysis"]["activation_depth"]["composition_effect_pp"] == -0.59

        detail = client.get(f"/api/opportunities/{opportunity['id']}")
        assert detail.status_code == 200
        assert detail.json() == opportunity

        steps = client.get(f"/api/runs/{run['id']}/steps").json()
        assert [item["node"] for item in steps] == [
            "VALIDATE_DATA",
            "ANALYZE_RETENTION",
            "CHECK_RETURN_TIMING",
            "CHECK_RECOVERY",
            "CHECK_ACQUISITION",
            "CHECK_DEVICE",
            "CHECK_ACTIVATION_DEPTH",
            "STOP_DRILLDOWN",
        ]


def test_lifecycle_post_window_is_required():
    app = create_app(database_url=database_url(), runner=DemoRunner(Case02GoldenTools()))
    with TestClient(app) as client:
        payload = {key: value for key, value in PAYLOAD.items() if not key.startswith("post_")}
        assert client.post("/api/runs", json=payload).status_code == 422


def test_existing_sqlite_schema_is_evolved_additively():
    path = (Path("work/m4-test-dbs") / f"legacy-{uuid4()}.db").resolve()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE analysis_runs (id VARCHAR(36) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE opportunities (id VARCHAR(36) PRIMARY KEY)")
    init_database(engine)
    assert {"analysis_type", "post_rate", "risk_pattern", "return_timing"} <= {
        item["name"] for item in inspect(engine).get_columns("analysis_runs")
    }
    assert {"post_rate", "recovery_ratio", "segment_analysis"} <= {
        item["name"] for item in inspect(engine).get_columns("opportunities")
    }
    engine.dispose()
