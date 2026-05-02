#!/usr/bin/env bash
# Stage 020: GPU Infrastructure and GPU-as-a-Service — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 020: GPU Infrastructure + GPUaaS — Validation            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "020-gpu-infrastructure-private-ai"

log_step "Required CRDs"
check_crd_exists "nodefeaturediscoveries.nfd.openshift.io"
check_crd_exists "clusterpolicies.nvidia.com"
check_crd_exists "kueues.kueue.openshift.io"
check_crd_exists "resourceflavors.kueue.x-k8s.io"
check_crd_exists "clusterqueues.kueue.x-k8s.io"
check_crd_exists "localqueues.kueue.x-k8s.io"
check_crd_exists "kedacontrollers.keda.sh"
check_crd_exists "scaledobjects.keda.sh"

log_step "Operator CSVs"
check_csv_succeeded "openshift-nfd" "nfd"
check_csv_succeeded "nvidia-gpu-operator" "gpu"
check_csv_succeeded "openshift-kueue-operator" "kueue"
check_csv_succeeded "openshift-keda" "custom-metrics-autoscaler"

log_step "GPUaaS Queue Control Plane"
check "Kueue cluster instance exists" \
    "oc get kueues.kueue.openshift.io cluster -o jsonpath='{.metadata.name}'" \
    "cluster"
check_warn "Kueue cluster instance ready" \
    "oc get kueues.kueue.openshift.io cluster -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "OpenShift AI Kueue integration is unmanaged" \
    "oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kueue.managementState}'" \
    "Unmanaged"
check "OpenShift AI dashboard Kueue support enabled" \
    "oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.disableKueue}'" \
    "false"
check "maas namespace managed by Kueue" \
    "oc get namespace maas -o jsonpath='{.metadata.labels.kueue\\.openshift\\.io/managed}'" \
    "true"
check "maas namespace visible in OpenShift AI dashboard" \
    "oc get namespace maas -o jsonpath='{.metadata.labels.opendatahub\\.io/dashboard}'" \
    "true"
check "Kueue namespace has cluster monitoring enabled" \
    "oc get namespace openshift-kueue-operator -o jsonpath='{.metadata.labels.openshift\\.io/cluster-monitoring}'" \
    "true"
check "NVIDIA L4 ResourceFlavor exists" \
    "oc get resourceflavor nvidia-l4-gpu -o jsonpath='{.metadata.name}'" \
    "nvidia-l4-gpu"
check "ResourceFlavor selects GPU nodes" \
    "oc get resourceflavor nvidia-l4-gpu -o jsonpath='{.spec.nodeLabels}'" \
    "node-role.kubernetes.io/gpu"
check "ResourceFlavor carries GPU taint toleration" \
    "oc get resourceflavor nvidia-l4-gpu -o jsonpath='{.spec.tolerations[0].key}{\"=\"}{.spec.tolerations[0].value}:{.spec.tolerations[0].effect}'" \
    "nvidia.com/gpu=true:NoSchedule"
check "ClusterQueue exists" \
    "oc get clusterqueue private-model-serving-gpu -o jsonpath='{.metadata.name}'" \
    "private-model-serving-gpu"
check "ClusterQueue advertises two GPU nominal quota" \
    "oc get clusterqueue private-model-serving-gpu -o jsonpath='{.spec.resourceGroups[0].flavors[0].resources[?(@.name==\"nvidia.com/gpu\")].nominalQuota}'" \
    "2"
check "LocalQueue exists in maas" \
    "oc get localqueue private-model-serving -n maas -o jsonpath='{.spec.clusterQueue}'" \
    "private-model-serving-gpu"
check "Queued 1GPU hardware profile exists" \
    "oc get hardwareprofile nvidia-l4-1gpu-queued -n redhat-ods-applications -o jsonpath='{.spec.scheduling.type}{\" \"}{.spec.scheduling.kueue.localQueueName}'" \
    "Queue private-model-serving"
check "Queued 2GPU hardware profile exists" \
    "oc get hardwareprofile nvidia-l4-2gpu-queued -n redhat-ods-applications -o jsonpath='{.spec.scheduling.type}{\" \"}{.spec.scheduling.kueue.localQueueName}'" \
    "Queue private-model-serving"
check "Direct 1GPU hardware profile preserved" \
    "oc get hardwareprofile nvidia-l4-1gpu -n redhat-ods-applications -o jsonpath='{.spec.scheduling.type}'" \
    "Node"

log_step "Autoscaling Building Block"
check "KedaController exists" \
    "oc get kedacontroller keda -n openshift-keda -o jsonpath='{.metadata.name}'" \
    "keda"
KEDA_RUNNING_PODS=$(oc get pods -n openshift-keda --no-headers 2>/dev/null | grep -i keda | grep -c Running || true)
if [[ "$KEDA_RUNNING_PODS" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} KEDA runtime pods running: $KEDA_RUNNING_PODS"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} KEDA runtime pods running: $KEDA_RUNNING_PODS"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

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

log_step "GPUaaS Observability"
check "DCGM dashboard ConfigMap exists" \
    "oc get configmap nvidia-dcgm-exporter-dashboard -n openshift-config-managed -o jsonpath='{.metadata.name}'" \
    "nvidia-dcgm-exporter-dashboard"
check "GPUaaS dashboard ConfigMap exists" \
    "oc get configmap rhoai-gpuaas-dashboard -n openshift-config-managed -o jsonpath='{.metadata.name}'" \
    "rhoai-gpuaas-dashboard"
check_warn "GPU utilization metric available" \
    "oc get --raw '/api/v1/namespaces/openshift-monitoring/services/https:prometheus-k8s:9091/proxy/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL' | jq -r '.status' 2>/dev/null" \
    "success"
check_warn "Kueue pending workload metric available" \
    "oc get --raw '/api/v1/namespaces/openshift-monitoring/services/https:prometheus-k8s:9091/proxy/api/v1/query?query=kueue_pending_workloads' | jq -r '.status' 2>/dev/null" \
    "success"

echo ""
validation_summary
