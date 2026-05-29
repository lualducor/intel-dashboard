from __future__ import annotations

import glob
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings


def backup(*, db_path=None, backup_dir=None, keep=None) -> Path:
    s = get_settings()
    db_path = Path(db_path or s.db_path)
    backup_dir = Path(backup_dir or s.backup_dir)
    keep = keep if keep is not None else s.backup_keep

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    dest = backup_dir / f"intel_{stamp}.db"

    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(dest))
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    files = sorted(
        backup_dir.glob("intel_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for old in files[keep:]:
        old.unlink()
    return dest


if __name__ == "__main__":
    print("backup written:", backup())
