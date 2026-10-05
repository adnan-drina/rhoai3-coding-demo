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
# Use a reviewed published revision; never silently deploy old main content.
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then
  GIT_REPO_BRANCH="$2"
elif [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--revision <published commit or ref>]" >&2; exit 1
fi
require_env GIT_REPO_URL "repository URL containing the reviewed Stage 010 source"
require_env GIT_REPO_BRANCH "reviewed published branch or commit for Argo CD"
assert_required_env
selected_commit=$(git -C "$ROOT_DIR" rev-parse --verify "${GIT_REPO_BRANCH}^{commit}")
source_paths=(gitops/bootstrap gitops/stages/010-openshift-ai-platform-foundation gitops/argocd/app-of-apps/010-openshift-ai-platform-foundation.yaml stages/010-openshift-ai-platform-foundation scripts/shared scripts/platform/require-node-sizing.sh)
if ! git -C "$ROOT_DIR" diff --quiet "$selected_commit" -- "${source_paths[@]}" ||
   [[ -n "$(git -C "$ROOT_DIR" ls-files --others --exclude-standard -- "${source_paths[@]}")" ]]; then
  echo "ERROR: Selected revision does not contain the local reviewed Stage 010 source." >&2
  exit 1
fi
if ! git ls-remote "$GIT_REPO_URL" | awk '{print $1}' | grep -Fx "$selected_commit" >/dev/null; then
  echo "ERROR: Selected commit is not an advertised published repository revision." >&2
  exit 1
fi
# Pin the Application to immutable reviewed content even when input was a branch.
GIT_REPO_BRANCH="$selected_commit"
command -v python3 >/dev/null || { echo "ERROR: python3 is required for exact InstallPlan checks" >&2; exit 1; }


# Source relocation must not prune a registry still owned by an older Stage 010.
# Read-only preflight runs before the first bootstrap/Application write.
python3 - <<'PY_GUARD'
import json, subprocess, sys
old_app = "010-openshift-ai-platform-foundation"
new_app = "030-private-model-serving"
def read(args):
    result = subprocess.run(["oc", "--request-timeout=10s", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Registry handoff preflight could not inspect cluster ownership")
    return result.stdout.strip()
def tracked_by(obj, app):
    return obj.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "").startswith(app + ":")
try:
    # MLflow has no receiving stage yet. Never remove its live service or data.
    apis = read(["api-resources", "-o", "name"]).splitlines()
    if "mlflows.mlflow.opendatahub.io" in apis:
        existing = json.loads(read(["get", "mlflows.mlflow.opendatahub.io", "-o", "json"]))
        if existing.get("items"):
            raise RuntimeError("Existing MLflow requires a reviewed evaluation-stage ownership handoff; keep the deployed foundation pinned")
    for resource, names in [("persistentvolumeclaim", ["mlflow-postgresql"]), ("secret", ["mlflow-db-credentials", "rhoai-mlflow-artifacts"]), ("statefulset", ["mlflow-postgresql"]), ("service", ["mlflow-postgresql"]), ("networkpolicy", ["mlflow-postgresql"]), ("configmap", ["mlflow-service-ca"])]:
        for name in names:
            if read(["get", resource, name, "-n", "redhat-ods-applications", "--ignore-not-found", "-o", "jsonpath={.metadata.uid}"]):
                raise RuntimeError("Retained MLflow data/configuration requires an explicit future-stage handoff")
    if "objectbucketclaims.objectbucket.io" in apis:
        if read(["get", "objectbucketclaims.objectbucket.io", "rhoai-mlflow-artifacts", "-n", "redhat-ods-applications", "--ignore-not-found", "-o", "jsonpath={.metadata.uid}"]):
            raise RuntimeError("Retained MLflow artifact bucket requires an explicit future-stage handoff")
    text = read(["get", "namespace", "rhoai-model-registries", "--ignore-not-found", "-o", "json"])
    namespace = json.loads(text) if text else {}
    if tracked_by(namespace, old_app):
        raise RuntimeError("Registry namespace is still Stage 010-owned; keep the deployed revision pinned until the reviewed Stage 030 adoption")
    available = read(["api-resources", "--api-group=modelregistry.opendatahub.io", "-o", "name"])
    if "modelregistries.modelregistry.opendatahub.io" in available.splitlines():
        text = read(["get", "modelregistries.modelregistry.opendatahub.io", "demo-registry", "-n", "rhoai-model-registries", "--ignore-not-found", "-o", "json"])
        registry = json.loads(text) if text else {}
        if registry and not tracked_by(registry, new_app):
            raise RuntimeError("Existing demo-registry has not been adopted by Stage 030; refusing a potentially destructive foundation transition")
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

gitops_csv_succeeded() {
  oc get csv -n openshift-operators \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}' \
    --insecure-skip-tls-verify=true 2>/dev/null \
    | grep openshift-gitops | grep -q Succeeded
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
wait_for 300 "GitOps operator CSV Succeeded" gitops_csv_succeeded || exit 1

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

# ── Step 4: Patch Application with repo URL and branch from .env ──────────────
echo ""
echo "── Step 4: Applying stage-010 Argo CD Application ──"

GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}"


