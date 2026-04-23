#!/usr/bin/env bash
# Step 01: RHOAI Platform - Deploy
# Applies the ArgoCD Application. All orchestration is handled by
# ArgoCD sync waves and in-cluster Jobs (GitOps-first pattern).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-01-rhoai-platform"

load_env
check_oc_logged_in

log_step "Step 01: RHOAI Platform"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "ArgoCD handles all orchestration via sync waves:"
log_info "  Wave -10..0: Namespaces, OperatorGroups, Subscriptions"
log_info "  Wave 5-10:   DSCI, DataScienceCluster"
log_info "  Wave 12-16:  Auth, DashboardConfig, HardwareProfiles"
log_info "  Wave 15:     Jobs (SM install plan approval, DSCI CA patch)"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get datasciencecluster default-dsc -w"
echo ""
