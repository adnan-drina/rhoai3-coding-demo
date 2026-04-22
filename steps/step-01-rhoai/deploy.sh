#!/usr/bin/env bash
# Step 01: Red Hat OpenShift AI 3.4 - Deploy Script
# Deploys RHOAI 3.4 Platform Layer:
# - RHOAI Operator (stable-3.x channel)
# - DSCInitialization (Service Mesh: Managed)
# - DataScienceCluster with full 3.4 components
# - Auth resource for user/admin groups
# - GenAI Studio configuration
# - Hardware Profiles for AWS G6 GPU nodes
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-01-rhoai"

load_env
check_oc_logged_in

log_step "Step 01: Red Hat OpenShift AI 3.4"

log_step "Creating Argo CD Application for RHOAI"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"

log_success "Argo CD Application '${STEP_NAME}' created"

log_step "Waiting for RHOAI Operator..."

until oc get namespace redhat-ods-operator &>/dev/null; do
    log_info "Waiting for namespace redhat-ods-operator..."
    sleep 10
done

log_info "Waiting for RHOAI Operator CSV (this may take a few minutes)..."
until oc get csv -n redhat-ods-operator -o jsonpath='{.items[?(@.spec.displayName=="Red Hat OpenShift AI")].status.phase}' 2>/dev/null | grep -q "Succeeded"; do
    sleep 15
done
log_success "RHOAI Operator installed"

log_info "Waiting for DSCInitialization CRD..."
until oc get crd dscinitializations.dscinitialization.opendatahub.io &>/dev/null; do
    sleep 5
done
log_success "DSCInitialization CRD available"

log_info "Waiting for DataScienceCluster CRD..."
until oc get crd datascienceclusters.datasciencecluster.opendatahub.io &>/dev/null; do
    sleep 5
done
log_success "DataScienceCluster CRD available"

# Approve Service Mesh 3 install plans (RHOAI forces Manual approval)
# The RHOAI operator auto-creates the servicemeshoperator3 Subscription with
# installPlanApproval: Manual and reconciles it back if changed. We must
# approve pending install plans explicitly to avoid the gateway getting stuck.
log_step "Checking Service Mesh 3 operator..."

log_info "Waiting for servicemeshoperator3 Subscription..."
until oc get subscription servicemeshoperator3 -n openshift-operators &>/dev/null; do
    sleep 10
done

SM_INSTALL_PLAN=$(oc get subscription servicemeshoperator3 -n openshift-operators \
    -o jsonpath='{.status.installplan.name}' 2>/dev/null || true)
if [[ -n "$SM_INSTALL_PLAN" ]]; then
    APPROVED=$(oc get installplan "$SM_INSTALL_PLAN" -n openshift-operators \
        -o jsonpath='{.spec.approved}' 2>/dev/null || echo "true")
    if [[ "$APPROVED" == "false" ]]; then
        log_info "Approving Service Mesh 3 install plan: $SM_INSTALL_PLAN"
        oc patch installplan "$SM_INSTALL_PLAN" -n openshift-operators \
            --type merge -p '{"spec":{"approved":true}}'
        log_success "Install plan approved"
    else
        log_success "Service Mesh 3 install plan already approved"
    fi
else
    log_info "No pending Service Mesh install plan found"
fi

SM_CSV=$(oc get subscription servicemeshoperator3 -n openshift-operators \
    -o jsonpath='{.status.installedCSV}' 2>/dev/null || true)
if [[ -n "$SM_CSV" ]]; then
    log_info "Waiting for Service Mesh CSV ($SM_CSV) to succeed..."
    until [[ "$(oc get csv "$SM_CSV" -n openshift-operators -o jsonpath='{.status.phase}' 2>/dev/null)" == "Succeeded" ]]; do
        sleep 15
    done
    log_success "Service Mesh 3 operator ready"
fi

log_info "Waiting for DataScienceCluster to be created..."
until oc get datasciencecluster default-dsc &>/dev/null; do
    sleep 10
done
log_success "DataScienceCluster created"

log_info "Waiting for DataScienceCluster to become Ready (this may take several minutes)..."
until [[ "$(oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}' 2>/dev/null)" == "Ready" ]]; do
    PHASE=$(oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}' 2>/dev/null || echo "Pending")
    log_info "Current phase: $PHASE"
    sleep 30
done
log_success "DataScienceCluster is Ready"

log_step "Verifying Hardware Profiles..."

until oc get hardwareprofiles -n redhat-ods-applications --no-headers 2>/dev/null | grep -q .; do
    sleep 5
done

PROFILES=$(oc get hardwareprofiles -n redhat-ods-applications -o custom-columns=NAME:.metadata.name --no-headers 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
log_success "Hardware Profiles available: $PROFILES"

# Patch DSCI with cluster CA bundle (required for LlamaStack TLS)
log_step "Patching DSCI with cluster CA bundle..."

CA_BUNDLE=$(oc get configmap kube-root-ca.crt -n openshift-config -o jsonpath='{.data.ca\.crt}' 2>/dev/null || true)
if [[ -n "$CA_BUNDLE" ]]; then
    CA_JSON=$(echo "$CA_BUNDLE" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
    oc patch dscinitializations default-dsci --type merge \
        -p "{\"spec\":{\"trustedCABundle\":{\"managementState\":\"Managed\",\"customCABundle\":${CA_JSON}}}}" 2>/dev/null \
        && log_success "DSCI CA bundle patched" \
        || log_warn "DSCI CA bundle patch failed (may not exist yet)"
else
    log_warn "Could not read cluster CA bundle"
fi

log_step "Ensuring GenAI Studio is enabled..."

until oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications &>/dev/null; do
    sleep 5
done
oc patch odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
    --type merge -p '{"spec":{"dashboardConfig":{"genAiStudio":true}}}' 2>/dev/null \
    && log_success "GenAI Studio enabled" \
    || log_warn "GenAI Studio patch failed"

log_step "Deployment Complete"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RHOAI 3.4 Platform Deployed Successfully"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Enabled Components:"
oc get datasciencecluster default-dsc -o jsonpath='{.spec.components}' 2>/dev/null | \
  jq -r 'to_entries | .[] | "  • \(.key): \(.value.managementState)"' 2>/dev/null || \
  echo "  (use 'oc get datasciencecluster default-dsc -o yaml' to view)"
echo ""
echo "Hardware Profiles:"
oc get hardwareprofiles -n redhat-ods-applications \
  -o custom-columns=NAME:.metadata.name,DISPLAY:.metadata.annotations."opendatahub\.io/display-name" 2>/dev/null || \
  echo "  (use 'oc get hardwareprofiles -n redhat-ods-applications' to view)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
log_info "RHOAI status:"
echo "  oc get datasciencecluster default-dsc"
echo "  oc get pods -n redhat-ods-applications"
echo ""
log_info "Dashboard URL:"
DASHBOARD_URL=$(oc get route -n openshift-ingress data-science-gateway -o jsonpath='{.spec.host}' 2>/dev/null \
    || oc get route -n redhat-ods-applications rhods-dashboard -o jsonpath='{.spec.host}' 2>/dev/null \
    || echo 'loading...')
echo "  https://${DASHBOARD_URL}"
echo ""
