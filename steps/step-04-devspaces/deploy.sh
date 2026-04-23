#!/usr/bin/env bash
# Step 04: Dev Spaces + AI Code Assistant - Deploy
# Applies the ArgoCD Application.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-04-devspaces"

load_env
check_oc_logged_in

log_step "Step 04: Dev Spaces & AI Code Assistant"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get checluster devspaces -n openshift-devspaces"
echo ""
