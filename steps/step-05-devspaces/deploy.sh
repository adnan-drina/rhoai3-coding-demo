#!/usr/bin/env bash
# Step 05: Dev Spaces & AI Code Assistant - Deploy Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-05-devspaces"

load_env
check_oc_logged_in

log_step "Step 05: Dev Spaces & AI Code Assistant"

log_step "Checking prerequisites..."

if ! oc get applications -n openshift-gitops step-03-llm-serving-maas &>/dev/null; then
    log_error "step-03-llm-serving-maas Argo CD Application not found!"
    log_info "Please run: ./steps/step-03-llm-serving-maas/deploy.sh first"
    exit 1
fi
log_success "Prerequisites verified"

log_step "Creating Argo CD Application for Dev Spaces"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"

log_success "Argo CD Application '${STEP_NAME}' created"

log_step "Waiting for Dev Spaces Operator..."
until oc get crd checlusters.org.eclipse.che &>/dev/null; do
    log_info "Waiting for CheCluster CRD..."
    sleep 10
done
log_success "Dev Spaces CRD available"

log_step "Waiting for CheCluster to become ready..."
until [[ "$(oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase}' 2>/dev/null)" == "Active" ]]; do
    PHASE=$(oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase}' 2>/dev/null || echo "Pending")
    log_info "CheCluster phase: $PHASE"
    sleep 15
done
log_success "Dev Spaces is Active"

log_step "Deployment Complete"

DEVSPACES_URL=$(oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.cheURL}' 2>/dev/null || echo 'loading...')
echo ""
log_info "Dev Spaces Dashboard URL:"
echo "  ${DEVSPACES_URL}"
echo ""
log_info "To create a workspace with the coding exercises:"
echo "  Open the Dev Spaces dashboard and create a new workspace from this repo"
echo "  The Continue extension will need to be configured with your MaaS model endpoint"
echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
