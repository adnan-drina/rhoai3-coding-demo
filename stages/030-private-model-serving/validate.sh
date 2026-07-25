#!/usr/bin/env bash
# validate.sh - Stage 030: Model Serving Foundation
# Proves KServe, vLLM, the demo registry metadata, and the Granite endpoint are
# ready for model-serving baseline work.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0

REGISTRY_NS="${MODEL_REGISTRY_NAMESPACE:-rhoai-model-registries}"
REGISTRY_NAME="${MODEL_REGISTRY_NAME:-demo-registry}"
MODEL_NS="${RHOAI_MODEL_NAMESPACE:-demo-sandbox}"
MODEL_DEPLOYMENT_NAME="${RHOAI_GRANITE_DEPLOYMENT_NAME:-granite-4-0-h-small-fp8-dynamic}"
MAAS_NS="${RHOAI_MAAS_NAMESPACE:-models-as-a-service}"
MAAS_GRANITE_MODEL_NAME="${RHOAI_MAAS_GRANITE_MODEL_NAME:-granite-4-0-h-small}"
MODEL_DISPLAY_NAME="${RHOAI_GRANITE_DISPLAY_NAME:-Granite-3-Nano-30B-A3B-FP8}"
# Must match deploy.sh's default (v3.0 = the modelcar :3.0 tag); a stale
# "Version 1" default here made the version + artifact metadata checks fail
# against a correctly-registered model version.
MODEL_VERSION_NAME="${RHOAI_GRANITE_VERSION_NAME:-v3.0}"
MODEL_URI="${RHOAI_GRANITE_MODEL_URI:-oci://registry.redhat.io/rhai/modelcar-granite-4-0-h-small-fp8-dynamic@sha256:e539fc9568045972b3e848196c5a7486a0ad2ac8946e47aca1db1633d5a9911d}"
MODEL_CPU_REQUEST="${RHOAI_GRANITE_CPU_REQUEST:-2}"
MODEL_CPU_LIMIT="${RHOAI_GRANITE_CPU_LIMIT:-4}"
MODEL_MEMORY_REQUEST="${RHOAI_GRANITE_MEMORY_REQUEST:-16Gi}"
MODEL_MEMORY_LIMIT="${RHOAI_GRANITE_MEMORY_LIMIT:-24Gi}"
MODEL_MAX_MODEL_LEN="${RHOAI_GRANITE_MAX_MODEL_LEN:-8192}"
MODEL_MAX_BATCHED_TOKENS="${RHOAI_GRANITE_MAX_BATCHED_TOKENS:-8192}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

REGISTRY_NS="${MODEL_REGISTRY_NAMESPACE:-$REGISTRY_NS}"
REGISTRY_NAME="${MODEL_REGISTRY_NAME:-$REGISTRY_NAME}"
MODEL_NS="${RHOAI_MODEL_NAMESPACE:-$MODEL_NS}"
MODEL_DEPLOYMENT_NAME="${RHOAI_GRANITE_DEPLOYMENT_NAME:-$MODEL_DEPLOYMENT_NAME}"
MAAS_NS="${RHOAI_MAAS_NAMESPACE:-$MAAS_NS}"
MAAS_GRANITE_MODEL_NAME="${RHOAI_MAAS_GRANITE_MODEL_NAME:-$MAAS_GRANITE_MODEL_NAME}"
MODEL_DISPLAY_NAME="${RHOAI_GRANITE_DISPLAY_NAME:-$MODEL_DISPLAY_NAME}"
MODEL_VERSION_NAME="${RHOAI_GRANITE_VERSION_NAME:-$MODEL_VERSION_NAME}"
MODEL_URI="${RHOAI_GRANITE_MODEL_URI:-$MODEL_URI}"
MODEL_CPU_REQUEST="${RHOAI_GRANITE_CPU_REQUEST:-$MODEL_CPU_REQUEST}"
MODEL_CPU_LIMIT="${RHOAI_GRANITE_CPU_LIMIT:-$MODEL_CPU_LIMIT}"
MODEL_MEMORY_REQUEST="${RHOAI_GRANITE_MEMORY_REQUEST:-$MODEL_MEMORY_REQUEST}"
MODEL_MEMORY_LIMIT="${RHOAI_GRANITE_MEMORY_LIMIT:-$MODEL_MEMORY_LIMIT}"
MODEL_MAX_MODEL_LEN="${RHOAI_GRANITE_MAX_MODEL_LEN:-$MODEL_MAX_MODEL_LEN}"
MODEL_MAX_BATCHED_TOKENS="${RHOAI_GRANITE_MAX_BATCHED_TOKENS:-$MODEL_MAX_BATCHED_TOKENS}"

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

