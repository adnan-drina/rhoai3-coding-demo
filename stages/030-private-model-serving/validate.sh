#!/usr/bin/env bash
# validate.sh - Stage 030: Model Serving Foundation
# Proves KServe, vLLM, the demo registry metadata, and the Nemotron endpoint are
# ready for model-serving baseline work.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0

REGISTRY_NS="${MODEL_REGISTRY_NAMESPACE:-rhoai-model-registries}"
REGISTRY_NAME="${MODEL_REGISTRY_NAME:-demo-registry}"
MODEL_NS="${RHOAI_MODEL_NAMESPACE:-demo-sandbox}"
MODEL_DEPLOYMENT_NAME="${RHOAI_NEMOTRON_DEPLOYMENT_NAME:-nvidia-nemotron-3-nano-30b-a3b}"
MAAS_NS="${RHOAI_MAAS_NAMESPACE:-models-as-a-service}"
MAAS_NEMOTRON_MODEL_NAME="${RHOAI_MAAS_NEMOTRON_MODEL_NAME:-nemotron-3-nano-30b-a3b}"
MODEL_DISPLAY_NAME="${RHOAI_NEMOTRON_DISPLAY_NAME:-NVIDIA-Nemotron-3-Nano-30B-A3B-FP8}"
MODEL_VERSION_NAME="${RHOAI_NEMOTRON_VERSION_NAME:-Version 1}"
MODEL_URI="${RHOAI_NEMOTRON_MODEL_URI:-oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0}"
GRAFANA_NS="${RHOAI_GRAFANA_NAMESPACE:-rhoai-demo-grafana}"
GUIDELLM_DATA_PVC="${RHOAI_GUIDELLM_DATA_PVC:-benchmark-data}"
GUIDELLM_PROMPTS_CONFIGMAP="${RHOAI_GUIDELLM_PROMPTS_CONFIGMAP:-stage210-guidellm-prompts}"
MODEL_CPU_REQUEST="${RHOAI_NEMOTRON_CPU_REQUEST:-2}"
MODEL_CPU_LIMIT="${RHOAI_NEMOTRON_CPU_LIMIT:-4}"
MODEL_MEMORY_REQUEST="${RHOAI_NEMOTRON_MEMORY_REQUEST:-16Gi}"
MODEL_MEMORY_LIMIT="${RHOAI_NEMOTRON_MEMORY_LIMIT:-24Gi}"
MODEL_MAX_MODEL_LEN="${RHOAI_NEMOTRON_MAX_MODEL_LEN:-8192}"
MODEL_MAX_BATCHED_TOKENS="${RHOAI_NEMOTRON_MAX_BATCHED_TOKENS:-8192}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

REGISTRY_NS="${MODEL_REGISTRY_NAMESPACE:-$REGISTRY_NS}"
REGISTRY_NAME="${MODEL_REGISTRY_NAME:-$REGISTRY_NAME}"
MODEL_NS="${RHOAI_MODEL_NAMESPACE:-$MODEL_NS}"
MODEL_DEPLOYMENT_NAME="${RHOAI_NEMOTRON_DEPLOYMENT_NAME:-$MODEL_DEPLOYMENT_NAME}"
MAAS_NS="${RHOAI_MAAS_NAMESPACE:-$MAAS_NS}"
MAAS_NEMOTRON_MODEL_NAME="${RHOAI_MAAS_NEMOTRON_MODEL_NAME:-$MAAS_NEMOTRON_MODEL_NAME}"
MODEL_DISPLAY_NAME="${RHOAI_NEMOTRON_DISPLAY_NAME:-$MODEL_DISPLAY_NAME}"
MODEL_VERSION_NAME="${RHOAI_NEMOTRON_VERSION_NAME:-$MODEL_VERSION_NAME}"
MODEL_URI="${RHOAI_NEMOTRON_MODEL_URI:-$MODEL_URI}"
GRAFANA_NS="${RHOAI_GRAFANA_NAMESPACE:-$GRAFANA_NS}"
GUIDELLM_DATA_PVC="${RHOAI_GUIDELLM_DATA_PVC:-$GUIDELLM_DATA_PVC}"
GUIDELLM_PROMPTS_CONFIGMAP="${RHOAI_GUIDELLM_PROMPTS_CONFIGMAP:-$GUIDELLM_PROMPTS_CONFIGMAP}"
MODEL_CPU_REQUEST="${RHOAI_NEMOTRON_CPU_REQUEST:-$MODEL_CPU_REQUEST}"
MODEL_CPU_LIMIT="${RHOAI_NEMOTRON_CPU_LIMIT:-$MODEL_CPU_LIMIT}"
MODEL_MEMORY_REQUEST="${RHOAI_NEMOTRON_MEMORY_REQUEST:-$MODEL_MEMORY_REQUEST}"
MODEL_MEMORY_LIMIT="${RHOAI_NEMOTRON_MEMORY_LIMIT:-$MODEL_MEMORY_LIMIT}"
MODEL_MAX_MODEL_LEN="${RHOAI_NEMOTRON_MAX_MODEL_LEN:-$MODEL_MAX_MODEL_LEN}"
MODEL_MAX_BATCHED_TOKENS="${RHOAI_NEMOTRON_MAX_BATCHED_TOKENS:-$MODEL_MAX_BATCHED_TOKENS}"

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

