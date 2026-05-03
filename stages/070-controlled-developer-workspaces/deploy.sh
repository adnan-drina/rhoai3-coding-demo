#!/usr/bin/env bash
# Stage 070: Dev Spaces + AI Code Assistant - Deploy
# Applies the ArgoCD Application.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="070-controlled-developer-workspaces"

load_env
check_oc_logged_in

log_step "Stage 070: Dev Spaces & AI Code Assistant"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STAGE_NAME}.yaml"
log_success "ArgoCD Application '${STAGE_NAME}' applied"

log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get checluster devspaces -n openshift-devspaces"
echo ""
