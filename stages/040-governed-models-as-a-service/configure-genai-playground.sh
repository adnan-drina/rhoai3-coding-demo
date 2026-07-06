#!/usr/bin/env bash
# configure-genai-playground.sh - Diagnostic repair for a dashboard-created
# Gen AI Playground that has stale MaaS credentials or model mappings.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd jq
require_cmd oc
require_cmd python3

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
  exit 1
fi

PROJECT_NS="${RHOAI_DEMO_PROJECT_NAMESPACE:-demo-sandbox}"
MAAS_NS="${RHOAI_MAAS_NAMESPACE:-models-as-a-service}"
MAAS_SUBSCRIPTION="${RHOAI_OPENAI_ACCESS_RESOURCE:-rhoai-developers-gpt-4o-mini}"
OPENAI_MODEL_ID="${RHOAI_OPENAI_MODEL_ID:-gpt-4o-mini}"
OPENAI_MODEL_RESOURCE="${RHOAI_OPENAI_MODEL_RESOURCE:-gpt-4o-mini}"
NEMOTRON_MODEL_RESOURCE="${RHOAI_MAAS_NEMOTRON_MODEL_NAME:-nemotron-3-nano-30b-a3b}"
PLAYGROUND_LSD_NAME="${RHOAI_PLAYGROUND_LSD_NAME:-lsd-genai-playground}"
PLAYGROUND_CONFIGMAP="${RHOAI_PLAYGROUND_CONFIGMAP:-llama-stack-config}"
PLAYGROUND_SECRET="${RHOAI_PLAYGROUND_MAAS_API_KEY_SECRET:-genai-playground-maas-api-key}"
# Preserve the dashboard-created provider ids while changing the GPT provider
# implementation to the OpenAI-compatible adapter. The browser must still
# refresh after this helper so it uses the Llama Stack model id ending in the
# provider target, for example /gpt-4o-mini.
PLAYGROUND_GPT_PROVIDER="${RHOAI_PLAYGROUND_GPT_PROVIDER_ID:-maas-vllm-inference-1}"
PLAYGROUND_NEMOTRON_PROVIDER="${RHOAI_PLAYGROUND_NEMOTRON_PROVIDER_ID:-maas-vllm-inference-2}"
PLAYGROUND_VLLM_MAX_TOKENS="${RHOAI_PLAYGROUND_VLLM_MAX_TOKENS:-512}"
PLAYGROUND_API_KEY_NAME="genai-playground-${PROJECT_NS}"
FORCE_OPENAI_PROVIDER_PATCH="${RHOAI_PLAYGROUND_FORCE_OPENAI_PROVIDER_PATCH:-false}"
CREATED_API_KEY_VALUE=""
CREATED_API_KEY_ID=""

