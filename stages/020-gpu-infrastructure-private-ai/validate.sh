#!/usr/bin/env bash
# Stage 020: GPU Infrastructure — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 020: GPU Infrastructure — Validation                     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "020-gpu-infrastructure-private-ai"

log_step "Required CRDs"
check_crd_exists "nodefeaturediscoveries.nfd.openshift.io"
check_crd_exists "clusterpolicies.nvidia.com"

log_step "Operator CSVs"
check_csv_succeeded "openshift-nfd" "nfd"
check_csv_succeeded "nvidia-gpu-operator" "gpu"

log_step "GPU MachineSets"
MS_COUNT=$(oc get machineset -n openshift-machine-api -o json 2>/dev/null \
    | jq '[.items[] | select(.spec.template.spec.providerSpec.value.instanceType | test("^g[0-9]"))] | length' 2>/dev/null || echo "0")
if [[ "$MS_COUNT" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU MachineSets found: $MS_COUNT"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} No GPU MachineSets found"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

MS_READY=$(oc get machineset -n openshift-machine-api -o json 2>/dev/null \
    | jq '[.items[] | select(.spec.template.spec.providerSpec.value.instanceType | test("^g[0-9]")) | select((.status.readyReplicas // 0) >= (.spec.replicas // 0))] | length' 2>/dev/null || echo "0")
if [[ "$MS_READY" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU MachineSet replicas ready"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} GPU MachineSet replicas not fully ready"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

GPU_NODES=$(oc get nodes -l nvidia.com/gpu.present=true --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$GPU_NODES" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU nodes available: $GPU_NODES"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} GPU nodes available: $GPU_NODES (may take 5-10 min to provision)"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

ALLOC_GPU_NODES=$(oc get nodes -l nvidia.com/gpu.present=true -o json 2>/dev/null \
    | jq '[.items[] | select(((.status.allocatable["nvidia.com/gpu"] // "0") | tonumber) >= 1)] | length' 2>/dev/null || echo "0")
if [[ "$ALLOC_GPU_NODES" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU allocatable resources present: $ALLOC_GPU_NODES"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} GPU allocatable resources present: $ALLOC_GPU_NODES"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

GPU_ROLE_NODES=$(oc get nodes -l node-role.kubernetes.io/gpu --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$GPU_ROLE_NODES" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU role labels present: $GPU_ROLE_NODES"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} GPU role labels present: $GPU_ROLE_NODES"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

GPU_TAINT_NODES=$(oc get nodes -l nvidia.com/gpu.present=true -o json 2>/dev/null \
    | jq '[.items[] | select(any(.spec.taints[]?; .key == "nvidia.com/gpu" and .effect == "NoSchedule"))] | length' 2>/dev/null || echo "0")
if [[ "$GPU_TAINT_NODES" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU NoSchedule taints present: $GPU_TAINT_NODES"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} GPU NoSchedule taints present: $GPU_TAINT_NODES"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "GPU Operator Runtime"
check "NodeFeatureDiscovery available" \
    "oc get nodefeaturediscovery nfd-instance -n openshift-nfd -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "NVIDIA ClusterPolicy ready" \
    "oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
    "True"
check "NVIDIA ClusterPolicy state ready" \
    "oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.state}'" \
    "ready"

echo ""
validation_summary
