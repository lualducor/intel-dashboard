# INTEL Dashboard

INTEL is a single-user, local-first intelligence triage system that fetches trusted RSS sources, normalizes and deduplicates articles, scores them with an explainable deterministic pipeline, presents them in triage queues, learns from user actions, exports saved knowledge, and can optionally enrich articles with local AI outside the ingest path.

## Quick start

```sh
git clone ... && cd NEWSDASHBOARD
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m scripts.seed_sources
uvicorn app.main:app --reload
```

`../../dashboard/news/PLAN.md` is the canonical spec.
