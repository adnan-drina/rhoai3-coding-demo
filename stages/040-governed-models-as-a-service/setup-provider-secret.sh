#!/usr/bin/env bash
# Ensures one external provider credential Secret in external-models (RHOAI_STAGE040_PROVIDER_SECRET, default
# openai-provider-api-key): reuses an existing owned Secret, copies the prior one from models-as-a-service, or
# creates it from OPENAI_API_KEY / ANTHROPIC_API_KEY / NVIDIA_API_KEY. RHOAI_STAGE040_ROTATE_PROVIDER_SECRET=true
# replaces the OpenAI key in place. Values only travel through pipes and jq's environment: never Git, arguments or
# output. Secret JSON is piped (printf | jq), not passed as a here-string, which bash 3.2 backs with a temp file.
# Usage: RHOAI_STAGE040_PROVIDER_SECRET=<name> stages/040-governed-models-as-a-service/setup-provider-secret.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

NS=external-models
APP=040-external-models
NAME="${RHOAI_STAGE040_PROVIDER_SECRET:-openai-provider-api-key}"
ROTATE=$(tr '[:upper:]' '[:lower:]' <<<"${RHOAI_STAGE040_ROTATE_PROVIDER_SECRET:-false}")
fail() { echo "ERROR: $*" >&2; exit 1; }
case "$NAME" in
    openai-provider-api-key) KEY_VAR=OPENAI_API_KEY ;;
    anthropic-provider-api-key) KEY_VAR=ANTHROPIC_API_KEY ;;
    nvidia-provider-api-key) KEY_VAR=NVIDIA_API_KEY ;;
    *) fail "Unreviewed provider credential $NAME" ;;
esac
[[ "$ROTATE" == true || "$ROTATE" == false ]] || fail "Rotation flag must be explicitly true or false"
[[ "$ROTATE" == false || "$NAME" == openai-provider-api-key ]] || fail "Explicit rotation is scoped to the OpenAI provider"
# The OpenAI key may also come from the older RHOAI_OPENAI_API_KEY name.
if [[ "$NAME" == openai-provider-api-key && -z "${OPENAI_API_KEY:-}" && -n "${RHOAI_OPENAI_API_KEY:-}" ]]; then
    export OPENAI_API_KEY="$RHOAI_OPENAI_API_KEY"
fi
export KEY_VAR
read_secret() { oc --request-timeout=10s get secret "$NAME" -n "$1" --ignore-not-found -o json; }

# The provider namespace comes from 040-external-models; wait for it (up to 5 minutes).
for attempt in $(seq 1 60); do
    tracking=$(oc --request-timeout=10s get namespace "$NS" --ignore-not-found \
        -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/tracking-id}{"|"}{.metadata.uid}')
    if [[ "$tracking" == *"|"?* ]]; then
        [[ "${tracking%|*}" == "$APP:/Namespace:openshift-gitops/$NS" ]] || fail "Provider namespace ownership differs"
        break
    fi
    (( attempt < 60 )) || fail "Provider namespace did not reconcile"
    sleep 5
done

target=$(read_secret "$NS")
if [[ -n "$target" ]]; then
    components=$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" names 040 --all | jq -R . | jq -s -c .)
    printf '%s' "$target" | jq -e --argjson apps "$components" '.metadata as $m
        | ($m.annotations["argocd.argoproj.io/tracking-id"] // "" | . == "" or (split(":")[0] as $a | $apps | index($a)))
        and ($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null
        and (.data["api-key"] // "" | length) > 0 and (.data["api-key"] | @base64d | length) > 0
        and $m.labels["inference.llm-d.ai/ipp-managed"] == "true"' >/dev/null ||
        fail "Existing provider credential is foreign, incomplete or lacks its native label"
    if [[ "$ROTATE" == true ]]; then
        [[ -n "${OPENAI_API_KEY:-}" ]] || fail "Fresh authorized OpenAI credential is unavailable"
        # JSON patch guarded by uid and resourceVersion; the new value comes from jq's environment.
        printf '%s' "$target" | jq -c '[{op: "test", path: "/metadata/uid", value: .metadata.uid},
            {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
            {op: "replace", path: "/data/api-key", value: ($ENV.OPENAI_API_KEY | @base64)}]' |
            oc --request-timeout=10s patch secret "$NAME" -n "$NS" --type=json --patch-file=/dev/stdin >/dev/null ||
            fail "Scoped provider credential rotation failed; response suppressed"
        read_secret "$NS" | jq -e --slurpfile before <(printf '%s' "$target") '$before[0] as $before
            | .metadata.uid == $before.metadata.uid
            and .metadata.labels == $before.metadata.labels and .type == $before.type
            and .data == ($before.data + {"api-key": ($ENV.OPENAI_API_KEY | @base64)})' >/dev/null ||
            fail "Provider identity, labels or readback differ after rotation"
        echo "PASS Authorized OpenAI credential matches the retained native Secret; identity and labels preserved."
    else
        echo "PASS Existing native provider credential reused without rotation."
    fi
    exit 0
fi

[[ "$ROTATE" == false ]] || fail "Explicit rotation requires the existing owned provider credential"
# New Secret: the prior credential from models-as-a-service if present, else the key from the environment.
prior=$(read_secret models-as-a-service)
if [[ -n "$prior" ]]; then
    printf '%s' "$prior" | jq -e '.metadata.deletionTimestamp == null and (.data["api-key"] // "" | @base64d | length) > 0' >/dev/null ||
        fail "Prior authorized credential is terminating or incomplete"
    source_json="$prior"
else
    [[ -n "${!KEY_VAR:-}" ]] || fail "Authorized provider credential is unavailable ($KEY_VAR)"
    source_json=$(jq -n '{data: {"api-key": ($ENV[$ENV.KEY_VAR] | @base64)}}')
fi
printf '%s' "$source_json" | jq --arg name "$NAME" --arg ns "$NS" '{apiVersion: "v1", kind: "Secret", type: "Opaque",
    metadata: {name: $name, namespace: $ns,
        labels: {"inference.llm-d.ai/ipp-managed": "true", "app.kubernetes.io/part-of": "rhoai3-coding-demo"}},
    data: {"api-key": .data["api-key"]}}' |
    oc --request-timeout=10s create -f - >/dev/null || fail "Native provider credential creation failed; inspect ownership before retry"
echo "PASS Authorized provider credential supplied through private standard input."
