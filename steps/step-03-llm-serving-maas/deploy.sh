#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# Applies the ArgoCD Application. The operator-managed maas-api in
# redhat-ods-applications handles MaaS API (no separate deployment needed).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-03-llm-serving-maas"

load_env
check_oc_logged_in

log_step "Step 03: LLM Serving + MaaS"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-5:    LWS, RHCL, CNPG, Grafana operators + instances"
log_info "  Wave 5:      Gateway, Kuadrant, Authorino (declarative)"
log_info "  Wave 9:      Tier-to-group mapping ConfigMap"
log_info "  Wave 10-12:  Kuadrant CR + Authorino SSL Job"
log_info "  Wave 15-21:  Models, RBAC, policies, Gateway, Grafana"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get kuadrant -n kuadrant-system"
echo ""
