#!/usr/bin/env bash
# Stage 020: GPU Infrastructure and GPU-as-a-Service - Deploy
# Applies the ArgoCD Application. GPU MachineSet creation and OpenShift AI
# Kueue enablement are handled by in-cluster Jobs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="020-gpu-infrastructure-private-ai"

load_env
check_oc_logged_in

log_step "Stage 020: GPU Infrastructure and GPU-as-a-Service Foundation"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STAGE_NAME}.yaml"
log_success "ArgoCD Application '${STAGE_NAME}' applied"

log_info "ArgoCD handles all orchestration via sync waves:"
log_info "  Wave -10..0: NFD, GPU Operator, Kueue, and Custom Metrics Autoscaler subscriptions"
log_info "  Wave 5-15:   Kueue CR, queue/quota resources, KEDA controller, dashboards"
log_info "  Wave 10-15:  NFD instance, ClusterPolicy, DCGM dashboard"
log_info "  Wave 20:     GPU MachineSet Job (discovers cluster, creates MachineSet)"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get pods -n openshift-kueue-operator"
echo "  oc get clusterqueue,resourceflavor"
echo "  oc get machines -n openshift-machine-api | grep gpu"
echo "  oc get nodes -l node-role.kubernetes.io/gpu"
echo ""
