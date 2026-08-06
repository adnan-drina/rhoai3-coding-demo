#!/usr/bin/env bash
# Prep a fresh Track B re-run after honesty-blocking harness landings.
# Does NOT start outer-loop — prints the exact next commands after gates pass.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh" 2>/dev/null || true
cd "$ROOT"

HARNESS_SRC="$ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
# O-HERMESWSRESOLVE: no stale named default — explicit V10_WS_NAME or single Running DW.
WS_NAME="$(qg_ws_name)" || {
  echo "REFUSE: set V10_WS_NAME or ensure exactly one Running DevWorkspace (O-HERMESWSRESOLVE)" >&2
  exit 1
}
NS="${V10_NS:-$(qg_ws_ns)}"

echo "=== 0) O-PREPARCHEXIT — host scoop BEFORE any wipe/sync that clears /tmp ==="
# Skip only when explicitly opted out (e.g. dry prep with no live pod).
if [ "${V10_SKIP_PREPARCHEXIT:-0}" != "1" ]; then
  bash "${ROOT}/scripts/track-b/v10-archive-before-wipe.sh" --label "${V10_ARCHIVE_LABEL:-prep-fresh}"
else
  echo "  skipped (V10_SKIP_PREPARCHEXIT=1)"
fi

echo "=== 1) Honesty + Wave3 retro bank rows (must be ✅) ==="
HONESTY="O-ALREADYPROP O-ALREADYFINDING O-T6EEMPTYESC O-RESUMEBASEEXCL O-KANTRAMISS O-CREATEFIRSTMUT O-M3EMPTY O-DUPPROP O-WIREUP O-ALREADYREPL O-ESCALCAUSE O-M5STALE O-KANTRAPATH O-SECAUTHTEST O-PRODSCHEMA"
bank="$ROOT/docs/V10-FUTURE-IMPROVEMENTS.md"
bad=0
for id in $HONESTY; do
  line=$(grep -E "^\\| ${id} \\|" "$bank" | head -1 || true)
  if echo "$line" | grep -q "| ✅ |"; then
    echo "  ✅ $id"
  else
    echo "  ⬜/missing $id — $line"
    bad=$((bad+1))
  fi
done
if [ "$bad" -gt 0 ]; then
  echo "HONESTY BANK RED — $bad items still open" >&2
  exit 1
fi

echo "=== 2) Static instruments (Wave3 + honesty) ==="
(
  cd "$HARNESS_SRC/harness/tests"
  python3 - <<'PY'
import os, subprocess, tempfile, textwrap
from pathlib import Path
H = Path("../already-complete.py").resolve().parent
AC = H / "already-complete.py"
assert "target_java_blocks_preserve" in AC.read_text()
assert "annotation_work_incomplete" in AC.read_text()
assert "replacement_constructs_missing" in AC.read_text()
sup = (H / "supervisor.sh").read_text()
assert "O-ESCALPAUSE" in sup and 'esc_cause="supervisor-pause"' in sup
assert "O-M5STALE" in sup or "FINDINGS_DELTA_STALE" in sup
assert "kantra-path.sh" in sup or "kantra_bin" in sup
assert (H / "wireup-check.py").is_file()
assert (H / "kantra-path.sh").is_file()
assert "O-PRODSCHEMA" in (H / "commit-hygiene.py").read_text()
assert "security_auth_test_contract" in (H / "sensors.sh").read_text()
# wireup fixture
fix = tempfile.mkdtemp()
os.makedirs(f"{fix}/migration/staging")
os.makedirs(f"{fix}/src/main/java/x")
open(f"{fix}/migration/staging/CallMonitoringAspect.java", "w").write(
    "@Aspect\npublic class CallMonitoringAspect {\n  @Around(\"x\") Object invoke(){return null;}\n}\n"
)
open(f"{fix}/src/main/java/x/CallMonitoringAspect.java", "w").write(
    "@ApplicationScoped\npublic class CallMonitoringAspect {\n  public Object invoke(){return null;}\n  public void reset(){}\n}\n"
)
r = subprocess.run(["python3", str(H / "wireup-check.py")], cwd=fix, capture_output=True, text=True)
assert r.returncode == 1, r.stdout + r.stderr
# stale delta
os.makedirs(f"{fix}/migration", exist_ok=True)
open(f"{fix}/migration/mta-findings.json", "w").write("[]")
open(f"{fix}/migration/mta-findings-after.json", "w").write("[]")
env = os.environ.copy()
env["FINDINGS_DELTA_STALE"] = "1"
env["FINDINGS_DELTA_ROOT"] = fix
out = subprocess.check_output(["python3", str(H / "findings-delta.py")], env=env, text=True)
assert "STALE-AFTER" in out and "honest_resolve_pct" not in out
print("static-probes-ok")
PY
)

echo "=== 3) Sync golden .hermes → live workspace (v10-sync-hermes) ==="
if command -v oc >/dev/null 2>&1 && oc whoami >/dev/null 2>&1; then
  export V10_WS_NAME="$WS_NAME" V8_WS_NS="$NS"
  bash "${ROOT}/scripts/track-b/v10-sync-hermes.sh"
else
  echo "WARN: oc not logged in — skip live sync"
fi

echo "=== 4) Next: host preflight (no pod hand steps) ==="
cat <<EOF

Harness synced + start markers cleared on the workspace.

  bash scripts/track-b/v9-preflight-outer-start.sh          # gate only
  bash scripts/track-b/v9-preflight-outer-start.sh --start # gate + start outer

Auto-sync on mismatch is on by default (V9_AUTO_HERMES_SYNC=1).
Do not hand-edit the pod .hermes tree.

EOF
echo "prep-fresh-rerun: OK"
