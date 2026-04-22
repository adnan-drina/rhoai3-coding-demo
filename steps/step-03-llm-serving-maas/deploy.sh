#!/usr/bin/env bash
# Step 03: LLM Serving with Models-as-a-Service - Deploy Script
# Deploys:
# - Model serving namespace with InferenceServices (gpt-oss-20b, Nemotron)
# - MaaS tier-to-group mapping (free/premium/enterprise)
# - RateLimitPolicy and TokenRateLimitPolicy per tier
# - TelemetryPolicy for MaaS usage metrics
# - MaaS Developer Preview API (via Kustomize remote base)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-03-llm-serving-maas"

load_env
check_oc_logged_in

log_step "Step 03: LLM Serving with Models-as-a-Service"

log_step "Checking prerequisites..."

if ! oc get applications -n openshift-gitops step-02-gpu-and-prereq &>/dev/null; then
    log_error "step-02-gpu-and-prereq Argo CD Application not found!"
    log_info "Please run: ./steps/step-02-gpu-and-prereq/deploy.sh first"
    exit 1
fi

GPU_NODES=$(oc get nodes -l node-role.kubernetes.io/gpu --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$GPU_NODES" -lt 2 ]]; then
    log_warn "Found $GPU_NODES GPU nodes (need 2 for both models). Models may queue."
fi

log_success "Prerequisites verified"

log_step "Deploying MaaS API (Developer Preview)..."

INGRESS_DOMAIN=$(oc get ingresscontroller -n openshift-ingress-operator default -o jsonpath='{.status.domain}' 2>/dev/null)
log_info "Ingress domain: $INGRESS_DOMAIN"

ensure_namespace "maas-api"
oc apply -k "$REPO_ROOT/gitops/step-03-llm-serving-maas/base/maas/" 2>/dev/null \
    && log_success "MaaS API base applied" \
    || log_warn "MaaS API apply failed (may need manual patching for cluster hostname)"

log_step "Creating Argo CD Application for LLM Serving + MaaS"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"

log_success "Argo CD Application '${STEP_NAME}' created"

log_step "Verifying MaaS tier user groups..."

# Groups are created declaratively via GitOps (governance/maas-groups.yaml)
# Verify they exist after ArgoCD syncs them
for group in tier-free-users tier-premium-users tier-enterprise-users; do
    until oc get group "$group" &>/dev/null; do
        log_info "Waiting for group $group..."
        sleep 5
    done
done

log_success "MaaS tier groups configured (tier-free-users, tier-premium-users, tier-enterprise-users)"

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
echo "Models:"
oc get inferenceservice -n maas --no-headers 2>/dev/null | while read -r line; do
    echo "  • $line"
done
echo ""
echo "MaaS Tiers:"
echo "  • Enterprise: admin"
echo "  • Premium: user1-user5"
echo "  • Free: (unassigned users)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "Argo CD Application status:"
echo "  oc get applications -n openshift-gitops ${STEP_NAME}"
echo ""
log_info "Model endpoints:"
echo "  oc get inferenceservice -n maas"
echo ""
