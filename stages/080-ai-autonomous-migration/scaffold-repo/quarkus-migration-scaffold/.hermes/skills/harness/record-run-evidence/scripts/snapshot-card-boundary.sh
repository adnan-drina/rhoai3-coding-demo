#!/usr/bin/env bash
# Fail-open run-audit snapshot at a card boundary (create · claim · block ·
# reclaim · complete). Never a gate. Exit 0 even when snapshot fails.
#
# Usage: snapshot-card-boundary.sh [create|claim|block|reclaim|complete]
set -u
BOUNDARY="${1:-unknown}"

resolve_migration_root() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}

ROOT="$(resolve_migration_root)" || {
  echo "snapshot-card-boundary: no migration.yaml walking up (SR-2); skip" >&2
  exit 0
}
SNAP="${ROOT}/.hermes/skills/harness/record-run-evidence/scripts/snapshot-run-audit.py"
[[ -f "${SNAP}" ]] || {
  echo "snapshot-card-boundary: missing ${SNAP}; skip" >&2
  exit 0
}
DB="${HERMES_HOME:-${ROOT}/.hermes/home}/kanban.db"
ARGS=("${SNAP}" "${ROOT}" "--boundary" "${BOUNDARY}")
if [[ -f "${DB}" ]]; then
  ARGS+=(--db "${DB}")
fi
python3 "${ARGS[@]}" >/dev/null || echo "snapshot-card-boundary: snapshot failed (fail-open)" >&2
exit 0
