from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from google.auth.exceptions import DefaultCredentialsError
from google.api_core.exceptions import Forbidden, GoogleAPICallError

from pulseops.backend.analytics.assessment import assess_case
from pulseops.backend.analytics.bigquery_client import BigQueryExecutor
from pulseops.backend.schemas.analytics import DateWindows, SegmentComparison
from pulseops.backend.tools.analyze_funnel import analyze_funnel
from pulseops.backend.tools.compare_segments import compare_segments
from pulseops.backend.tools.validate_data import validate_data

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "case_01.json"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PulseOps Golden Case 01 against live BigQuery data."
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="Google Cloud billing project (or set GOOGLE_CLOUD_PROJECT).",
    )
    parser.add_argument(
        "--tolerance-pp",
        type=float,
        default=0.15,
        help="Allowed absolute conversion-rate difference in percentage points.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON result path.")
    return parser.parse_args()


def _rates(comparison: SegmentComparison) -> dict[str, dict[str, float | None]]:
    return {
        row.segment.lower(): {
            "baseline_rate": row.baseline_rate,
            "target_rate": row.target_rate,
            "change_pp": row.change_pp,
        }
        for row in comparison.segments
    }


def _expected_segment_rates(fixture: dict[str, Any], dimension: str) -> dict[str, dict[str, float]]:
    values = fixture["segments"][dimension]
    baseline = {str(row["segment"]).lower(): row for row in values["baseline"]}
    target = {str(row["segment"]).lower(): row for row in values["target"]}
    expected: dict[str, dict[str, float]] = {}
    for name in baseline.keys() & target.keys():
        b_rate = round(100 * baseline[name]["converted_users"] / baseline[name]["view_users"], 2)
        t_rate = round(100 * target[name]["converted_users"] / target[name]["view_users"], 2)
        expected[name] = {
            "baseline_rate": b_rate,
            "target_rate": t_rate,
            "change_pp": round(t_rate - b_rate, 2),
        }
    return expected


def _check(
    checks: list[dict[str, Any]],
    name: str,
    expected: float | str,
    actual: float | str | None,
    tolerance: float = 0.0,
) -> None:
    if isinstance(expected, float) and isinstance(actual, (float, int)):
        difference: float | None = round(float(actual) - expected, 4)
        passed = abs(difference) <= tolerance
    else:
        difference = None
        passed = actual == expected
    checks.append(
        {
            "name": name,
            "expected": expected,
            "actual": actual,
            "difference": difference,
            "tolerance": tolerance,
            "passed": passed,
        }
    )


def run(project: str, tolerance_pp: float) -> dict[str, Any]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    windows = DateWindows(
        baseline_start=date(2020, 12, 7),
        baseline_end=date(2020, 12, 13),
        target_start=date(2020, 12, 21),
        target_end=date(2020, 12, 27),
    )
    executor = BigQueryExecutor(project=project)

    validation = validate_data(executor, windows)
    funnel = analyze_funnel(
        executor,
        ["view_item", "add_to_cart"],
        **windows.model_dump(),
    )
    comparisons = {
        "lifecycle": compare_segments(executor, "lifecycle", **windows.model_dump()),
        "device": compare_segments(
            executor, "device", **windows.model_dump(), lifecycle_filter="new"
        ),
        "acquisition": compare_segments(
            executor, "acquisition", **windows.model_dump(), lifecycle_filter="new"
        ),
        "category": compare_segments(
            executor, "category", **windows.model_dump(), lifecycle_filter="new"
        ),
    }
    assessment = assess_case(funnel, comparisons)
    checks: list[dict[str, Any]] = []

    expected_funnel = fixture["funnel"]
    expected_baseline = round(
        100
        * expected_funnel["baseline"]["converted_sessions"]
        / expected_funnel["baseline"]["view_sessions"],
        2,
    )
    expected_target = round(
        100
        * expected_funnel["target"]["converted_sessions"]
        / expected_funnel["target"]["view_sessions"],
        2,
    )
    _check(checks, "funnel.baseline_rate", expected_baseline, funnel.baseline.session_conversion_rate, tolerance_pp)
    _check(checks, "funnel.target_rate", expected_target, funnel.target.session_conversion_rate, tolerance_pp)
    _check(checks, "funnel.delta_pp", round(expected_target - expected_baseline, 2), funnel.session_delta_pp, tolerance_pp)

    for dimension in ("lifecycle", "device", "acquisition"):
        expected_rates = _expected_segment_rates(fixture, dimension)
        actual_rates = _rates(comparisons[dimension])
        for segment, values in expected_rates.items():
            for metric in ("baseline_rate", "target_rate", "change_pp"):
                _check(
                    checks,
                    f"{dimension}.{segment}.{metric}",
                    values[metric],
                    actual_rates.get(segment, {}).get(metric),
                    tolerance_pp,
                )

    category_supported = any("Category" in item for item in assessment.unknowns)
    _check(checks, "category.no_single_root_cause", "true", str(category_supported).lower())
    _check(checks, "assessment.signal_confidence", "HIGH", assessment.signal_confidence.value)
    _check(checks, "assessment.root_cause_confidence", "LOW", assessment.root_cause_confidence.value)
    _check(checks, "assessment.recommended_status", "NEEDS_EVIDENCE", assessment.recommended_status.value)
    _check(checks, "validation.analysis_allowed", "true", str(validation.analysis_allowed).lower())

    return {
        "case": "Golden Case 01",
        "project": project,
        "windows": windows.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "live_results": {
            "funnel": funnel.model_dump(mode="json"),
            "segments": {
                name: value.model_dump(mode="json") for name, value in comparisons.items()
            },
            "assessment": assessment.model_dump(mode="json"),
        },
        "fixture_differences": checks,
        "integration_verification": "PASS" if all(item["passed"] for item in checks) else "FAIL",
    }


def main() -> int:
    args = _args()
    if not args.project:
        print(
            "Integration verification not run: no billing project was supplied.\n"
            "Set GOOGLE_CLOUD_PROJECT or pass --project, and configure Google "
            "Application Default Credentials.",
            file=sys.stderr,
        )
        return 2
    try:
        result = run(args.project, args.tolerance_pp)
    except DefaultCredentialsError as exc:
        print(
            "Integration verification not run: Google Application Default "
            f"Credentials are unavailable. ({exc})",
            file=sys.stderr,
        )
        return 2
    except Forbidden as exc:
        print(
            "Integration verification not run: credentials cannot execute BigQuery "
            f"jobs in project '{args.project}'. ({exc.message})",
            file=sys.stderr,
        )
        return 2
    except GoogleAPICallError as exc:
        print(f"BigQuery integration failed: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["integration_verification"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

