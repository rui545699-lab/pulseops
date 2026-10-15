from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from pulseops.backend.analytics.bigquery_client import BigQueryExecutor
from pulseops.backend.schemas.analytics import DateWindows
from pulseops.backend.tools.analyze_funnel import analyze_funnel
from pulseops.backend.tools.compare_segments import compare_segments
from pulseops.backend.tools.scan_metrics import scan_metrics
from pulseops.backend.tools.validate_data import validate_data

app = FastAPI(title="PulseOps Analytics Backend", version="0.1.0")


class FunnelRequest(DateWindows):
    events: list[str] = Field(default_factory=lambda: ["view_item", "add_to_cart"], min_length=2)


class SegmentRequest(DateWindows):
    dimension: Literal["lifecycle", "device", "acquisition", "category"]
    minimum_sample_size: int = Field(default=100, ge=1)
    lifecycle_filter: Literal["new", "returning"] | None = None


class ValidationRequest(DateWindows):
    minimum_view_sessions: int = Field(default=100, ge=1)


def _executor() -> BigQueryExecutor:
    return BigQueryExecutor(project=os.getenv("GOOGLE_CLOUD_PROJECT"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analytics/validate")
def validate(request: ValidationRequest):
    return validate_data(_executor(), request, request.minimum_view_sessions)


@app.post("/analytics/metrics/scan")
def metrics(request: DateWindows):
    return scan_metrics(_executor(), **request.model_dump())


@app.post("/analytics/funnel")
def funnel(request: FunnelRequest):
    values = request.model_dump(exclude={"events"})
    return analyze_funnel(_executor(), request.events, **values)


@app.post("/analytics/segments")
def segments(request: SegmentRequest):
    values = request.model_dump(
        exclude={"dimension", "minimum_sample_size", "lifecycle_filter"}
    )
    return compare_segments(
        _executor(),
        request.dimension,
        **values,
        minimum_sample_size=request.minimum_sample_size,
        lifecycle_filter=request.lifecycle_filter,
    )

