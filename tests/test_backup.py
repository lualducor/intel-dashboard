from __future__ import annotations

import sqlite3

from sqlalchemy import func, select

from app.config import get_settings
from app.models import Article, Source
from scripts.backup_db import backup


def test_backup_copies_articles(db_factory, tmp_path):
    session = db_factory()
    source = Source(
        slug="backup-test",
        name="Backup Test",
        url="https://example.com",
        kind="rss",
        source_type="news",
        topic="ai",
    )
    session.add(source)
    session.flush()
    session.add(
        Article(
            source_id=source.id,
            title="Backup Article",
            raw_title="Backup Article",
            normalized_title="backup article",
            original_url="https://example.com/a1",
            canonical_url="https://example.com/a1",
            dedup_hash="backup-hash",
            content_hash="backup-content-hash",
            language="en",
            country_scope="global",
            topic="ai",
            urgency="normal",
            reading_time_minutes=1,
            scraping_method="rss",
        )
    )
    session.commit()

    live_count = session.scalar(select(func.count()).select_from(Article))
    dest = backup(
        db_path=get_settings().db_path, backup_dir=tmp_path / "backups", keep=30
    )

    assert dest.exists()
    conn = sqlite3.connect(str(dest))
    try:
        backed_up_count = conn.execute("SELECT count(*) FROM articles").fetchone()[0]
    finally:
        conn.close()
        session.close()

    assert backed_up_count == live_count