for crd in grafanas.grafana.integreatly.org grafanadatasources.grafana.integreatly.org grafanadashboards.grafana.integreatly.org; do
  if crd_exists "$crd"; then
    R="pass"
  else
    R="missing"
  fi
  check "Grafana CRD present: ${crd}" "$R"
done

if resource_exists "subscription/grafana" "$GRAFANA_NS"; then
  R="pass"
else
  R="missing"
fi
check "Grafana Operator subscription present" "$R"

GRAFANA_CSV_PHASE=$(oc get csv -n "$GRAFANA_NS" --no-headers \
  --insecure-skip-tls-verify=true 2>/dev/null \
  | awk '$1 ~ /^grafana-operator/ {print $NF; exit}')
[[ "$GRAFANA_CSV_PHASE" == "Succeeded" ]] && R="pass" || R="phase=${GRAFANA_CSV_PHASE:-not found}"
check "Grafana Operator CSV Succeeded" "$R"

if resource_exists "grafana/grafana" "$GRAFANA_NS"; then
  R="pass"
else
  R="missing"
fi
check "Grafana instance present" "$R"

if resource_exists "grafanadatasource/prometheus" "$GRAFANA_NS"; then
  R="pass"
else
  R="missing"
fi
check "Grafana Prometheus datasource present" "$R"

