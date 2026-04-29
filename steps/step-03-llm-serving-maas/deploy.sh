#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# Applies the ArgoCD Application. The RHOAI 3.4 operator manages maas-api,
# tier ConfigMap, RBAC, and AuthPolicies natively via modelsAsService: Managed.
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
log_info "  Wave 0-3:    LWS, RHCL, CNPG, Grafana operators"
log_info "  Wave 4-5:    GatewayClass, MaaS Gateway"
log_info "  Wave 5-6:    Project namespaces, user RBAC, MaaS tier groups"
log_info "  Wave 10:     Kuadrant CR, LLMInferenceService models"
log_info "  Wave 15-16:  MCP servers"
log_info "  Wave 20-22:  Grafana, Gateway hostname patch, Model Registry seed"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get pods -n redhat-ods-applications -l app.kubernetes.io/name=maas-api"
echo "  oc get kuadrant -n kuadrant-system"
echo ""
