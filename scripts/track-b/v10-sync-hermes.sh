#!/usr/bin/env bash
# Tar-sync golden scaffold .hermes → the Running DevWorkspace modernized tree.
# Idempotent. Wipes pod .hermes first so leftovers cannot poison digests.
# Usage:
#   V10_WS_NAME=petclinic-rest-v5 bash scripts/track-b/v10-sync-hermes.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

load_env >/dev/null 2>&1 || true
check_oc_logged_in

WS_NAME="$(qg_ws_name)" || {
  echo "v10-sync-hermes: REFUSE — set V10_WS_NAME or ensure one Running DevWorkspace" >&2
  exit 1
}
NS="$(qg_ws_ns)"
CTR="$(qg_ws_ctr)"
SCAFFOLD="${HERMES_PARITY_ROOT:-${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold}"
HARNESS_SRC="${SCAFFOLD}/.hermes"

if [[ ! -d "$HARNESS_SRC" ]]; then
  echo "v10-sync-hermes: missing golden .hermes at $HARNESS_SRC" >&2
  exit 1
fi

POD="$(qg_ws_pod)" || {
  echo "v10-sync-hermes: REFUSE — no Running pod for ${WS_NAME}" >&2
  exit 1
}

n_files="$(find "$HARNESS_SRC" -type f ! -name '._*' ! -name '.DS_Store' | wc -l | tr -d ' ')"
echo "v10-sync-hermes: ${WS_NAME} → ${NS}/${POD} (${n_files} golden files)"

oc exec -n "$NS" "$POD" -c "$CTR" -- \
  bash -lc 'cd /projects/modernized && rm -rf .hermes && mkdir -p .hermes'

( cd "$SCAFFOLD" && COPYFILE_DISABLE=1 tar cf - .hermes ) | oc exec -i -n "$NS" "$POD" -c "$CTR" -- \
  bash -lc 'cd /projects/modernized && tar xf - && find .hermes -name "._*" -delete 2>/dev/null || true'

# Clear start-blocking markers (fresh wave — never resume a prior outer).
oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  rm -f /tmp/outer-loop-done /tmp/debt-freeze /tmp/supervisor-pause \
        /tmp/outer-loop.lock /tmp/supervisor.lock /tmp/worker-wedge-skip \
        /projects/modernized/migration/findings-delta.STALE \
        /projects/modernized/migration/.stopped \
        /projects/modernized/migration/.supervisor-pause 2>/dev/null || true
  # Prefer KANTRA_HOME layout when helper exists.
  export KANTRA_HOME="${KANTRA_HOME:-/projects/.tools/kantra}"
  if command -v kantra-ensure >/dev/null 2>&1; then
    kantra-ensure || true
  fi
  if [ -x "${KANTRA_HOME}/kantra" ] || [ -f "${KANTRA_HOME}/kantra" ]; then
    echo "kantra-ok:${KANTRA_HOME}/kantra"
  elif [ -x /tmp/kantra/kantra ]; then
    echo "kantra-ok:/tmp/kantra/kantra"
  else
    echo "WARN: kantra binary still missing — M1 analyze will fail until installed"
  fi
'

qg_remote_orchestrator_preflight || {
  echo "v10-sync-hermes: WARN orchestrator preflight RED after sync" >&2
  exit 1
}

echo "v10-sync-hermes: OK"
