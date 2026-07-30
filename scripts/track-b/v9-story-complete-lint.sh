#!/usr/bin/env bash
# O-FALSECOMPLETE — story-complete commit subjects must match harness outcomes.
# Outer-loop only emits: "${SID} story complete: ${OUTCOME}" where OUTCOME is
# supervisor-done (success*|story-gate-passed*). Agent prose / parenthetical
# annotations are RED.
#
# Usage:
#   bash scripts/track-b/v9-story-complete-lint.sh          # cwd = app repo
#   bash scripts/track-b/v9-story-complete-lint.sh --oc     # lint in DevWorkspace
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"

USE_OC=0
[ "${1:-}" = "--oc" ] && USE_OC=1

# Only the newest story-complete subject per S0N counts (history may keep a
# superseded agent-authored subject after SHIP_ONLY re-earn).
collect_bad() {
  python3 - <<'PY'
import re, subprocess, sys
ok_re = re.compile(r"^S0[0-9] story complete: (success .+|story-gate-passed)$")
sid_re = re.compile(r"^(S0[0-9]) story complete:")
out = subprocess.check_output(
    ["git", "log", "--format=%s", "--all", "--grep=^S0[0-9] story complete:"],
    text=True, stderr=subprocess.DEVNULL,
)
newest = {}
for subj in out.splitlines():
    m = sid_re.match(subj)
    if not m:
        continue
    sid = m.group(1)
    if sid not in newest:  # git log is newest-first
        newest[sid] = subj
bad = [s for s in newest.values() if not ok_re.match(s)]
sys.stdout.write("\n".join(bad))
PY
}

if [ "$USE_OC" = "1" ]; then
  # shellcheck source=/dev/null
  source "${ROOT}/scripts/lib.sh"
  load_env >/dev/null
  check_oc_logged_in
  POD="$(qg_ws_pod)"
  NS="$(qg_ws_ns)"
  CTR="$(qg_ws_ctr)"
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized
    python3 - <<'"'"'PY'"'"'
import re, subprocess
ok_re = re.compile(r"^S0[0-9] story complete: (success .+|story-gate-passed)$")
sid_re = re.compile(r"^(S0[0-9]) story complete:")
out = subprocess.check_output(
    ["git", "log", "--format=%s", "--all", "--grep=^S0[0-9] story complete:"],
    text=True, stderr=subprocess.DEVNULL,
)
newest = {}
for subj in out.splitlines():
    m = sid_re.match(subj)
    if not m:
        continue
    sid = m.group(1)
    if sid not in newest:
        newest[sid] = subj
bad = [s for s in newest.values() if not ok_re.match(s)]
open("/tmp/v9-story-complete-lint.bad", "w").write("\n".join(bad))
PY
  ' >/dev/null
  BAD=$(oc exec -n "$NS" "$POD" -c "$CTR" -- \
    cat /tmp/v9-story-complete-lint.bad 2>/dev/null | qg_strip_oc_noise || true)
else
  BAD=$(collect_bad || true)
fi

if [ -n "${BAD:-}" ]; then
  echo "STORY-COMPLETE LINT RED (O-FALSECOMPLETE):" >&2
  printf '%s\n' "$BAD" >&2
  echo "Re-earn via: scripts/track-b/v9-ship-only-waiter.sh + v9-record-ship-only.sh" >&2
  exit 1
fi
echo "STORY-COMPLETE LINT GREEN"
exit 0
