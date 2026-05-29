"""Filelock wrapper for the ingest mutex (PLAN.md §2.3, §7 Phase 1.7).

filelock is blocking/sync; in async ingest routes acquire via
asyncio.to_thread(lock.acquire, timeout=0.5) and release in finally.
"""

from __future__ import annotations

from filelock import FileLock, Timeout  # noqa: F401  (re-exported)

from ..config import Settings


def make_ingest_lock(settings: Settings) -> FileLock:
    settings.ensure_directories()
    # thread_local=False is required: we acquire in a worker thread (via
    # asyncio.to_thread) and release in the event-loop thread. With the default
    # thread-local state the release would be a no-op and the flock would leak.
    return FileLock(str(settings.lock_dir / "ingest.lock"), thread_local=False)
