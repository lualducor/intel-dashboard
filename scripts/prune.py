from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from app.config import get_settings
from app.db import SessionLocal
from app.models import Article

def prune(*, session_factory=SessionLocal, settings=None, now=None) -> int:
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.prune_days)
    db = session_factory()
    try:
        ids = list(db.scalars(select(Article.id).where(Article.status.in_(["ignored", "archived"]), Article.fetched_at < cutoff)))
        if ids:
            db.execute(delete(Article).where(Article.id.in_(ids)))
            db.commit()
        return len(ids)
    finally:
        db.close()

if __name__ == "__main__":
    print("pruned:", prune())
