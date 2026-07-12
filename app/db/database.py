from __future__ import annotations

import os
from collections.abc import Generator

from app.config.settings import get_settings

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session, sessionmaker
except ImportError as exc:  # pragma: no cover - shown in UI when deps are missing.
    raise RuntimeError(
        "SQLAlchemy is required. Install dependencies with: python -m pip install -r requirements.txt"
    ) from exc

from app.db.models import Base
from app.db.schema import ensure_runtime_schema

settings = get_settings()

database_url = settings.database_url
database_schema = os.getenv("DATABASE_SCHEMA", "").strip()

is_sqlite = database_url.startswith("sqlite")
is_postgres = database_url.startswith("postgresql")

connect_args: dict[str, object] = {}

if is_sqlite:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connect_args["check_same_thread"] = False

elif is_postgres:
    # PostgreSQL: no filesystem path. Use schema/search_path when configured.
    # This lets the app operate against the shortsfactory schema instead of public.
    if database_schema:
        connect_args["options"] = f"-csearch_path={database_schema},public"

else:
    raise ValueError(
        "Unsupported DATABASE_URL. Use sqlite:///... or postgresql/postgresql+psycopg://..."
    )

engine = create_engine(
    database_url,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    if is_postgres and database_schema:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{database_schema}"'))

    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def new_session() -> Session:
    return SessionLocal()
