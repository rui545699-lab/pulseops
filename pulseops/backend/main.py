from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from pulseops.backend.analytics.bigquery_client import BigQueryExecutor
from pulseops.backend.persistence.database import create_database, init_database
from pulseops.backend.persistence.runner import AnalysisRunner, DefaultAnalysisRunner
from pulseops.backend.persistence.service import RunService
from pulseops.backend.product_api import router as product_router
from pulseops.backend.schemas.analytics import DateWindows
from pulseops.backend.tools.analyze_funnel import analyze_funnel
from pulseops.backend.tools.compare_segments import compare_segments
from pulseops.backend.tools.scan_metrics import scan_metrics
from pulseops.backend.tools.validate_data import validate_data

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


def create_app(
    *,
    database_url: str | None = None,
    runner: AnalysisRunner | None = None,
) -> FastAPI:
    engine, sessions = create_database(database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        init_database(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="PulseOps Analytics Backend",
        version="0.4.0",
        lifespan=lifespan,
    )
    application.state.database_engine = engine
    application.state.run_service = RunService(sessions, runner or DefaultAnalysisRunner())
    application.include_router(product_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/analytics/validate")
    def validate(request: ValidationRequest):
        return validate_data(_executor(), request, request.minimum_view_sessions)

    @application.post("/analytics/metrics/scan")
    def metrics(request: DateWindows):
        return scan_metrics(_executor(), **request.model_dump())

    @application.post("/analytics/funnel")
    def funnel(request: FunnelRequest):
        values = request.model_dump(exclude={"events"})
        return analyze_funnel(_executor(), request.events, **values)

    @application.post("/analytics/segments")
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

    return application


app = create_app()

