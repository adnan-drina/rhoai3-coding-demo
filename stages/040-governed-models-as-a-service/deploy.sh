#!/usr/bin/env bash
# deploy.sh - Stage 040: Models-as-a-Service
# Enables MaaS prerequisites through GitOps, while generating environment-local
# secrets that must never be committed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -n "${RHOAI_OPENAI_ENV_FILE:-}" ]]; then
  if [[ ! -f "$RHOAI_OPENAI_ENV_FILE" ]]; then
    echo "ERROR: RHOAI_OPENAI_ENV_FILE points to a missing file." >&2
    exit 1
  fi
  set -a
  # shellcheck source=/dev/null
  source "$RHOAI_OPENAI_ENV_FILE"
  set +a
fi

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
  exit 1
fi

echo "✓ Cluster guard passed: $ACTUAL_SERVER"

# Fail fast if the nodes are too small for the demo stack, before any changes.
"$ROOT_DIR/scripts/require-node-sizing.sh"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

require_cmd jq
require_cmd oc
require_cmd openssl

GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}"
GIT_REPO_BRANCH="${GIT_REPO_BRANCH:-main}"
MAAS_NS="${RHOAI_MAAS_NAMESPACE:-models-as-a-service}"
MAAS_DB_NS="${RHOAI_MAAS_DATABASE_NAMESPACE:-models-as-a-service-db}"
MAAS_POSTGRES_SECRET="${RHOAI_MAAS_POSTGRES_SECRET:-maas-postgres-credentials}"
MAAS_POSTGRES_USER="${RHOAI_MAAS_POSTGRES_USER:-maas}"
MAAS_POSTGRES_DATABASE="${RHOAI_MAAS_POSTGRES_DATABASE:-maas}"
MAAS_DB_CONFIG_SECRET="${RHOAI_MAAS_DB_CONFIG_SECRET:-maas-db-config}"
PINNED_RHCL_CSV="${RHOAI_PINNED_RHCL_CSV:-rhcl-operator.v1.3.5}"
OPENAI_MODEL_ID="${RHOAI_OPENAI_MODEL_ID:-gpt-4o-mini}"
OPENAI_PROVIDER_SECRET="${RHOAI_OPENAI_PROVIDER_SECRET:-openai-provider-api-key}"
OPENAI_API_KEY_VALUE="${RHOAI_OPENAI_API_KEY:-${OPENAI_API_KEY:-}}"
REDHAT_MODELS_API_KEY_VALUE="${RHOAI_REDHAT_MODELS_API_KEY:-${REDHAT_MODELS_API_KEY:-}}"
REDHAT_MODELS_BASE_URL="${RHOAI_REDHAT_MODELS_BASE_URL:-${REDHAT_MODELS_BASE_URL:-}}"
DEMO_PROJECT_NS="${RHOAI_DEMO_PROJECT_NAMESPACE:-demo-sandbox}"
DIRECT_NEMOTRON_NAME="${RHOAI_NEMOTRON_DEPLOYMENT_NAME:-nvidia-nemotron-3-nano-30b-a3b}"
MAAS_NEMOTRON_NAME="${RHOAI_MAAS_NEMOTRON_MODEL_NAME:-nemotron-3-nano-30b-a3b}"
CLEANUP_DEMO_NEMOTRON="${RHOAI_STAGE220_CLEANUP_DEMO_SANDBOX_NEMOTRON:-true}"

