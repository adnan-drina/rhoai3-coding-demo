#!/usr/bin/env bash
# O-IDLEWSFP — dual idle clock for Track B review/wake.
# Usage:
#   bash scripts/track-b/v10-idle-clock.sh [--json]
# Prints:
#   workspace_fp=<head>-<outer>-<sup>   # run clock (stall detection)
#   run_idle_s=<seconds since workspace_fp changed>
#   agent_idle_s=<seconds since harness/project activity>  # implementing clock
#   idle_note_basis=workspace_fp        # mandatory: run idle uses workspace only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

JSON=0
[ "${1:-}" = "--json" ] && JSON=1

load_env >/dev/null 2>&1 || true
check_oc_logged_in >/dev/null 2>&1 || true

WS="${V10_WS_NAME:-petclinic-rest-v3}"
NS="${V10_NS:-wksp-ai-developer}"
STATE="${ROOT}/tmp/V10-IDLE-CLOCK.state"
POLL="${ROOT}/tmp/KAI-POLL-STATE.txt"
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"

pod="$(oc get pod -n "$NS" -l "controller.devfile.io/devworkspace_name=${WS}" \
  --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"

head="unknown"; outer=0; sup=0
if [ -n "$pod" ]; then
  read -r head outer sup < <(oc exec -n "$NS" "$pod" -c development-tooling -- bash -lc '
    h=$(git -C /projects/modernized rev-parse --short HEAD 2>/dev/null || echo none)
    o=0; pgrep -f "[.]hermes/harness/outer-loop[.]sh" >/dev/null && o=1
    s=0; pgrep -f "[.]hermes/harness/supervisor[.]sh" >/dev/null && s=1
    echo "$h $o $s"
  ' 2>/dev/null | tr -d '\r' | sed 's/\x1b]633;[^\x07]*\x07//g' | tail -1)
fi
workspace_fp="${head}-${outer}-${sup}"

# Host harness fingerprint (agent-implementing clock only — not run idle).
harness_fp="$(
  cd "$HARNESS" 2>/dev/null && \
    find . -type f \( -name '*.sh' -o -name '*.py' \) -print0 \
      | sort -z | xargs -0 md5 -q 2>/dev/null | md5 -q 2>/dev/null \
      || echo none
)"
# Shorter portable fp
harness_fp="$(printf '%s' "$harness_fp" | cut -c1-12)"

now=$(date +%s)
prev_ws=""; prev_ws_ts=0; prev_ag=""; prev_ag_ts=0
if [ -f "$STATE" ]; then
  # shellcheck disable=SC1090
  source "$STATE" || true
  prev_ws="${workspace_fp_prev:-}"
  prev_ws_ts="${workspace_fp_ts:-0}"
  prev_ag="${agent_fp_prev:-}"
  prev_ag_ts="${agent_fp_ts:-0}"
fi

if [ "$workspace_fp" != "$prev_ws" ]; then
  prev_ws_ts=$now
  prev_ws=$workspace_fp
fi
if [ "$harness_fp" != "$prev_ag" ]; then
  prev_ag_ts=$now
  prev_ag=$harness_fp
fi

run_idle_s=$((now - prev_ws_ts))
agent_idle_s=$((now - prev_ag_ts))

cat >"$STATE" <<EOF
workspace_fp_prev=$prev_ws
workspace_fp_ts=$prev_ws_ts
agent_fp_prev=$prev_ag
agent_fp_ts=$prev_ag_ts
EOF

# Keep poll-state comment contract honest when file exists.
if [ -f "$POLL" ]; then
  # Do not rewrite idle_note_level here — review agent owns ladder; we only
  # document the basis so harness_fp churn cannot be mistaken for run progress.
  :
fi

if [ "$JSON" = "1" ]; then
  printf '{"workspace_fp":"%s","harness_fp":"%s","run_idle_s":%s,"agent_idle_s":%s,"idle_note_basis":"workspace_fp"}\n' \
    "$workspace_fp" "$harness_fp" "$run_idle_s" "$agent_idle_s"
else
  echo "workspace_fp=$workspace_fp"
  echo "harness_fp=$harness_fp"
  echo "run_idle_s=$run_idle_s"
  echo "agent_idle_s=$agent_idle_s"
  echo "idle_note_basis=workspace_fp"
fi
