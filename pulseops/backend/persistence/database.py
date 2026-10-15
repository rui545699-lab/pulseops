from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
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
