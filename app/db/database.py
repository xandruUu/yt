from __future__ import annotations

from collections.abc import Generator

from app.config.settings import get_settings

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
except ImportError as exc:  # pragma: no cover - shown in UI when deps are missing.
    raise RuntimeError(
        "SQLAlchemy is required. Install dependencies with: python -m pip install -r requirements.txt"
    ) from exc

from app.db.models import Base
from app.db.schema import ensure_runtime_schema

settings = get_settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
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
