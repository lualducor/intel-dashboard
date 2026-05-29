"""Shared Jinja2 templates instance.

Lives in its own module so routers can import `templates` without importing
app.main (which would create a circular import).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from .config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def to_bogota_local(dt: datetime | None, settings=None):
    if dt is None:
        return None
    if settings is None:
        settings = get_settings()
    if dt.tzinfo is not None:
        return dt.astimezone(ZoneInfo(settings.display_tz))
    return dt


templates.env.filters["to_bogota_local"] = to_bogota_local
