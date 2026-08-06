#!/usr/bin/env bash
# ADR-27 / ADR-28 — atomic M1 architecture revalidation (no mid-seat harness edits).
#
# Use AFTER golden publish when PROFILE/ANALYZE architecture must be re-proven:
#   bash scripts/bootstrap-scaffold-repos.sh
#   STOP_AFTER_M1=1 bash scripts/track-b/v10-m1-arch-revalidate.sh          # PROFILE only
#   STOP_AFTER_M1=1 bash scripts/track-b/v10-m1-arch-revalidate.sh --full   # ANALYZE+PROFILE wipe
#
# Guarantees:
#   1. Refuses if a MiniMax/Hermes PROFILE (or M2/M3) seat is in flight
#   2. Stops only an *idle* outer (lock present, no active mchat log growth)
#   3. Syncs golden .hermes → pod
#   4. Clears PROFILE stamp (default) or full M1 analyze+profile artifacts (--full)
#   5. Starts outer with STOP_AFTER_M1 (default) — never kills mid-prompt
#
# Do NOT call v10-sync-hermes.sh by hand while outer is in mchat — that is the
# Wave-5 waste mode this script exists to prevent.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

load_env >/dev/null
check_oc_logged_in

FULL=0
ARCHIVE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --full) FULL=1 ;;
    --no-archive) ARCHIVE=0 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "v10-m1-arch-revalidate: unknown arg: $1" >&2
      exit 2
      ;;
  esac
  shift
done

export V10_WS_NAME="${V10_WS_NAME:-petclinic-rest-v5}"
POD="$(qg_ws_pod)"
NS="$(qg_ws_ns)"
CTR="$(qg_ws_ctr)"

seat_busy() {
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    # Active Hermes PROFILE/M2/M3 session logs updated in the last 90s
    for f in /tmp/outer-m1-profile-a*.log /tmp/outer-m2-sequence-a*.log /tmp/outer-m3-*.log; do
      [ -f "$f" ] || continue
      # mtime within 90s ⇒ seat likely live
      if [ "$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0) ))" -lt 90 ]; then
        if pgrep -f "hermes|minimax|opencode" >/dev/null 2>&1; then
          echo BUSY:$f
          exit 0
        fi
      fi
    done
    echo IDLE
  ' 2>/dev/null || echo UNKNOWN
}

BUSY="$(seat_busy)"
if [[ "$BUSY" == BUSY:* ]]; then
  echo "v10-m1-arch-revalidate: REFUSE — LLM seat in flight ($BUSY)" >&2
  echo "  Wait for the seat to finish (or deliberate-stop). Never sync/kill mid-mchat." >&2
  exit 2
fi

if [ "$ARCHIVE" = "1" ]; then
  echo "v10-m1-arch-revalidate: archiving before wipe"
  _arch_label="${V10_ARCHIVE_LABEL:-}"
  if [ -z "${_arch_label}" ]; then
    _arch_label="m1-revalidate"
    [ "$FULL" = "1" ] && _arch_label="${_arch_label}-full"
  fi
  V10_ARCHIVE_LABEL="${_arch_label}" \
    bash "${ROOT}/scripts/track-b/v10-archive-before-wipe.sh" \
      --label "${_arch_label}"
fi

echo "v10-m1-arch-revalidate: stopping idle outer (if any)"
oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  cd /projects/modernized
  if [ -f /tmp/outer-loop.lock ]; then
    pid=$(tr -dc 0-9 </tmp/outer-loop.lock || true)
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      sleep 2
    fi
  fi
  rm -f /tmp/outer-loop.lock /tmp/outer-loop-done migration/.stopped
'

