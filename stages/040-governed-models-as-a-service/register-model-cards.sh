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

  # Registry schema alignment (matches the Stage 030 Nemotron pattern):
  # first-class fields for owner/provider/license/tasks; empty-value
  # customProperties render as dashboard labels; key=value properties carry
  # the extended model card.
  local props
  props=$(printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' \
    "$(prop qwen '')" \
    "$(prop code-generation '')" \
    "$(prop text-generation '')" \
    "$(prop tool-calling '')" \
    "$(prop validated '')" \
    "$(prop validated_by RedHatAI)" \
    "$(prop source_repo https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-FP8-dynamic)" \
    "$(prop architecture MoE-35B-A3B)" \
    "$(prop quantization FP8-dynamic)" \
    "$(prop context_window_deployed 32768)" \
    "$(prop primary_use coding-assistant)" \
    "$(prop capabilities 'code,reasoning,tool-calling,vision')")

  local rm_id
  rm_id=$(mr_post "/registered_models" '{
    "name": "'"$name"'",
    "description": "Qwen3.6 35B A3B (FP8-dynamic) - Red Hat AI validated mixture-of-experts model (35B total, 3B active) for coding, reasoning, and multimodal tasks. Quantized with llm-compressor for single-GPU serving on NVIDIA L40S; deployed with a 32K context window through the private vLLM runtime and published via MaaS as qwen3-6-35b-a3b.",
    "owner": "rhoai3-coding-demo",
    "provider": "Alibaba Cloud (Red Hat AI validated)",
    "license": "apache-2.0",
    "licenseLink": "https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-FP8-dynamic/blob/main/LICENSE",
    "tasks": ["text-generation", "code-generation"],
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

register_qwen27b() {
  local name="Qwen3.6-27B-FP8"
  local existing
  existing=$(mr_get "/registered_models" | jq -r --arg n "$name" '.items[]? | select(.name == $n) | .id' | head -1)
  if [[ -n "$existing" ]]; then
    log_success "Registered model already present: ${name} (id=${existing})"
    return 0
  fi

  local props
  props=$(printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' \
    "$(prop qwen '')" \
    "$(prop tool-calling '')" \
    "$(prop agent-orchestration '')" \
    "$(prop text-generation '')" \
    "$(prop validated '')" \
    "$(prop validated_by RedHatAI)" \
    "$(prop source_repo https://huggingface.co/RedHatAI/Qwen3.6-27B-FP8)" \
    "$(prop architecture dense-hybrid-GDN-27B)" \
    "$(prop quantization FP8-dynamic)" \
    "$(prop context_window_deployed 131072)" \
    "$(prop primary_use agent-orchestration)" \
    "$(prop capabilities 'tool-calling,code,reasoning,AA-tau2-0.94')")

  local rm_id
  rm_id=$(mr_post "/registered_models" '{
    "name": "'"$name"'",
    "description": "Qwen3.6 27B (FP8) - benchmark-selected platform agent-orchestrator: Artificial Analysis Intelligence 37, tau2-Bench 0.94, SWE-bench 77.2 (the tool-calling reliability the seat demands). Multimodal checkpoint served text-only (--language-model-only) on a single NVIDIA L40S with a 131K window and thinking-mode sampling defaults per the model card; published via MaaS as qwen3-6-27b.",
    "owner": "rhoai3-coding-demo",
    "provider": "Alibaba Cloud (Red Hat AI quantized)",
    "license": "apache-2.0",
    "licenseLink": "https://huggingface.co/RedHatAI/Qwen3.6-27B-FP8/blob/main/LICENSE",
    "tasks": ["text-generation", "code-generation"],
    "customProperties": {'"$props"'}
  }' | jq -r '.id // empty')
  [[ -n "$rm_id" ]] || { log_error "Failed to create registered model ${name}"; exit 1; }
  log_success "Created RegisteredModel ${name} (id=${rm_id})"

  local mv_id
  mv_id=$(mr_post "/model_versions" '{
    "name": "v1.0",
    "description": "Deployed as LLMInferenceService qwen3-6-27b in models-as-a-service (orchestrator seat; benchmark-driven replacement of granite-4.0-h-small). Source: hf://RedHatAI/Qwen3.6-27B-FP8 — no official modelcar published yet (graduation tracked in demo BACKLOG)",
    "author": "ai-admin",
    "registeredModelId": "'"$rm_id"'",
    "customProperties": {'"$(prop serving_runtime vLLM)"','"$(prop deployed_on 'RHOAI 3.4')"'}
  }' | jq -r '.id // empty')
  [[ -n "$mv_id" ]] || { log_error "Failed to create model version"; exit 1; }

  mr_post "/model_versions/${mv_id}/artifacts" '{
    "name": "v1.0",
    "description": "Hugging Face source (no official modelcar yet)",
    "uri": "hf://RedHatAI/Qwen3.6-27B-FP8",
    "artifactType": "model-artifact",
    "modelFormatName": "vLLM",
    "modelFormatVersion": "1"
  }' >/dev/null
  log_success "Qwen3.6 27B model card registered (version + OCI artifact)"
}

archive_granite() {
  # Benchmark-driven retirement (2026-07-25): Artificial Analysis tau2-Bench
  # 17% / Intelligence 11 disqualify it for the orchestrator seat despite
  # clean serving. Replaced by Qwen3.6-27B (tau2 0.94).
  local id
  id=$(mr_get "/registered_models" | jq -r '.items[]? | select(.name == "Granite-4.0-h-small-FP8-dynamic") | .id' | head -1)
  [[ -z "$id" ]] && { log_info "No granite card to archive"; return 0; }
  local state
  state=$(mr_get "/registered_models/${id}" | jq -r '.state // empty')
  [[ "$state" == "ARCHIVED" ]] && { log_success "Granite card already archived (id=${id})"; return 0; }
  curl -sk -X PATCH -H "Authorization: Bearer ${MR_TOKEN}" -H "Content-Type: application/json" \
    -d '{"state":"ARCHIVED","description":"Retired 2026-07-25 after benchmark review: tau2-Bench 17% / AA Intelligence 11 disqualify the orchestrator role (long-horizon tool calling). Served correctly; capability, not compatibility. Replaced by Qwen3.6-27B-FP8."}' \
    "${MR_BASE_URL}/registered_models/${id}" >/dev/null
  log_success "Granite card archived (id=${id})"
}

archive_gemma() {
  # Registered during the swap attempt but never served: the RHOAI 3.4
  # vLLM runtime's Transformers predates the gemma4 architecture. Archive
  # with the reason; revisit at RHOAI 3.5.
  local id
  id=$(mr_get "/registered_models" | jq -r '.items[]? | select(.name == "Gemma-4-26B-A4B-it-FP8-dynamic") | .id' | head -1)
  [[ -z "$id" ]] && { log_info "No gemma card to archive"; return 0; }
  local state
  state=$(mr_get "/registered_models/${id}" | jq -r '.state // empty')
  [[ "$state" == "ARCHIVED" ]] && { log_success "Gemma card already archived (id=${id})"; return 0; }
  curl -sk -X PATCH -H "Authorization: Bearer ${MR_TOKEN}" -H "Content-Type: application/json" \
    -d '{"state":"ARCHIVED","description":"Never served: RHOAI 3.4 vLLM runtime Transformers predates the gemma4 architecture (KeyError at engine start). Revisit when RHOAI 3.5 ships a newer runtime. Granite-4.0-h-small took the orchestrator seat instead."}' \
    "${MR_BASE_URL}/registered_models/${id}" >/dev/null
  log_success "Gemma card archived (id=${id})"
}

archive_nemotron() {
  # The nemotron serving instance was replaced by gemma (stage 080 harness
  # A/B, 2026-07-25). Registries keep records: archive, never delete.
  local id
  id=$(mr_get "/registered_models" | jq -r '.items[]? | select(.name == "NVIDIA-Nemotron-3-Nano-30B-A3B-FP8") | .id' | head -1)
  [[ -z "$id" ]] && { log_info "No nemotron card to archive"; return 0; }
  local state
  state=$(mr_get "/registered_models/${id}" | jq -r '.state // empty')
  if [[ "$state" == "ARCHIVED" ]]; then
    log_success "Nemotron card already archived (id=${id})"
    return 0
  fi
  curl -sk -X PATCH -H "Authorization: Bearer ${MR_TOKEN}" -H "Content-Type: application/json" \
    -d '{"state":"ARCHIVED","description":"Retired 2026-07-25: replaced by Gemma-4-26B-A4B in the orchestrator seat (stage 080 harness A/B showed nemotron nano unreliable for long-horizon tool calling). Kept as a registry record."}' \
    "${MR_BASE_URL}/registered_models/${id}" >/dev/null
  log_success "Nemotron card archived (id=${id})"
}

log_step "Registering private-model cards in ${REGISTRY_NAME}"
register_qwen
register_qwen27b
archive_granite
archive_gemma
archive_nemotron
log_info "Registry contents:"
mr_get "/registered_models" | jq -r '.items[].name'