TMP_FILES=()
cleanup() {
  if ((${#TMP_FILES[@]} > 0)); then
    rm -f "${TMP_FILES[@]}"
  fi
}
trap cleanup EXIT

get_demo_user_token() {
  local kubeconfig token

  if [[ -z "${AI_DEVELOPER_PASSWORD:-}" ]]; then
    echo "ERROR: AI_DEVELOPER_PASSWORD is required in .env to create a MaaS API key." >&2
    return 1
  fi

  kubeconfig=$(mktemp "${TMPDIR:-/tmp}/rhoai-playground-login.XXXXXX")
  TMP_FILES+=("$kubeconfig")

  oc login "$ACTUAL_SERVER" -u ai-developer -p "$AI_DEVELOPER_PASSWORD" \
    --kubeconfig "$kubeconfig" \
    --insecure-skip-tls-verify=true >/dev/null

  token=$(oc --kubeconfig "$kubeconfig" whoami -t \
    --insecure-skip-tls-verify=true 2>/dev/null || true)
  [[ -n "$token" ]] || return 1
  printf '%s' "$token"
}

gateway_host() {
  oc get gateway maas-default-gateway -n openshift-ingress \
    -o jsonpath='{.spec.listeners[0].hostname}' \
    --insecure-skip-tls-verify=true
}

create_maas_api_key() {
  local token="$1"
  local host="$2"
  local body status key key_id

  body=$(mktemp "${TMPDIR:-/tmp}/rhoai-playground-api-key.XXXXXX")
  TMP_FILES+=("$body")

  status=$(curl -sk --max-time 30 -o "$body" -w '%{http_code}' \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    "https://${host}/maas-api/v1/api-keys" \
    --data-binary "{\"name\":\"${PLAYGROUND_API_KEY_NAME}\",\"subscriptionName\":\"${MAAS_SUBSCRIPTION}\"}" \
    2>/dev/null || true)

  key=$(jq -r '.key // empty' "$body" 2>/dev/null || true)
  key_id=$(jq -r '.id // empty' "$body" 2>/dev/null || true)

  if [[ "$status" != "201" || "$key" != sk-oai-* || -z "$key_id" ]]; then
    echo "ERROR: failed to create MaaS API key for playground (status=${status})." >&2
    head -c 240 "$body" >&2 || true
    echo >&2
    return 1
  fi

  CREATED_API_KEY_VALUE="$key"
  CREATED_API_KEY_ID="$key_id"
}

store_playground_api_key() {
  local key="$1"
  local key_id="$2"

  oc create secret generic "$PLAYGROUND_SECRET" -n "$PROJECT_NS" \
    --from-literal=VLLM_API_TOKEN="$key" \
    --from-literal=MAAS_API_KEY_ID="$key_id" \
    --from-literal=MAAS_SUBSCRIPTION="$MAAS_SUBSCRIPTION" \
    --dry-run=client -o yaml | oc apply -f - --insecure-skip-tls-verify=true >/dev/null

  oc label secret "$PLAYGROUND_SECRET" -n "$PROJECT_NS" --overwrite \
    app.kubernetes.io/name="$PLAYGROUND_SECRET" \
    app.kubernetes.io/component=genai-playground \
    app.kubernetes.io/part-of=rhoai3-coding-demo \
    demo.rhoai.io/stage=220 \
    --insecure-skip-tls-verify=true >/dev/null

  echo "✓ Project Secret ${PROJECT_NS}/${PLAYGROUND_SECRET} contains a MaaS API key for the playground"
}

revoke_maas_api_key() {
  local token="$1"
  local host="$2"
  local key_id="$3"
  local status

  [[ -n "$key_id" ]] || return 0

  status=$(curl -sk --max-time 30 -o /dev/null -w '%{http_code}' \
    -X DELETE \
    -H "Authorization: Bearer ${token}" \
    "https://${host}/maas-api/v1/api-keys/${key_id}" \
    2>/dev/null || true)

  if [[ "$status" == "200" || "$status" == "204" || "$status" == "404" ]]; then
    echo "✓ Revoked stale MaaS API key ${key_id}"
    return 0
  fi

  echo "WARN: failed to revoke stale MaaS API key ${key_id} (status=${status})" >&2
  return 1
}

cleanup_duplicate_playground_api_keys() {
  local token="$1"
  local host="$2"
  local keep_id="$3"
  local strict="${4:-false}"
  local body status duplicate_ids key_id

  body=$(mktemp "${TMPDIR:-/tmp}/rhoai-playground-key-search.XXXXXX")
  TMP_FILES+=("$body")

  status=$(curl -sk --max-time 30 -o "$body" -w '%{http_code}' \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    "https://${host}/maas-api/v1/api-keys/search" \
    --data-binary "{\"name\":\"${PLAYGROUND_API_KEY_NAME}\"}" \
    2>/dev/null || true)

  if [[ "$status" != "200" ]]; then
    echo "WARN: could not search for duplicate playground MaaS API keys (status=${status})." >&2
    if [[ "$strict" == "true" ]]; then
      head -c 240 "$body" >&2 || true
      echo >&2
      return 1
    fi
    return 0
  fi

  duplicate_ids=$(jq -r --arg name "$PLAYGROUND_API_KEY_NAME" --arg keep "$keep_id" '
    .data[]? |
    select(.name == $name and .status == "active" and .id != $keep) |
    .id
  ' "$body" 2>/dev/null | sort -u || true)

  while IFS= read -r key_id; do
    [[ -n "$key_id" ]] || continue
    revoke_maas_api_key "$token" "$host" "$key_id" || true
  done <<<"$duplicate_ids"
}

patch_llamastack_env() {
  local patch

  patch=$(oc get llamastackdistribution "$PLAYGROUND_LSD_NAME" -n "$PROJECT_NS" \
    -o json --insecure-skip-tls-verify=true |
    jq -c --arg secret "$PLAYGROUND_SECRET" --arg max_tokens "$PLAYGROUND_VLLM_MAX_TOKENS" '
      (
      [.spec.server.containerSpec.env | to_entries[] |
       select(.value.name == "VLLM_API_TOKEN_1" or .value.name == "VLLM_API_TOKEN_2") |
       {
         op: "replace",
         path: ("/spec/server/containerSpec/env/" + (.key|tostring)),
         value: {
           name: .value.name,
           valueFrom: {secretKeyRef: {name: $secret, key: "VLLM_API_TOKEN"}}
         }
       }]
      )
      +
      (
        if any(.spec.server.containerSpec.env[]?; .name == "VLLM_MAX_TOKENS") then
          [.spec.server.containerSpec.env | to_entries[] |
           select(.value.name == "VLLM_MAX_TOKENS") |
           {
             op: "replace",
             path: ("/spec/server/containerSpec/env/" + (.key|tostring)),
             value: {name: "VLLM_MAX_TOKENS", value: $max_tokens}
           }]
        else
          [{
            op: "add",
            path: "/spec/server/containerSpec/env/-",
            value: {name: "VLLM_MAX_TOKENS", value: $max_tokens}
          }]
        end
      )
    ')

  if [[ "$patch" == "[]" ]]; then
    echo "ERROR: ${PROJECT_NS}/${PLAYGROUND_LSD_NAME} does not contain VLLM_API_TOKEN_1/2 env entries." >&2
    exit 1
  fi

  oc patch llamastackdistribution "$PLAYGROUND_LSD_NAME" -n "$PROJECT_NS" \
    --type=json -p "$patch" --insecure-skip-tls-verify=true >/dev/null

  echo "✓ LlamaStackDistribution reads MaaS tokens from ${PLAYGROUND_SECRET} and sets VLLM_MAX_TOKENS=${PLAYGROUND_VLLM_MAX_TOKENS}"
}

patch_llamastack_config() {
  local host tmp

  host="$(gateway_host)"
  tmp=$(mktemp "${TMPDIR:-/tmp}/rhoai-playground-config.XXXXXX")
  TMP_FILES+=("$tmp")

  oc get configmap "$PLAYGROUND_CONFIGMAP" -n "$PROJECT_NS" \
    -o jsonpath='{.data.config\.yaml}' \
    --insecure-skip-tls-verify=true > "$tmp"

  python3 - "$tmp" "$host" "$OPENAI_MODEL_RESOURCE" "$OPENAI_MODEL_ID" \
    "$NEMOTRON_MODEL_RESOURCE" "$PLAYGROUND_GPT_PROVIDER" "$PLAYGROUND_NEMOTRON_PROVIDER" \
    "$PLAYGROUND_VLLM_MAX_TOKENS" "$FORCE_OPENAI_PROVIDER_PATCH" <<'PY'
from pathlib import Path
import sys
import yaml

path, host, openai_resource, openai_model, nemotron_model, gpt_provider, nemotron_provider, vllm_max_tokens, force_openai_provider_patch = sys.argv[1:]
force_openai_provider_patch = force_openai_provider_patch == "true"
text = Path(path).read_text()
config = yaml.safe_load(text)
inference_providers = config["providers"]["inference"]
registered_models = config["registered_resources"]["models"]

def endpoint(resource):
    return f"https://{host}/models-as-a-service/{resource}/v1"

def provider_for_resource(resource, fallback):
    expected = endpoint(resource)
    for provider in inference_providers:
        if provider.get("config", {}).get("base_url") == expected:
            return provider["provider_id"]
    return fallback

gpt_provider = provider_for_resource(openai_resource, gpt_provider)
nemotron_provider = provider_for_resource(nemotron_model, nemotron_provider)

for provider in inference_providers:
    if force_openai_provider_patch and provider["provider_id"] == gpt_provider:
        provider["provider_type"] = "remote::openai"
        provider["config"] = {
            "api_key": "${env.VLLM_API_TOKEN_1:=fake}",
            "base_url": endpoint(openai_resource),
            "network": {"tls": {"verify": "${env.VLLM_TLS_VERIFY:=true}"}},
        }
    elif provider["provider_id"] == nemotron_provider:
        provider["provider_type"] = "remote::vllm"
        provider["config"] = {
            "api_token": "${env.VLLM_API_TOKEN_2:=fake}",
            "base_url": endpoint(nemotron_model),
            "max_tokens": "${env.VLLM_MAX_TOKENS:=" + vllm_max_tokens + "}",
            "tls_verify": "${env.VLLM_TLS_VERIFY:=true}",
        }

if force_openai_provider_patch:
    registered_models[:] = [
        model for model in registered_models
        if not (
            model.get("provider_id") in {gpt_provider, nemotron_provider}
            or model.get("model_id") in {
                openai_resource,
                openai_model,
                nemotron_model,
            }
        )
    ]

    def add_model(model_id, provider_id, provider_model_id, display_name=None):
        model = {
            "provider_id": provider_id,
            "model_id": model_id,
            "provider_model_id": provider_model_id,
            "model_type": "llm",
        }
        if display_name:
            model["metadata"] = {"display_name": display_name}
        registered_models.append(model)

    add_model(nemotron_model, nemotron_provider, nemotron_model)
    add_model(openai_model, gpt_provider, openai_model, openai_model)

checks = [
    any(p["provider_id"] == nemotron_provider and p["provider_type"] == "remote::vllm" for p in inference_providers),
    any(
        p["provider_id"] == nemotron_provider
        and p.get("config", {}).get("max_tokens") == "${env.VLLM_MAX_TOKENS:=" + vllm_max_tokens + "}"
        for p in inference_providers
    ),
]
if force_openai_provider_patch:
    checks.extend([
        any(p["provider_id"] == gpt_provider and p["provider_type"] == "remote::openai" for p in inference_providers),
        any(m.get("provider_id") == gpt_provider and m.get("provider_model_id") == openai_model for m in registered_models),
        any(m.get("provider_id") == nemotron_provider and m.get("provider_model_id") == nemotron_model for m in registered_models),
    ])
if not all(checks):
    raise SystemExit("failed to produce required Llama Stack provider/model mappings")

Path(path).write_text(yaml.safe_dump(config, sort_keys=False))
PY

  oc create configmap "$PLAYGROUND_CONFIGMAP" -n "$PROJECT_NS" \
    --from-file=config.yaml="$tmp" \
    --dry-run=client -o yaml | oc apply -f - --insecure-skip-tls-verify=true >/dev/null

  if [[ "$FORCE_OPENAI_PROVIDER_PATCH" == "true" ]]; then
    echo "✓ Llama Stack config uses vLLM for Nemotron and OpenAI-compatible provider for ${OPENAI_MODEL_ID} through MaaS"
  else
    echo "✓ Llama Stack config keeps dashboard provider mappings and sets Nemotron max_tokens default to ${PLAYGROUND_VLLM_MAX_TOKENS}"
  fi
}

recreate_playground_deployment() {
  oc annotate llamastackdistribution "$PLAYGROUND_LSD_NAME" -n "$PROJECT_NS" \
    "demo.rhoai.io/config-updated-at=$(date -u +%Y%m%dT%H%M%SZ)" \
    --overwrite --insecure-skip-tls-verify=true >/dev/null

  # The RHOAI 3.4 Llama Stack operator can fail to merge valueFrom over the
  # dashboard-created literal "fake" token env. Recreate the generated Deployment
  # so it is rendered from the corrected LlamaStackDistribution spec.
  oc delete deployment "$PLAYGROUND_LSD_NAME" -n "$PROJECT_NS" \
    --ignore-not-found=true --wait=true --insecure-skip-tls-verify=true >/dev/null

  for _ in $(seq 1 72); do
    if oc get deployment "$PLAYGROUND_LSD_NAME" -n "$PROJECT_NS" \
      --insecure-skip-tls-verify=true >/dev/null 2>&1 &&
      oc rollout status "deployment/${PLAYGROUND_LSD_NAME}" -n "$PROJECT_NS" \
        --timeout=10s --insecure-skip-tls-verify=true >/dev/null 2>&1; then
      echo "✓ Llama Stack deployment recreated and ready"
      return 0
    fi
    sleep 5
  done

  echo "ERROR: Llama Stack deployment did not become ready." >&2
  return 1
}

validate_playground_responses() {
  local output

  output=$(oc exec "deployment/${PLAYGROUND_LSD_NAME}" -n "$PROJECT_NS" -- python3 -c "
import json
import urllib.error
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:8321/v1/models', timeout=60) as resp:
    listed_models = json.loads(resp.read()).get('data', [])

def find_model_id(target):
    for item in listed_models:
        model_id = item.get('identifier') or item.get('id') or ''
        metadata = item.get('custom_metadata') or {}
        if metadata.get('provider_resource_id') == target or model_id == target or model_id.endswith('/' + target):
            return model_id
    raise RuntimeError(f'model target not listed: {target}')

models = [
    ('nemotron', find_model_id('${NEMOTRON_MODEL_RESOURCE}')),
    ('openai', find_model_id('${OPENAI_MODEL_ID}')),
]

for label, model in models:
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
            if resp.status == 200 and 'playground-ok' in body:
                print(f'OK {label}')
            else:
                print(f'FAIL {label}: status={resp.status} body={body[:240]}')
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')
        print(f'FAIL {label}: status={exc.code} body={body[:240]}')
    except Exception as exc:
        print(f'FAIL {label}: {exc!r}')
")

  echo "$output"
  grep -q "OK nemotron" <<<"$output"
  grep -q "OK openai" <<<"$output"
  echo "✓ Playground Responses API returns completions from Nemotron and ${OPENAI_MODEL_ID}"
}

if ! oc get llamastackdistribution "$PLAYGROUND_LSD_NAME" -n "$PROJECT_NS" \
  --insecure-skip-tls-verify=true >/dev/null 2>&1; then
  echo "ERROR: ${PROJECT_NS}/${PLAYGROUND_LSD_NAME} was not found." >&2
  echo "Create the Gen AI Playground from the RHOAI dashboard first, then rerun this helper." >&2
  exit 1
fi

if ! oc get configmap "$PLAYGROUND_CONFIGMAP" -n "$PROJECT_NS" \
  --insecure-skip-tls-verify=true >/dev/null 2>&1; then
  echo "ERROR: ${PROJECT_NS}/${PLAYGROUND_CONFIGMAP} was not found." >&2
  exit 1
fi

USER_TOKEN=$(get_demo_user_token)
HOST=$(gateway_host)
cleanup_duplicate_playground_api_keys "$USER_TOKEN" "$HOST" "" false
create_maas_api_key "$USER_TOKEN" "$HOST"
store_playground_api_key "$CREATED_API_KEY_VALUE" "$CREATED_API_KEY_ID"
cleanup_duplicate_playground_api_keys "$USER_TOKEN" "$HOST" "$CREATED_API_KEY_ID" false
patch_llamastack_env
patch_llamastack_config
recreate_playground_deployment
validate_playground_responses
echo "NOTE: This is a diagnostic repair path. Prefer recreating or updating the Playground through the RHOAI dashboard and validating with validate.sh before using provider rewrites."
