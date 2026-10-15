from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from scripts.seed_demo import seed_demo


def test_demo_seed_creates_three_representative_runs_and_one_opportunity():
    database_path = Path("work/m5-test-dbs") / f"demo-{uuid4()}.db"
    result = seed_demo(database_path, api_key=None)

    assert result["counts"] == {
        "active_opportunities": 1,
        "completed_runs": 3,
        "needs_evidence": 1,
        "high_confidence_signals": 1,
    }
    assert result["opportunity_count"] == 1
    assert [item["scenario"] for item in result["runs"]] == [
        "material_signal",
        "data_quality_alert",
        "no_significant_signal",
    ]
    assert [item["recommended_status"] for item in result["runs"]] == [
        "NEEDS_EVIDENCE",
        "DATA_QUALITY_ALERT",
        "NO_OPPORTUNITY",
    ]
    assert [item["opportunity_created"] for item in result["runs"]] == [True, False, False]


def test_demo_seed_refuses_to_reset_a_database_outside_work():
    try:
        seed_demo(Path("pulseops-demo.db"), api_key=None)
    except ValueError as error:
        assert "must be inside" in str(error)
    else:
        raise AssertionError("unsafe demo database path was accepted")