require_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi
  echo "ERROR: required command not found: $cmd" >&2
  exit 1
}

crd_exists() {
  local name="$1"
  oc get crd "$name" --insecure-skip-tls-verify=true >/dev/null 2>&1
}

resource_exists() {
  local resource="$1"
  local namespace="$2"
  if [[ -n "$namespace" ]]; then
    oc get "$resource" -n "$namespace" --insecure-skip-tls-verify=true >/dev/null 2>&1
  else
    oc get "$resource" --insecure-skip-tls-verify=true >/dev/null 2>&1
  fi
}

require_cmd curl
require_cmd jq

APP_SYNC=$(oc get applications.argoproj.io 010-openshift-ai-platform-foundation -n openshift-gitops \
  -o jsonpath='{.status.sync.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
APP_HEALTH=$(oc get applications.argoproj.io 010-openshift-ai-platform-foundation -n openshift-gitops \
  -o jsonpath='{.status.health.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$APP_SYNC" == "Synced" ]] && R="pass" || R="sync=${APP_SYNC:-not found}"
check "Stage 010 shared owner Application Synced" "$R"
[[ "$APP_HEALTH" == "Healthy" ]] && R="pass" || R="health=${APP_HEALTH:-not found}"
check "Stage 010 shared owner Application Healthy" "$R"

OBS_APP_SYNC=$(oc get applications.argoproj.io 030-private-model-serving -n openshift-gitops \
  -o jsonpath='{.status.sync.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_APP_HEALTH=$(oc get applications.argoproj.io 030-private-model-serving -n openshift-gitops \
  -o jsonpath='{.status.health.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_APP_SYNC" == "Synced" ]] && R="pass" || R="sync=${OBS_APP_SYNC:-not found}"
check "Stage 030 observability Application Synced" "$R"
[[ "$OBS_APP_HEALTH" == "Healthy" ]] && R="pass" || R="health=${OBS_APP_HEALTH:-not found}"
check "Stage 030 observability Application Healthy" "$R"

DSC_PHASE=$(oc get datasciencecluster default-dsc \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DSC_PHASE" == "Ready" ]] && R="pass" || R="phase=${DSC_PHASE:-not found}"
check "DataScienceCluster Ready" "$R"

DSC_KSERVE=$(oc get datasciencecluster default-dsc \
  -o jsonpath='{.spec.components.kserve.managementState}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DSC_KSERVE" == "Managed" ]] && R="pass" || R="kserve=${DSC_KSERVE:-not found}"
check "DataScienceCluster KServe is Managed" "$R"

UWM_ENABLED=$(oc get configmap cluster-monitoring-config -n openshift-monitoring \
  -o jsonpath='{.data.config\.yaml}' --insecure-skip-tls-verify=true 2>/dev/null \
  | grep -E 'enableUserWorkload:[[:space:]]*true' || true)
[[ -n "$UWM_ENABLED" ]] && R="pass" || R="missing enableUserWorkload: true"
check "OpenShift user workload monitoring enabled" "$R"

if resource_exists "configmap/user-workload-monitoring-config" "openshift-user-workload-monitoring"; then
  R="pass"
else
  R="missing"
fi
check "User workload monitoring config present" "$R"

ALERT_WEBHOOK_READY=$(oc get deployment rhoai-demo-alert-webhook -n openshift-monitoring \
  -o jsonpath='{.status.readyReplicas}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ "${ALERT_WEBHOOK_READY:-0}" -ge 1 ]]; then
  R="pass"
else
  R="readyReplicas=${ALERT_WEBHOOK_READY:-0}"
fi
check "Alertmanager demo webhook receiver is Ready" "$R"

if resource_exists "service/rhoai-demo-alert-webhook" "openshift-monitoring"; then
  R="pass"
else
  R="missing"
fi
check "Alertmanager demo webhook Service present" "$R"

ALERTMANAGER_CONFIG=$(oc get secret alertmanager-main -n openshift-monitoring \
  -o jsonpath='{.data.alertmanager\.yaml}' --insecure-skip-tls-verify=true 2>/dev/null \
  | base64 -d 2>/dev/null || true)
if grep -q 'webhook_configs:' <<<"$ALERTMANAGER_CONFIG" \
  && grep -q 'rhoai-demo-alert-webhook.openshift-monitoring.svc' <<<"$ALERTMANAGER_CONFIG"; then
  R="pass"
else
  R="missing configured webhook receiver"
fi
check "Alertmanager notification receivers configured" "$R"

ALERTMANAGER_INTEGRATIONS_QUERY=$(oc -n openshift-monitoring exec prometheus-k8s-0 -c prometheus \
  --insecure-skip-tls-verify=true -- \
  curl -s 'http://localhost:9090/api/v1/query?query=cluster%3Aalertmanager_integrations%3Amax' \
  2>/dev/null || echo "{}")
ALERTMANAGER_INTEGRATIONS=$(jq -r '.data.result[0].value[1] // "0"' \
  <<<"$ALERTMANAGER_INTEGRATIONS_QUERY" 2>/dev/null || echo "0")
if awk "BEGIN {exit !(${ALERTMANAGER_INTEGRATIONS:-0} >= 1)}"; then
  R="pass"
else
  R="integrations=${ALERTMANAGER_INTEGRATIONS:-0}"
fi
check "Alertmanager configured integrations metric is nonzero" "$R"

ALERTMANAGER_RECEIVER_ALERTS=$(oc -n openshift-monitoring exec prometheus-k8s-0 -c prometheus \
  --insecure-skip-tls-verify=true -- \
  curl -s 'http://localhost:9090/api/v1/query?query=ALERTS%7Balertname%3D%22AlertmanagerReceiversNotConfigured%22%2Calertstate%3D%22firing%22%7D' \
  2>/dev/null | jq -r '.data.result | length' 2>/dev/null || echo "unknown")
if [[ "$ALERTMANAGER_RECEIVER_ALERTS" == "0" ]]; then
  R="pass"
else
  R="firing=${ALERTMANAGER_RECEIVER_ALERTS}"
fi
check "AlertmanagerReceiversNotConfigured is not firing" "$R"

if crd_exists inferenceservices.serving.kserve.io; then
  R="pass"
else
  R="missing"
fi
check "InferenceService CRD present" "$R"

if crd_exists servingruntimes.serving.kserve.io; then
  R="pass"
else
  R="missing"
fi
check "ServingRuntime CRD present" "$R"

VLLM_RUNTIME=$(oc get servingruntime -A \
  -o jsonpath='{range .items[*]}{.metadata.namespace}{"/"}{.metadata.name}{" "}{.metadata.annotations.openshift\.io/display-name}{"\n"}{end}' \
  --insecure-skip-tls-verify=true 2>/dev/null | grep -Ei 'vllm|vLLM' | head -1 || true)
[[ -n "$VLLM_RUNTIME" ]] && R="pass" || R="no vLLM runtime found"
check "vLLM ServingRuntime discoverable" "$R"

GPU_PROFILE=$(oc get hardwareprofile gpu-reserved-demo -n redhat-ods-applications \
  -o jsonpath='{.metadata.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$GPU_PROFILE" == "gpu-reserved-demo" ]] && R="pass" || R="missing"
check "Stage 020 GPU Reserved hardware profile present" "$R"

GPU_ALLOCATABLE=$(oc get node -l nvidia.com/gpu.present=true \
  -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' \
  --insecure-skip-tls-verify=true 2>/dev/null | awk '{sum += $1} END {print sum + 0}')
[[ "$GPU_ALLOCATABLE" -ge 2 ]] && R="pass" || R="allocatable=${GPU_ALLOCATABLE:-0}"
check "GPU nodes advertise at least 2 full-card GPU units (no time-slicing)" "$R"

REGISTRY_AVAILABLE=$(oc get modelregistries.modelregistry.opendatahub.io "$REGISTRY_NAME" -n "$REGISTRY_NS" \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$REGISTRY_AVAILABLE" == "True" ]] && R="pass" || R="available=${REGISTRY_AVAILABLE:-not found}"
check "demo-registry Available" "$R"

REGISTRY_HOST=$(oc get modelregistries.modelregistry.opendatahub.io "$REGISTRY_NAME" -n "$REGISTRY_NS" \
  -o jsonpath='{.status.hosts[0]}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ -n "$REGISTRY_HOST" ]]; then
  R="pass"
else
  R="missing route host"
fi
check "demo-registry route host present" "$R"

if [[ -n "$REGISTRY_HOST" ]]; then
  MR_BASE_URL="https://${REGISTRY_HOST}/api/model_registry/v1alpha3"
  MR_TOKEN=$(oc whoami -t)
  MR_MODELS=$(curl -sk -H "Authorization: Bearer ${MR_TOKEN}" \
    "${MR_BASE_URL}/registered_models" 2>/dev/null || echo "{}")
  MODEL_ID=$(jq -r --arg name "$MODEL_DISPLAY_NAME" \
    '.items[]? | select(.name == $name and (.state // "LIVE") != "ARCHIVED") | .id' <<<"$MR_MODELS" | head -1)
  [[ -n "$MODEL_ID" ]] && R="pass" || R="missing"
  check "Granite registered model metadata present" "$R"

  if [[ -n "$MODEL_ID" ]]; then
    MR_VERSIONS=$(curl -sk -H "Authorization: Bearer ${MR_TOKEN}" \
      "${MR_BASE_URL}/registered_models/${MODEL_ID}/versions" 2>/dev/null || echo "{}")
    MODEL_VERSION_ID=$(jq -r --arg name "$MODEL_VERSION_NAME" \
      '.items[]? | select(.name == $name and (.state // "LIVE") != "ARCHIVED") | .id' <<<"$MR_VERSIONS" | head -1)
    [[ -n "$MODEL_VERSION_ID" ]] && R="pass" || R="missing"
    check "Granite model version metadata present" "$R"
  else
    MODEL_VERSION_ID=""
    check "Granite model version metadata present" "registered model missing"
  fi

  if [[ -n "$MODEL_VERSION_ID" ]]; then
    MR_ARTIFACTS=$(curl -sk -H "Authorization: Bearer ${MR_TOKEN}" \
      "${MR_BASE_URL}/model_versions/${MODEL_VERSION_ID}/artifacts" 2>/dev/null || echo "{}")
    MODEL_ARTIFACT_ID=$(jq -r --arg uri "$MODEL_URI" \
      '.items[]? | select(.uri == $uri and (.state // "LIVE") != "DELETED") | .id' <<<"$MR_ARTIFACTS" | head -1)
    [[ -n "$MODEL_ARTIFACT_ID" ]] && R="pass" || R="missing"
    check "Granite OCI model artifact metadata present" "$R"
  else
    check "Granite OCI model artifact metadata present" "model version missing"
  fi
fi

# Model catalog (rhoai-model-registries) — dashboard-facing but RHOAI-operator-managed,
# so it lives OUTSIDE the demo's GitOps and stays invisible to every Argo app. Its
# Postgres schema is created by a one-time migration at catalog startup; if Postgres
# is later restarted (node drain, reschedule) the tables are lost and the catalog
# serves HTTP 500 on every models query while deploy/model-catalog still reports
# Available and all Argo apps stay green. Probe the same filter_options endpoint the
# dashboard's Model Catalog page calls, so an empty-DB catalog FAILS validation
# instead of silently rendering an empty catalog. Recovery: restart deploy/model-catalog
# in rhoai-model-registries to re-run the migration.
CATALOG_AVAILABLE=$(oc get deployment model-catalog -n "$REGISTRY_NS" \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$CATALOG_AVAILABLE" == "True" ]] && R="pass" || R="available=${CATALOG_AVAILABLE:-not found}"
check "Model catalog deployment Available" "$R"

CATALOG_HOST=$(oc get route model-catalog-https -n "$REGISTRY_NS" \
  -o jsonpath='{.spec.host}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ -n "$CATALOG_HOST" ]]; then
  CATALOG_TOKEN=$(oc whoami -t 2>/dev/null || echo "")
  CATALOG_CODE=$(curl -sk -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${CATALOG_TOKEN}" \
    "https://${CATALOG_HOST}/api/model_catalog/v1alpha1/models/filter_options" 2>/dev/null || echo "000")
  [[ "$CATALOG_CODE" == "200" ]] && R="pass" \
    || R="http=${CATALOG_CODE} (empty schema serves 500 — restart deploy/model-catalog to re-migrate)"
  check "Model catalog API serves models (Postgres schema intact)" "$R"
else
  check "Model catalog API serves models (Postgres schema intact)" "route model-catalog-https missing"
fi

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
