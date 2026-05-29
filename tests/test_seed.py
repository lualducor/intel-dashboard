from sqlalchemy import func, select

from app.models import Source
from scripts.seed_sources import seed


def test_seed_is_idempotent(db_factory):
    r1 = seed(session_factory=db_factory)
    assert r1["created"] >= 12
    assert r1["updated"] == 0

    r2 = seed(session_factory=db_factory)
    assert r2["created"] == 0
    assert r2["updated"] == r1["total"]

    db = db_factory()
    assert db.scalar(select(func.count()).select_from(Source)) == r1["total"]
    db.close()
