#!/usr/bin/env bash
# deploy.sh — Stage 010: RHOAI Base Platform
# Bootstraps OpenShift GitOps, then hands off ODF + RHOAI to Argo CD.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Shared fail-closed environment and cluster identity guard.
REPO_ROOT="$ROOT_DIR"
# shellcheck source=../../scripts/shared/lib.sh
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/010-openshift-ai-platform-foundation"
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/bootstrap/overlays/operator"
# Use a reviewed published revision; never silently deploy old main content.
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then
  GIT_REPO_BRANCH="$2"
elif [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--revision <published commit or ref>]" >&2; exit 1
fi
require_env GIT_REPO_URL "repository URL containing the reviewed Stage 010 source"
assert_required_env
STAGE_APPS="$ROOT_DIR/scripts/shared/stage_apps.py"
# The reviewed, published commit; Applications are pinned to it even when the input was a branch.
selected_commit=$(python3 "$STAGE_APPS" select 010 --ref "${GIT_REPO_BRANCH:-HEAD}" --repo-url "$GIT_REPO_URL" \
  --extra gitops/bootstrap --extra scripts/platform/require-node-sizing.sh --extra scripts/platform/check-operator-policy.py)
command -v python3 >/dev/null || { echo "ERROR: python3 is required for native operator checks" >&2; exit 1; }


# Read-only preflight runs before the first bootstrap/Application write.
python3 - <<'PY_GUARD'
import json, subprocess, sys
def read(args):
    result = subprocess.run(["oc", "--request-timeout=10s", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Preflight could not inspect cluster ownership")
    return result.stdout.strip()
def tracked_by(obj, app):
    return obj.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "").startswith(app + ":")
try:
    # The model registry belongs to Stage 030; never let a foundation component take it back.
    text = read(["get", "namespace", "rhoai-model-registries", "--ignore-not-found", "-o", "json"])
    if text and not tracked_by(json.loads(text), "030-private-model-serving"):
        raise RuntimeError("Registry namespace exists but is not owned by Stage 030")
except (RuntimeError, ValueError) as error:
    print("ERROR: " + str(error), file=sys.stderr)
    sys.exit(1)
PY_GUARD

# Fail fast if the nodes are too small for the demo stack, before any changes.
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"

# ── Portable wait helper (no GNU `timeout` dependency; macOS lacks it) ─────────
# wait_for <timeout-seconds> <label> <command...>
# Polls the command every 10s until it exits 0 or the deadline passes.
wait_for() {
  local timeout_s="$1" label="$2"; shift 2
  local deadline=$(( SECONDS + timeout_s ))
  until "$@"; do
    if (( SECONDS >= deadline )); then
      echo ""
      echo "ERROR: timed out after ${timeout_s}s waiting for ${label}." >&2
      return 1
    fi
    sleep 10
    echo -n "."
  done
  echo ""
}

argocd_available() {
  oc get argocd openshift-gitops -n openshift-gitops \
    -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null \
    | grep -q Available
}

# ── Step 1: Bootstrap OpenShift GitOps operator ───────────────────────────────
echo ""
echo "── Step 1: Installing OpenShift GitOps operator ──"
# Apply the operator overlay (base Subscription + baseline-pinned channel).
# Never apply bootstrap/base directly: its channel is a placeholder.
oc apply -k "$ROOT_DIR/gitops/bootstrap/overlays/operator" --insecure-skip-tls-verify=true

echo "   Waiting for openshift-gitops-operator CSV to reach Succeeded …"
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/bootstrap/overlays/operator" --wait 900

echo "✓ OpenShift GitOps operator ready"

# ── Step 2: Wait for default ArgoCD instance to be Available ─────────────────
echo ""
echo "── Step 2: Waiting for ArgoCD instance to become available ──"
wait_for 300 "ArgoCD instance Available" argocd_available || exit 1

echo "✓ ArgoCD instance available"

# ── Step 3: Apply bootstrap overlay (resource tracking + AppProject) ──────────
echo ""
echo "── Step 3: Configuring ArgoCD and creating AppProject rhoai-demo ──"
oc apply -k "$ROOT_DIR/gitops/bootstrap/overlays/demo" --insecure-skip-tls-verify=true
echo "✓ ArgoCD configured (annotation resource tracking)"
echo "✓ AppProject rhoai-demo created"

# ── Step 4: Apply the Stage 010 component Applications at the reviewed revision ──
echo ""
echo "── Step 4: Applying Stage 010 component Argo CD Applications ──"
echo "  Argo CD syncs ODF and RHOAI; this takes 10–20 minutes."
python3 "$STAGE_APPS" deploy 010 --revision "$selected_commit" --repo-url "$GIT_REPO_URL"
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/010-openshift-ai-platform-foundation" --wait 1800

"$SCRIPT_DIR/deploy-sandbox-storage.sh" --revision "$selected_commit"

"$SCRIPT_DIR/deploy-console-observability.sh" --revision "$selected_commit"

# ── Step 5: Report Argo CD console URL ───────────────────────────────────────
ARGOCD_URL=$(oc get route openshift-gitops-server -n openshift-gitops \
  -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$ARGOCD_URL" ]]; then
  echo ""
  echo "  Argo CD console: https://$ARGOCD_URL"
  echo "  Applications:    https://$ARGOCD_URL/applications?labels=demo.rhoai.io%2Fstage%3D010"
fi

echo ""
echo "Run ./validate.sh to confirm all components are healthy."
