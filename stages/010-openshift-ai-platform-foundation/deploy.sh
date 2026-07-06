#!/usr/bin/env bash
# deploy.sh — Stage 010: RHOAI Base Platform
# Bootstraps OpenShift GitOps, then hands off ODF + RHOAI to Argo CD.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Load local environment ────────────────────────────────────────────────────
if [[ -f "$ROOT_DIR/.env" ]]; then
  # set -a so values like KUBECONFIG are exported to oc child processes,
  # not just set as local shell variables.
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

# ── OpenShift safety guard ────────────────────────────────────────────────────
if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  echo "       Set it in .env to a unique substring of the target cluster API URL." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
  exit 1
fi

echo "✓ Cluster guard passed: $ACTUAL_SERVER"

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
GIT_REPO_BRANCH="${GIT_REPO_BRANCH:-main}"

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
