from app.config import get_settings
from app.services import ingest
from app.services.lock import make_ingest_lock


async def test_run_ingest_skips_when_lock_held(db_factory):
    settings = get_settings()  # temp settings (lock dir under tmp_path)
    held = make_ingest_lock(settings)
    held.acquire()
    try:
        res = await ingest.run_ingest(
            settings=settings, session_factory=db_factory, force=True
        )
    finally:
        held.release()
    assert res == {"locked": True, "skipped": True}
