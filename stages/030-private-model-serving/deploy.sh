#!/usr/bin/env bash
# Stage 030: Private Model Serving - Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="030-private-model-serving"

load_env
check_oc_logged_in

log_step "Stage 030: Private Model Serving"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-2:   LeaderWorkerSet operator prerequisites"
log_info "  Wave 5-10:  maas namespace, tier mapping, local LLMInferenceService resources"
log_info "  Wave 22:    model registry seed job"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo ""
