#!/usr/bin/env bash
# Stage 050: Approved External Model Access - Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="050-approved-external-model-access"

load_env
check_oc_logged_in

log_step "Stage 050: Approved External Model Access"

log_step "Provisioning external provider credential"
ensure_namespace "maas"

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    ensure_secret_from_env "openai-api-key" "maas" "api-key=${OPENAI_API_KEY}"
    oc label secret openai-api-key -n maas inference.networking.k8s.io/bbr-managed=true --overwrite
    log_success "openai-api-key provisioned in maas namespace"
else
    log_info "OPENAI_API_KEY not set — external models register with placeholder credentials; inference will fail"
fi

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STAGE_NAME}.yaml"
log_success "ArgoCD Application '${STAGE_NAME}' applied"

log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get externalmodel,maasmodelref -n maas"
echo ""
