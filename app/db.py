"""Database engine, session factory, and declarative Base.

SQLite is configured per PLAN.md §2.1/§2.3:
  PRAGMA foreign_keys=ON, journal_mode=WAL, busy_timeout=30000, synchronous=NORMAL
  connect_args: check_same_thread=False, timeout=30
The PRAGMA bundle is applied on every connection via a connect-event listener.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

# Stable naming convention so Alembic autogenerate produces deterministic names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _db_url(db_path: str | Path) -> str:
    resolved = Path(db_path).expanduser().resolve()
    return f"sqlite:///{resolved}"


def _register_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def make_engine(db_path: str | Path | None = None) -> Engine:
    """Build an engine with the PRAGMA bundle attached.

    Pass an explicit db_path in tests to target a temp DB.
    """
    path = db_path if db_path is not None else get_settings().db_path
    engine = create_engine(
        _db_url(path),
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )
    _register_pragmas(engine)
    return engine


engine = make_engine()
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=Session
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
