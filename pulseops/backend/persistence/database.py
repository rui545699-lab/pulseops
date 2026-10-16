from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from pulseops.backend.persistence.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./pulseops.db"


def create_database(database_url: str | None = None) -> tuple[Engine, sessionmaker[Session]]:
    url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def init_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        _evolve_sqlite_schema(engine)


def _evolve_sqlite_schema(engine: Engine) -> None:
    """Add nullable product fields without invalidating existing local databases."""
    additions = {
        "analysis_runs": {
            "analysis_type": "VARCHAR(64) NOT NULL DEFAULT 'CONVERSION'",
            "post_start": "DATE",
            "post_end": "DATE",
            "post_rate": "FLOAT",
            "target_to_post_delta_pp": "FLOAT",
            "baseline_to_post_delta_pp": "FLOAT",
            "recovery_ratio": "FLOAT",
            "risk_pattern": "VARCHAR(64)",
            "return_timing": "JSON",
            "confirmation_start": "DATE",
            "confirmation_end": "DATE",
            "holdout_1_start": "DATE",
            "holdout_1_end": "DATE",
            "holdout_2_start": "DATE",
            "holdout_2_end": "DATE",
            "growth_analysis": "JSON",
            "reproducibility": "VARCHAR(64)",
            "growth_signal_confidence": "VARCHAR(32)",
            "reproducibility_confidence": "VARCHAR(32)",
            "growth_localization": "VARCHAR(64)",
        },
        "opportunities": {
            "post_rate": "FLOAT",
            "target_to_post_delta_pp": "FLOAT",
            "baseline_to_post_delta_pp": "FLOAT",
            "recovery_ratio": "FLOAT",
            "risk_pattern": "VARCHAR(64)",
            "return_timing": "JSON",
            "segment_analysis": "JSON",
            "hypothesis_records": "JSON",
            "growth_period": "JSON",
            "confirmation_period": "JSON",
            "holdout_results": "JSON",
            "reproducibility": "VARCHAR(64)",
            "growth_signal_confidence": "VARCHAR(32)",
            "reproducibility_confidence": "VARCHAR(32)",
            "growth_localization": "VARCHAR(64)",
            "order_value_context": "JSON",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {item["name"] for item in inspect(connection).get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.exec_driver_sql(
                        f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'
                    )
