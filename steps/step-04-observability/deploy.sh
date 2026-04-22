#!/usr/bin/env bash
# Step 04: Observability & Governance Dashboard - Deploy Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-04-observability"

load_env
check_oc_logged_in

log_step "Step 04: Observability & Governance Dashboard"

log_step "Checking prerequisites..."

if ! oc get applications -n openshift-gitops step-03-llm-serving-maas &>/dev/null; then
    log_error "step-03-llm-serving-maas Argo CD Application not found!"
    log_info "Please run: ./steps/step-03-llm-serving-maas/deploy.sh first"
    exit 1
fi
log_success "Prerequisites verified"

log_step "Creating Argo CD Application for Observability"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"

log_success "Argo CD Application '${STEP_NAME}' created"

log_step "Waiting for Grafana Operator..."
until oc get crd grafanas.grafana.integreatly.org &>/dev/null; do
    log_info "Waiting for Grafana CRD..."
    sleep 10
done
log_success "Grafana CRD available"

log_step "Waiting for Grafana instance..."
until oc get grafana grafana -n grafana &>/dev/null; do
    sleep 5
done
log_success "Grafana instance created"

log_step "Deployment Complete"

GRAFANA_URL=$(oc get route grafana-route -n grafana -o jsonpath='{.spec.host}' 2>/dev/null || echo 'loading...')
echo ""
log_info "Grafana Dashboard URL:"
echo "  https://${GRAFANA_URL}"
echo "  Credentials: admin / <demo-password>"
echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
