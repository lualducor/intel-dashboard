import pytest
from app.config import Settings

def test_defaults():
    settings = Settings()
    assert settings.threshold_must_read == 0.70
    assert settings.display_tz == "America/Bogota"
    assert str(settings.db_path).endswith("intel.db")

def test_env_override(monkeypatch):
    monkeypatch.setenv("INTEL_THRESHOLD_MUST_READ", "0.9")
    settings = Settings()
    assert settings.threshold_must_read == 0.9

def test_ensure_directories(tmp_path):
    settings = Settings(
        db_path=tmp_path / "d/intel.db",
        cache_dir=tmp_path / "c",
        export_dir=tmp_path / "e",
        backup_dir=tmp_path / "b",
        lock_dir=tmp_path / "l",
        log_path=tmp_path / "logs/intel.log"
    )
    settings.ensure_directories()
    
    assert (tmp_path / "d").exists()
    assert (tmp_path / "c").exists()
    assert (tmp_path / "e").exists()
    assert (tmp_path / "b").exists()
    assert (tmp_path / "l").exists()
    assert (tmp_path / "logs").exists()
