#!/usr/bin/env bash
# O-PREPARCHEXIT — scoop pod seat logs + migration tree to the host BEFORE any
# wipe / prep-fresh-rerun that clears /tmp or resets the specimen.
#
# Usage:
#   V10_WS_NAME=petclinic-rest-v5 bash scripts/track-b/v10-archive-before-wipe.sh
#   bash scripts/track-b/v10-archive-before-wipe.sh --label s02-abort
#
# Writes: tmp/wipe-archives/<UTC>-<label>/
#   - seats.tgz          (/tmp/oc-* /tmp/sup-* /tmp/hermes-* /tmp/sensor-*)
#   - modernized-tree.tgz (migration/ specs/ src/ pom.xml migration.yaml …)
#   - git-head.txt run-archives.tgz MANIFEST.txt
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
# shellcheck source=/dev/null
source "${ROOT}/scripts/lib.sh"

LABEL="prewipe"
for a in "$@"; do
  case "$a" in
    --label) shift; LABEL="${1:-prewipe}" ;;
    --label=*) LABEL="${a#--label=}" ;;
  esac
done

load_env >/dev/null 2>&1 || true
check_oc_logged_in
WS_NAME="$(qg_ws_name)" || {
  echo "REFUSE: set V10_WS_NAME or ensure one Running DevWorkspace (O-HERMESWSRESOLVE)" >&2
  exit 1
}
NS="$(qg_ws_ns)"
POD="$(qg_ws_pod)"
CTR="$(qg_ws_ctr)"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${ROOT}/tmp/wipe-archives/${TS}-${LABEL}"
mkdir -p "$OUT"

echo "O-PREPARCHEXIT: scooping ${NS}/${POD} → ${OUT}"

# Seat / sensor forensics from /tmp (survive wipe that clears pod /tmp).
oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  set -euo pipefail
  cd /tmp
  COPYFILE_DISABLE=1 tar czf - \
    oc-*.json oc-*.err oc-*.log \
    sup-*.log hermes-*.log \
    sensor-*.log sonar-*.txt sonar-*.log \
    outer-loop.log supervisor.log \
    escalation-cause-* mechan-match.out \
    commit-hygiene.out scope-violation.txt \
    2>/dev/null || true
' > "${OUT}/seats.tgz" || true

# Durable run-archives already on disk (may be empty — still scoop).
oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  set -euo pipefail
  cd /projects/modernized
  if [ -d migration/run-archives ]; then
    COPYFILE_DISABLE=1 tar czf - migration/run-archives
  else
    COPYFILE_DISABLE=1 tar czf - --files-from /dev/null
  fi
' > "${OUT}/run-archives.tgz" || true

# Specimen tree needed to re-verify M4 analysis (specs + src + migration + pom).
oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
  set -euo pipefail
  cd /projects/modernized
  git rev-parse HEAD > /tmp/wipe-arch-head.txt
  git log -1 --format="%H %s" > /tmp/wipe-arch-subject.txt
  git status --porcelain > /tmp/wipe-arch-status.txt || true
  COPYFILE_DISABLE=1 tar czf - \
    migration specs src pom.xml migration.yaml devfile.yaml \
    /tmp/wipe-arch-head.txt /tmp/wipe-arch-subject.txt /tmp/wipe-arch-status.txt \
    /tmp/outer-loop-done \
    2>/dev/null || true
' > "${OUT}/modernized-tree.tgz"

oc exec -n "$NS" "$POD" -c "$CTR" -- cat /tmp/wipe-arch-head.txt \
  > "${OUT}/git-head.txt" 2>/dev/null || echo "unknown" > "${OUT}/git-head.txt"
oc exec -n "$NS" "$POD" -c "$CTR" -- cat /tmp/wipe-arch-subject.txt \
  > "${OUT}/git-subject.txt" 2>/dev/null || true

{
  echo "O-PREPARCHEXIT archive"
  echo "utc=${TS}"
  echo "label=${LABEL}"
  echo "ws=${WS_NAME}"
  echo "ns=${NS}"
  echo "pod=${POD}"
  echo "head=$(cat "${OUT}/git-head.txt")"
  echo "seats_bytes=$(wc -c < "${OUT}/seats.tgz" | tr -d ' ')"
  echo "tree_bytes=$(wc -c < "${OUT}/modernized-tree.tgz" | tr -d ' ')"
  echo "archives_bytes=$(wc -c < "${OUT}/run-archives.tgz" | tr -d ' ')"
} | tee "${OUT}/MANIFEST.txt"

# Refuse empty seat scoop when outer-loop-done claims a prior run (honesty).
if [ "$(wc -c < "${OUT}/seats.tgz" | tr -d ' ')" -lt 100 ]; then
  echo "WARN: seats.tgz tiny — /tmp may already be wiped; tree scoop is the durable half" >&2
fi
if [ "$(wc -c < "${OUT}/modernized-tree.tgz" | tr -d ' ')" -lt 1000 ]; then
  echo "REFUSE: modernized-tree.tgz too small — archive failed" >&2
  exit 1
fi

echo "O-PREPARCHEXIT: OK ${OUT}"
echo "$OUT" > "${ROOT}/tmp/V10-LAST-WIPE-ARCHIVE.txt"

# O-STOPMARKER: after archive, leave a durable stop record on the specimen
# (host-driven wipe/stop path). Callers that continue to wipe should keep this;
# outer-loop refuses start until OPERATOR_CONFIRM_START/CLEAR_STOPPED.
if [ "${V10_WRITE_STOPPED:-1}" = "1" ]; then
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc "
    cd /projects/modernized || exit 0
    if [ -f .hermes/harness/write-stopped.sh ]; then
      bash .hermes/harness/write-stopped.sh \
        --kind deliberate-stop \
        --authorizing 'host v10-archive-before-wipe (${LABEL})' \
        --reason 'archive-before-wipe complete; outer stopped for wipe/restart' \
        --expected-next 'complete wipe if needed; OPERATOR_CONFIRM_START=1 to restart outer'
    fi
  " || echo "WARN: O-STOPMARKER write skipped" >&2
fi
