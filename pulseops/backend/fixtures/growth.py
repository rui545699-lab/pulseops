from __future__ import annotations

import json
from pathlib import Path

from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    GrowthComparison,
    GrowthSegmentComparison,
    OrderValueContext,
    ValidationResult,
    WeeklyGrowthResult,
)


CASE_03 = json.loads((Path(__file__).with_name("case_03.json")).read_text(encoding="utf-8"))


class Case03GoldenTools:
    """Offline adapter using only the verified Phase A/B BigQuery outputs."""

    provenance = CASE_03["provenance"]

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def validate_growth_data(self, windows):
        self.calls.append(("validate_growth_data",))
        return ValidationResult(status=AnalysisStatus.PASS, analysis_allowed=True)

    def analyze_growth(self, windows):
        self.calls.append(("analyze_growth",))
        return GrowthComparison.model_validate(CASE_03["growth"])

    def analyze_weekly_growth(self, windows):
        self.calls.append(("analyze_weekly_growth",))
        return [WeeklyGrowthResult.model_validate(row) for row in CASE_03["weekly"]]

    def compare_growth_segments(self, dimension, windows):
        self.calls.append(("compare_growth_segments", dimension, None))
        return GrowthSegmentComparison.model_validate(CASE_03["segments"][dimension])

    def analyze_order_value(self, windows):
        self.calls.append(("analyze_order_value",))
        return OrderValueContext.model_validate(CASE_03["order_value_context"])