if [ "$FULL" = "1" ]; then
  echo "v10-m1-arch-revalidate: FULL wipe — M1 ANALYZE + PROFILE artifacts"
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    set -euo pipefail
    cd /projects/modernized
    # M1 stamps / hold
    rm -f migration/.m1-analyze.stamp.json \
          migration/.m1-profile.stamp.json \
          migration/.stopped \
          migration/.profile-coverage \
          migration/.profile-coverage-best \
          /tmp/profile-rubric.txt
    # PROFILE deliverable
    rm -f migration/architecture-profile.md
    # ANALYZE / model / findings control plane (ADR-24/25/26)
    rm -f migration/model.json \
          migration/findings.json \
          migration/mta-findings.json \
          migration/mta-findings-dest-baseline.json \
          migration/findings-inventory.md \
          migration/dependency-order.md \
          migration/recipe-log.md \
          migration/ruleset-coverage.md \
          migration/scaffold-presatisfied.generated.txt
    rm -rf migration/staging
    # Keep migration.yaml, README, debt, run-log, run-archives (history).
    # Commit wipe so O-M1SKIPPROV cannot resurrect deleted paths from HEAD.
    if [ -n "$(git status --porcelain migration/ 2>/dev/null || true)" ]; then
      git add -A migration/
      SKIP_SENSOR_GATE=1 git commit -q -m "chore: wipe M1 analyze+profile for architecture revalidate" \
        || true
    fi
    echo WIPED_TIP=$(git rev-parse --short HEAD)
    echo WIPED_MIGRATION=
    ls migration/ | sed "s/^/  /"
  '
else
  # PROFILE wipe keeps ANALYZE stamps + model universe/findings; clears the
  # PROFILE seat surface so ADR-29 / O-PROF1OF79STOP revalidate is honest
  # (not a resume of a 10/79 dirty tree).
  echo "v10-m1-arch-revalidate: PROFILE wipe (keeps analyze + model units/findings)"
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    set -euo pipefail
    cd /projects/modernized
    rm -f migration/.m1-profile.stamp.json \
          migration/.stopped \
          migration/.profile-coverage \
          migration/.profile-coverage-best \
          migration/architecture-profile.md \
          migration/profile-decisions.json \
          migration/profile-roles.json \
          /tmp/outer-loop-done \
          /tmp/profile-rubric.txt
    # Clear typed decisions on the model SoT; keep units/findings/SCC/order.
    if [ -f migration/model.json ]; then
      python3 - <<'"'"'PY'"'"'
import json
from pathlib import Path
p = Path("migration/model.json")
m = json.loads(p.read_text(encoding="utf-8"))
n = 0
for u in m.get("units") or []:
    if u.get("decision") is not None:
        u["decision"] = None
        n += 1
prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
for k in ("profile_coverage", "profile_coverage_best", "profile_coverage_sot"):
    if k in prov:
        prov.pop(k, None)
m["provenance"] = prov
p.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
print(f"CLEARED_DECISIONS={n}")
PY
    fi
    if [ -n "$(git status --porcelain migration/ 2>/dev/null || true)" ]; then
      git add -A migration/
      SKIP_SENSOR_GATE=1 git commit -q -m "chore: wipe M1 profile for architecture revalidate" \
        || true
    fi
    echo WIPED_TIP=$(git rev-parse --short HEAD)
    echo WIPED_PROFILE_KEEP_ANALYZE=1
  '
fi

echo "v10-m1-arch-revalidate: syncing golden .hermes"
bash "${ROOT}/scripts/track-b/v10-sync-hermes.sh"

echo "v10-m1-arch-revalidate: starting STOP_AFTER_M1 outer"
STOP_AFTER_M1="${STOP_AFTER_M1:-1}" M3_ALL="${M3_ALL:-1}" V9_AUTO_HERMES_SYNC=1 \
  bash "${ROOT}/scripts/track-b/v9-preflight-outer-start.sh" --start

MODE="PROFILE-only"
[ "$FULL" = "1" ] && MODE="FULL ANALYZE+PROFILE"
echo "v10-m1-arch-revalidate: OK — outer started under STOP_AFTER_M1 (${MODE}); await dual ACCEPT before M2"
