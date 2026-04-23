#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# 1. Applies the ArgoCD Application (operators, models, governance, Grafana)
# 2. Deploys the dev-preview MaaS API separately (remote Kustomize base)
#    The dev-preview maas-api is a public community image with full MaaS support
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

# Deploy dev-preview MaaS API (separate from operator-managed components)
log_step "Deploying MaaS API (Developer Preview)..."
oc create namespace maas-api 2>/dev/null || true
oc apply -k "$REPO_ROOT/gitops/step-03-llm-serving-maas/base/maas-api/" 2>/dev/null \
    && log_success "MaaS API dev-preview applied" \
    || log_warn "MaaS API apply failed (may need cluster-specific patching)"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-5:    LWS, RHCL, CNPG, Grafana operators + instances"
log_info "  Wave 5:      Gateway, Kuadrant, Authorino (declarative)"
log_info "  Wave 10-12:  Kuadrant CR + Authorino SSL Job"
log_info "  Wave 15:     Models + RBAC + Rate limit / Token limit / Telemetry policies"
log_info "  Wave 20:     Grafana dashboard + Gateway hostname Job"
log_info ""
log_info "MaaS API dev-preview deployed separately (oc apply -k maas-api/)"
log_info "  Image: quay.io/opendatahub/maas-api:latest-0681979"
log_info "  Namespace: maas-api"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get kuadrant -n kuadrant-system"
echo "  oc get pods -n maas-api"
echo ""
