"""Application settings (pydantic-settings).

Every key from PLAN.md §5.1 is mirrored here with a sane default, so the app
boots without an .env file. Env vars use the INTEL_ prefix.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    db_path: Path = Path("./data/intel.db")
    cache_dir: Path = Path("./data/cache")
    export_dir: Path = Path("./data/exports")
    backup_dir: Path = Path("./data/backups")
    lock_dir: Path = Path("./data/locks")
    log_path: Path = Path("./data/intel.log")

    # HTTP
    user_agent: str = "intel-dashboard/0.1 (+local; lualducor@gmail.com)"
    http_timeout_seconds: int = 15

    # Paywall
    paywall_proxy_prefix: str = "https://removepaywalls.com/"

    # Retention
    prune_days: int = 180
    backup_keep: int = 30

    # Queue thresholds
    threshold_must_read: float = 0.70
    threshold_maybe_useful: float = 0.40

    # Feedback
    feedback_cold_floor: float = 0.3
    feedback_ramp_at_actions: int = 50

    # Display
    display_tz: str = "America/Bogota"

    # Ingest guardrail (L1: arXiv flooding). 0 = unlimited.
    max_items_per_pass: int = 0

    def ensure_directories(self) -> None:
        """Create all data/* directories on first run (PLAN.md §3)."""
        for directory in (
            self.db_path.parent,
            self.cache_dir,
            self.export_dir,
            self.backup_dir,
            self.lock_dir,
            self.log_path.parent,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
