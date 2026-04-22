#!/usr/bin/env bash
# Step 03: LLM Serving with Models-as-a-Service - Deploy Script
# Deploys MaaS operator prerequisites + model serving + governance:
# - LeaderWorkerSet Operator (llm-d distributed inference)
# - Red Hat Connectivity Link (MaaS rate limiting)
# - CloudNative PG (MaaS API database)
# - GatewayClass + MaaS Gateway
# - Kuadrant + Authorino TLS
# - LLMInferenceServices (gpt-oss-20b, Nemotron)
# - MaaS tier groups, rate limits, telemetry
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-03-llm-serving-maas"

load_env
check_oc_logged_in

log_step "Step 03: LLM Serving with Models-as-a-Service"

log_step "Checking prerequisites..."

if ! oc get applications -n openshift-gitops step-02-gpu-infra &>/dev/null; then
    log_error "step-02-gpu-infra Argo CD Application not found!"
    log_info "Please run: ./steps/step-02-gpu-infra/deploy.sh first"
    exit 1
fi

GPU_NODES=$(oc get nodes -l node-role.kubernetes.io/gpu --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$GPU_NODES" -lt 2 ]]; then
    log_warn "Found $GPU_NODES GPU nodes (need 2 for both models). Models may queue."
fi

log_success "Prerequisites verified"

log_step "Creating Argo CD Application for LLM Serving + MaaS"
oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "Argo CD Application '${STEP_NAME}' created"

log_step "Waiting for LeaderWorkerSet Operator..."
until oc get csv -n openshift-lws-operator -o jsonpath='{.items[?(@.spec.displayName=="Red Hat build of Leader Worker Set")].status.phase}' 2>/dev/null | grep -q "Succeeded"; do
    log_info "Waiting for LWS Operator..."
    sleep 10
done
log_success "LeaderWorkerSet Operator ready"

log_step "Waiting for Red Hat Connectivity Link (RHCL)..."
until oc get crd authpolicies.kuadrant.io &>/dev/null; do
    log_info "Waiting for RHCL AuthPolicy CRD..."
    sleep 10
done
log_success "RHCL AuthPolicy CRD available"

log_step "Creating Kuadrant instance..."
ensure_namespace "kuadrant-system"

log_info "Restarting Kuadrant operator to ensure webhook readiness..."
oc delete pod -n openshift-operators -l app=kuadrant,control-plane=controller-manager 2>/dev/null || true
sleep 5
oc rollout status -n openshift-operators deployment/kuadrant-operator-controller-manager --timeout=120s 2>/dev/null || true

cat <<EOF | oc apply -f -
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
  namespace: kuadrant-system
EOF

log_info "Waiting for Kuadrant to become ready..."
until oc wait Kuadrant -n kuadrant-system kuadrant --for=condition=Ready --timeout=10m 2>/dev/null; do
    sleep 10
done
log_success "Kuadrant ready"

log_step "Configuring Authorino with TLS..."
oc annotate svc/authorino-authorino-authorization \
    service.beta.openshift.io/serving-cert-secret-name=authorino-server-cert \
    -n kuadrant-system --overwrite 2>/dev/null || true
sleep 5

cat <<EOF | oc apply -f -
apiVersion: operator.authorino.kuadrant.io/v1beta1
kind: Authorino
metadata:
  name: authorino
  namespace: kuadrant-system
spec:
  replicas: 1
  clusterWide: true
  listener:
    tls:
      enabled: true
      certSecretRef:
        name: authorino-server-cert
  oidcServer:
    tls:
      enabled: false
EOF

until oc wait --for=condition=ready pod -l authorino-resource=authorino -n kuadrant-system --timeout=150s 2>/dev/null; do
    sleep 5
done
log_success "Authorino ready with TLS"

log_step "Patching MaaS Gateway with cluster hostname..."
INGRESS_DOMAIN=$(oc get ingresscontroller -n openshift-ingress-operator default -o jsonpath='{.status.domain}' 2>/dev/null)
if [[ -n "$INGRESS_DOMAIN" ]]; then
    MAAS_HOST="maas.${INGRESS_DOMAIN}"
    oc patch gateway maas-default-gateway -n openshift-ingress --type json \
        -p "[{\"op\": \"replace\", \"path\": \"/spec/listeners/0/hostname\", \"value\": \"${MAAS_HOST}\"}]" 2>/dev/null \
        && log_success "MaaS Gateway hostname set to $MAAS_HOST" \
        || log_warn "Could not patch MaaS Gateway hostname"
else
    log_warn "Could not detect ingress domain"
fi

log_step "Deploying MaaS API (Developer Preview)..."
ensure_namespace "maas-api"
oc apply -k "$REPO_ROOT/gitops/step-03-llm-serving-maas/base/maas/" 2>/dev/null \
    && log_success "MaaS API base applied" \
    || log_warn "MaaS API apply failed (may need manual patching for cluster hostname)"

log_step "Verifying MaaS tier user groups..."
for group in tier-free-users tier-premium-users tier-enterprise-users; do
    until oc get group "$group" &>/dev/null; do
        log_info "Waiting for group $group..."
        sleep 5
    done
done
log_success "MaaS tier groups configured"

log_step "Waiting for LLMInferenceServices to be created..."
log_info "This may take several minutes as GPU workloads schedule and models load..."

for model in gpt-oss-20b nemotron-3-nano-30b-a3b; do
    log_info "Waiting for $model..."
    until oc get llminferenceservice "$model" -n maas &>/dev/null; do
        sleep 15
    done
    log_success "$model created"
done

log_step "Deployment Complete"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "LLM Serving + MaaS Deployed Successfully"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "MaaS Tiers:"
echo "  Enterprise: admin"
echo "  Premium: user1-user5"
echo "  Free: (unassigned users)"
echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
