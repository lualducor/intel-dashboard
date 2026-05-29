"""Full-text search (PLAN.md §4.2 / Phase 4.2).

Searches the articles_fts FTS5 virtual table AND notes.body, merges the matching
article ids, and returns articles ordered by final_score.
"""

from __future__ import annotations

import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import Article, Note


def _fts_query(q: str) -> str:
    """Build a safe FTS5 MATCH expression from arbitrary user input.

    Only alphanumeric tokens are kept (so no FTS5 operator can be injected),
    each is turned into a prefix term, and they are AND-combined (implicit).
    """
    tokens = re.findall(r"\w+", q, flags=re.UNICODE)
    return " ".join(f"{t}*" for t in tokens)


def search_articles(db: Session, q: str, *, limit: int = 100) -> list[Article]:
    """Return articles matching q via FTS5 title/summary OR a matching note body."""
    q = (q or "").strip()
    if not q:
        return []

    ids: set[int] = set()

    fts_expr = _fts_query(q)
    if fts_expr:
        rows = db.execute(
            text("SELECT rowid FROM articles_fts WHERE articles_fts MATCH :expr"),
            {"expr": fts_expr},
        ).all()
        ids.update(r[0] for r in rows)

    # notes.body substring match (LIKE; q is bound, so safely escaped)
    note_ids = db.scalars(
        select(Note.article_id).where(Note.body.like(f"%{q}%"))
    )
    ids.update(note_ids)

    if not ids:
        return []

    stmt = (
        select(Article)
        .where(Article.id.in_(ids))
        .order_by(Article.final_score.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
