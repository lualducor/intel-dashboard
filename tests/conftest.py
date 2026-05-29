"""Shared pytest fixtures.

`db_factory` builds a fully-migrated temp SQLite DB (via the real Alembic
migration, so the articles_fts virtual table + triggers exist) and returns a
session factory bound to it. Env vars point all data paths at tmp_path so tests
never touch the project's data/ directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from app.db import make_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db_factory(tmp_path, monkeypatch):
    db_file = tmp_path / "intel.db"
    monkeypatch.setenv("INTEL_DB_PATH", str(db_file))
    monkeypatch.setenv("INTEL_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("INTEL_LOG_PATH", str(tmp_path / "intel.log"))
    monkeypatch.setenv("INTEL_CACHE_DIR", str(tmp_path / "cache"))

    from app.config import get_settings

    get_settings.cache_clear()

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    engine = make_engine(str(db_file))
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()
        get_settings.cache_clear()
