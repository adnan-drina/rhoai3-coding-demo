#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# Applies the ArgoCD Application. All orchestration is handled by ArgoCD sync
# waves and in-cluster Jobs. The operator manages maas-api, tier configs, and
# AuthPolicies natively through MaaSSubscription/MaaSAuthPolicy CRs.
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

log_info "ArgoCD handles all orchestration via sync waves:"
log_info "  Wave 0-5:    LWS, RHCL, CNPG, Grafana operators + instances"
log_info "  Wave 10-12:  Kuadrant CR + configuration Job (Authorino TLS + SSL)"
log_info "  Wave 15-21:  Gateway, LLMInferenceService models, RBAC"
log_info "  Wave 20-22:  Grafana dashboard + SA token Job, Gateway hostname Job"
log_info "  Wave 25:     MaaS publish (MaaSModelRef, MaaSAuthPolicy, MaaSSubscription)"
log_info "               -> Operator reconciles into AuthPolicies, tiers, MaaS tab"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get maasmodelref -n maas"
echo "  oc get maassubscription -n models-as-a-service"
echo "  oc get kuadrant -n kuadrant-system"
echo ""
