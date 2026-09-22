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

# The model registry Deployments tab matches an LLMInferenceService by these
# labels. Ids are assigned when the card is created, so a fresh registry
# restamps the service after registration. Argo CD ignores drift on them.
link_registry_deployment() {
  local rm_id="$1"
  local mv_id="$2"
  local llmis_name="$3"
  local llmis_ns="${4:-models-as-a-service}"
  [[ -n "$rm_id" && -n "$mv_id" ]] || { log_error "Cannot link ${llmis_name}: missing registry id"; exit 1; }
  if ! oc get llminferenceservice "$llmis_name" -n "$llmis_ns" >/dev/null 2>&1; then
    log_info "LLMInferenceService ${llmis_ns}/${llmis_name} is not present yet; labels will be applied when it exists"
    return 0
  fi
  oc label llminferenceservice "$llmis_name" -n "$llmis_ns" \
    "modelregistry.opendatahub.io/name=${REGISTRY_NAME}" \
    "modelregistry.opendatahub.io/registered-model-id=${rm_id}" \
    "modelregistry.opendatahub.io/model-version-id=${mv_id}" \
    --overwrite >/dev/null
  log_success "Linked ${llmis_name} to ${REGISTRY_NAME} model ${rm_id} version ${mv_id}"
}

latest_live_version_id() {
  local rm_id="$1"
  local prefer="${2:-}"
  local id=""
  if [[ -n "$prefer" ]]; then
    id=$(mr_get "/registered_models/${rm_id}/versions" | jq -r --arg n "$prefer" '.items[]? | select(.name == $n and (.state // "LIVE") != "ARCHIVED") | .id' | head -1)
  fi
  if [[ -z "$id" ]]; then
    id=$(mr_get "/registered_models/${rm_id}/versions" | jq -r '[.items[]? | select((.state // "LIVE") != "ARCHIVED")] | sort_by(.createTimeSinceEpoch) | last | .id // empty')
  fi
  printf '%s' "$id"
}

archive_qwen35b() {
  # The 35B coder card is no longer part of the demo registry. The model
  # registry removes a card from the active catalog by archiving it.
  local name="Qwen3.6-35B-A3B-FP8-dynamic"
  local id state
  id=$(mr_get "/registered_models" | jq -r --arg n "$name" '.items[]? | select(.name == $n) | .id' | head -1)
  [[ -z "$id" ]] && { log_info "No ${name} card to archive"; return 0; }
  state=$(mr_get "/registered_models/${id}" | jq -r '.state // empty')
  [[ "$state" == "ARCHIVED" ]] && { log_success "${name} already archived (id=${id})"; return 0; }
  local code
  code=$(curl -sk -o /tmp/qwen35b-archive.json -w '%{http_code}' -X PATCH \
    -H "Authorization: Bearer ${MR_TOKEN}" -H "Content-Type: application/json" \
    -d '{"state":"ARCHIVED","description":"Removed from the demo registry on 2026-09-22. The active private models are Qwen3.6-27B-FP8 and Qwen3.8-27B-INT4."}' \
    "${MR_BASE_URL}/registered_models/${id}")
  [[ "$code" == "200" ]] || { log_error "Failed to archive ${name} (HTTP ${code})"; cat /tmp/qwen35b-archive.json >&2; exit 1; }
  log_success "${name} archived (id=${id})"
}