GRAFANA_DATASOURCE_UID=$(oc get grafanadatasource prometheus -n "$GRAFANA_NS" \
  -o jsonpath='{.spec.uid}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$GRAFANA_DATASOURCE_UID" == "Prometheus" ]] && R="pass" || R="uid=${GRAFANA_DATASOURCE_UID:-missing}"
check "Grafana Prometheus datasource UID is stable" "$R"

GRAFANA_POD=$(oc get pod -n "$GRAFANA_NS" -l app=grafana \
  -o jsonpath='{.items[0].metadata.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
GRAFANA_ADMIN_USER=$(oc get secret grafana-admin-credentials -n "$GRAFANA_NS" \
  -o jsonpath='{.data.GF_SECURITY_ADMIN_USER}' --insecure-skip-tls-verify=true 2>/dev/null \
  | base64 -d 2>/dev/null || true)
GRAFANA_ADMIN_PASSWORD=$(oc get secret grafana-admin-credentials -n "$GRAFANA_NS" \
  -o jsonpath='{.data.GF_SECURITY_ADMIN_PASSWORD}' --insecure-skip-tls-verify=true 2>/dev/null \
  | base64 -d 2>/dev/null || true)
GRAFANA_DS_QUERY_RESULT=""
if [[ -n "$GRAFANA_POD" && -n "$GRAFANA_ADMIN_USER" && -n "$GRAFANA_ADMIN_PASSWORD" ]]; then
  NOW_MS=$(( $(date +%s) * 1000 ))
  FROM_MS=$(( NOW_MS - 300000 ))
  GRAFANA_DS_QUERY_RESULT=$(oc exec -i -n "$GRAFANA_NS" "$GRAFANA_POD" -c grafana \
    --insecure-skip-tls-verify=true -- \
    curl -sS -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
      -H "Content-Type: application/json" \
      -X POST http://localhost:3000/api/ds/query \
      --data-binary @- <<JSON 2>/dev/null || true
{
  "queries": [
    {
      "refId": "A",
      "datasource": {
        "type": "prometheus",
        "uid": "Prometheus"
      },
      "expr": "up",
      "instant": true,
      "range": false
    }
  ],
  "from": "${FROM_MS}",
  "to": "${NOW_MS}"
}
JSON
)
fi
if jq -e '(.results.A.status | tostring | test("^2")) and ((.results.A.error // "") == "")' \
  <<<"$GRAFANA_DS_QUERY_RESULT" >/dev/null 2>&1; then
  R="pass"
else
  GRAFANA_DS_ERROR=$(jq -r '.results.A.error // .message // "datasource query failed"' \
    <<<"$GRAFANA_DS_QUERY_RESULT" 2>/dev/null || echo "datasource query failed")
  R="$GRAFANA_DS_ERROR"
fi
check "Grafana Prometheus datasource query succeeds" "$R"

for dashboard_metric_check in \
  "Grafana vLLM KV cache metric query succeeds|max(max_over_time(vllm:kv_cache_usage_perc[1h])) * 100" \
  "Grafana DCGM framebuffer metric query succeeds|max(max_over_time((100 * DCGM_FI_DEV_FB_USED / clamp_min(DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE + DCGM_FI_DEV_FB_RESERVED, 1))[1h:]))"; do
  IFS="|" read -r metric_label metric_expr <<<"$dashboard_metric_check"
  GRAFANA_METRIC_QUERY_RESULT=""
  if [[ -n "$GRAFANA_POD" && -n "$GRAFANA_ADMIN_USER" && -n "$GRAFANA_ADMIN_PASSWORD" ]]; then
    NOW_MS=$(( $(date +%s) * 1000 ))
    FROM_MS=$(( NOW_MS - 3600000 ))
    GRAFANA_METRIC_QUERY_RESULT=$(oc exec -i -n "$GRAFANA_NS" "$GRAFANA_POD" -c grafana \
      --insecure-skip-tls-verify=true -- \
      curl -sS -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
        -H "Content-Type: application/json" \
        -X POST http://localhost:3000/api/ds/query \
        --data-binary @- <<JSON 2>/dev/null || true
{
  "queries": [
    {
      "refId": "A",
      "datasource": {
        "type": "prometheus",
        "uid": "Prometheus"
      },
      "expr": "${metric_expr}",
      "instant": true,
      "range": false
    }
  ],
  "from": "${FROM_MS}",
  "to": "${NOW_MS}"
}
JSON
)
  fi
  if jq -e '
      (.results.A.status | tostring | test("^2")) and
      ((.results.A.error // "") == "") and
      ((.results.A.frames // []) | length > 0)
    ' <<<"$GRAFANA_METRIC_QUERY_RESULT" >/dev/null 2>&1; then
    R="pass"
  else
    GRAFANA_METRIC_ERROR=$(jq -r '.results.A.error // .message // "metric query failed"' \
      <<<"$GRAFANA_METRIC_QUERY_RESULT" 2>/dev/null || echo "metric query failed")
    R="$GRAFANA_METRIC_ERROR"
  fi
  check "$metric_label" "$R"
done

if resource_exists "grafanadashboard/vllm-model-serving-baseline" "$GRAFANA_NS"; then
  R="pass"
else
  R="missing"
fi
check "Grafana vLLM baseline dashboard present" "$R"

if resource_exists "grafanadashboard/llm-performance" "$GRAFANA_NS"; then
  R="pass"
else
  R="missing"
fi
check "Grafana llm-performance workshop dashboard present" "$R"

LLM_DASHBOARD_JSON=$(oc get grafanadashboard llm-performance -n "$GRAFANA_NS" \
  -o jsonpath='{.spec.json}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ "$LLM_DASHBOARD_JSON" == *'${DS_PROMETHEUS}'* ]]; then
  R="contains unresolved datasource placeholder"
else
  R="pass"
fi
check "Grafana llm-performance dashboard uses concrete datasource UID" "$R"

if grep -Eq 'kubernetes_namespace|time_per_output_token_seconds_bucket|8000|GPU Cache Usage' \
  <<<"$LLM_DASHBOARD_JSON"; then
  R="contains stale imported vLLM query assumptions"
else
  R="pass"
fi
check "Grafana llm-performance dashboard uses live vLLM label and metric names" "$R"

for llm_dashboard_metric_check in \
  "Grafana llm-performance inter-token metric exists|count(vllm:inter_token_latency_seconds_bucket)" \
  "Grafana llm-performance prefix-cache metric exists|count(vllm:prefix_cache_queries_total)"; do
  IFS="|" read -r metric_label metric_expr <<<"$llm_dashboard_metric_check"
  GRAFANA_METRIC_QUERY_RESULT=""
  if [[ -n "$GRAFANA_POD" && -n "$GRAFANA_ADMIN_USER" && -n "$GRAFANA_ADMIN_PASSWORD" ]]; then
    NOW_MS=$(( $(date +%s) * 1000 ))
    FROM_MS=$(( NOW_MS - 3600000 ))
    GRAFANA_METRIC_QUERY_RESULT=$(oc exec -i -n "$GRAFANA_NS" "$GRAFANA_POD" -c grafana \
      --insecure-skip-tls-verify=true -- \
      curl -sS -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
        -H "Content-Type: application/json" \
        -X POST http://localhost:3000/api/ds/query \
        --data-binary @- <<JSON 2>/dev/null || true
{
  "queries": [
    {
      "refId": "A",
      "datasource": {
        "type": "prometheus",
        "uid": "Prometheus"
      },
      "expr": "${metric_expr}",
      "instant": true,
      "range": false
    }
  ],
  "from": "${FROM_MS}",
  "to": "${NOW_MS}"
}
JSON
)
  fi
  if jq -e '
      (.results.A.status | tostring | test("^2")) and
      ((.results.A.error // "") == "") and
      ((.results.A.frames // []) | length > 0)
    ' <<<"$GRAFANA_METRIC_QUERY_RESULT" >/dev/null 2>&1; then
    R="pass"
  else
    GRAFANA_METRIC_ERROR=$(jq -r '.results.A.error // .message // "metric query failed"' \
      <<<"$GRAFANA_METRIC_QUERY_RESULT" 2>/dev/null || echo "metric query failed")
    R="$GRAFANA_METRIC_ERROR"
  fi
  check "$metric_label" "$R"
done

if resource_exists "route/grafana-route" "$GRAFANA_NS"; then
  R="pass"
else
  R="missing"
fi
check "Grafana OAuth route present" "$R"

for demo_user in ai-admin ai-developer; do
  case "$demo_user" in
    ai-admin)
      demo_group="rhods-admins"
      ;;
    ai-developer)
      demo_group="rhoai-developers"
      ;;
  esac
  if oc auth can-i get services -n "$GRAFANA_NS" \
    --as "$demo_user" --as-group "$demo_group" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    R="pass"
  else
    R="missing namespace-scoped Grafana viewer RBAC"
  fi
  check "Grafana OAuth SAR passes for ${demo_user}" "$R"
done

CONSOLELINK_HREF=$(oc get consolelink rhoai-demo-grafana \
  -o jsonpath='{.spec.href}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ "$CONSOLELINK_HREF" == https://*"/d/llm-performance/"* ]]; then
  R="pass"
else
  R="href=${CONSOLELINK_HREF:-missing}"
fi
check "OpenShift ConsoleLink points to Grafana llm-performance dashboard" "$R"

PVC_PHASE=$(oc get pvc "$GUIDELLM_DATA_PVC" -n "$MODEL_NS" \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$PVC_PHASE" == "Bound" ]] && R="pass" || R="phase=${PVC_PHASE:-missing}"
check "GuideLLM benchmark-data PVC Bound" "$R"

PROMPTS_HEADER=$(oc get configmap "$GUIDELLM_PROMPTS_CONFIGMAP" -n "$MODEL_NS" \
  -o jsonpath='{.data.prompts\.csv}' --insecure-skip-tls-verify=true 2>/dev/null \
  | head -1 || true)
[[ "$PROMPTS_HEADER" == "prompt,output_tokens_count" ]] && R="pass" || R="missing prompts.csv header"
check "GuideLLM prompts ConfigMap present" "$R"

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
  check "Nemotron registered model metadata present" "$R"

  if [[ -n "$MODEL_ID" ]]; then
    MR_VERSIONS=$(curl -sk -H "Authorization: Bearer ${MR_TOKEN}" \
      "${MR_BASE_URL}/registered_models/${MODEL_ID}/versions" 2>/dev/null || echo "{}")
    MODEL_VERSION_ID=$(jq -r --arg name "$MODEL_VERSION_NAME" \
      '.items[]? | select(.name == $name and (.state // "LIVE") != "ARCHIVED") | .id' <<<"$MR_VERSIONS" | head -1)
    [[ -n "$MODEL_VERSION_ID" ]] && R="pass" || R="missing"
    check "Nemotron model version metadata present" "$R"
  else
    MODEL_VERSION_ID=""
    check "Nemotron model version metadata present" "registered model missing"
  fi

  if [[ -n "$MODEL_VERSION_ID" ]]; then
    MR_ARTIFACTS=$(curl -sk -H "Authorization: Bearer ${MR_TOKEN}" \
      "${MR_BASE_URL}/model_versions/${MODEL_VERSION_ID}/artifacts" 2>/dev/null || echo "{}")
    MODEL_ARTIFACT_ID=$(jq -r --arg uri "$MODEL_URI" \
      '.items[]? | select(.uri == $uri and (.state // "LIVE") != "DELETED") | .id' <<<"$MR_ARTIFACTS" | head -1)
    [[ -n "$MODEL_ARTIFACT_ID" ]] && R="pass" || R="missing"
    check "Nemotron OCI model artifact metadata present" "$R"
  else
    check "Nemotron OCI model artifact metadata present" "model version missing"
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

ISVC_JSON=""
LLMISVC_JSON=""

if resource_exists "inferenceservice/${MODEL_DEPLOYMENT_NAME}" "$MODEL_NS"; then
  ISVC_READY=$(oc get inferenceservice "$MODEL_DEPLOYMENT_NAME" -n "$MODEL_NS" \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$ISVC_READY" == "True" ]] && R="pass" || R="ready=${ISVC_READY:-not found}"
  check "Nemotron direct InferenceService Ready" "$R"

  ISVC_RUNTIME=$(oc get inferenceservice "$MODEL_DEPLOYMENT_NAME" -n "$MODEL_NS" \
    -o jsonpath='{.spec.predictor.model.runtime}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ -n "$ISVC_RUNTIME" ]] && R="pass" || R="missing"
  check "Nemotron direct InferenceService runtime selected" "$R"

  ISVC_URI=$(oc get inferenceservice "$MODEL_DEPLOYMENT_NAME" -n "$MODEL_NS" \
    -o jsonpath='{.spec.predictor.model.storageUri}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  [[ "$ISVC_URI" == "$MODEL_URI" ]] && R="pass" || R="uri=${ISVC_URI:-not found}"
  check "Nemotron direct InferenceService uses expected OCI model" "$R"

  ISVC_JSON=$(oc get inferenceservice "$MODEL_DEPLOYMENT_NAME" -n "$MODEL_NS" \
    -o json --insecure-skip-tls-verify=true 2>/dev/null || echo "{}")
  if jq -e \
      --arg maxModelLen "$MODEL_MAX_MODEL_LEN" \
      --arg maxBatchedTokens "$MODEL_MAX_BATCHED_TOKENS" '
      .spec.predictor.model.args == [
        "--enable-force-include-usage",
        "--disable-uvicorn-access-log",
        "--enable-prefix-caching",
        ("--max-model-len=" + $maxModelLen),
        ("--max-num-batched-tokens=" + $maxBatchedTokens),
        "--enable-auto-tool-choice",
        "--tool-call-parser=qwen3_coder",
        "--trust-remote-code",
        "--reasoning-parser-plugin=/mnt/models/nano_v3_reasoning_parser.py",
        "--reasoning-parser=nano_v3"
      ]
    ' <<<"$ISVC_JSON" >/dev/null; then
    R="pass"
  else
    R="args do not match curated Nemotron vLLM configuration"
  fi
  check "Nemotron direct InferenceService uses curated vLLM args" "$R"

  if jq -e \
      --arg cpuRequest "$MODEL_CPU_REQUEST" \
      --arg cpuLimit "$MODEL_CPU_LIMIT" \
      --arg memoryRequest "$MODEL_MEMORY_REQUEST" \
      --arg memoryLimit "$MODEL_MEMORY_LIMIT" \
      '
        .spec.predictor.model.resources.requests.cpu == $cpuRequest and
        .spec.predictor.model.resources.requests.memory == $memoryRequest and
        .spec.predictor.model.resources.requests["nvidia.com/gpu"] == "1" and
        .spec.predictor.model.resources.limits.cpu == $cpuLimit and
        .spec.predictor.model.resources.limits.memory == $memoryLimit and
        .spec.predictor.model.resources.limits["nvidia.com/gpu"] == "1"
      ' <<<"$ISVC_JSON" >/dev/null; then
    R="pass"
  else
    R="resources do not match ${MODEL_CPU_REQUEST}/${MODEL_CPU_LIMIT} CPU and ${MODEL_MEMORY_REQUEST}/${MODEL_MEMORY_LIMIT} memory"
  fi
  check "Nemotron direct InferenceService uses curated resource sizing" "$R"

  if resource_exists "servicemonitor/${MODEL_DEPLOYMENT_NAME}-metrics" "$MODEL_NS"; then
    R="pass"
  else
    R="missing"
  fi
  check "Nemotron direct ServiceMonitor present" "$R"
else
  LLMISVC_JSON=$(oc get llminferenceservice "$MAAS_NEMOTRON_MODEL_NAME" -n "$MAAS_NS" \
    -o json --insecure-skip-tls-verify=true 2>/dev/null || echo "{}")

  if jq -e '.status.conditions[]? | select(.type == "Ready" and .status == "True")' \
    <<<"$LLMISVC_JSON" >/dev/null; then
    R="pass"
  else
    R="direct InferenceService absent and MaaS LLMInferenceService is not Ready"
  fi
  check "Nemotron MaaS LLMInferenceService Ready" "$R"

  if jq -e '
      .spec.template.containers[]? |
      select(.name == "main") |
      (.image | contains("registry.redhat.io/rhaii/vllm-cuda-rhel9"))
    ' <<<"$LLMISVC_JSON" >/dev/null; then
    R="pass"
  else
    R="vLLM image not found on MaaS LLMInferenceService main container"
  fi
  check "Nemotron MaaS LLMInferenceService uses vLLM image" "$R"

  LLMISVC_URI=$(jq -r '.spec.model.uri // ""' <<<"$LLMISVC_JSON")
  [[ "$LLMISVC_URI" == "$MODEL_URI" ]] && R="pass" || R="uri=${LLMISVC_URI:-not found}"
  check "Nemotron MaaS LLMInferenceService uses expected OCI model" "$R"

  if jq -e \
      --arg maxModelLen "$MODEL_MAX_MODEL_LEN" \
      --arg maxBatchedTokens "$MODEL_MAX_BATCHED_TOKENS" '
      .spec.template.containers[]? |
      select(.name == "main") |
      .args as $args |
      all([
        "--enable-force-include-usage",
        "--disable-uvicorn-access-log",
        "--enable-prefix-caching",
        ("--max-model-len=" + $maxModelLen),
        ("--max-num-batched-tokens=" + $maxBatchedTokens),
        "--enable-auto-tool-choice",
        "--tool-call-parser=qwen3_coder",
        "--trust-remote-code",
        "--reasoning-parser-plugin=/mnt/models/nano_v3_reasoning_parser.py",
        "--reasoning-parser=nano_v3"
      ][]; $args | index(.))
    ' <<<"$LLMISVC_JSON" >/dev/null; then
    R="pass"
  else
    R="args do not include curated Nemotron vLLM configuration"
  fi
  check "Nemotron MaaS LLMInferenceService uses curated vLLM args" "$R"

  if jq -e \
      --arg cpuRequest "$MODEL_CPU_REQUEST" \
      --arg cpuLimit "$MODEL_CPU_LIMIT" \
      --arg memoryRequest "$MODEL_MEMORY_REQUEST" \
      --arg memoryLimit "$MODEL_MEMORY_LIMIT" '
        .spec.template.containers[]? |
        select(.name == "main") |
        .resources.requests.cpu == $cpuRequest and
        .resources.requests.memory == $memoryRequest and
        .resources.requests["nvidia.com/gpu"] == "1" and
        .resources.limits.cpu == $cpuLimit and
        .resources.limits.memory == $memoryLimit and
        .resources.limits["nvidia.com/gpu"] == "1"
      ' <<<"$LLMISVC_JSON" >/dev/null; then
    R="pass"
  else
    R="resources do not match ${MODEL_CPU_REQUEST}/${MODEL_CPU_LIMIT} CPU and ${MODEL_MEMORY_REQUEST}/${MODEL_MEMORY_LIMIT} memory"
  fi
  check "Nemotron MaaS LLMInferenceService uses curated resource sizing" "$R"

  if resource_exists "podmonitor/kserve-llm-isvc-vllm-engine" "$MAAS_NS" ||
    resource_exists "podmonitor/kserve-llm-isvc-vllm-engine-default" "$MAAS_NS"; then
    R="pass"
  else
    R="missing"
  fi
  check "Nemotron MaaS vLLM PodMonitor present" "$R"
fi

if [[ -n "$GRAFANA_POD" && -n "$GRAFANA_ADMIN_USER" && -n "$GRAFANA_ADMIN_PASSWORD" ]]; then
  NOW_MS=$(( $(date +%s) * 1000 ))
  FROM_MS=$(( NOW_MS - 3600000 ))
  VLLM_METRIC_QUERY_RESULT=$(oc exec -i -n "$GRAFANA_NS" "$GRAFANA_POD" -c grafana \
    --insecure-skip-tls-verify=true -- \
    curl -sS -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
      -H "Content-Type: application/json" \
      -X POST http://localhost:3000/api/ds/query \
      --data-binary @- <<JSON 2>/dev/null || true
{
  "queries": [
    {
      "refId": "A",
      "datasource": {
        "type": "prometheus",
        "uid": "Prometheus"
      },
      "expr": "count(vllm:time_to_first_token_seconds_bucket)",
      "instant": true,
      "range": false
    }
  ],
  "from": "${FROM_MS}",
  "to": "${NOW_MS}"
}
JSON
)
else
  VLLM_METRIC_QUERY_RESULT=""
fi
if jq -e '
    (.results.A.status | tostring | test("^2")) and
    ((.results.A.error // "") == "") and
    ((.results.A.frames // []) | length > 0)
  ' <<<"$VLLM_METRIC_QUERY_RESULT" >/dev/null 2>&1; then
  R="pass"
else
  R="missing vLLM metrics in Prometheus"
fi
check "Active Nemotron backend exposes vLLM metrics" "$R"

if [[ -n "$ISVC_JSON" ]] && [[ "$ISVC_JSON" != "{}" ]]; then
  TOOL_ARGS_SOURCE="$ISVC_JSON"
  TOOL_ARGS_QUERY='.spec.predictor.model.args as $args | all(["--enable-auto-tool-choice","--tool-call-parser=qwen3_coder","--reasoning-parser=nano_v3"][]; $args | index(.))'
else
  TOOL_ARGS_SOURCE="$LLMISVC_JSON"
  TOOL_ARGS_QUERY='.spec.template.containers[]? | select(.name == "main") | .args as $args | all(["--enable-auto-tool-choice","--tool-call-parser=qwen3_coder","--reasoning-parser=nano_v3"][]; $args | index(.))'
fi
if jq -e "$TOOL_ARGS_QUERY" <<<"$TOOL_ARGS_SOURCE" >/dev/null; then
  R="pass"
else
  R="tool-call parser args missing"
fi
check "Active Nemotron backend is configured for structured tool calling" "$R"

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
