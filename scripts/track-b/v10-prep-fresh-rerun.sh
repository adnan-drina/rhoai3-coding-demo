#!/usr/bin/env bash
# Prep a fresh Track B re-run after honesty-blocking harness landings.
# Does NOT start outer-loop — prints the exact next commands after gates pass.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh" 2>/dev/null || true
cd "$ROOT"

HARNESS_SRC="$ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes"
WS_NAME="${V10_WS_NAME:-petclinic-rest-v3}"
NS="${V10_NS:-wksp-ai-developer}"

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

echo "=== 3) Sync golden .hermes → live workspace (if oc available) ==="
SCAFFOLD="$ROOT/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
if command -v oc >/dev/null 2>&1 && oc whoami >/dev/null 2>&1; then
  load_env >/dev/null 2>&1 || true
  check_oc_logged_in >/dev/null 2>&1 || true
  POD=$(oc get pod -n "$NS" -l "controller.devfile.io/devworkspace_name=${WS_NAME}" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [ -n "${POD:-}" ]; then
    echo "Tar-sync entire golden .hermes → ${NS}/${POD}:/projects/modernized/.hermes ..."
    ( cd "$SCAFFOLD" && tar cf - .hermes ) | oc exec -i -n "$NS" "$POD" -c development-tooling -- \
      bash -lc 'cd /projects/modernized && tar xf -'
    echo "  synced .hermes/ ($(find "$HARNESS_SRC" -type f | wc -l | tr -d " ") files in golden tree)"
    # shellcheck source=/dev/null
    source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
    export V10_WS_NAME="$WS_NAME" V8_WS_NS="$NS"
    qg_remote_orchestrator_preflight || {
      echo "WARN: orchestrator preflight RED after sync — run workspace init (ensure_hermes) on pod" >&2
      exit 1
    }
    oc exec -n "$NS" "$POD" -c development-tooling -- bash -lc '
      export KANTRA_HOME="${KANTRA_HOME:-/projects/.tools/kantra}"
      command -v kantra-ensure >/dev/null && kantra-ensure || echo "WARN: kantra-ensure not in PATH"
      if [ -x "${KANTRA_HOME}/kantra" ] || [ -f "${KANTRA_HOME}/kantra" ]; then
        echo "kantra-ok:${KANTRA_HOME}/kantra"
      elif [ -x /tmp/kantra/kantra ]; then
        echo "kantra-ok:/tmp/kantra/kantra (fallback — migrate to KANTRA_HOME)"
      else
        echo "WARN: kantra binary still missing"
      fi
      test -f /tmp/outer-loop-done && echo outer-done-present || echo outer-done-absent
    '
  else
    echo "WARN: no DevWorkspace pod for $WS_NAME — skip live sync"
  fi
else
  echo "WARN: oc not logged in — skip live sync"
fi

echo "=== 4) Re-run recipe (manual next steps) ==="
cat <<EOF

Fresh re-run (wipe specimen or new branch) — only after human confirms:

  1. In the modernized workspace, reset app to pristine scaffold + legacy stamp
     (or provision a new specimen). Do NOT resume the completed S07 tip.
  2. Clear markers:
       rm -f /tmp/outer-loop-done /tmp/debt-freeze /tmp/supervisor-pause \\
             /tmp/outer-loop.lock /tmp/supervisor.lock /tmp/worker-wedge-skip \\
             migration/findings-delta.STALE
  3. export KANTRA_HOME=/projects/.tools/kantra; kantra-ensure && test -x "\$KANTRA_HOME/kantra"
  4. From modernized:
       WORKER_FIRST=true nohup bash .hermes/harness/outer-loop.sh >> /tmp/outer-loop.log 2>&1 &
  5. Optional: restart tmp/v10-smart-wake-loop.sh for O-DRV4

Wave3 / honesty KPIs on the proving re-run:
  - MiniMax coding escalations ≈ 0 (pause-kills must NOT escalate)
  - Lead tip commits = 0
  - False already-complete = 0
  - No hollow aspect/empty @ApplicationScoped (O-WIREUP)
  - No STALE-AFTER M5 score inflation
  - Security story ships 401/403 TestProfile coverage
  - Watch kill-ledger for rc=130 SIGINT source (O-SIGINT)

EOF
echo "prep-fresh-rerun: OK"