register_qwen27b() {
  local name="Qwen3.6-27B-FP8"
  local existing
  existing=$(mr_get "/registered_models" | jq -r --arg n "$name" '.items[]? | select(.name == $n) | .id' | head -1)
  if [[ -n "$existing" ]]; then
    log_success "Registered model already present: ${name} (id=${existing})"
    link_registry_deployment "$existing" "$(latest_live_version_id "$existing")" qwen3-6-27b
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
  link_registry_deployment "$rm_id" "$mv_id" qwen3-6-27b
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

ensure_qwen38_version() {
  local rm_id="$1"
  local version_name="v1.0"
  local mv_id code
  mv_id=$(mr_get "/registered_models/${rm_id}/versions" | jq -r --arg n "$version_name" '.items[]? | select(.name == $n and (.state // "LIVE") != "ARCHIVED") | .id' | head -1)
  if [[ -z "$mv_id" ]]; then
    mv_id=$(mr_post "/model_versions" '{
      "name": "'"$version_name"'",
      "description": "Deployed as LLMInferenceService qwen3-8-27b-int4 in models-as-a-service. Source: hf://RedHatAI/Qwen3.8-27B-INT4 revision 7fb3aaca2d21c0db4716572945208db40cef9966. No official modelcar is listed in the validated-model matrix.",
      "author": "ai-admin",
      "registeredModelId": "'"$rm_id"'",
      "customProperties": {'"$(prop serving_runtime vLLM)"','"$(prop deployed_on 'RHOAI 3.4')"'}
    }' | jq -r '.id // empty')
    [[ -n "$mv_id" ]] || { log_error "Failed to create Qwen 3.8 model version"; exit 1; }
    mr_post "/model_versions/${mv_id}/artifacts" '{
      "name": "v1.0",
      "description": "Hugging Face source pinned to revision 7fb3aaca2d21c0db4716572945208db40cef9966",
      "uri": "hf://RedHatAI/Qwen3.8-27B-INT4:7fb3aaca2d21c0db4716572945208db40cef9966",
      "artifactType": "model-artifact",
      "modelFormatName": "vLLM",
      "modelFormatVersion": "1"
    }' >/dev/null
    log_success "Qwen 3.8 version v1.0 registered (id=${mv_id})"
  else
    log_success "Qwen 3.8 version v1.0 already present (id=${mv_id})"
  fi

  # Version names cannot be edited. Archive the earlier hash-named version
  # so the catalog's latest version is v1.0.
  local old_id
  old_id=$(mr_get "/registered_models/${rm_id}/versions" | jq -r '.items[]? | select(.name == "7fb3aaca2d21" and (.state // "LIVE") != "ARCHIVED") | .id' | head -1)
  if [[ -n "$old_id" ]]; then
    code=$(curl -sk -o /tmp/qwen38-archive-version.json -w '%{http_code}' -X PATCH \
      -H "Authorization: Bearer ${MR_TOKEN}" -H "Content-Type: application/json" \
      -d '{"state":"ARCHIVED"}' \
      "${MR_BASE_URL}/model_versions/${old_id}")
    [[ "$code" == "200" ]] || { log_error "Failed to archive Qwen 3.8 hash version (HTTP ${code})"; cat /tmp/qwen38-archive-version.json >&2; exit 1; }
    log_success "Archived Qwen 3.8 version 7fb3aaca2d21 (id=${old_id})"
  fi
  link_registry_deployment "$rm_id" "$mv_id" qwen3-8-27b-int4
}

register_qwen38() {
  local name="Qwen3.8-27B-INT4"
  local existing
  existing=$(mr_get "/registered_models" | jq -r --arg n "$name" '.items[]? | select(.name == $n and (.state // "LIVE") != "ARCHIVED") | .id' | head -1)
  if [[ -n "$existing" ]]; then
    ensure_qwen38_version "$existing"
    return 0
  fi

  local props
  props=$(printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' \
    "$(prop qwen '')" \
    "$(prop tool-calling '')" \
    "$(prop text-generation '')" \
    "$(prop code-generation '')" \
    "$(prop source_repo https://huggingface.co/RedHatAI/Qwen3.8-27B-INT4)" \
    "$(prop revision 7fb3aaca2d21c0db4716572945208db40cef9966)" \
    "$(prop architecture Qwen3_5-dense-hybrid-27B)" \
    "$(prop quantization compressed-tensors-INT4)" \
    "$(prop context_window_deployed 262144)" \
    "$(prop primary_use coding-assistant)" \
    "$(prop support_classification locally-demonstrated)")

  local rm_id
  rm_id=$(mr_post "/registered_models" '{
    "name": "'"$name"'",
    "description": "Qwen3.8 27B (INT4, compressed-tensors) served text-only on one NVIDIA L40S and published via MaaS as qwen3-8-27b-int4. Pinned revision 7fb3aaca2d21c0db4716572945208db40cef9966. This card records locally demonstrated compatibility with the installed RHOAI 3.4 vLLM runtime. It is not a Red Hat validated-model-matrix entry.",
    "owner": "rhoai3-coding-demo",
    "provider": "Alibaba Cloud (Red Hat AI quantized)",
    "license": "apache-2.0",
    "licenseLink": "https://huggingface.co/RedHatAI/Qwen3.8-27B-INT4/blob/main/LICENSE",
    "tasks": ["text-generation", "code-generation"],
    "customProperties": {'"$props"'}
  }' | jq -r '.id // empty')
  [[ -n "$rm_id" ]] || { log_error "Failed to create registered model ${name}"; exit 1; }
  log_success "Created RegisteredModel ${name} (id=${rm_id})"
  ensure_qwen38_version "$rm_id"
}

log_step "Registering private-model cards in ${REGISTRY_NAME}"
archive_qwen35b
register_qwen27b
register_qwen38
archive_granite
archive_gemma
archive_nemotron
log_info "Registry contents:"
mr_get "/registered_models" | jq -r '.items[] | "\(.state // "LIVE") \(.name)"'
