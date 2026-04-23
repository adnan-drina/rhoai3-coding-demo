#!/usr/bin/env bash
# Step 02: GPU Infrastructure - Deploy
# Applies the ArgoCD Application. GPU MachineSet creation is handled by
# an in-cluster Job (gitops-catalog pattern) at sync wave 20.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-02-gpu-infra"

load_env
check_oc_logged_in

log_step "Step 02: GPU Infrastructure"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "ArgoCD handles all orchestration via sync waves:"
log_info "  Wave -10..0: NFD + GPU Operator namespaces, subscriptions"
log_info "  Wave 5-10:   NFD instance, ClusterPolicy, DCGM dashboard"
log_info "  Wave 20:     GPU MachineSet Job (discovers cluster, creates MachineSet)"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get machines -n openshift-machine-api | grep gpu"
echo "  oc get nodes -l node-role.kubernetes.io/gpu"
echo ""