TMP_FILES=()
cleanup() {
  if ((${#TMP_FILES[@]} > 0)); then
    rm -f "${TMP_FILES[@]}"
  fi
}
trap cleanup EXIT

wait_for_jsonpath() {
  local label="$1"
  local resource="$2"
  local namespace="$3"
  local jsonpath="$4"
  local expected="$5"
  local attempts="${6:-60}"
  local value=""

  echo "── Waiting for ${label} ──"
  for _ in $(seq 1 "$attempts"); do
    if [[ -n "$namespace" ]]; then
      value=$(oc get "$resource" -n "$namespace" \
        -o jsonpath="$jsonpath" --insecure-skip-tls-verify=true 2>/dev/null || true)
    else
      value=$(oc get "$resource" \
        -o jsonpath="$jsonpath" --insecure-skip-tls-verify=true 2>/dev/null || true)
    fi
    if [[ "$value" == "$expected" ]]; then
      echo "✓ ${label}: ${value}"
      return 0
    fi
    sleep 10
  done

  echo "ERROR: ${label} did not reach ${expected} (last value: ${value:-missing})." >&2
  return 1
}

wait_for_delete() {
  local label="$1"
  local resource="$2"
  local namespace="$3"
  local attempts="${4:-90}"

  echo "── Waiting for ${label} to be removed ──"
  for _ in $(seq 1 "$attempts"); do
    if ! oc get "$resource" -n "$namespace" \
      --insecure-skip-tls-verify=true >/dev/null 2>&1; then
      echo "✓ ${label} removed"
      return 0
    fi
    sleep 10
  done

  echo "ERROR: ${label} still exists in ${namespace}." >&2
  return 1
}

patch_stage_220_application() {
  local domain hostname patch_body patch_json

  domain="$(oc get ingresscontroller default -n openshift-ingress-operator \
    -o jsonpath='{.status.domain}' --insecure-skip-tls-verify=true)"
  hostname="maas.${domain}"

  patch_body=$(jq -rn \
    --arg hostname "$hostname" \
    '[
      {"op":"replace","path":"/spec/listeners/0/hostname","value":$hostname},
      {"op":"replace","path":"/spec/listeners/1/hostname","value":$hostname},
      {"op":"replace","path":"/spec/listeners/1/tls/certificateRefs/0/name","value":"maas-gateway-tls"}
    ] | map("- op: \(.op)\n  path: \(.path)\n  value: \(.value)") | join("\n")')

  patch_json=$(jq -n --arg patch_body "$patch_body" '{
    spec: {
      source: {
        kustomize: {
          patches: [
            {
              target: {
                group: "gateway.networking.k8s.io",
                version: "v1",
                kind: "Gateway",
                name: "maas-default-gateway",
                namespace: "openshift-ingress"
              },
              patch: $patch_body
            }
          ]
        }
      }
    }
  }')

  oc patch applications.argoproj.io 040-governed-models-as-a-service -n openshift-gitops \
    --type=merge -p "$patch_json" --insecure-skip-tls-verify=true >/dev/null

  echo "✓ Stage 040 Application uses MaaS Gateway hostname=${hostname}, tlsCertificate=maas-gateway-tls"
}

apply_argocd_application() {
  local app_name="$1"
  local manifest_path="$2"
  local app_manifest
  app_manifest=$(mktemp)
  TMP_FILES+=("$app_manifest")

  sed \
    -e "s|repoURL: .*|repoURL: ${GIT_REPO_URL}|" \
    -e "s|targetRevision: .*|targetRevision: ${GIT_REPO_BRANCH}|" \
    "$manifest_path" > "$app_manifest"

  oc apply -f "$app_manifest" --insecure-skip-tls-verify=true

  if [[ "$app_name" == "040-governed-models-as-a-service" ]]; then
    patch_stage_220_application
    oc patch applications.argoproj.io "$app_name" -n openshift-gitops --type=merge \
      -p '{"operation":null}' \
      --insecure-skip-tls-verify=true >/dev/null 2>&1 || true
  fi

  oc annotate applications.argoproj.io "$app_name" -n openshift-gitops \
    argocd.argoproj.io/refresh=hard --overwrite \
    --insecure-skip-tls-verify=true >/dev/null
}

urlencode() {
  jq -rn --arg v "$1" '$v|@uri'
}

ensure_namespace_exists() {
  local namespace="$1"

  if oc get namespace "$namespace" --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    return 0
  fi

  oc create namespace "$namespace" --insecure-skip-tls-verify=true >/dev/null
}

ensure_maas_secrets() {
  echo "── Ensuring environment-local MaaS database secrets ──"

  ensure_namespace_exists "$MAAS_DB_NS"

  local password
  password="$(oc get secret "$MAAS_POSTGRES_SECRET" -n "$MAAS_DB_NS" \
    -o jsonpath='{.data.POSTGRESQL_PASSWORD}' --insecure-skip-tls-verify=true 2>/dev/null \
    | base64 --decode 2>/dev/null || true)"

  if [[ -z "$password" ]]; then
    password="${RHOAI_MAAS_POSTGRES_PASSWORD:-$(openssl rand -base64 36 | tr -dc 'A-Za-z0-9' | head -c 32)}"
  fi

  oc create secret generic "$MAAS_POSTGRES_SECRET" \
    -n "$MAAS_DB_NS" \
    --from-literal=POSTGRESQL_USER="$MAAS_POSTGRES_USER" \
    --from-literal=POSTGRESQL_PASSWORD="$password" \
    --from-literal=POSTGRESQL_DATABASE="$MAAS_POSTGRES_DATABASE" \
    --dry-run=client -o yaml | oc apply -f - --insecure-skip-tls-verify=true >/dev/null

  local encoded_password connection_url
  encoded_password="$(urlencode "$password")"
  connection_url="postgresql://${MAAS_POSTGRES_USER}:${encoded_password}@maas-postgres.${MAAS_DB_NS}.svc.cluster.local:5432/${MAAS_POSTGRES_DATABASE}?sslmode=disable"

  oc create secret generic "$MAAS_DB_CONFIG_SECRET" \
    -n redhat-ods-applications \
    --from-literal=DB_CONNECTION_URL="$connection_url" \
    --dry-run=client -o yaml | oc apply -f - --insecure-skip-tls-verify=true >/dev/null

  echo "✓ MaaS database credentials and maas-db-config are present"
}

ensure_openai_provider_secret() {
  echo "── Ensuring environment-local OpenAI provider Secret ──"

  ensure_namespace_exists "$MAAS_NS"

  if [[ -n "$OPENAI_API_KEY_VALUE" ]]; then
    oc create secret generic "$OPENAI_PROVIDER_SECRET" \
      -n "$MAAS_NS" \
      --from-literal=api-key="$OPENAI_API_KEY_VALUE" \
      --dry-run=client -o yaml | oc apply -f - --insecure-skip-tls-verify=true >/dev/null

    oc label secret "$OPENAI_PROVIDER_SECRET" -n "$MAAS_NS" --overwrite \
      app.kubernetes.io/name="$OPENAI_PROVIDER_SECRET" \
      app.kubernetes.io/component=external-model-provider \
      app.kubernetes.io/part-of=rhoai3-coding-demo \
      demo.rhoai.io/stage=040 \
      demo.rhoai.io/provider=openai \
      inference.networking.k8s.io/bbr-managed=true \
      --insecure-skip-tls-verify=true >/dev/null

    echo "✓ OpenAI provider Secret is present for ${OPENAI_MODEL_ID}"
    return 0
  fi

  if oc get secret "$OPENAI_PROVIDER_SECRET" -n "$MAAS_NS" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    oc label secret "$OPENAI_PROVIDER_SECRET" -n "$MAAS_NS" --overwrite \
      app.kubernetes.io/name="$OPENAI_PROVIDER_SECRET" \
      app.kubernetes.io/component=external-model-provider \
      app.kubernetes.io/part-of=rhoai3-coding-demo \
      demo.rhoai.io/stage=040 \
      demo.rhoai.io/provider=openai \
      inference.networking.k8s.io/bbr-managed=true \
      --insecure-skip-tls-verify=true >/dev/null
    echo "✓ Existing OpenAI provider Secret found for ${OPENAI_MODEL_ID}"
    return 0
  fi

  echo "ERROR: Missing OpenAI provider Secret ${OPENAI_PROVIDER_SECRET} in ${MAAS_NS}." >&2
  echo "Set OPENAI_API_KEY or RHOAI_OPENAI_API_KEY locally before deploying Stage 040 model publication." >&2
  exit 1
}

ensure_redhat_models_provider_secret() {
  echo "── Ensuring environment-local Red Hat internal models provider Secret ──"

  ensure_namespace_exists "$MAAS_NS"

  if [[ -n "$REDHAT_MODELS_BASE_URL" ]]; then
    local rh_host
    rh_host=$(printf '%s' "$REDHAT_MODELS_BASE_URL" | sed -E 's|^https?://||; s|/.*||; s|:.*||')
    if [[ "$rh_host" != "maas-rhdp.apps.maas.redhatworkshops.io" ]]; then
      echo "WARNING: REDHAT_MODELS_BASE_URL host differs from expected maas-rhdp.apps.maas.redhatworkshops.io — verify endpoint." >&2
    fi
  fi

  if [[ -n "$REDHAT_MODELS_API_KEY_VALUE" ]]; then
    oc create secret generic redhat-models-provider-api-key \
      -n "$MAAS_NS" \
      --from-literal=api-key="$REDHAT_MODELS_API_KEY_VALUE" \
      --dry-run=client -o yaml | oc apply -f - --insecure-skip-tls-verify=true >/dev/null

    oc label secret redhat-models-provider-api-key -n "$MAAS_NS" --overwrite \
      app.kubernetes.io/name=redhat-models-provider-api-key \
      app.kubernetes.io/component=external-model-provider \
      app.kubernetes.io/part-of=rhoai3-coding-demo \
      demo.rhoai.io/stage=040 \
      demo.rhoai.io/provider=redhat-internal \
      inference.networking.k8s.io/bbr-managed=true \
      --insecure-skip-tls-verify=true >/dev/null

    echo "✓ Red Hat internal models provider Secret is present"
    return 0
  fi

  if oc get secret redhat-models-provider-api-key -n "$MAAS_NS" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    oc label secret redhat-models-provider-api-key -n "$MAAS_NS" --overwrite \
      app.kubernetes.io/name=redhat-models-provider-api-key \
      app.kubernetes.io/component=external-model-provider \
      app.kubernetes.io/part-of=rhoai3-coding-demo \
      demo.rhoai.io/stage=040 \
      demo.rhoai.io/provider=redhat-internal \
      inference.networking.k8s.io/bbr-managed=true \
      --insecure-skip-tls-verify=true >/dev/null
    echo "✓ Existing Red Hat internal models provider Secret found"
    return 0
  fi

  echo "WARNING: REDHAT_MODELS_API_KEY not set — Red Hat internal models (qwen3-235b, minimax-m2) will register but inference calls will fail." >&2
  echo "Set REDHAT_MODELS_API_KEY in .env to enable them." >&2
  return 0
}

cleanup_demo_sandbox_nemotron() {
  local deleted="false"

  if [[ "$CLEANUP_DEMO_NEMOTRON" != "true" ]]; then
    echo "── Skipping demo-sandbox Nemotron cleanup by configuration ──"
    return 0
  fi

  echo "── Checking for stale direct Nemotron deployments in ${DEMO_PROJECT_NS} ──"

  if oc get inferenceservice "$DIRECT_NEMOTRON_NAME" -n "$DEMO_PROJECT_NS" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    echo "Deleting direct InferenceService ${DIRECT_NEMOTRON_NAME} from ${DEMO_PROJECT_NS}; Stage 040 will recreate Nemotron through MaaS in ${MAAS_NS}."
    oc delete inferenceservice "$DIRECT_NEMOTRON_NAME" -n "$DEMO_PROJECT_NS" \
      --wait=false --ignore-not-found=true --insecure-skip-tls-verify=true >/dev/null
    wait_for_delete "InferenceService/${DIRECT_NEMOTRON_NAME}" \
      "inferenceservice/${DIRECT_NEMOTRON_NAME}" "$DEMO_PROJECT_NS"
    deleted="true"
  fi

  for stale_llmis_name in "$MAAS_NEMOTRON_NAME" "$DIRECT_NEMOTRON_NAME"; do
    if oc get llminferenceservice "$stale_llmis_name" -n "$DEMO_PROJECT_NS" \
      --insecure-skip-tls-verify=true >/dev/null 2>&1; then
      echo "Deleting stale LLMInferenceService ${stale_llmis_name} from ${DEMO_PROJECT_NS}; MaaS-owned Nemotron belongs in ${MAAS_NS}."
      oc delete llminferenceservice "$stale_llmis_name" -n "$DEMO_PROJECT_NS" \
        --wait=false --ignore-not-found=true --insecure-skip-tls-verify=true >/dev/null
      wait_for_delete "LLMInferenceService/${stale_llmis_name}" \
        "llminferenceservice/${stale_llmis_name}" "$DEMO_PROJECT_NS"
      deleted="true"
    fi
  done

  if [[ "$deleted" == "false" ]]; then
    echo "✓ No stale direct Nemotron deployment found in ${DEMO_PROJECT_NS}"
  fi
}

label_servicemonitor_out_of_user_workload_monitoring() {
  local namespace="$1"
  local name="$2"

  if ! oc get servicemonitor "$name" -n "$namespace" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    return 0
  fi

  oc label servicemonitor "$name" -n "$namespace" \
    openshift.io/user-monitoring=false --overwrite \
    --insecure-skip-tls-verify=true >/dev/null
}

ensure_istio_podmonitor_targets_metrics_port() {
  local namespace="openshift-ingress"
  local name="istio-pod-monitor"
  local port relabel_exists

  if ! oc get podmonitor "$name" -n "$namespace" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    return 0
  fi

  port=$(oc get podmonitor "$name" -n "$namespace" \
    -o jsonpath='{.spec.podMetricsEndpoints[0].port}' \
    --insecure-skip-tls-verify=true 2>/dev/null || true)

  if [[ "$port" != "metrics" ]]; then
    if [[ -n "$port" ]]; then
      oc patch podmonitor "$name" -n "$namespace" --type=json \
        -p='[{"op":"replace","path":"/spec/podMetricsEndpoints/0/port","value":"metrics"}]' \
        --insecure-skip-tls-verify=true >/dev/null
    else
      oc patch podmonitor "$name" -n "$namespace" --type=json \
        -p='[{"op":"add","path":"/spec/podMetricsEndpoints/0/port","value":"metrics"}]' \
        --insecure-skip-tls-verify=true >/dev/null
    fi
  fi

  relabel_exists=$(oc get podmonitor "$name" -n "$namespace" -o json \
    --insecure-skip-tls-verify=true \
    | jq -r '
      any(.spec.podMetricsEndpoints[0].relabelings[]?;
        .action == "keep"
        and .regex == "metrics"
        and (.sourceLabels // []) == ["__meta_kubernetes_pod_container_port_name"]
      )
    ')

  if [[ "$relabel_exists" != "true" ]]; then
    oc patch podmonitor "$name" -n "$namespace" --type=json \
      -p='[{"op":"add","path":"/spec/podMetricsEndpoints/0/relabelings/0","value":{"action":"keep","regex":"metrics","sourceLabels":["__meta_kubernetes_pod_container_port_name"]}}]' \
      --insecure-skip-tls-verify=true >/dev/null
  fi
}

ensure_known_monitoring_noise_is_excluded() {
  echo "── Excluding known invalid generated monitoring targets ──"

  label_servicemonitor_out_of_user_workload_monitoring \
    openshift-kueue-operator kueue-metrics
  label_servicemonitor_out_of_user_workload_monitoring \
    openshift-nfd nfd-controller-manager-metrics-monitor
  label_servicemonitor_out_of_user_workload_monitoring \
    redhat-ods-applications odh-model-controller-metrics-monitor
  label_servicemonitor_out_of_user_workload_monitoring \
    openshift-lws-operator lws-controller-manager-metrics-monitor

  ensure_istio_podmonitor_targets_metrics_port

  echo "✓ Known generated monitoring targets are aligned"
}

if ! oc get crd certificates.cert-manager.io --insecure-skip-tls-verify=true >/dev/null 2>&1; then
  echo "ERROR: cert-manager CRDs are missing. Install cert-manager Operator for Red Hat OpenShift before Stage 040." >&2
  exit 1
fi

if ! oc get certmanager cluster --insecure-skip-tls-verify=true >/dev/null 2>&1; then
  echo "ERROR: cert-manager cluster resource is missing. Configure the cert-manager operand before Stage 040." >&2
  exit 1
fi

ensure_maas_secrets
ensure_optional_mcp_secrets() {
  echo "── Ensuring optional MCP credential Secrets (rhoai-mcp) ──"

  ensure_namespace_exists "rhoai-mcp"

  if [[ -n "${SLACK_BOT_TOKEN:-}" ]]; then
    oc create secret generic slack-mcp-credentials \
      -n rhoai-mcp \
      --from-literal=SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN}" \
      --dry-run=client -o yaml | oc apply -f - >/dev/null
    echo "✓ slack-mcp-credentials provisioned"
  else
    echo "· SLACK_BOT_TOKEN not set — Slack MCP stays credential-gated"
  fi

  if [[ -n "${BRIGHTDATA_API_TOKEN:-}" ]]; then
    oc create secret generic brightdata-mcp-credentials \
      -n rhoai-mcp \
      --from-literal=API_TOKEN="${BRIGHTDATA_API_TOKEN}" \
      --dry-run=client -o yaml | oc apply -f - >/dev/null
    echo "✓ brightdata-mcp-credentials provisioned"
  else
    echo "· BRIGHTDATA_API_TOKEN not set — BrightData MCP stays credential-gated"
  fi
}

ensure_openai_provider_secret
ensure_redhat_models_provider_secret
ensure_optional_mcp_secrets
"$SCRIPT_DIR/register-model-cards.sh"
cleanup_demo_sandbox_nemotron

echo "── Applying shared Stage 010 Argo CD Application ──"
apply_argocd_application \
  "010-openshift-ai-platform-foundation" \
  "$ROOT_DIR/gitops/argocd/app-of-apps/010-openshift-ai-platform-foundation.yaml"

echo "── Applying Stage 040 Argo CD Application ──"
apply_argocd_application \
  "040-governed-models-as-a-service" \
  "$ROOT_DIR/gitops/argocd/app-of-apps/040-governed-models-as-a-service.yaml"

wait_for_jsonpath "Stage 010 shared owner Application sync" \
  "applications.argoproj.io/010-openshift-ai-platform-foundation" "openshift-gitops" \
  "{.status.sync.status}" "Synced" 90

wait_for_jsonpath "Stage 040 Application sync" \
  "applications.argoproj.io/040-governed-models-as-a-service" "openshift-gitops" \
  "{.status.sync.status}" "Synced" 90

wait_for_jsonpath "DataScienceCluster readiness" \
  "datasciencecluster/default-dsc" "" "{.status.phase}" "Ready" 90

wait_for_jsonpath "Red Hat Connectivity Link pinned CSV" \
  "csv/${PINNED_RHCL_CSV}" "openshift-operators" \
  "{.status.phase}" "Succeeded" 90

wait_for_jsonpath "DataScienceCluster MaaS management" \
  "datasciencecluster/default-dsc" "" \
  "{.spec.components.kserve.modelsAsService.managementState}" "Managed" 60

wait_for_jsonpath "DataScienceCluster Llama Stack Operator management" \
  "datasciencecluster/default-dsc" "" \
  "{.spec.components.llamastackoperator.managementState}" "Managed" 60

wait_for_jsonpath "MaaS PostgreSQL StatefulSet availability" \
  "statefulset/maas-postgres" "$MAAS_DB_NS" \
  "{.status.readyReplicas}" "1" 90

wait_for_jsonpath "MaaS Nemotron LLMInferenceService readiness" \
  "llminferenceservice/${MAAS_NEMOTRON_NAME}" "$MAAS_NS" \
  "{.status.conditions[?(@.type==\"Ready\")].status}" "True" \
  "${RHOAI_STAGE220_NEMOTRON_READY_ATTEMPTS:-180}"

if oc get deployment/maas-api -n redhat-ods-applications \
  --insecure-skip-tls-verify=true >/dev/null 2>&1; then
  echo "── Restarting maas-api to pick up maas-db-config ──"
  oc rollout restart deployment/maas-api -n redhat-ods-applications \
    --insecure-skip-tls-verify=true >/dev/null
  oc rollout status deployment/maas-api -n redhat-ods-applications \
    --timeout=180s --insecure-skip-tls-verify=true
fi

ensure_known_monitoring_noise_is_excluded

echo "✓ Stage 040 rollout requested"
echo "  Run ./040-governed-models-as-a-service/validate.sh to check MaaS prerequisites, local Nemotron publication, external model publication, and access policy."
