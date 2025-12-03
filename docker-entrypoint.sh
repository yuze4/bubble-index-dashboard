#!/bin/sh
set -e

MODE=${1:-serve}
shift || true

case "$MODE" in
  serve)
    echo "[entrypoint] Computing bubble index (USE_PLACEHOLDERS=${USE_PLACEHOLDERS:-true})"
    python /app/bubble_calc.py
    echo "[entrypoint] Starting static server on :8000"
    exec python -m http.server 8000 --directory /app
    ;;
  compute)
    echo "[entrypoint] Computing bubble index only"
    exec python /app/bubble_calc.py "$@"
    ;;
  *)
    echo "[entrypoint] Exec passthrough: $MODE $@"
    exec "$MODE" "$@"
    ;;
esac
