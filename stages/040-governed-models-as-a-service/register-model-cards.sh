#!/usr/bin/env bash
# Registers the deployed local model, and every prepared format alternate under 040-local-models/components, in the
# demo model registry: one registered model per checkpoint (title = repository name), one version per immutable
# revision, one artifact. Links the deployment to its record through labels. Idempotent; never overwrites or
# archives existing records.
# Usage: stages/040-governed-models-as-a-service/register-model-cards.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

NS=internal-models
REGISTRY=demo-registry
LOCAL_MODELS="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-local-models"
fail() { echo "ERROR: registry publication stopped: $*" >&2; exit 1; }
yaml_stream_json() { ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)'; }

revision="${RHOAI_STAGE040_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || fail "reviewed immutable source differs"
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" status 040 --revision "$revision" --repo-url "$GIT_REPO_URL" >/dev/null ||
    fail "Stage 040 must reconcile before model registration"
host=$(oc --request-timeout=10s get modelregistries.modelregistry.opendatahub.io "$REGISTRY" -n rhoai-model-registries \
    -o jsonpath='{.status.hosts[0]}')
BASE="https://$host/api/model_registry/v1alpha3"
TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin

# Authenticated, CA-verified registry call; redirects are not followed. Prints the JSON response.
api() {
    local path=$1 body=${2:-}
    printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" |
        curl --config - -sf --max-time 20 -H 'Content-Type: application/json' ${body:+--data "$body"} "$BASE$path" ||
        fail "authenticated registry request failed"
}
# Every item of a paginated listing (at most 100 pages), as one JSON array.
items() {
    local path=$1 cursor="" page all='[]'
    for _ in $(seq 1 100); do
        page=$(api "$path${cursor:+?nextPageToken=$(jq -rn --arg c "$cursor" '$c | @uri')}")
        all=$(jq -c --argjson all "$all" '$all + (.items // [])' <<<"$page")
        cursor=$(jq -r '.nextPageToken // ""' <<<"$page")
        [[ -z "$cursor" ]] && { echo "$all"; return; }
    done
    fail "registry pagination exceeded its bound"
}
# Ensure model, version and artifact for one pinned source URI; prints "<title> <model id> <version id>".
register() {
    local uri=$1 title revision quant model version artifacts
    title=${uri##*/}
    title=${title%%:*}
    revision=${uri##*:}
    [[ ${#revision} == 40 ]] || fail "model source must be immutable"
    case "$(tr '[:lower:]' '[:upper:]' <<<"$title")" in
        *-NVFP4) quant="NVFP4 (FP4 weights, FP8 attention)" ;;
        *-FP8) quant="FP8 block-128" ;;
        *-INT4) quant="INT4 W4A16" ;;
        *) quant="unquantized" ;;
    esac
    model=$(items /registered_models | jq -c --arg t "$title" '[.[] | select(.name == $t)]')
    [[ $(jq length <<<"$model") -le 1 ]] || fail "ambiguous registered model name"
    if [[ $(jq length <<<"$model") == 0 ]]; then
        local location=${uri#*://}
        model=$(api /registered_models "$(jq -n --arg t "$title" --arg q "$quant" --arg l "${location%%:*}" '{name: $t,
            owner: "rhoai3-coding-demo", description: ("Quantization: \($q). Pinned model artifact used by the project (\($l)). "
            + "Runtime and GPU compatibility are qualified separately; this is not a Red Hat validated-model claim.")}')")
    else
        model=$(jq -c '.[0]' <<<"$model")
    fi
    local model_id
    model_id=$(jq -r '.id' <<<"$model")
    version=$(items "/registered_models/$model_id/versions" | jq -c --arg v "source-$revision" '[.[] | select(.name == $v)]')
    [[ $(jq length <<<"$version") -le 1 ]] || fail "ambiguous registered model version"
    if [[ $(jq length <<<"$version") == 0 ]]; then
        version=$(api /model_versions "$(jq -n --arg v "source-$revision" --arg m "$model_id" --arg q "$quant" --arg r "$revision" \
            '{name: $v, registeredModelId: $m, description: "Quantization: \($q). Immutable source \($r)"}')")
    else
        version=$(jq -c '.[0]' <<<"$version")
    fi
    local version_id
    version_id=$(jq -r '.id' <<<"$version")
    artifacts=$(items "/model_versions/$version_id/artifacts")
    jq -e --arg u "$uri" 'length == 0 or (length == 1 and .[0].uri == $u)' <<<"$artifacts" >/dev/null ||
        fail "existing version artifact differs; no overwrite"
    if [[ $(jq length <<<"$artifacts") == 0 ]]; then
        api "/model_versions/$version_id/artifacts" "$(jq -n --arg u "$uri" '{name: "model-source", uri: $u,
            artifactType: "model-artifact", modelFormatName: "vLLM", modelFormatVersion: "1"}')" >/dev/null
    fi
    echo "$title $model_id $version_id"
}

# Deployed models: register the source Git declares and link the deployment to its record.
rendered=$(oc kustomize "$LOCAL_MODELS" | yaml_stream_json)
active=""
for name in qwen3-8-27b; do
    uri=$(jq -r --arg n "$name" '.[] | select(.kind == "LLMInferenceService" and .metadata.name == $n) | .spec.model.uri' <<<"$rendered")
    llmi=$(oc --request-timeout=10s get llminferenceservices.serving.kserve.io "$name" -n "$NS" -o json)
    jq -e --arg u "$uri" '.spec.model.uri == $u
        and (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("040-local-models:"))
        and (.metadata.generation | type) == "number" and .status.observedGeneration == .metadata.generation' \
        <<<"$llmi" >/dev/null || fail "$name source, ownership or readiness differs"
    parked=$(jq -r '.spec.replicas == 0' <<<"$llmi")
    [[ "$parked" == true ]] || jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' <<<"$llmi" >/dev/null ||
        fail "active model $name must be Ready before registry publication"
    registered=$(register "$uri")  # captured, so a failure stops the script (set -e)
    read -r title model_id version_id <<<"$registered"
    active+=" $name=$uri"
    existing=$(jq -r '.metadata.labels["modelregistry.opendatahub.io/registered-model-id"] // ""' <<<"$llmi")
    if [[ -n "$existing" && "$existing" != "$model_id" ]]; then
        # Relink only for a format switch: the linked record must be another checkpoint, never a same-name duplicate.
        linked=$(api "/registered_models/$existing" | jq -r '.name // "?"')
        [[ "$linked" != "$title" ]] || fail "existing model registry identity differs; no reassignment"
        echo "NOTE Format switch: deployment relinked from $linked to $title"
    fi
    jq -c --arg r "$REGISTRY" --arg m "$model_id" --arg v "$version_id" '[
        {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
        {op: "add", path: "/metadata/labels", value: ((.metadata.labels // {}) + {"modelregistry.opendatahub.io/name": $r,
            "modelregistry.opendatahub.io/registered-model-id": $m, "modelregistry.opendatahub.io/model-version-id": $v})}]' \
        <<<"$llmi" | oc --request-timeout=10s patch llminferenceservices.serving.kserve.io "$name" -n "$NS" \
        --type=json --patch-file=/dev/stdin >/dev/null || fail "deployment linkage patch failed"
    if [[ "$parked" == true ]]; then
        echo "PASS Registered pinned metadata; parked runtime not qualified: $name -> $title"
    else
        echo "PASS Registered pinned source and native deployment linkage: $name -> $title"
    fi
done

# Prepared alternates: each format component registers its artifact (no deployment linkage), so the registry
# lists every build that can be switched on.
for component in "$LOCAL_MODELS"/components/*/; do
    component=$(basename "$component")
    work=$(mktemp -d)
    cp -R "$LOCAL_MODELS" "$work/local-models"
    printf '\ncomponents:\n  - components/%s\n' "$component" >>"$work/local-models/kustomization.yaml"
    alternates=$(oc kustomize "$work/local-models" | yaml_stream_json |
        jq -r '.[] | select(.kind == "LLMInferenceService") | "\(.metadata.name)=\(.spec.model.uri)"')
    rm -rf "$work"
    for entry in $alternates; do
        [[ "$active" == *" $entry"* ]] && continue
        registered=$(register "${entry#*=}")
        read -r title _ _ <<<"$registered"
        echo "PASS Registered prepared alternate (component $component, not deployed): $title"
    done
done
