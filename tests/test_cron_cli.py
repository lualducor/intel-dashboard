from __future__ import annotations

from app.services import ingest
from scripts import cron_ingest


def test_cron_ingest_locked(monkeypatch, capsys):
    async def fake(**kw):
        return {"locked": True, "skipped": True}

    monkeypatch.setattr(ingest, "run_ingest", fake)

    assert cron_ingest.main() == 0
    assert "lock held" in capsys.readouterr().out


def test_cron_ingest_ok(monkeypatch, capsys):
    async def fake(**kw):
        return {
            "locked": False,
            "sources": [],
            "totals": {"items_seen": 0, "items_new": 0, "sources_run": 0},
        }

    monkeypatch.setattr(ingest, "run_ingest", fake)

    assert cron_ingest.main() == 0
    assert "ingest ok" in capsys.readouterr().out
