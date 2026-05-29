from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _aware(dt):
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def derive_status(source, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if not source.active:
        return "inactive"

    cf = source.consecutive_failures
    if cf >= 5:
        return "needs_review"
    if 3 <= cf < 5:
        return "broken"
    if 1 <= cf < 3:
        return "degraded"

    last = _aware(source.last_success_at)
    interval = timedelta(minutes=source.fetch_interval_minutes)
    if last is not None and last >= now - 2 * interval:
        return "healthy"
    return "stale"
