#!/usr/bin/env bash
# Cron/launchd entry point for the 9router model dashboard.
# Nothing installs this automatically: see docs/REFRESH.md.
#
#   REFRESH_ARGS="--offline"   extra flags passed to the dashboard command
#   REFRESH_OUT=...            report path  (default dist/models.html)
#   REFRESH_LOG=...            log path     (default dist/refresh.log)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${REFRESH_OUT:-$ROOT/dist/models.html}"
LOG="${REFRESH_LOG:-$ROOT/dist/refresh.log}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

mkdir -p "$(dirname "$OUT")" "$(dirname "$LOG")"
echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) refresh $OUT" >>"$LOG"

set +e
# shellcheck disable=SC2086  # REFRESH_ARGS is intentionally word-split
"$PY" -m nine_router_followup dashboard --out "$OUT" --skip-if-busy ${REFRESH_ARGS:-} >>"$LOG" 2>&1
CODE=$?
set -e

if [ "$(wc -l <"$LOG")" -gt 500 ]; then
  tail -n 500 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

exit "$CODE"
