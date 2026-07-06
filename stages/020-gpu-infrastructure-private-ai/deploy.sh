#!/usr/bin/env bash
# deploy.sh — Stage 020: GPU-as-a-Service
# Hands GPU infrastructure, Kueue quotas, and hardware profiles to Argo CD.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
  exit 1
fi

echo "✓ Cluster guard passed: $ACTUAL_SERVER"

GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}"
GIT_REPO_BRANCH="${GIT_REPO_BRANCH:-main}"

APP_MANIFEST=$(mktemp)
sed \
  -e "s|repoURL: .*|repoURL: ${GIT_REPO_URL}|" \
  -e "s|targetRevision: .*|targetRevision: ${GIT_REPO_BRANCH}|" \
  "$ROOT_DIR/gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai.yaml" \
  > "$APP_MANIFEST"

echo "── Applying stage-120 Argo CD Application ──"
oc apply -f "$APP_MANIFEST" --insecure-skip-tls-verify=true
rm -f "$APP_MANIFEST"

echo "✓ Application 020-gpu-infrastructure-private-ai applied"
echo "  Argo CD will reconcile GPU infrastructure and queue resources."
echo "  Run ./validate.sh to confirm GPU-as-a-Service readiness."
