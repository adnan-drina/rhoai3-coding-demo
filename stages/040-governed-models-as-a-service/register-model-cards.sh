#!/usr/bin/env bash
# Stage 040: register/enrich private-model cards in the RHOAI model registry.
# Uses the authenticated HTTPS registry route (the Stage 030 pattern); the
# in-cluster plain-HTTP seed job was retired because the migrated registry
# only exposes TLS on 8443 behind an auth proxy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

load_env
check_oc_logged_in

REGISTRY_NAME="demo-registry"
REGISTRY_NS="rhoai-model-registries"

MR_HOST="$(oc get modelregistries.modelregistry.opendatahub.io "$REGISTRY_NAME" -n "$REGISTRY_NS" -o jsonpath='{.status.hosts[0]}')"
[[ -n "$MR_HOST" ]] || { log_error "demo-registry has no route host"; exit 1; }
MR_BASE_URL="https://${MR_HOST}/api/model_registry/v1alpha3"
MR_TOKEN="$(oc whoami -t)"

mr_get()  { curl -sk -H "Authorization: Bearer ${MR_TOKEN}" "${MR_BASE_URL}$1"; }
mr_post() { curl -sk -X POST -H "Authorization: Bearer ${MR_TOKEN}" -H "Content-Type: application/json" -d "$2" "${MR_BASE_URL}$1"; }

prop() { printf '"%s":{"metadataType":"MetadataStringValue","string_value":"%s"}' "$1" "$2"; }

register_qwen() {
  local name="Qwen3.6-35B-A3B-FP8-dynamic"
  local existing
  existing=$(mr_get "/registered_models" | jq -r --arg n "$name" '.items[]? | select(.name == $n) | .id' | head -1)
  if [[ -n "$existing" ]]; then
    log_success "Registered model already present: ${name} (id=${existing})"
    return 0
  fi

  local props
  props=$(printf '%s,%s,%s,%s,%s,%s,%s,%s,%s' \
    "$(prop provider Alibaba-Qwen)" \
    "$(prop validated_by RedHatAI)" \
    "$(prop source_repo https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-FP8-dynamic)" \
    "$(prop license apache-2.0)" \
    "$(prop architecture MoE-35B-A3B)" \
    "$(prop quantization FP8-dynamic)" \
    "$(prop context_window_deployed 32768)" \
    "$(prop primary_use coding-assistant)" \
    "$(prop capabilities 'code,reasoning,tool-calling,vision')")

  local rm_id
  rm_id=$(mr_post "/registered_models" '{
    "name": "'"$name"'",
    "description": "Qwen3.6 35B A3B (FP8-dynamic) - Red Hat AI validated mixture-of-experts model (35B total, 3B active) for coding, reasoning, and multimodal tasks. Quantized with llm-compressor for single-GPU serving on NVIDIA L40S; deployed with a 32K context window through the private vLLM runtime and published via MaaS as qwen3-6-35b-a3b.",
    "owner": "ai-admin",
    "customProperties": {'"$props"'}
  }' | jq -r '.id // empty')
  [[ -n "$rm_id" ]] || { log_error "Failed to create registered model ${name}"; exit 1; }
  log_success "Created RegisteredModel ${name} (id=${rm_id})"

  local mv_id
  mv_id=$(mr_post "/model_versions" '{
    "name": "v3.0",
    "description": "Deployed as LLMInferenceService qwen3-6-35b-a3b in models-as-a-service",
    "author": "ai-admin",
    "registeredModelId": "'"$rm_id"'",
    "customProperties": {'"$(prop serving_runtime vLLM)"','"$(prop deployed_on 'RHOAI 3.4')"'}
  }' | jq -r '.id // empty')
  [[ -n "$mv_id" ]] || { log_error "Failed to create model version"; exit 1; }

  mr_post "/model_versions/${mv_id}/artifacts" '{
    "name": "v3.0",
    "description": "OCI modelcar image",
    "uri": "oci://registry.redhat.io/rhai/modelcar-redhatai-qwen3-6-35b-a3b-fp8-dynamic:3.0",
    "artifactType": "model-artifact",
    "modelFormatName": "vLLM",
    "modelFormatVersion": "1"
  }' >/dev/null
  log_success "Qwen3.6 model card registered (version + OCI artifact)"
}

log_step "Registering private-model cards in ${REGISTRY_NAME}"
register_qwen
log_info "Registry contents:"
mr_get "/registered_models" | jq -r '.items[].name'
