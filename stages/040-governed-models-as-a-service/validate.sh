#!/usr/bin/env bash
# validate.sh - Stage 220: Models-as-a-Service
# Checks the MaaS prerequisite boundary before model publication/subscription CRs
# are authored.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
WARN=0
FAIL=0

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

MAAS_NS="${RHOAI_MAAS_NAMESPACE:-models-as-a-service}"
MAAS_DB_NS="${RHOAI_MAAS_DATABASE_NAMESPACE:-models-as-a-service-db}"
MAAS_DB_CONFIG_SECRET="${RHOAI_MAAS_DB_CONFIG_SECRET:-maas-db-config}"
PINNED_RHCL_CSV="${RHOAI_PINNED_RHCL_CSV:-rhcl-operator.v1.3.4}"
PINNED_AUTHORINO_CSV="${RHOAI_PINNED_AUTHORINO_CSV:-authorino-operator.v1.3.1}"
PINNED_DNS_CSV="${RHOAI_PINNED_DNS_CSV:-dns-operator.v1.3.1}"
PINNED_LIMITADOR_CSV="${RHOAI_PINNED_LIMITADOR_CSV:-limitador-operator.v1.3.1}"
OPENAI_MODEL_ID="${RHOAI_OPENAI_MODEL_ID:-gpt-4o-mini}"
OPENAI_MODEL_RESOURCE="${RHOAI_OPENAI_MODEL_RESOURCE:-gpt-4o-mini}"
OPENAI_PROVIDER_SECRET="${RHOAI_OPENAI_PROVIDER_SECRET:-openai-provider-api-key}"
OPENAI_ACCESS_RESOURCE="${RHOAI_OPENAI_ACCESS_RESOURCE:-rhoai-developers-gpt-4o-mini}"
NEMOTRON_MODEL_RESOURCE="${RHOAI_MAAS_NEMOTRON_MODEL_NAME:-nemotron-3-nano-30b-a3b}"
DIRECT_NEMOTRON_NAME="${RHOAI_NEMOTRON_DEPLOYMENT_NAME:-nvidia-nemotron-3-nano-30b-a3b}"
PROJECT_NS="${RHOAI_DEMO_PROJECT_NAMESPACE:-demo-sandbox}"
PLAYGROUND_LSD_NAME="${RHOAI_PLAYGROUND_LSD_NAME:-lsd-genai-playground}"
PLAYGROUND_CONFIGMAP="${RHOAI_PLAYGROUND_CONFIGMAP:-llama-stack-config}"
PLAYGROUND_SECRET="${RHOAI_PLAYGROUND_MAAS_API_KEY_SECRET:-genai-playground-maas-api-key}"
MCP_NS="${RHOAI_MCP_NAMESPACE:-rhoai-mcp}"
MCP_SERVER_NAME="${RHOAI_OPENSHIFT_MCP_NAME:-openshift-mcp}"
MCP_CONFIGMAP="${RHOAI_OPENSHIFT_MCP_CONFIGMAP:-openshift-mcp-config}"
MCP_DISCOVERY_CONFIGMAP="${RHOAI_MCP_DISCOVERY_CONFIGMAP:-gen-ai-aa-mcp-servers}"
MCP_DISCOVERY_KEY="${RHOAI_OPENSHIFT_MCP_DISCOVERY_KEY:-OpenShift-MCP}"
MCP_IMAGE="${RHOAI_OPENSHIFT_MCP_IMAGE:-quay.io/redhat-user-workloads/crt-nshift-lightspeed-tenant/openshift-mcp-server:latest}"
PLAYGROUND_VLLM_MAX_TOKENS="${RHOAI_PLAYGROUND_VLLM_MAX_TOKENS:-512}"
# Keep the dashboard-generated provider id stable while changing the provider
# implementation to remote::openai. The generated provider number can change
# when the dashboard recreates a playground, so validation discovers model ids
# from Llama Stack /v1/models instead of assuming provider order.
PLAYGROUND_GPT_PROVIDER="${RHOAI_PLAYGROUND_GPT_PROVIDER_ID:-maas-vllm-inference-1}"
PLAYGROUND_NEMOTRON_PROVIDER="${RHOAI_PLAYGROUND_NEMOTRON_PROVIDER_ID:-maas-vllm-inference-2}"

