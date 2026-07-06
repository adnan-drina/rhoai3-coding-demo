#!/usr/bin/env bash
# validate.sh — Stage 020: GPU-as-a-Service
# Proves the GPU node, NVIDIA stack, Kueue queues, and RHOAI hardware profiles
# are ready for self-service use.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set. Set it in .env." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match guard." >&2
  exit 1
fi

check() {
  local label="$1"
  local result="$2"
  if [[ "$result" == "pass" ]]; then
    echo "✓ $label"
    (( PASS++ )) || true
  else
    echo "✗ $label  ($result)"
    (( FAIL++ )) || true
  fi
}

csv_phase() {
  local namespace="$1"
  local display_name="$2"
  oc get csv -n "$namespace" \
    -o jsonpath="{.items[?(@.spec.displayName==\"${display_name}\")].status.phase}" \
    --insecure-skip-tls-verify=true 2>/dev/null || true
}

condition_status() {
  local kind="$1"
  local name="$2"
  local type="$3"
  local namespace="${4:-}"
  if [[ -n "$namespace" ]]; then
    oc get "$kind" "$name" -n "$namespace" \
      -o jsonpath="{.status.conditions[?(@.type==\"${type}\")].status}" \
      --insecure-skip-tls-verify=true 2>/dev/null || true
  else
    oc get "$kind" "$name" \
      -o jsonpath="{.status.conditions[?(@.type==\"${type}\")].status}" \
      --insecure-skip-tls-verify=true 2>/dev/null || true
  fi
}

APP_SYNC=$(oc get applications.argoproj.io 020-gpu-infrastructure-private-ai -n openshift-gitops \
  -o jsonpath='{.status.sync.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
APP_HEALTH=$(oc get applications.argoproj.io 020-gpu-infrastructure-private-ai -n openshift-gitops \
  -o jsonpath='{.status.health.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$APP_SYNC" == "Synced" ]] && R="pass" || R="sync=${APP_SYNC:-not found}"
check "Argo CD Application Synced" "$R"
[[ "$APP_HEALTH" == "Healthy" ]] && R="pass" || R="health=${APP_HEALTH:-not found}"
check "Argo CD Application Healthy" "$R"

NFD_CSV=$(csv_phase openshift-nfd "Node Feature Discovery Operator")
[[ "$NFD_CSV" == "Succeeded" ]] && R="pass" || R="phase=${NFD_CSV:-not found}"
check "NFD operator CSV Succeeded" "$R"

GPU_CSV=$(csv_phase nvidia-gpu-operator "NVIDIA GPU Operator")
[[ "$GPU_CSV" == "Succeeded" ]] && R="pass" || R="phase=${GPU_CSV:-not found}"
check "NVIDIA GPU operator CSV Succeeded" "$R"

KUEUE_CSV=$(csv_phase openshift-kueue-operator "Red Hat build of Kueue")
[[ "$KUEUE_CSV" == "Succeeded" ]] && R="pass" || R="phase=${KUEUE_CSV:-not found}"
check "Kueue operator CSV Succeeded" "$R"

NFD_AVAILABLE=$(condition_status nodefeaturediscovery nfd-instance Available openshift-nfd)
[[ "$NFD_AVAILABLE" == "True" ]] && R="pass" || R="available=${NFD_AVAILABLE:-not found}"
check "NodeFeatureDiscovery Available" "$R"

CLUSTER_POLICY_STATE=$(oc get clusterpolicy gpu-cluster-policy \
  -o jsonpath='{.status.state}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$CLUSTER_POLICY_STATE" == "ready" ]] && R="pass" || R="state=${CLUSTER_POLICY_STATE:-not found}"
check "NVIDIA ClusterPolicy ready" "$R"

GPU_MS=$(oc get machineset -n openshift-machine-api \
  -l cluster-api/accelerator=nvidia-gpu \
  -o jsonpath='{.items[0].metadata.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ -n "$GPU_MS" ]]; then
  READY=$(oc get machineset "$GPU_MS" -n openshift-machine-api \
    -o jsonpath='{.status.readyReplicas}' --insecure-skip-tls-verify=true 2>/dev/null || echo "0")
  [[ "${READY:-0}" -ge 1 ]] && R="pass" || R="readyReplicas=${READY:-0}"
else
  R="not found"
fi
check "GPU MachineSet has a ready worker" "$R"

GPU_ALLOCATABLE=$(oc get node -l nvidia.com/gpu.present=true \
  -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' \
  --insecure-skip-tls-verify=true 2>/dev/null | awk '{sum += $1} END {print sum + 0}')
[[ "$GPU_ALLOCATABLE" -ge 4 ]] && R="pass" || R="allocatable=${GPU_ALLOCATABLE:-0}"
check "GPU node advertises at least 4 time-sliced GPU units" "$R"

DSC_KUEUE=$(oc get datasciencecluster default-dsc \
  -o jsonpath='{.spec.components.kueue.managementState}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
DSC_KSERVE=$(oc get datasciencecluster default-dsc \
  -o jsonpath='{.spec.components.kserve.managementState}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DSC_KUEUE" == "Unmanaged" ]] && R="pass" || R="kueue=${DSC_KUEUE:-not found}"
check "DataScienceCluster Kueue integration is Unmanaged" "$R"
if [[ "$DSC_KSERVE" == "Removed" || "$DSC_KSERVE" == "Managed" ]]; then
  R="pass"
else
  R="kserve=${DSC_KSERVE:-not found}"
fi
check "DataScienceCluster KServe state is valid for current stage progression" "$R"

for cq in cq-cpu-default cq-gpu-shared cq-gpu-priority cq-gpu-reserved-demo; do
  ACTIVE=$(condition_status clusterqueue "$cq" Active)
  [[ "$ACTIVE" == "True" ]] && R="pass" || R="active=${ACTIVE:-not found}"
  check "ClusterQueue ${cq} Active" "$R"
done

for lq in lq-cpu-default lq-gpu-shared lq-gpu-priority lq-gpu-reserved-demo; do
  ACTIVE=$(condition_status localqueue "$lq" Active demo-sandbox)
  [[ "$ACTIVE" == "True" ]] && R="pass" || R="active=${ACTIVE:-not found}"
  check "LocalQueue ${lq} Active" "$R"
done

for hp in cpu-default gpu-shared gpu-priority gpu-reserved-demo; do
  DISPLAY_NAME=$(oc get hardwareprofile "$hp" -n redhat-ods-applications \
    -o jsonpath='{.metadata.annotations.opendatahub\.io/display-name}' \
    --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ -n "$DISPLAY_NAME" ]] && R="pass" || R="missing"
  check "HardwareProfile ${hp} present" "$R"
done

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
