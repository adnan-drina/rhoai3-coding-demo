#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# Applies the ArgoCD Application. Kuadrant configuration, Gateway hostname
# patching, and Grafana SA setup are handled by in-cluster Jobs.
# MaaS API Developer Preview is applied separately (remote Kustomize base).
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

# MaaS API Developer Preview (remote Kustomize base, not in ArgoCD)
log_step "Deploying MaaS API (Developer Preview)..."
oc create namespace maas-api 2>/dev/null || true
oc apply -k "$REPO_ROOT/gitops/step-03-llm-serving-maas/base/maas/" 2>/dev/null \
    && log_success "MaaS API applied" \
    || log_warn "MaaS API apply failed (may need cluster-specific patching)"

log_info "ArgoCD handles all orchestration via sync waves:"
log_info "  Wave 0-5:    LWS, RHCL, CNPG, Grafana operators + instances"
log_info "  Wave 10-12:  Kuadrant CR + configuration Job (Authorino TLS)"
log_info "  Wave 15-18:  Gateway, models, RBAC, policies"
log_info "  Wave 20-22:  Grafana dashboard + SA token Job, Gateway hostname Job"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get kuadrant -n kuadrant-system"
echo ""
