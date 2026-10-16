from __future__ import annotations

import json
from pathlib import Path

from pulseops.backend.schemas.analytics import (
    AnalysisStatus,
    LifecycleSegmentComparison,
    RecoveryAnalysis,
    RetentionComparison,
    ReturnTimingAnalysis,
    ValidationResult,
)


CASE_02 = json.loads(
    (Path(__file__).with_name("case_02.json")).read_text(encoding="utf-8")
)


class Case02GoldenTools:
    """Offline demo adapter derived only from verified live BigQuery outputs."""

    provenance = CASE_02["provenance"]

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def validate_lifecycle_data(self, windows):
        self.calls.append(("validate_lifecycle_data",))
        return ValidationResult(status=AnalysisStatus.PASS, analysis_allowed=True)

    def analyze_retention(self, windows):
        self.calls.append(("analyze_retention",))
        return RetentionComparison.model_validate(CASE_02["retention"])

    def analyze_return_timing(self, windows):
        self.calls.append(("analyze_return_timing",))
        return ReturnTimingAnalysis.model_validate(CASE_02["timing"])

    def analyze_recovery(self, windows, retention):
        self.calls.append(("analyze_recovery",))
        return RecoveryAnalysis.model_validate(CASE_02["recovery"])

    def compare_lifecycle_segments(self, dimension, windows):
        self.calls.append(("compare_lifecycle_segments", dimension, None))
        return LifecycleSegmentComparison.model_validate(CASE_02["segments"][dimension])
