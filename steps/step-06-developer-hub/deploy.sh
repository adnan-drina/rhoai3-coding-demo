#!/usr/bin/env bash
# Step 06: Developer Hub — Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-06-developer-hub"

load_env
check_oc_logged_in

log_step "Step 06: Red Hat Developer Hub — Self-Service Developer Portal"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-2:    RHDH Operator (namespace, operatorgroup, subscription)"
log_info "  Wave 5:      app-config ConfigMap, rhdh-secrets, dynamic-plugins ConfigMap"
log_info "  Wave 10:     Backstage CR (RHDH instance)"
log_info "  Wave 15:     ConsoleLink (OpenShift launcher)"
log_info "  PostSync:    Configure OIDC auth via MTA Keycloak, patch secrets, restart"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get pods -n rhdh"
echo "  oc get backstage developer-hub -n rhdh"
echo ""
log_info "After deploy, access Developer Hub:"
echo "  oc get route -n rhdh"
echo ""
