#!/usr/bin/env bash
# External watchdog: keeps v9-ensure-driver.sh running outside Cursor.
# Prefer launchd (macOS) — see scripts/track-b/com.rhoai3.v9-driver-watchdog.plist.example
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INTERVAL="${V9_WATCHDOG_INTERVAL:-60}"
echo "watchdog: interval=${INTERVAL}s root=$ROOT"
while true; do
  bash "${ROOT}/scripts/track-b/v9-ensure-driver.sh" || true
  sleep "$INTERVAL"
done
