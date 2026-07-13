# INTEL Dashboard

A single-user, **local-first intelligence triage system**. INTEL fetches trusted RSS
sources, normalizes and deduplicates articles, scores them with an explainable
deterministic pipeline, presents them in triage queues, learns from your actions,
and exports what you save — all running on your own machine against a local SQLite
database.

Built with FastAPI + SQLAlchemy + SQLite + Jinja/HTMX, with a dark "command-center"
UI (IBM Plex Sans/Mono).

---

## Features

- **RSS ingestion** from a curated, editable source set (`app/sources.yaml`):
  AI/Tech, Colombia/Bogotá, Crypto, and a daily Cancer horoscope.
- **Explainable deterministic scorer** (`v1_base`) — every article gets a 0–1 score
  with a plain-text explanation. No black box:

  | Signal   | Weight | What it measures |
  |----------|:------:|------------------|
  | source   | 0.20 | trust × priority of the source |
  | freshness| 0.20 | exponential decay by age |
  | keyword  | 0.20 | saturating sum of matched interest buckets |
  | category | 0.10 | category priority from `interests.yaml` |
  | feedback | 0.20 | learned affinity from your past actions |
  | novelty  | 0.10 | 1 − title similarity vs. the last 24h |

- **Triage queues** derived from score + your actions: `Must Read`, `Maybe Useful`,
  `For Content`, `Noise`.
- **Side panels:** Colombia/Bogotá, Crypto, and a daily **Cancer horoscope** (pulled
  from a JSON horoscope API with a fallback source).
- **Daily briefing** — a generated summary of the top stories.
- **Feedback learning** — save / archive / useful / not-relevant actions feed
  source/tag/category affinity maps that nudge future scores.
- **Keyboard-driven triage** — `j/k` to move, `s/a/u/n` to act, `o` to open, `c` to
  copy, `/` to search, `?` for the shortcut overlay.
- **Saved & archive**, full-text **search** (SQLite FTS5), per-article **notes**, and
  **content-use tracking** (mark an article for Twitch / LinkedIn / blog / project /
  job, with an angle and hook).
- **Source health** monitoring with automatic exponential backoff and deactivation of
  failing feeds.
- **Config & knowledge export**, DB backup/prune scripts, and a score-debug view.
- **Local-first by design** — no external accounts, no telemetry; the optional AI
  enrichment schema stays out of the ingest path.

---

## Quick start

```sh
git clone https://github.com/lualducor/intel-dashboard.git
cd intel-dashboard

python -m venv .venv && source .venv/bin/activate
pip install -c requirements.lock -e ".[dev]"

cp .env.example .env          # optional — sane defaults work without it
alembic upgrade head          # create the SQLite schema
python -m scripts.seed_sources # load app/sources.yaml into the DB

uvicorn app.main:app --reload
```

Then open:

- **Dashboard:** http://localhost:8000
- **Interactive API docs:** http://localhost:8000/docs

Click **Refresh All** (top-right) to run an ingest pass and refresh the horoscope, or
trigger it directly:

```sh
curl -X POST http://localhost:8000/ingest/run        # fetch all active sources
curl -X POST http://localhost:8000/horoscope/refresh  # refresh today's horoscope
```

Requires **Python 3.12+**.

---

## Configuration

Settings load from environment variables (prefix `INTEL_`) or a `.env` file. See
`.env.example` for the full list. Common knobs:

| Variable | Default | Purpose |
|----------|---------|---------|
| `INTEL_DB_PATH` | `./data/intel.db` | SQLite database location |
| `INTEL_THRESHOLD_MUST_READ` | `0.70` | min score for the Must-Read queue |
| `INTEL_THRESHOLD_MAYBE_USEFUL` | `0.40` | min score for the Maybe-Useful queue |
| `INTEL_FEED_PAGE_SIZE` | `50` | cards loaded per dashboard page (max 200) |
| `INTEL_DISPLAY_TZ` | `America/Bogota` | timezone for displayed timestamps |
| `INTEL_HTTP_TIMEOUT_SECONDS` | `15` | per-request fetch timeout |
| `INTEL_PRUNE_DAYS` | `180` | retention window for pruning |

**Sources** are defined in `app/sources.yaml` (slug, feed URL, topic, trust/priority).
**Interests** — keyword buckets, weights, and category priorities — live in
`app/interests.yaml` and drive the keyword/category scores. Edit either file and re-run
`python -m scripts.seed_sources` to apply source changes.

---

## Project layout

```
app/
  main.py            FastAPI app + router wiring
  config.py          pydantic-settings (INTEL_ env prefix)
  models.py          SQLAlchemy ORM (full schema)
  sources.yaml       curated RSS sources
  interests.yaml     keyword buckets + category priorities
  routers/           dashboard, feed, ingest, horoscope, search, saved,
                     briefing, actions, notes, content, clip, export, ...
  services/          ingest, rss, normalizer, scorer, tagger, derive,
                     feedback, queues, briefing, horoscope, search, ...
  templates/         Jinja + HTMX views
  static/            style.css (dark command-center theme), shortcuts.js
scripts/             seed_sources, cron_ingest, backup_db, prune, export_config, ...
alembic/             migrations
tests/               pytest suite
```

---

## Testing

```sh
python -m pytest tests/ -v
```

The suite covers the scorer, ingest pipeline, queue assignment, routes, search,
feedback, and the source admin / health flows.

The dashboard loads queues incrementally and includes an explicit inbox cleanup
control for archiving untouched AI stories older than 30, 60, or 90 days. Saved,
used, Colombia, crypto, and horoscope items are never affected by that bulk action.

---

## How ingestion works

```
acquire file lock → read active sources → for each due source:
  fetch RSS (outside any DB txn) → normalize + dedupe → tag + categorize →
  score (deterministic) → insert article + tags + score_run → update source health
```

HTTP and parsing happen outside DB transactions; a file lock prevents overlapping
ingest passes. Due-time uses exponential backoff per source based on consecutive
failures. The horoscope is fetched out-of-band from a JSON API (the RSS feed is
unreliable) and upserted as a single `topic=horoscope` article per day.

---

## License

Personal project — no license specified yet. Ask before reuse.