APP_MANIFEST=$(mktemp)
sed \
  -e "s|repoURL: .*|repoURL: ${GIT_REPO_URL}|" \
  -e "s|targetRevision: .*|targetRevision: ${GIT_REPO_BRANCH}|" \
  "$ROOT_DIR/gitops/argocd/app-of-apps/010-openshift-ai-platform-foundation.yaml" \
  > "$APP_MANIFEST"

oc apply -f "$APP_MANIFEST" --insecure-skip-tls-verify=true
rm -f "$APP_MANIFEST"

echo "✓ Application 010-openshift-ai-platform-foundation created"
echo "  Argo CD will now sync ODF and RHOAI. This takes 10–20 minutes."

# Approve only the exact reviewed CSV for each unbounded observability stream.
# The InstallPlan must belong to this Subscription and contain no other CSV.
approve_reviewed_plan() {
  local namespace="$1" subscription="$2" expected="$3" plan payload
  plan=$(oc get subscription "$subscription" -n "$namespace" -o jsonpath='{.status.installPlanRef.name}' 2>/dev/null || true)
  [[ -n "$plan" ]] || return 1
  payload=$(oc get installplan "$plan" -n "$namespace" -o json)
  if ! printf '%s' "$payload" | python3 -c '
import json,sys
p=json.load(sys.stdin); sub,expected=sys.argv[1:]
owned=any(x.get("kind")=="Subscription" and x.get("name")==sub for x in p.get("metadata",{}).get("ownerReferences",[]))
sys.exit(0 if owned and p.get("spec",{}).get("clusterServiceVersionNames")==[expected] else 1)
' "$subscription" "$expected"; then
    echo "ERROR: InstallPlan ownership or CSV contents differ from reviewed selection." >&2
    return 2
  fi
  oc patch installplan "$plan" -n "$namespace" --type merge -p '{"spec":{"approved":true}}'
}
for selection in \
  'openshift-cluster-observability-operator cluster-observability-operator cluster-observability-operator.v1.5.3' \
  'openshift-opentelemetry-operator opentelemetry-product opentelemetry-operator.v0.158.0-2' \
  'openshift-tempo-operator tempo-product tempo-operator.v0.22.0-2'; do
  read -r namespace subscription expected <<< "$selection"
  deadline=$((SECONDS + 600))
  while true; do
    if approve_reviewed_plan "$namespace" "$subscription" "$expected"; then break; else approval_status=$?; fi
    [[ "$approval_status" -ne 2 ]] || exit 1
    (( SECONDS < deadline )) || { echo "ERROR: reviewed InstallPlan unavailable" >&2; exit 1; }
    sleep 10
  done
done


# ── Step 5: Report Argo CD console URL ───────────────────────────────────────
ARGOCD_URL=$(oc get route openshift-gitops-server -n openshift-gitops \
  -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$ARGOCD_URL" ]]; then
  echo ""
  echo "  Argo CD console: https://$ARGOCD_URL"
  echo "  Application:     https://$ARGOCD_URL/applications/010-openshift-ai-platform-foundation"
fi

echo ""
echo "Run ./validate.sh to confirm all components are healthy."