TMP_FILES=()
cleanup() {
  if ((${#TMP_FILES[@]} > 0)); then
    rm -f "${TMP_FILES[@]}"
  fi
}
trap cleanup EXIT

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
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

warn() {
  local label="$1"
  local result="$2"
  echo "! $label  ($result)"
  (( WARN++ )) || true
}

resource_exists() {
  local resource="$1"
  local namespace="$2"
  local attempt

  for attempt in 1 2 3; do
    if [[ -n "$namespace" ]]; then
      oc get "$resource" -n "$namespace" --insecure-skip-tls-verify=true >/dev/null 2>&1 && return 0
    else
      oc get "$resource" --insecure-skip-tls-verify=true >/dev/null 2>&1 && return 0
    fi
    sleep 2
  done

  return 1
}

crd_exists() {
  local crd="$1"
  local attempt

  for attempt in 1 2 3; do
    oc get crd "$crd" --insecure-skip-tls-verify=true >/dev/null 2>&1 && return 0
    sleep 2
  done

  return 1
}

jsonpath() {
  local resource="$1"
  local namespace="$2"
  local path="$3"
  if [[ -n "$namespace" ]]; then
    oc get "$resource" -n "$namespace" -o jsonpath="$path" \
      --insecure-skip-tls-verify=true 2>/dev/null || true
  else
    oc get "$resource" -o jsonpath="$path" \
      --insecure-skip-tls-verify=true 2>/dev/null || true
  fi
}

jsonpath_nonempty() {
  local resource="$1"
  local namespace="$2"
  local path="$3"
  local attempt value

  for attempt in 1 2 3; do
    value=$(jsonpath "$resource" "$namespace" "$path")
    if [[ -n "$value" ]]; then
      printf '%s' "$value"
      return 0
    fi
    sleep 2
  done

  printf '%s' "$value"
}

get_gateway_host() {
  local host endpoint

  host=$(jsonpath_nonempty "gateway/maas-default-gateway" "openshift-ingress" "{.spec.listeners[?(@.name==\"https\")].hostname}")
  if [[ -z "$host" ]]; then
    host=$(jsonpath_nonempty "gateway/maas-default-gateway" "openshift-ingress" "{.spec.listeners[0].hostname}")
  fi

  if [[ -z "$host" ]]; then
    endpoint=$(jsonpath_nonempty "maasmodelrefs.maas.opendatahub.io/${NEMOTRON_MODEL_RESOURCE}" "$MAAS_NS" "{.status.endpoint}")
    if [[ -n "$endpoint" ]]; then
      host=$(ENDPOINT="$endpoint" python3 - <<'PY'
import os
from urllib.parse import urlparse

print(urlparse(os.environ["ENDPOINT"]).netloc)
PY
)
    fi
  fi

  printf '%s' "$host"
}

contains_word() {
  local list="$1"
  local item="$2"
  [[ " ${list} " == *" ${item} "* ]]
}

body_contains_model() {
  local body_file="$1"
  local model

  for model in "$OPENAI_MODEL_RESOURCE" "$OPENAI_MODEL_ID" "$NEMOTRON_MODEL_RESOURCE"; do
    if grep -Fq "$model" "$body_file"; then
      return 0
    fi
  done

  return 1
}

can_i_as() {
  local user="$1"
  local verb="$2"
  local resource="$3"
  local namespace="$4"
  local group="${5:-}"
  local group_args=()
  if [[ -n "$group" ]]; then
    group_args+=(--as-group="$group")
  fi
  oc auth can-i "$verb" "$resource" -n "$namespace" --as="$user" "${group_args[@]}" \
    --insecure-skip-tls-verify=true 2>/dev/null || true
}

get_demo_user_token() {
  local user="$1"
  local password="$2"
  local kubeconfig token

  [[ -n "$password" ]] || return 1

  kubeconfig=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-validate.XXXXXX")
  TMP_FILES+=("$kubeconfig")

  if ! oc login "$ACTUAL_SERVER" -u "$user" -p "$password" \
    --kubeconfig "$kubeconfig" \
    --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    return 1
  fi

  token=$(oc --kubeconfig "$kubeconfig" whoami -t \
    --insecure-skip-tls-verify=true 2>/dev/null || true)
  [[ -n "$token" ]] || return 1
  printf '%s' "$token"
}

http_get() {
  local url="$1"
  local token="$2"
  local body_file="$3"

  URL="$url" TOKEN="$token" BODY_FILE="$body_file" python3 - <<'PY'
import os
import ssl
import sys
import urllib.error
import urllib.request

url = os.environ["URL"]
token = os.environ["TOKEN"]
body_file = os.environ["BODY_FILE"]

ctx = ssl._create_unverified_context()
req = urllib.request.Request(
    url,
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    },
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        status = resp.getcode()
        body = resp.read()
except urllib.error.HTTPError as exc:
    status = exc.code
    body = exc.read()
except Exception as exc:
    status = "000"
    body = str(exc).encode()

with open(body_file, "wb") as handle:
    handle.write(body)

print(status)
PY
}

validate_playground_if_present() {
  local data_key data_token data_subscription result token_index
  local lsd_secret lsd_key lsd_value deploy_secret deploy_key deploy_value
  local config_file output models_output
  local lsd_token_result deploy_token_result

  if ! resource_exists "llamastackdistribution/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS"; then
    check "Gen AI Playground LlamaStackDistribution is not present yet" "pass"
    return
  fi

  if resource_exists "secret/${PLAYGROUND_SECRET}" "$PROJECT_NS"; then
    data_token=$(jsonpath "secret/${PLAYGROUND_SECRET}" "$PROJECT_NS" "{.data.VLLM_API_TOKEN}")
    data_key=$(jsonpath "secret/${PLAYGROUND_SECRET}" "$PROJECT_NS" "{.data.MAAS_API_KEY_ID}")
    data_subscription=$(jsonpath "secret/${PLAYGROUND_SECRET}" "$PROJECT_NS" "{.data.MAAS_SUBSCRIPTION}")
    if [[ -n "$data_token" && -n "$data_key" && -n "$data_subscription" ]]; then
      result="pass"
    else
      result="missing VLLM_API_TOKEN, MAAS_API_KEY_ID, or MAAS_SUBSCRIPTION data"
    fi
  else
    result="pass"
  fi
  check "Gen AI Playground optional helper MaaS API key Secret state" "$result"

  lsd_token_result="pass"
  for token_index in 1 2; do
    lsd_secret=$(jsonpath "llamastackdistribution/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS" "{.spec.server.containerSpec.env[?(@.name==\"VLLM_API_TOKEN_${token_index}\")].valueFrom.secretKeyRef.name}")
    lsd_key=$(jsonpath "llamastackdistribution/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS" "{.spec.server.containerSpec.env[?(@.name==\"VLLM_API_TOKEN_${token_index}\")].valueFrom.secretKeyRef.key}")
    lsd_value=$(jsonpath "llamastackdistribution/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS" "{.spec.server.containerSpec.env[?(@.name==\"VLLM_API_TOKEN_${token_index}\")].value}")
    if [[ -n "$lsd_secret" && -n "$lsd_key" ]]; then
      continue
    elif [[ -n "$lsd_value" && "$lsd_value" != "fake" ]]; then
      continue
    else
      lsd_token_result="VLLM_API_TOKEN_${token_index} is missing or still fake"
    fi
  done
  check "Gen AI Playground LlamaStackDistribution has usable MaaS token env" "$lsd_token_result"

  if resource_exists "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS"; then
    deploy_token_result="pass"
    for token_index in 1 2; do
      deploy_secret=$(jsonpath "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS" "{.spec.template.spec.containers[0].env[?(@.name==\"VLLM_API_TOKEN_${token_index}\")].valueFrom.secretKeyRef.name}")
      deploy_key=$(jsonpath "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS" "{.spec.template.spec.containers[0].env[?(@.name==\"VLLM_API_TOKEN_${token_index}\")].valueFrom.secretKeyRef.key}")
      deploy_value=$(jsonpath "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS" "{.spec.template.spec.containers[0].env[?(@.name==\"VLLM_API_TOKEN_${token_index}\")].value}")
      if [[ -n "$deploy_secret" && -n "$deploy_key" ]]; then
        continue
      elif [[ -n "$deploy_value" && "$deploy_value" != "fake" ]]; then
        continue
      else
        deploy_token_result="deployment VLLM_API_TOKEN_${token_index} is missing or still fake"
      fi
    done
  else
    deploy_token_result="deployment missing"
  fi
  check "Gen AI Playground deployment has usable MaaS token env" "$deploy_token_result"

  if resource_exists "configmap/${PLAYGROUND_CONFIGMAP}" "$PROJECT_NS"; then
    config_file=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-playground-config.XXXXXX")
    TMP_FILES+=("$config_file")
    oc get configmap "$PLAYGROUND_CONFIGMAP" -n "$PROJECT_NS" \
      -o jsonpath='{.data.config\.yaml}' \
      --insecure-skip-tls-verify=true > "$config_file"
    if grep -q "base_url: https://${GATEWAY_HOST}/models-as-a-service/${OPENAI_MODEL_RESOURCE}/v1" "$config_file" &&
      grep -q "model_id: ${OPENAI_MODEL_ID}" "$config_file" &&
      grep -q "base_url: https://${GATEWAY_HOST}/models-as-a-service/${NEMOTRON_MODEL_RESOURCE}/v1" "$config_file" &&
      grep -q "provider_model_id: ${NEMOTRON_MODEL_RESOURCE}" "$config_file"; then
      result="pass"
    else
      result="missing MaaS base URL or model mapping"
    fi
  else
    result="missing"
  fi
  check "Gen AI Playground Llama Stack config maps MaaS models correctly" "$result"

  if resource_exists "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS"; then
    models_output=$(oc exec "deployment/${PLAYGROUND_LSD_NAME}" -n "$PROJECT_NS" -- python3 -c "
import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:8321/v1/models', timeout=60) as resp:
    data = json.loads(resp.read())
items = data.get('data', [])
targets = {'${NEMOTRON_MODEL_RESOURCE}', '${OPENAI_MODEL_ID}'}
seen = set()
for item in items:
    model_id = item.get('identifier') or item.get('id') or ''
    metadata = item.get('custom_metadata') or {}
    for target in targets:
        if metadata.get('provider_resource_id') == target or model_id == target or model_id.endswith('/' + target):
            seen.add(target)
missing = sorted(targets - seen)
print('OK models' if not missing else 'MISSING ' + ','.join(missing))
" 2>&1 || true)
    if grep -q "OK models" <<<"$models_output"; then
      result="pass"
    else
      result="models=${models_output//$'\n'/ }"
    fi
  else
    result="deployment missing"
  fi
  check "Gen AI Playground Llama Stack model discovery lists MaaS models" "$result"

  if resource_exists "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS"; then
    output=$(oc exec "deployment/${PLAYGROUND_LSD_NAME}" -n "$PROJECT_NS" -- python3 -c "
import json
import urllib.error
import urllib.request

models = [
    ('nemotron', '${NEMOTRON_MODEL_RESOURCE}'),
    ('openai', '${OPENAI_MODEL_ID}'),
]

with urllib.request.urlopen('http://127.0.0.1:8321/v1/models', timeout=60) as resp:
    listed_models = json.loads(resp.read()).get('data', [])

def find_model_id(target):
    for item in listed_models:
        model_id = item.get('identifier') or item.get('id') or ''
        metadata = item.get('custom_metadata') or {}
        if metadata.get('provider_resource_id') == target or model_id == target or model_id.endswith('/' + target):
            return model_id
    raise RuntimeError(f'model target not listed: {target}')

for label, target in models:
    model = find_model_id(target)
    payload = json.dumps({
        'model': model,
        'input': 'You are concise. Reply with exactly: playground-ok',
        'max_output_tokens': 128,
        'temperature': 0,
    }).encode()
    req = urllib.request.Request(
        'http://127.0.0.1:8321/v1/responses',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode('utf-8', 'replace')
            print(f'OK {label}' if resp.status == 200 and 'playground-ok' in body else f'FAIL {label}: status={resp.status} body={body[:160]}')
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')
        print(f'FAIL {label}: status={exc.code} body={body[:160]}')
    except Exception as exc:
        print(f'FAIL {label}: {exc!r}')
" 2>&1 || true)
    if grep -q "OK nemotron" <<<"$output" && grep -q "OK openai" <<<"$output"; then
      check "Gen AI Playground Responses API works for MaaS Nemotron and GPT" "pass"
    elif grep -q "FAIL" <<<"$output" &&
      grep -qi "Too Many Requests" <<<"$output"; then
      warn "Gen AI Playground Responses API works for MaaS Nemotron and GPT" \
        "MaaS policy or external provider throttled inference: ${output//$'\n'/ }"
    else
      check "Gen AI Playground Responses API works for MaaS Nemotron and GPT" \
        "responses=${output//$'\n'/ }"
    fi
  else
    check "Gen AI Playground Responses API works for MaaS Nemotron and GPT" "deployment missing"
  fi

  if resource_exists "deployment/rhods-dashboard" "redhat-ods-applications"; then
    local dashboard_pod developer_token bff_model_list bff_models bff_output

    dashboard_pod=$(oc get pod -n redhat-ods-applications -l app=rhods-dashboard \
      -o jsonpath='{.items[0].metadata.name}' --insecure-skip-tls-verify=true 2>/dev/null || true)
    developer_token=$(get_demo_user_token "ai-developer" "${AI_DEVELOPER_PASSWORD:-}" || true)

    if [[ -z "$dashboard_pod" || -z "$developer_token" ]]; then
      result="dashboard pod or ai-developer token unavailable"
    else
      bff_model_list=$(oc exec -i -n redhat-ods-applications "$dashboard_pod" -c rhods-dashboard -- \
        env USER_TOKEN="$developer_token" PROJECT_NS="$PROJECT_NS" python3 - <<'PY' 2>/dev/null || true
import os
import ssl
import urllib.error
import urllib.request

ctx = ssl._create_unverified_context()
url = (
    "https://127.0.0.1:8443/gen-ai/api/v1/lsd/models"
    f"?namespace={os.environ['PROJECT_NS']}"
)
req = urllib.request.Request(
    url,
    headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {os.environ['USER_TOKEN']}",
        "x-forwarded-access-token": os.environ["USER_TOKEN"],
    },
)
try:
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        print(resp.read().decode(errors="replace"))
except urllib.error.HTTPError as err:
    print(err.read().decode(errors="replace"))
PY
)

      if [[ "$bff_model_list" != *"/${OPENAI_MODEL_ID}"* && "$bff_model_list" != *"\"${OPENAI_MODEL_ID}\""* ]]; then
        result="dashboard model list does not expose /${OPENAI_MODEL_ID}"
      elif [[ "$OPENAI_MODEL_RESOURCE" != "$OPENAI_MODEL_ID" && "$bff_model_list" == *"/${OPENAI_MODEL_RESOURCE}"* ]]; then
        result="dashboard model list still exposes stale /${OPENAI_MODEL_RESOURCE}"
      else
        bff_models=$(oc exec "deployment/${PLAYGROUND_LSD_NAME}" -n "$PROJECT_NS" -- python3 -c "
import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:8321/v1/models', timeout=60) as resp:
    listed_models = json.loads(resp.read()).get('data', [])

targets = {
    'nemotron': '${NEMOTRON_MODEL_RESOURCE}',
    'openai': '${OPENAI_MODEL_ID}',
}
resolved = {}
for item in listed_models:
    model_id = item.get('identifier') or item.get('id') or ''
    metadata = item.get('custom_metadata') or {}
    for label, target in targets.items():
        if metadata.get('provider_resource_id') == target or model_id == target or model_id.endswith('/' + target):
            resolved[label] = model_id
missing = sorted(set(targets) - set(resolved))
if missing:
    raise SystemExit('missing models: ' + ','.join(missing))
print(json.dumps(resolved))
" 2>/dev/null || true)

        if [[ -z "$bff_models" ]]; then
          result="could not discover provider-qualified Llama Stack model ids"
        else
          bff_output=$(oc exec -i -n redhat-ods-applications "$dashboard_pod" -c rhods-dashboard -- \
            env USER_TOKEN="$developer_token" PROJECT_NS="$PROJECT_NS" BFF_MODELS="$bff_models" python3 - <<'PY' 2>&1 || true
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

models = json.loads(os.environ["BFF_MODELS"])
url = (
    "https://127.0.0.1:8443/gen-ai/api/v1/lsd/responses"
    f"?namespace={os.environ['PROJECT_NS']}"
)
ctx = ssl._create_unverified_context()
failed = []

for label, model in models.items():
    payload = {
        "model": model,
        "input": "Reply with exactly: ok",
        "max_output_tokens": 8,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "Authorization": f"Bearer {os.environ['USER_TOKEN']}",
            "x-forwarded-access-token": os.environ["USER_TOKEN"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=180) as resp:
            body = resp.read().decode(errors="replace")
            status = resp.status
    except urllib.error.HTTPError as err:
        status = err.code
        body = err.read().decode(errors="replace")
    except Exception as err:
        status = "ERR"
        body = repr(err)

    if status not in (200, 201) or "ok" not in body.lower():
        failed.append(f"{label}:{status}:{body[:180].replace(chr(10), ' ')}")

if failed:
    print("; ".join(failed))
    sys.exit(1)

print("OK dashboard BFF responses")
PY
)
          if grep -q "OK dashboard BFF responses" <<<"$bff_output"; then
            result="pass"
          elif grep -q ":" <<<"$bff_output" &&
            (grep -qi "Too Many Requests" <<<"$bff_output" ||
              grep -qi "internal_server_error" <<<"$bff_output" ||
              grep -qi "LlamaStack error" <<<"$bff_output"); then
            result="warn: MaaS policy or external provider throttled inference through the dashboard BFF: ${bff_output//$'\n'/ }"
          else
            result="bff=${bff_output//$'\n'/ }"
          fi
        fi
      fi
    fi
  else
    result="dashboard deployment missing"
  fi
  if [[ "$result" == warn:* ]]; then
    warn "Gen AI Playground dashboard BFF works for MaaS Nemotron and GPT" "${result#warn: }"
  else
    check "Gen AI Playground dashboard BFF works for MaaS Nemotron and GPT" "$result"
  fi
}

check_known_servicemonitor_excluded() {
  local namespace="$1"
  local name="$2"
  local label

  if ! resource_exists "servicemonitor/${name}" "$namespace"; then
    check "Known generated ServiceMonitor absent or not installed: ${namespace}/${name}" "pass"
    return
  fi

  label=$(jsonpath "servicemonitor/${name}" "$namespace" '{.metadata.labels.openshift\.io/user-monitoring}')
  [[ "$label" == "false" ]] && R="pass" || R="openshift.io/user-monitoring=${label:-missing}"
  check "Known invalid generated ServiceMonitor excluded from user-workload monitoring: ${namespace}/${name}" "$R"
}

validate_known_monitoring_noise_is_resolved() {
  local port relabel_exists alerts targets

  check_known_servicemonitor_excluded \
    openshift-kueue-operator kueue-metrics
  check_known_servicemonitor_excluded \
    openshift-nfd nfd-controller-manager-metrics-monitor
  check_known_servicemonitor_excluded \
    redhat-ods-applications odh-model-controller-metrics-monitor
  check_known_servicemonitor_excluded \
    openshift-lws-operator lws-controller-manager-metrics-monitor

  if resource_exists "podmonitor/istio-pod-monitor" "openshift-ingress"; then
    port=$(jsonpath "podmonitor/istio-pod-monitor" "openshift-ingress" '{.spec.podMetricsEndpoints[0].port}')
    relabel_exists=$(oc get podmonitor istio-pod-monitor -n openshift-ingress -o json \
      --insecure-skip-tls-verify=true \
      | jq -r '
        any(.spec.podMetricsEndpoints[0].relabelings[]?;
          .action == "keep"
          and .regex == "metrics"
          and (.sourceLabels // []) == ["__meta_kubernetes_pod_container_port_name"]
        )
      ' 2>/dev/null || true)
    if [[ "$port" == "metrics" && "$relabel_exists" == "true" ]]; then
      R="pass"
    else
      R="port=${port:-missing}, metrics-port keep relabel=${relabel_exists:-missing}"
    fi
    check "Generated Istio PodMonitor scrapes only the gateway metrics port" "$R"
  else
    check "Generated Istio PodMonitor absent or not installed" "pass"
  fi

  if ! command -v jq >/dev/null 2>&1 ||
    ! resource_exists "pod/prometheus-k8s-0" "openshift-monitoring"; then
    warn "Prometheus alert API validation" "jq or prometheus-k8s-0 unavailable"
    return
  fi

  alerts=$(oc -n openshift-monitoring exec prometheus-k8s-0 -c prometheus -- \
    curl -s 'http://localhost:9090/api/v1/query?query=ALERTS%7Balertname%3D~%22TargetDown%7CPrometheusOperatorRejectedResources%22%2Calertstate%3D%22firing%22%7D' \
    2>/dev/null \
    | jq -r '.data.result[]? | [.metric.alertname, (.metric.job // ""), (.metric.namespace // ""), (.metric.resource // "")] | @tsv' \
    2>/dev/null || true)
  [[ -z "$alerts" ]] && R="pass" || R="${alerts//$'\n'/; }"
  check "Prometheus has no firing TargetDown or rejected-resource alerts for the known monitoring issue" "$R"

  targets=$(oc -n openshift-monitoring exec prometheus-k8s-0 -c prometheus -- \
    curl -s 'http://localhost:9090/api/v1/targets?state=active' \
    2>/dev/null \
    | jq -r '
      .data.activeTargets[]
      | select((.labels.job // "") == "openshift-ingress/istio-pod-monitor")
      | select(.health != "up")
      | [.scrapeUrl, (.lastError // "")] | @tsv
    ' 2>/dev/null || true)
  [[ -z "$targets" ]] && R="pass" || R="${targets//$'\n'/; }"
  check "Generated Istio PodMonitor has no down active targets" "$R"
}

APP_SYNC=$(jsonpath "applications.argoproj.io/040-governed-models-as-a-service" "openshift-gitops" "{.status.sync.status}")
[[ "$APP_SYNC" == "Synced" ]] && R="pass" || R="sync=${APP_SYNC:-not found}"
check "Stage 220 Application Synced" "$R"

STAGE110_SYNC=$(jsonpath "applications.argoproj.io/010-openshift-ai-platform-foundation" "openshift-gitops" "{.status.sync.status}")
[[ "$STAGE110_SYNC" == "Synced" ]] && R="pass" || R="sync=${STAGE110_SYNC:-not found}"
check "Stage 110 shared owner Application Synced" "$R"

DSC_PHASE=$(jsonpath "datasciencecluster/default-dsc" "" "{.status.phase}")
[[ "$DSC_PHASE" == "Ready" ]] && R="pass" || R="phase=${DSC_PHASE:-not found}"
check "DataScienceCluster Ready" "$R"

DSC_MAAS=$(jsonpath "datasciencecluster/default-dsc" "" "{.spec.components.kserve.modelsAsService.managementState}")
[[ "$DSC_MAAS" == "Managed" ]] && R="pass" || R="modelsAsService=${DSC_MAAS:-not found}"
check "DataScienceCluster MaaS is Managed" "$R"

DSC_LLAMA=$(jsonpath "datasciencecluster/default-dsc" "" "{.spec.components.llamastackoperator.managementState}")
[[ "$DSC_LLAMA" == "Managed" ]] && R="pass" || R="llamastackoperator=${DSC_LLAMA:-not found}"
check "DataScienceCluster Llama Stack Operator is Managed" "$R"

for flag in modelAsService vLLMDeploymentOnMaaS genAiStudio maasAuthPolicies observabilityDashboard; do
  value=$(jsonpath "odhdashboardconfig/odh-dashboard-config" "redhat-ods-applications" "{.spec.dashboardConfig.${flag}}")
  [[ "$value" == "true" ]] && R="pass" || R="${flag}=${value:-missing}"
  check "Dashboard flag enabled: ${flag}" "$R"
done

if resource_exists "certmanager/cluster" ""; then
  R="pass"
else
  R="missing"
fi
check "cert-manager cluster resource present" "$R"

CERT_READY=0
for deploy in cert-manager cert-manager-cainjector cert-manager-webhook; do
  ready=$(jsonpath "deployment/${deploy}" "cert-manager" "{.status.readyReplicas}")
  if [[ "${ready:-0}" == "1" ]]; then
    (( CERT_READY++ )) || true
  fi
done
[[ "$CERT_READY" == "3" ]] && R="pass" || R="readyDeployments=${CERT_READY}/3"
check "cert-manager deployments available" "$R"

RHCL_CSV=$(jsonpath "subscription/rhcl-operator" "openshift-operators" "{.status.installedCSV}")
RHCL_APPROVAL=$(jsonpath "subscription/rhcl-operator" "openshift-operators" "{.spec.installPlanApproval}")
RHCL_STARTING_CSV=$(jsonpath "subscription/rhcl-operator" "openshift-operators" "{.spec.startingCSV}")
if [[ "$RHCL_CSV" == "$PINNED_RHCL_CSV" &&
  "$RHCL_APPROVAL" == "Manual" &&
  "$RHCL_STARTING_CSV" == "$PINNED_RHCL_CSV" ]]; then
  R="pass"
else
  R="installedCSV=${RHCL_CSV:-missing},approval=${RHCL_APPROVAL:-missing},startingCSV=${RHCL_STARTING_CSV:-missing},expected=${PINNED_RHCL_CSV}"
fi
check "Red Hat Connectivity Link Operator is pinned to the MaaS-compatible CSV" "$R"

while IFS='|' read -r sub_name expected_csv label; do
  DEP_CSV=$(jsonpath "subscription/${sub_name}" "openshift-operators" "{.status.installedCSV}")
  DEP_APPROVAL=$(jsonpath "subscription/${sub_name}" "openshift-operators" "{.spec.installPlanApproval}")
  DEP_STARTING_CSV=$(jsonpath "subscription/${sub_name}" "openshift-operators" "{.spec.startingCSV}")
  if [[ "$DEP_CSV" == "$expected_csv" &&
    "$DEP_APPROVAL" == "Manual" &&
    "$DEP_STARTING_CSV" == "$expected_csv" ]]; then
    R="pass"
  else
    R="installedCSV=${DEP_CSV:-missing},approval=${DEP_APPROVAL:-missing},startingCSV=${DEP_STARTING_CSV:-missing},expected=${expected_csv}"
  fi
  check "${label} Operator is pinned to the MaaS-compatible CSV" "$R"
done <<EOF
authorino-operator-stable-redhat-operators-openshift-marketplace|${PINNED_AUTHORINO_CSV}|Authorino
dns-operator-stable-redhat-operators-openshift-marketplace|${PINNED_DNS_CSV}|DNS
limitador-operator-stable-redhat-operators-openshift-marketplace|${PINNED_LIMITADOR_CSV}|Limitador
EOF

for crd in \
  kuadrants.kuadrant.io \
  authorinos.operator.authorino.kuadrant.io \
  gateways.gateway.networking.k8s.io \
  httproutes.gateway.networking.k8s.io \
  leaderworkersetoperators.operator.openshift.io \
  leaderworkersets.leaderworkerset.x-k8s.io \
  llamastackdistributions.llamastack.io; do
  if crd_exists "$crd"; then
    R="pass"
  else
    R="missing"
  fi
  check "Prerequisite CRD present: ${crd}" "$R"
done

for crd in \
  tenants.maas.opendatahub.io \
  maasmodelrefs.maas.opendatahub.io \
  maassubscriptions.maas.opendatahub.io \
  maasauthpolicies.maas.opendatahub.io \
  externalmodels.maas.opendatahub.io; do
  if crd_exists "$crd"; then
    R="pass"
  else
    R="missing"
  fi
  check "MaaS CRD present: ${crd}" "$R"
done

DB_READY=$(jsonpath "statefulset/maas-postgres" "$MAAS_DB_NS" "{.status.readyReplicas}")
[[ "$DB_READY" == "1" ]] && R="pass" || R="readyReplicas=${DB_READY:-0}"
check "MaaS PostgreSQL StatefulSet ready" "$R"

if resource_exists "secret/${MAAS_DB_CONFIG_SECRET}" "redhat-ods-applications"; then
  MAAS_DB_URL=$(oc get "secret/${MAAS_DB_CONFIG_SECRET}" -n redhat-ods-applications \
    -o jsonpath='{.data.DB_CONNECTION_URL}' --insecure-skip-tls-verify=true 2>/dev/null \
    | base64 --decode 2>/dev/null || true)
  if [[ "$MAAS_DB_URL" == *"maas-postgres.${MAAS_DB_NS}.svc.cluster.local"* ]]; then
    R="pass"
  else
    R="DB_CONNECTION_URL does not point to maas-postgres.${MAAS_DB_NS}.svc.cluster.local"
  fi
else
  R="missing"
fi
check "maas-db-config secret points at the MaaS database namespace" "$R"

if resource_exists "secret/${OPENAI_PROVIDER_SECRET}" "$MAAS_NS"; then
  OPENAI_SECRET_LABEL=$(jsonpath "secret/${OPENAI_PROVIDER_SECRET}" "$MAAS_NS" "{.metadata.labels.inference\\.networking\\.k8s\\.io/bbr-managed}")
  if oc get "secret/${OPENAI_PROVIDER_SECRET}" -n "$MAAS_NS" -o jsonpath='{.data}' \
    --insecure-skip-tls-verify=true 2>/dev/null | grep -q 'api-key' &&
    [[ "$OPENAI_SECRET_LABEL" == "true" ]]; then
    R="pass"
  else
    R="missing data key api-key or inference.networking.k8s.io/bbr-managed=true label"
  fi
else
  R="missing"
fi
check "OpenAI provider Secret present with api-key data key and BBR label" "$R"

if resource_exists "rolebinding/rhods-admins-maas-admin" "$MAAS_NS"; then
  R="pass"
else
  R="missing"
fi
check "rhods-admins has MaaS namespace admin RoleBinding" "$R"

MAAS_PROJECT_LABEL=$(jsonpath "namespace/${MAAS_NS}" "" "{.metadata.labels.opendatahub\\.io/dashboard}")
[[ "$MAAS_PROJECT_LABEL" == "true" ]] && R="pass" || R="opendatahub.io/dashboard=${MAAS_PROJECT_LABEL:-missing}"
check "MaaS namespace is visible as an OpenShift AI project" "$R"

MAAS_KUEUE_LABEL=$(jsonpath "namespace/${MAAS_NS}" "" "{.metadata.labels.kueue\\.openshift\\.io/managed}")
[[ "$MAAS_KUEUE_LABEL" == "true" ]] && R="pass" || R="kueue.openshift.io/managed=${MAAS_KUEUE_LABEL:-missing}"
check "MaaS namespace is managed by Kueue" "$R"

AI_ADMIN_CAN=$(can_i_as "ai-admin" "get" "pods" "$MAAS_NS" "rhods-admins")
[[ "$AI_ADMIN_CAN" == "yes" ]] && R="pass" || R="can-i=${AI_ADMIN_CAN:-unknown}"
check "ai-admin can administer the MaaS namespace" "$R"

AI_DEVELOPER_CAN=$(can_i_as "ai-developer" "get" "pods" "$MAAS_NS" "rhoai-developers")
[[ "$AI_DEVELOPER_CAN" == "no" ]] && R="pass" || R="can-i=${AI_DEVELOPER_CAN:-unknown}"
check "ai-developer has no direct MaaS namespace access" "$R"

GATEWAY_HOST=$(get_gateway_host)
if [[ "$GATEWAY_HOST" == maas.* && "$GATEWAY_HOST" != "maas.placeholder.example.com" ]]; then
  R="pass"
else
  R="hostname=${GATEWAY_HOST:-missing}"
fi
check "MaaS Gateway hostname patched" "$R"

GATEWAY_TLS=$(jsonpath "gateway/maas-default-gateway" "openshift-ingress" "{.metadata.annotations.security\\.opendatahub\\.io/authorino-tls-bootstrap}")
[[ "$GATEWAY_TLS" == "true" ]] && R="pass" || R="annotation=${GATEWAY_TLS:-missing}"
check "MaaS Gateway Authorino TLS annotation present" "$R"

if crd_exists kuadrants.kuadrant.io; then
  KUADRANT_READY=$(jsonpath "kuadrant/kuadrant" "kuadrant-system" "{.status.conditions[?(@.type==\"Ready\")].status}")
  [[ "$KUADRANT_READY" == "True" ]] && R="pass" || R="ready=${KUADRANT_READY:-missing}"
else
  R="CRD missing"
fi
check "Kuadrant Ready" "$R"

if crd_exists authorinos.operator.authorino.kuadrant.io; then
  AUTHORINO_TLS=$(jsonpath "authorino/authorino" "kuadrant-system" "{.spec.listener.tls.enabled}")
  [[ "$AUTHORINO_TLS" == "true" ]] && R="pass" || R="tls=${AUTHORINO_TLS:-missing}"
else
  R="CRD missing"
fi
check "Authorino TLS enabled" "$R"

if crd_exists tenants.maas.opendatahub.io && resource_exists "tenant/default-tenant" "$MAAS_NS"; then
  TENANT_READY=$(jsonpath "tenant/default-tenant" "$MAAS_NS" "{.status.conditions[?(@.type==\"Ready\")].status}")
  [[ "$TENANT_READY" == "True" ]] && R="pass" || R="ready=${TENANT_READY:-missing}"
else
  R="missing"
fi
check "MaaS Tenant Ready" "$R"

if resource_exists "inferenceservice/${DIRECT_NEMOTRON_NAME}" "$PROJECT_NS"; then
  R="direct InferenceService still exists in ${PROJECT_NS}"
else
  R="pass"
fi
check "direct demo-sandbox Nemotron deployment has been removed" "$R"

STALE_LLMIS=""
for stale_llmis_name in "$NEMOTRON_MODEL_RESOURCE" "$DIRECT_NEMOTRON_NAME"; do
  if resource_exists "llminferenceservice/${stale_llmis_name}" "$PROJECT_NS"; then
    STALE_LLMIS="${STALE_LLMIS} ${stale_llmis_name}"
  fi
done
if [[ -z "$STALE_LLMIS" ]]; then
  R="pass"
else
  R="stale LLMInferenceService still exists in ${PROJECT_NS}:${STALE_LLMIS}"
fi
check "no stale demo-sandbox Nemotron LLMInferenceService remains" "$R"

if resource_exists "localqueue/lq-gpu-reserved-demo" "$MAAS_NS"; then
  LQ_CLUSTER_QUEUE=$(jsonpath "localqueue/lq-gpu-reserved-demo" "$MAAS_NS" "{.spec.clusterQueue}")
  [[ "$LQ_CLUSTER_QUEUE" == "cq-gpu-reserved-demo" ]] && R="pass" || R="clusterQueue=${LQ_CLUSTER_QUEUE:-missing}"
else
  R="missing"
fi
check "MaaS namespace has the GPU reserved LocalQueue" "$R"

if resource_exists "llminferenceservices.serving.kserve.io/${NEMOTRON_MODEL_RESOURCE}" "$MAAS_NS"; then
  NEMOTRON_URI=$(jsonpath_nonempty "llminferenceservices.serving.kserve.io/${NEMOTRON_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.model.uri}")
  NEMOTRON_READY=$(jsonpath_nonempty "llminferenceservices.serving.kserve.io/${NEMOTRON_MODEL_RESOURCE}" "$MAAS_NS" "{.status.conditions[?(@.type==\"Ready\")].status}")
  if [[ "$NEMOTRON_URI" == "oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0" &&
    "$NEMOTRON_READY" == "True" ]]; then
    R="pass"
  else
    R="uri=${NEMOTRON_URI:-missing},ready=${NEMOTRON_READY:-missing}"
  fi
else
  R="missing"
fi
check "local Nemotron LLMInferenceService is ready in MaaS namespace" "$R"

NEMOTRON_MODELREF_KIND=$(jsonpath "maasmodelrefs.maas.opendatahub.io/${NEMOTRON_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.modelRef.kind}")
NEMOTRON_MODELREF_NAME=$(jsonpath "maasmodelrefs.maas.opendatahub.io/${NEMOTRON_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.modelRef.name}")
if [[ "$NEMOTRON_MODELREF_KIND" == "LLMInferenceService" && "$NEMOTRON_MODELREF_NAME" == "$NEMOTRON_MODEL_RESOURCE" ]]; then
  R="pass"
else
  R="kind=${NEMOTRON_MODELREF_KIND:-missing},name=${NEMOTRON_MODELREF_NAME:-missing}"
fi
check "MaaSModelRef points to the local Nemotron LLMInferenceService" "$R"

EXTERNAL_PROVIDER=$(jsonpath "externalmodels.maas.opendatahub.io/${OPENAI_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.provider}")
EXTERNAL_ENDPOINT=$(jsonpath "externalmodels.maas.opendatahub.io/${OPENAI_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.endpoint}")
EXTERNAL_TARGET=$(jsonpath "externalmodels.maas.opendatahub.io/${OPENAI_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.targetModel}")
EXTERNAL_SECRET=$(jsonpath "externalmodels.maas.opendatahub.io/${OPENAI_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.credentialRef.name}")
if [[ "$EXTERNAL_PROVIDER" == "openai" && "$EXTERNAL_ENDPOINT" == "api.openai.com" && "$EXTERNAL_TARGET" == "$OPENAI_MODEL_ID" && "$EXTERNAL_SECRET" == "$OPENAI_PROVIDER_SECRET" ]]; then
  R="pass"
else
  R="provider=${EXTERNAL_PROVIDER:-missing},endpoint=${EXTERNAL_ENDPOINT:-missing},target=${EXTERNAL_TARGET:-missing},secret=${EXTERNAL_SECRET:-missing}"
fi
check "External OpenAI model is registered through MaaS schema" "$R"

MODELREF_KIND=$(jsonpath "maasmodelrefs.maas.opendatahub.io/${OPENAI_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.modelRef.kind}")
MODELREF_NAME=$(jsonpath "maasmodelrefs.maas.opendatahub.io/${OPENAI_MODEL_RESOURCE}" "$MAAS_NS" "{.spec.modelRef.name}")
if [[ "$MODELREF_KIND" == "ExternalModel" && "$MODELREF_NAME" == "$OPENAI_MODEL_RESOURCE" ]]; then
  R="pass"
else
  R="kind=${MODELREF_KIND:-missing},name=${MODELREF_NAME:-missing}"
fi
check "MaaSModelRef points to the external OpenAI model" "$R"

SUB_OWNER_GROUPS=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.owner.groups[*].name}")
SUB_OWNER_USERS=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.owner.users[*]}")
SUB_MODELS=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.modelRefs[*].name}")
SUB_OPENAI_LIMIT=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.modelRefs[?(@.name==\"${OPENAI_MODEL_RESOURCE}\")].tokenRateLimits[0].limit}")
SUB_OPENAI_WINDOW=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.modelRefs[?(@.name==\"${OPENAI_MODEL_RESOURCE}\")].tokenRateLimits[0].window}")
SUB_NEMOTRON_LIMIT=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.modelRefs[?(@.name==\"${NEMOTRON_MODEL_RESOURCE}\")].tokenRateLimits[0].limit}")
SUB_NEMOTRON_WINDOW=$(jsonpath "maassubscriptions.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.modelRefs[?(@.name==\"${NEMOTRON_MODEL_RESOURCE}\")].tokenRateLimits[0].window}")
if contains_word "$SUB_OWNER_GROUPS" "rhoai-developers" &&
  contains_word "$SUB_OWNER_GROUPS" "rhods-admins" &&
  contains_word "$SUB_OWNER_USERS" "kube:admin" &&
  contains_word "$SUB_MODELS" "$OPENAI_MODEL_RESOURCE" &&
  contains_word "$SUB_MODELS" "$NEMOTRON_MODEL_RESOURCE" &&
  [[ "$SUB_OPENAI_LIMIT" == "20000" && "$SUB_OPENAI_WINDOW" == "1h" &&
    "$SUB_NEMOTRON_LIMIT" == "100000" && "$SUB_NEMOTRON_WINDOW" == "1h" ]]; then
  R="pass"
else
  R="groups=${SUB_OWNER_GROUPS:-missing},users=${SUB_OWNER_USERS:-missing},models=${SUB_MODELS:-missing},openaiLimit=${SUB_OPENAI_LIMIT:-missing}/${SUB_OPENAI_WINDOW:-missing},nemotronLimit=${SUB_NEMOTRON_LIMIT:-missing}/${SUB_NEMOTRON_WINDOW:-missing}"
fi
check "demo users have MaaS subscription quota for local and external models" "$R"

AUTH_SUBJECT_GROUPS=$(jsonpath "maasauthpolicies.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.subjects.groups[*].name}")
AUTH_SUBJECT_USERS=$(jsonpath "maasauthpolicies.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.subjects.users[*]}")
AUTH_MODELS=$(jsonpath "maasauthpolicies.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.modelRefs[*].name}")
AUTH_ORG=$(jsonpath "maasauthpolicies.maas.opendatahub.io/${OPENAI_ACCESS_RESOURCE}" "$MAAS_NS" "{.spec.meteringMetadata.organizationId}")
if contains_word "$AUTH_SUBJECT_GROUPS" "rhoai-developers" &&
  contains_word "$AUTH_SUBJECT_GROUPS" "rhods-admins" &&
  contains_word "$AUTH_SUBJECT_USERS" "kube:admin" &&
  contains_word "$AUTH_MODELS" "$OPENAI_MODEL_RESOURCE" &&
  contains_word "$AUTH_MODELS" "$NEMOTRON_MODEL_RESOURCE" &&
  [[ "$AUTH_ORG" == "rhoai3-coding-demo" ]]; then
  R="pass"
else
  R="groups=${AUTH_SUBJECT_GROUPS:-missing},users=${AUTH_SUBJECT_USERS:-missing},models=${AUTH_MODELS:-missing},org=${AUTH_ORG:-missing}"
fi
check "demo users have MaaS auth policy for local and external models" "$R"

GATEWAY_FILTERS=$(oc get envoyfilter -n openshift-ingress -o name \
  --insecure-skip-tls-verify=true 2>/dev/null || true)
GATEWAY_READY=$(oc get pods -n openshift-ingress \
  -l gateway.networking.k8s.io/gateway-name=maas-default-gateway \
  -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{" "}{end}' \
  --insecure-skip-tls-verify=true 2>/dev/null || true)
GATEWAY_LOG_ERRORS=$(oc logs -n openshift-ingress \
  -l gateway.networking.k8s.io/gateway-name=maas-default-gateway \
  --since=3m --tail=500 --insecure-skip-tls-verify=true 2>/dev/null \
  | grep -E 'allow_on_headers_stop_iteration|Proto constraint validation failed|unknown field|Error adding/updating listener' \
  || true)
OPENAI_AUTH_ENFORCED=$(jsonpath "authpolicy/maas-auth-gpt-4o-mini" "$MAAS_NS" "{.status.conditions[?(@.type==\"Enforced\")].status}")
NEMOTRON_AUTH_ENFORCED=$(jsonpath "authpolicy/maas-auth-nemotron-3-nano-30b-a3b" "$MAAS_NS" "{.status.conditions[?(@.type==\"Enforced\")].status}")
OPENAI_TRLP_ENFORCED=$(jsonpath "tokenratelimitpolicy/maas-trlp-gpt-4o-mini" "$MAAS_NS" "{.status.conditions[?(@.type==\"Enforced\")].status}")
NEMOTRON_TRLP_ENFORCED=$(jsonpath "tokenratelimitpolicy/maas-trlp-nemotron-3-nano-30b-a3b" "$MAAS_NS" "{.status.conditions[?(@.type==\"Enforced\")].status}")
if [[ -n "$GATEWAY_LOG_ERRORS" ]]; then
  R="gateway Envoy log reports recent generated filter rejection"
elif ! contains_word "$GATEWAY_READY" "True"; then
  R="gateway pod Ready conditions=${GATEWAY_READY:-missing}"
elif ! grep -q 'kuadrant-auth-maas-default-gateway' <<<"$GATEWAY_FILTERS" ||
  ! grep -q 'kuadrant-ratelimiting-maas-default-gateway' <<<"$GATEWAY_FILTERS"; then
  R="generated Kuadrant auth/rate-limit EnvoyFilters missing"
elif [[ "$OPENAI_AUTH_ENFORCED" != "True" ||
  "$NEMOTRON_AUTH_ENFORCED" != "True" ||
  "$OPENAI_TRLP_ENFORCED" != "True" ||
  "$NEMOTRON_TRLP_ENFORCED" != "True" ]]; then
  R="policy enforcement openaiAuth=${OPENAI_AUTH_ENFORCED:-missing},nemotronAuth=${NEMOTRON_AUTH_ENFORCED:-missing},openaiLimit=${OPENAI_TRLP_ENFORCED:-missing},nemotronLimit=${NEMOTRON_TRLP_ENFORCED:-missing}"
else
  R="pass"
fi
check "MaaS Gateway generated policy filters are healthy" "$R"

if resource_exists "configmap/${MCP_DISCOVERY_CONFIGMAP}" "redhat-ods-applications"; then
  MCP_DISCOVERY_DATA=$(oc get configmap "$MCP_DISCOVERY_CONFIGMAP" -n redhat-ods-applications \
    -o json --insecure-skip-tls-verify=true 2>/dev/null \
    | jq -r --arg key "$MCP_DISCOVERY_KEY" '.data[$key] // ""' 2>/dev/null || true)
  if [[ "$MCP_DISCOVERY_DATA" == *"http://${MCP_SERVER_NAME}.${MCP_NS}.svc:8080/mcp"* &&
    "$MCP_DISCOVERY_DATA" == *"Read-only MCP server"* ]]; then
    R="pass"
  else
    R="missing ${MCP_DISCOVERY_KEY} entry or expected URL"
  fi
else
  R="missing"
fi
check "OpenShift MCP is registered for Gen AI Playground discovery" "$R"

if resource_exists "deployment/${MCP_SERVER_NAME}" "$MCP_NS"; then
  MCP_READY=$(jsonpath "deployment/${MCP_SERVER_NAME}" "$MCP_NS" "{.status.availableReplicas}")
  MCP_DEPLOY_IMAGE=$(jsonpath "deployment/${MCP_SERVER_NAME}" "$MCP_NS" "{.spec.template.spec.containers[0].image}")
  if [[ "$MCP_READY" == "1" && "$MCP_DEPLOY_IMAGE" == "$MCP_IMAGE" ]]; then
    R="pass"
  else
    R="availableReplicas=${MCP_READY:-0},image=${MCP_DEPLOY_IMAGE:-missing}"
  fi
else
  R="missing"
fi
check "OpenShift MCP server deployment is available with the OpenShift MCP image" "$R"

if resource_exists "service/${MCP_SERVER_NAME}" "$MCP_NS"; then
  MCP_ENDPOINTS=$(oc get endpoints "$MCP_SERVER_NAME" -n "$MCP_NS" \
    -o jsonpath='{.subsets[*].addresses[*].ip}' \
    --insecure-skip-tls-verify=true 2>/dev/null || true)
  [[ -n "$MCP_ENDPOINTS" ]] && R="pass" || R="service has no ready endpoints"
else
  R="missing"
fi
check "OpenShift MCP service has ready endpoints" "$R"

MCP_RBAC_REF=$(jsonpath "clusterrolebinding/rhoai-demo-openshift-mcp-view" "" "{.roleRef.kind}/{.roleRef.name}:{.subjects[0].namespace}/{.subjects[0].name}")
if [[ "$MCP_RBAC_REF" == "ClusterRole/view:${MCP_NS}/${MCP_SERVER_NAME}" ]]; then
  R="pass"
else
  R="binding=${MCP_RBAC_REF:-missing}"
fi
check "OpenShift MCP ServiceAccount is bound to read-only cluster view" "$R"

if resource_exists "configmap/${MCP_CONFIGMAP}" "$MCP_NS"; then
  MCP_CONFIG_BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-mcp-config.XXXXXX")
  TMP_FILES+=("$MCP_CONFIG_BODY")
  oc get configmap "$MCP_CONFIGMAP" -n "$MCP_NS" \
    -o jsonpath='{.data.config\.toml}' \
    --insecure-skip-tls-verify=true >"$MCP_CONFIG_BODY" 2>/dev/null || true
  MCP_ENABLED_TOOLS=$(awk '
    /enabled_tools = \[/ {inside=1}
    inside {print}
    inside && /\]/ {inside=0}
  ' "$MCP_CONFIG_BODY")
  if grep -Fq 'read_only = true' "$MCP_CONFIG_BODY" &&
    grep -Fq 'list_output = "table"' "$MCP_CONFIG_BODY" &&
    grep -Fq 'toolsets = ["core", "config"]' "$MCP_CONFIG_BODY" &&
    grep -Fq 'enabled_tools = [' <<<"$MCP_ENABLED_TOOLS" &&
    grep -Fq '"pods_list_in_namespace"' <<<"$MCP_ENABLED_TOOLS" &&
    ! grep -Fq '"pods_list"' <<<"$MCP_ENABLED_TOOLS" &&
    ! grep -Fq '"namespaces_list"' <<<"$MCP_ENABLED_TOOLS" &&
    grep -Fq '"pods_get"' <<<"$MCP_ENABLED_TOOLS" &&
    grep -Fq '"pods_list"' "$MCP_CONFIG_BODY" &&
    grep -Fq '"namespaces_list"' "$MCP_CONFIG_BODY" &&
    grep -Fq 'kind = "Secret"' "$MCP_CONFIG_BODY" &&
    grep -Fq 'kind = "ConfigMap"' "$MCP_CONFIG_BODY" &&
    grep -Fq 'kind = "ClusterRoleBinding"' "$MCP_CONFIG_BODY"; then
    R="pass"
  else
    R="missing read_only, table list output, restricted toolsets, namespace-scoped inspection tools, broad list exclusions, or denied sensitive resources"
  fi
else
  R="missing"
fi
check "OpenShift MCP config is read-only, small-surface, and denies sensitive resources" "$R"

if resource_exists "deployment/${PLAYGROUND_LSD_NAME}" "$PROJECT_NS"; then
  MCP_RESPONSE_OUTPUT=$(oc exec "deployment/${PLAYGROUND_LSD_NAME}" -n "$PROJECT_NS" -- python3 -c "
import json
import sys
import urllib.error
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:8321/v1/models', timeout=60) as resp:
    listed_models = json.loads(resp.read()).get('data', [])

model = None
target = '${NEMOTRON_MODEL_RESOURCE}'
for item in listed_models:
    model_id = item.get('identifier') or item.get('id') or ''
    if model_id == target or model_id.endswith('/' + target):
        model = model_id
        break
if not model:
    raise SystemExit('nemotron model target not listed')

payload = {
    'model': model,
    'input': 'Use OpenShift-MCP pods_list_in_namespace with namespace demo-sandbox. Reply under 30 words with pod readiness only.',
    'tools': [{
        'type': 'mcp',
        'server_label': '${MCP_DISCOVERY_KEY}',
        'server_url': 'http://${MCP_SERVER_NAME}.${MCP_NS}.svc:8080/mcp',
        'require_approval': 'never',
        'allowed_tools': ['pods_list_in_namespace'],
    }],
    'tool_choice': 'auto',
    'max_tool_calls': 2,
    'max_output_tokens': int('${PLAYGROUND_VLLM_MAX_TOKENS}'),
    'temperature': 0,
    'stream': False,
}
req = urllib.request.Request(
    'http://127.0.0.1:8321/v1/responses',
    data=json.dumps(payload).encode(),
    headers={'content-type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=240) as resp:
        body = resp.read().decode('utf-8', 'replace')
        data = json.loads(body)
        output_types = [item.get('type') for item in data.get('output', [])]
        if data.get('error'):
            print('error=' + json.dumps(data.get('error')))
            sys.exit(1)
        if 'mcp_list_tools' not in output_types:
            print('missing mcp_list_tools output, types=' + ','.join(output_types))
            sys.exit(1)
        if 'mcp_call' not in output_types:
            print('missing mcp_call output, types=' + ','.join(output_types))
            sys.exit(1)
        for item in data.get('output', []):
            if item.get('type') == 'mcp_call' and item.get('error'):
                print('mcp_call error=' + json.dumps(item.get('error')))
                sys.exit(1)
        if 'message' not in output_types:
            print('missing final message output, types=' + ','.join(output_types))
            sys.exit(1)
        print('OK mcp response path output_types=' + ','.join(output_types))
except urllib.error.HTTPError as err:
    body = err.read().decode('utf-8', 'replace')
    print('http=' + str(err.code) + ' body=' + body[:240].replace('\\n', ' '))
    sys.exit(1)
except Exception as err:
    print(repr(err))
    sys.exit(1)
" 2>&1 || true)
  if grep -q "OK mcp response path" <<<"$MCP_RESPONSE_OUTPUT"; then
    R="pass"
  else
    R="mcp=${MCP_RESPONSE_OUTPUT//$'\n'/ }"
  fi
else
  R="warn: playground deployment is not present yet; create a Gen AI Playground in ${PROJECT_NS} to validate MCP through Llama Stack Responses API"
fi
if [[ "$R" == warn:* ]]; then
  warn "Gen AI Playground can reach OpenShift MCP through Llama Stack Responses API" "${R#warn: }"
else
  check "Gen AI Playground can reach OpenShift MCP through Llama Stack Responses API" "$R"
fi

if command -v python3 >/dev/null 2>&1; then
  DASHBOARD_HOST=$(jsonpath "route/rhods-dashboard" "redhat-ods-applications" "{.spec.host}")
  AI_DEVELOPER_TOKEN=$(get_demo_user_token "ai-developer" "${AI_DEVELOPER_PASSWORD:-}" || true)
  if [[ -n "$AI_DEVELOPER_TOKEN" ]]; then
    BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-dashboard.XXXXXX")
    TMP_FILES+=("$BODY")
    STATUS=$(http_get "https://${DASHBOARD_HOST}/gen-ai/api/v1/maas/models?namespace=${PROJECT_NS}" "$AI_DEVELOPER_TOKEN" "$BODY")
    if [[ "$STATUS" == "200" ]] && body_contains_model "$BODY"; then
      R="pass"
    else
      R="status=${STATUS},body=$(head -c 180 "$BODY" | tr '\n' ' ')"
    fi
    check "ai-developer dashboard AI asset endpoints can load MaaS models" "$R"

    BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-maas-api.XXXXXX")
    TMP_FILES+=("$BODY")
    STATUS=$(http_get "https://${GATEWAY_HOST}/maas-api/v1/subscriptions" "$AI_DEVELOPER_TOKEN" "$BODY")
    if [[ "$STATUS" == "200" ]] && grep -q "$OPENAI_ACCESS_RESOURCE" "$BODY"; then
      R="pass"
    else
      R="status=${STATUS},body=$(head -c 180 "$BODY" | tr '\n' ' ')"
    fi
    check "ai-developer MaaS API subscription discovery works through Gateway" "$R"

    if command -v curl >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
      API_KEY_BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-api-key.XXXXXX")
      TMP_FILES+=("$API_KEY_BODY")
      INFERENCE_BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-inference.XXXXXX")
      TMP_FILES+=("$INFERENCE_BODY")

      API_KEY_STATUS=$(curl -sk --max-time 30 -o "$API_KEY_BODY" -w '%{http_code}' \
        -H "Authorization: Bearer ${AI_DEVELOPER_TOKEN}" \
        -H "Content-Type: application/json" \
        "https://${GATEWAY_HOST}/maas-api/v1/api-keys" \
        --data-binary "{\"name\":\"stage220-validation\",\"subscriptionName\":\"${OPENAI_ACCESS_RESOURCE}\"}" \
        2>/dev/null || true)
      API_KEY_VALUE=$(jq -r '.key // empty' "$API_KEY_BODY" 2>/dev/null || true)
      API_KEY_ID=$(jq -r '.id // empty' "$API_KEY_BODY" 2>/dev/null || true)

      if [[ "$API_KEY_STATUS" == "201" && "$API_KEY_VALUE" == sk-oai-* && -n "$API_KEY_ID" ]]; then
        R="pass"
      else
        R="status=${API_KEY_STATUS:-missing},body=$(head -c 180 "$API_KEY_BODY" | tr '\n' ' ')"
      fi
      check "ai-developer can create a MaaS API key for the demo subscription" "$R"

      if [[ "$API_KEY_VALUE" == sk-oai-* ]]; then
        INFERENCE_STATUS=$(curl -sk --max-time 120 -o "$INFERENCE_BODY" -w '%{http_code}' \
          -H "Authorization: Bearer ${API_KEY_VALUE}" \
          -H "Content-Type: application/json" \
          "https://${GATEWAY_HOST}/models-as-a-service/${NEMOTRON_MODEL_RESOURCE}/v1/chat/completions" \
          --data-binary @- <<JSON 2>/dev/null || true
{
  "model": "${NEMOTRON_MODEL_RESOURCE}",
  "messages": [
    {
      "role": "user",
      "content": "Use the available tool to get the weather for Amsterdam."
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string"
            }
          },
          "required": [
            "city"
          ]
        }
      }
    }
  ],
  "tool_choice": {
    "type": "function",
    "function": {
      "name": "get_weather"
    }
  },
  "max_tokens": 128,
  "temperature": 0
}
JSON
)
        if [[ "$INFERENCE_STATUS" == "200" ]] &&
          jq -e '
            .choices[0].message.tool_calls[0].function.name == "get_weather" and
            (.choices[0].message.tool_calls[0].function.arguments | contains("Amsterdam")) and
            (.usage.total_tokens // 0) > 0
          ' "$INFERENCE_BODY" >/dev/null 2>&1; then
          R="pass"
        elif [[ "$INFERENCE_STATUS" == "429" ]] &&
          grep -qi "Too Many Requests" "$INFERENCE_BODY"; then
          R="warn: MaaS policy throttled local Nemotron validation request: status=${INFERENCE_STATUS},body=$(head -c 180 "$INFERENCE_BODY" | tr '\n' ' ')"
        else
          R="status=${INFERENCE_STATUS:-missing},body=$(head -c 180 "$INFERENCE_BODY" | tr '\n' ' ')"
        fi
      else
        R="MaaS API key was not created"
      fi
      if [[ "$R" == warn:* ]]; then
        warn "ai-developer can call Nemotron through MaaS with tool calling and token usage" "${R#warn: }"
      else
        check "ai-developer can call Nemotron through MaaS with tool calling and token usage" "$R"
      fi

      if [[ "$API_KEY_VALUE" == sk-oai-* ]]; then
        EXTERNAL_INFERENCE_BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-openai-inference.XXXXXX")
        TMP_FILES+=("$EXTERNAL_INFERENCE_BODY")
        EXTERNAL_INFERENCE_STATUS=""
        for attempt in 1 2 3; do
          : > "$EXTERNAL_INFERENCE_BODY"
          EXTERNAL_INFERENCE_STATUS=$(curl -sk --max-time 120 -o "$EXTERNAL_INFERENCE_BODY" -w '%{http_code}' \
            -H "Authorization: Bearer ${API_KEY_VALUE}" \
            -H "Content-Type: application/json" \
            "https://${GATEWAY_HOST}/models-as-a-service/${OPENAI_MODEL_RESOURCE}/v1/chat/completions" \
            --data-binary @- <<JSON 2>/dev/null || true
{
  "model": "${OPENAI_MODEL_ID}",
  "messages": [
    {
      "role": "user",
      "content": "Use the get_pod_readiness_summary tool for namespace demo-sandbox."
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_pod_readiness_summary",
        "description": "Return a short OpenShift pod readiness summary for one namespace.",
        "parameters": {
          "type": "object",
          "properties": {
            "namespace": {
              "type": "string"
            }
          },
          "required": [
            "namespace"
          ]
        }
      }
    }
  ],
  "tool_choice": {
    "type": "function",
    "function": {
      "name": "get_pod_readiness_summary"
    }
  },
  "max_tokens": 80,
  "temperature": 0
}
JSON
)
          if [[ "$EXTERNAL_INFERENCE_STATUS" == "200" ]]; then
            break
          fi
          sleep 3
        done
        if [[ "$EXTERNAL_INFERENCE_STATUS" == "200" ]] &&
          jq -e '
            .choices[0].message.tool_calls[0].function.name == "get_pod_readiness_summary" and
            (.choices[0].message.tool_calls[0].function.arguments | contains("demo-sandbox")) and
            (.usage.total_tokens // 0) > 0
          ' "$EXTERNAL_INFERENCE_BODY" >/dev/null 2>&1; then
          R="pass"
        elif [[ "$EXTERNAL_INFERENCE_STATUS" == "429" ]] &&
          grep -qi "Too Many Requests" "$EXTERNAL_INFERENCE_BODY"; then
          R="warn: external OpenAI provider throttled: status=${EXTERNAL_INFERENCE_STATUS},body=$(head -c 180 "$EXTERNAL_INFERENCE_BODY" | tr '\n' ' ')"
        else
          R="status=${EXTERNAL_INFERENCE_STATUS:-missing},body=$(head -c 180 "$EXTERNAL_INFERENCE_BODY" | tr '\n' ' ')"
        fi
      else
        R="MaaS API key was not created"
      fi
      if [[ "$R" == warn:* ]]; then
        warn "ai-developer can call external OpenAI through MaaS with tool calling and token usage" "${R#warn: }"
      else
        check "ai-developer can call external OpenAI through MaaS with tool calling and token usage" "$R"
      fi

      UNAUTH_BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-unauth.XXXXXX")
      TMP_FILES+=("$UNAUTH_BODY")
      UNAUTH_STATUS=$(curl -sk --max-time 30 -o "$UNAUTH_BODY" -w '%{http_code}' \
        -H "Content-Type: application/json" \
        "https://${GATEWAY_HOST}/models-as-a-service/${NEMOTRON_MODEL_RESOURCE}/v1/chat/completions" \
        --data-binary "{\"model\":\"${NEMOTRON_MODEL_RESOURCE}\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}],\"max_tokens\":4}" \
        2>/dev/null || true)
      [[ "$UNAUTH_STATUS" == "401" ]] && R="pass" || R="status=${UNAUTH_STATUS:-missing}"
      check "unauthenticated MaaS inference is rejected" "$R"

      if [[ -n "$API_KEY_ID" ]]; then
        DELETE_STATUS=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' \
          -X DELETE \
          -H "Authorization: Bearer ${AI_DEVELOPER_TOKEN}" \
          "https://${GATEWAY_HOST}/maas-api/v1/api-keys/${API_KEY_ID}" \
          2>/dev/null || true)
        [[ "$DELETE_STATUS" == "200" ]] && R="pass" || R="status=${DELETE_STATUS:-missing}"
      else
        R="API key id missing"
      fi
      check "ai-developer validation MaaS API key is revoked" "$R"
    else
      check "ai-developer MaaS API key and inference validation can run" "curl or jq missing"
    fi
  else
    check "ai-developer dashboard/API validation token available" "AI_DEVELOPER_PASSWORD missing or login failed"
  fi

  AI_ADMIN_TOKEN=$(get_demo_user_token "ai-admin" "${AI_ADMIN_PASSWORD:-}" || true)
  if [[ -n "$AI_ADMIN_TOKEN" ]]; then
    BODY=$(mktemp "${TMPDIR:-/tmp}/rhoai-stage220-dashboard-admin.XXXXXX")
    TMP_FILES+=("$BODY")
    STATUS=$(http_get "https://${DASHBOARD_HOST}/gen-ai/api/v1/maas/models?namespace=${MAAS_NS}" "$AI_ADMIN_TOKEN" "$BODY")
    if [[ "$STATUS" == "200" ]] && body_contains_model "$BODY"; then
      R="pass"
    else
      R="status=${STATUS},body=$(head -c 180 "$BODY" | tr '\n' ' ')"
    fi
    check "ai-admin dashboard can load MaaS models from the MaaS project" "$R"
  else
    check "ai-admin dashboard validation token available" "AI_ADMIN_PASSWORD missing or login failed"
  fi
else
  check "Dashboard and MaaS API HTTP validation can run" "python3 missing"
fi

validate_playground_if_present
validate_known_monitoring_noise_is_resolved

echo
echo "Stage 220 validation summary: ${PASS} passed, ${WARN} warned, ${FAIL} failed"
if (( FAIL > 0 )); then
  exit 1
fi
