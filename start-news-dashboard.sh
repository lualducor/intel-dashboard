#!/usr/bin/env bash
# INTEL News Dashboard launcher — idempotent start + RSS refresh.
# Used by the workspace orchestrator (start-all-dashboards.sh) on login.
set -euo pipefail

DASHBOARD_DIR="/home/lu47/Desktop/Lucholabs/WORKSPACE/proyects/NEWSDASHBOARD"
PORT=8099
HEALTH_URL="http://127.0.0.1:${PORT}/healthz"
INGEST_URL="http://127.0.0.1:${PORT}/ingest/run"
LOG="/tmp/news-dashboard.log"

cd "$DASHBOARD_DIR"

is_up() { curl -fsS -o /dev/null "$HEALTH_URL" 2>/dev/null; }

if is_up; then
  echo "[news] already running on port ${PORT}"
else
  echo "[news] starting INTEL dashboard on port ${PORT}..."
  setsid nohup "${DASHBOARD_DIR}/.venv/bin/uvicorn" app.main:app \
    --host 127.0.0.1 --port "${PORT}" \
    > "$LOG" 2>&1 < /dev/null &
  for _ in $(seq 1 60); do
    is_up && break
    sleep 0.5
  done
  if ! is_up; then
    echo "[news] FAILED to start. Logs: $LOG" >&2
    exit 1
  fi
  echo "[news] up. Logs: $LOG"
fi

# Refresh: fire ingest in the background, retry if network not yet up.
(
  for attempt in 1 2 3 4 5; do
    if curl -fsS -X POST "$INGEST_URL" -o /dev/null --max-time 120; then
      echo "[news] ingest refresh ok (attempt $attempt)" >> "$LOG"
      exit 0
    fi
    sleep $((attempt * 5))
  done
  echo "[news] ingest refresh failed after 5 attempts" >> "$LOG"
) &

echo "[news] ready at http://localhost:${PORT}/"
