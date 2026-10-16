from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from pulseops.backend.fixtures.growth import Case03GoldenTools
from pulseops.backend.main import create_app
from pulseops.backend.persistence.service import _positive_growth_opportunity_title
from scripts.seed_demo import DemoRunner
import pytest


def database_url() -> str:
    path = (Path("work/m4-test-dbs") / f"growth-{uuid4()}.db").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


PAYLOAD = {
    "analysis_type": "POSITIVE_GROWTH",
    "baseline_start": "2020-11-23", "baseline_end": "2020-12-06",
    "target_start": "2020-12-07", "target_end": "2020-12-20",
    "confirmation_start": "2020-12-21", "confirmation_end": "2021-01-03",
    "holdout_1_start": "2021-01-04", "holdout_1_end": "2021-01-17",
    "holdout_2_start": "2021-01-18", "holdout_2_end": "2021-01-31",
    "planner_mode": "deterministic",
}


def test_case_03_persistence_and_api_round_trip():
    app = create_app(database_url=database_url(), runner=DemoRunner(Case03GoldenTools()))
    with TestClient(app) as client:
        response = client.post("/api/runs", json=PAYLOAD)
        assert response.status_code == 201
        run = response.json()
        assert run["analysis_type"] == "POSITIVE_GROWTH"
        assert run["overall_baseline_rate"] == 40.35
        assert run["overall_target_rate"] == 51.14
        assert run["overall_delta_pp"] == 10.78
        assert run["reproducibility"] == "REPRODUCED"
        assert run["growth_signal_confidence"] == "HIGH"
        assert run["reproducibility_confidence"] == "HIGH"

        opportunity = client.get("/api/opportunities").json()[0]
        assert opportunity["opportunity_type"] == "POSITIVE_GROWTH"
        assert opportunity["baseline_rate"] == 40.35
        assert opportunity["target_rate"] == 51.14
        assert opportunity["delta_pp"] == 10.78
        assert opportunity["confirmation_period"]["conversion_rate"] == 55.07
        assert opportunity["holdout_results"]["holdout_1"]["conversion_rate"] == 48.74
        assert opportunity["reproducibility"] == "REPRODUCED"
        assert opportunity["recommended_status"] == "READY_FOR_REPLICATION_TEST"
        assert opportunity["recommended_action_type"] == "REPLICATION_TEST"
        assert opportunity["segment_analysis"]["device"]["localization"] == "BROAD"
        assert opportunity["title"] == "Broad Checkout→Purchase lift ready for replication test"


@pytest.mark.parametrize(
    ("localization", "expected"),
    [
        ("BROAD", "Broad Checkout→Purchase lift ready for replication test"),
        ("SEGMENT_CONCENTRATED", "Segment-concentrated Checkout→Purchase lift ready for replication test"),
        ("MIX_DRIVEN", "Mix-driven Checkout→Purchase lift ready for replication test"),
        ("MIXED", "Mixed Checkout→Purchase lift ready for replication test"),
        (None, "Checkout→Purchase Growth Opportunity"),
    ],
)
def test_growth_opportunity_title_is_localization_aware(localization, expected):
    assert _positive_growth_opportunity_title(localization) == expected


def test_growth_windows_are_required():
    app = create_app(database_url=database_url(), runner=DemoRunner(Case03GoldenTools()))
    with TestClient(app) as client:
        invalid = {key: value for key, value in PAYLOAD.items() if not key.startswith("holdout_2_")}
        assert client.post("/api/runs", json=invalid).status_code == 422
