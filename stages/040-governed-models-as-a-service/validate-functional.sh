#!/usr/bin/env bash
# Explicit, bounded MaaS functional check (never run by deployment polling). As an existing persona login, creates
# one synthetic expiring API key, checks each reviewed model in the persona catalog (fail-closed without and with an
# invalid key, a completion with usage, an incremental SSE stream, a GPT-6 Luna tool call, the local traffic metric),
# then revokes that key and proves it is refused. Writes sanitized evidence (no tokens, URLs or response text).
# No model or workload creation, provider-key access, browser operation or load test.
# Inputs: RHOAI_STAGE040_PERSONA_KUBECONFIG (private ai-admin or ai-developer login, required),
#   RHOAI_STAGE040_MODEL (one model), RHOAI_STAGE040_SINGLE_COMPLETION=true (one completion, needs a model),
#   RHOAI_STAGE040_TEST_EXTERNAL=false (skip external models: result pending), RHOAI_STAGE040_SUBSCRIPTION,
#   RHOAI_STAGE040_CA_BUNDLE (extra CA file), RHOAI_STAGE040_EVIDENCE_PATH (new file under /private/tmp).
# Exit codes: 0 pass, 1 fail, 2 pending. API contract: shipped MaaS 563117f1/openapi3.yaml.
# Usage: RHOAI_STAGE040_PERSONA_KUBECONFIG=<file> stages/040-governed-models-as-a-service/validate-functional.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

fail() { echo "[FAIL] $*"; exit 1; }
pending() { echo "[PENDING] $*"; exit 2; }
# Native readiness first: a functional run never creates a key on an unready stage.
"$SCRIPT_DIR/validate-native.sh" >/dev/null || fail "Native readiness failed (run validate-native.sh)"

PERSONA="${RHOAI_STAGE040_PERSONA_KUBECONFIG:-}"
[[ -n "$PERSONA" ]] || pending "Set RHOAI_STAGE040_PERSONA_KUBECONFIG to an existing private ai-admin or ai-developer login"
[[ -f "$PERSONA" && -z "$(find "$PERSONA" -maxdepth 0 \( -perm -001 -o -perm -002 -o -perm -004 -o -perm -010 -o -perm -020 -o -perm -040 \))" ]] ||
    fail "Persona kubeconfig must be a private existing login"
KUBECONFIG="$PERSONA" bash -c 'source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in' guard "$REPO_ROOT" >/dev/null 2>&1 ||
    fail "Persona cluster guard failed"
WHO=$(KUBECONFIG="$PERSONA" oc --request-timeout=10s whoami)
[[ "$WHO" == ai-admin || "$WHO" == ai-developer ]] || fail "Persona is not an approved demo user"
USER_TOKEN=$(KUBECONFIG="$PERSONA" oc --request-timeout=10s whoami -t)  # memory only
ADMIN_TOKEN=$(oc whoami -t)  # memory only: Thanos metric reads

GATEWAY=$(oc --request-timeout=10s get gateway maas-default-gateway -n openshift-ingress -o json)
API_HOST=$(jq -r '.spec.listeners[] | select(.name == "api") | .hostname' <<<"$GATEWAY")
LOCAL_HOST=$(jq -r '.spec.listeners[] | select(.name == "qwen3-8") | .hostname' <<<"$GATEWAY")
BASE="https://$API_HOST"
CA_ARGS=()
[[ -n "${RHOAI_STAGE040_CA_BUNDLE:-}" ]] && CA_ARGS=(--cacert "$RHOAI_STAGE040_CA_BUNDLE")  # extra public CA only
EVIDENCE="${RHOAI_STAGE040_EVIDENCE_PATH:-/private/tmp/stage040-functional-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4).json}"
case "$(cd "$(dirname "$EVIDENCE")" 2>/dev/null && pwd -P)/" in /private/tmp/*) ;; *) fail "Use a new private evidence path under /private/tmp" ;; esac
[[ ! -e "$EVIDENCE" && ! -L "$EVIDENCE" ]] || fail "Evidence path already exists"
WORK=$(mktemp -d)
umask 077

# HTTPS request; credentials reach curl only through --config on stdin. Prints the HTTP status; body in $WORK/body.
# Arguments: METHOD URL [token kind: user|key|invalid|none] [JSON body file]. Redirects are never followed.
http() {
    local method=$1 url=$2 auth=${3:-none} body=${4:-} header=""
    case "$auth" in
        user) header="Authorization: Bearer $USER_TOKEN" ;;
        key) header="Authorization: Bearer $API_KEY" ;;
        admin) header="Authorization: Bearer $ADMIN_TOKEN" ;;
        invalid) header="Authorization: Bearer stage040-invalid-$(openssl rand -hex 16)" ;;
    esac
    { [[ -n "$header" ]] && printf 'header = "%s"\n' "$header"; true; } |
        curl --config - -s --max-time 90 ${CA_ARGS[@]+"${CA_ARGS[@]}"} -X "$method" -H 'Accept: application/json' \
            ${body:+-H 'Content-Type: application/json' --data-binary "@$body"} -o "$WORK/body" -w '%{http_code}' "$url" ||
        echo 000
}
# GET/POST expecting one status; prints the JSON body.
api() {
    local status
    status=$(http "$@")
    [[ "$status" == "${EXPECT:-200}" ]] || { echo "HTTP $status" >&2; return 1; }
    cat "$WORK/body"
}
json_file() { local f; f=$(mktemp "$WORK/req.XXXX"); cat >"$f"; echo "$f"; }

DESIRED=$(oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" |
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)')
REFS=$(jq -c --arg sel "${RHOAI_STAGE040_MODEL:-}" '[.[] | select(.kind == "MaaSModelRef")
    | select($sel == "" or .metadata.name == $sel)] | sort_by([.metadata.namespace == "external-models", .metadata.name])' <<<"$DESIRED")
SINGLE=$(tr '[:upper:]' '[:lower:]' <<<"${RHOAI_STAGE040_SINGLE_COMPLETION:-false}")
[[ -z "${RHOAI_STAGE040_MODEL:-}" || $(jq length <<<"$REFS") == 1 ]] || fail "Selected model must uniquely match a reviewed model reference"
[[ "$SINGLE" != true || -n "${RHOAI_STAGE040_MODEL:-}" ]] || fail "Single-completion qualification requires an explicit model"
[[ $(jq length <<<"$REFS") -ge 1 && $(jq length <<<"$REFS") -le 5 ]] || fail "Functional model count exceeds the reviewed bounded scope"
SUBSCRIPTION="${RHOAI_STAGE040_SUBSCRIPTION:-personal-$WHO}"
api GET "$BASE/v1/subscriptions" user | jq -e --arg s "$SUBSCRIPTION" 'type == "array" and any(.[]; .subscription_id_header == $s)' \
    >/dev/null || fail "Persona cannot discover the intended subscription"

# Sanitized evidence, written once on exit.
jq -n --arg who "$WHO" --arg model "${RHOAI_STAGE040_MODEL:-}" --argjson single "$([[ "$SINGLE" == true ]] && echo true || echo false)" \
    '{timestamp: (now | todate), persona: $who, selected_model: (if $model == "" then null else $model end), single_completion: $single,
      scope: "bounded authenticated API only; Studio browser and per-request EPP selection remain separate",
      models: [], model_http_failures: [], key_revoked: false,
      not_qualified: (["quota enforcement", "per-request EPP invocation", "Studio visual acceptance"]
        + (if $single then ["streaming", "tool calling", "unselected models"] else [] end))}' >"$WORK/evidence.json"
evidence() { jq "$@" "$WORK/evidence.json" >"$WORK/evidence.next" && mv "$WORK/evidence.next" "$WORK/evidence.json"; }
FAILED=false
PENDING_EXTERNAL=false
KEY_ID=""
API_KEY=""
REVOKE_URL=""
REVOKE_BODY=""
finish() {
    local status=$? revoked
    if [[ -n "$KEY_ID" ]]; then
        revoked=$(api DELETE "$BASE/v1/api-keys/$(jq -rn --arg i "$KEY_ID" '$i | @uri')" user 2>/dev/null || echo '{}')
        if jq -e --arg i "$KEY_ID" '.id == $i and .status == "revoked"' <<<"$revoked" >/dev/null; then
            evidence '.key_revoked = true'
            if [[ -n "$REVOKE_URL" ]] && [[ $(http POST "$REVOKE_URL" key "$REVOKE_BODY") =~ ^40[13]$ ]]; then
                evidence '.revoked_key_inference_denied = true'
            elif [[ -n "$REVOKE_URL" ]]; then
                echo "[FAIL] Revoked synthetic key inference was not denied"; FAILED=true
            fi
        else
            echo "[FAIL] Synthetic key revocation failed; use the recorded synthetic key id for scoped cleanup"; FAILED=true
        fi
    fi
    [[ $status == 0 ]] || FAILED=true
    evidence --argjson failed "$FAILED" --argjson skipped "$PENDING_EXTERNAL" '.passed = (($failed | not) and ($skipped | not)) | .external_skipped = $skipped'
    set -o noclobber
    cat "$WORK/evidence.json" >"$EVIDENCE"
    rm -rf "$WORK"
    echo "Sanitized functional evidence saved to $EVIDENCE; no tokens, URLs or response text included"
    if [[ "$FAILED" == true ]]; then echo "[FAIL] One or more bounded checks failed"; exit 1; fi
    if [[ "$PENDING_EXTERNAL" == true ]]; then echo "[PENDING] External inference was skipped; full API acceptance pending"; exit 2; fi
    echo "[PASS] Bounded API functional checks and synthetic key revocation. Quota enforcement, Studio visual acceptance and per-request EPP selection remain unqualified."
    exit 0
}
trap finish EXIT

created=$(jq -n --arg s "$SUBSCRIPTION" --arg n "stage040-validation-$(openssl rand -hex 6)" \
    '{name: $n, subscription: $s, expiresIn: "1h", ephemeral: true}' | json_file)
EXPECT=201 api POST "$BASE/v1/api-keys" user "$created" >"$WORK/created.json" || { echo "[FAIL] Synthetic key creation failed"; exit 1; }
KEY_ID=$(jq -r '.id // ""' "$WORK/created.json")
[[ -n "$KEY_ID" ]] || { echo "[FAIL] Synthetic key identifier absent; expiry limits residual lifecycle risk"; exit 1; }
jq -e --arg s "$SUBSCRIPTION" '(.key // "") != "" and .subscription == $s and .ephemeral == true' "$WORK/created.json" >/dev/null ||
    { echo "[FAIL] Synthetic key contract is incomplete"; exit 1; }
API_KEY=$(jq -r '.key' "$WORK/created.json")
rm -f "$WORK/created.json"
evidence --arg id "$KEY_ID" '.synthetic_key_id = $id'  # identifier only, never the key or its prefix

# Persona catalog, independent of the synthetic key.
CATALOG=$(api GET "$BASE/v1/models" user) || { echo "[FAIL] Persona model catalog request failed"; exit 1; }
jq -e '.data | type == "array"' <<<"$CATALOG" >/dev/null || { echo "[FAIL] Native model catalog response is invalid"; exit 1; }

# Local Qwen traffic counter from the native Thanos route.
counter() {
    local host query
    host=$(oc --request-timeout=10s get route thanos-querier -n openshift-monitoring -o jsonpath='{.spec.host}')
    query="sum(vllm:request_success_total{namespace=\"internal-models\",model_name=\"$1\"})"
    EXPECT=200 api GET "https://$host/api/v1/query?query=$(jq -rn --arg q "$query" '$q | @uri')" admin |
        jq -r 'if .status == "success" then ([.data.result[].value[1] | tonumber] | add // 0) else error("query") end'
}
# Streams a chat completion; proves incremental delivery from curl's per-chunk receive timestamps (wire arrival).
stream_check() {
    local url=$1 body=$2 trace="$WORK/trace" out="$WORK/stream"
    printf 'header = "Authorization: Bearer %s"\n' "$API_KEY" |
        curl --config - -sN --max-time 120 ${CA_ARGS[@]+"${CA_ARGS[@]}"} -H 'Content-Type: application/json' \
            --data-binary "@$body" --trace-ascii "$trace" --trace-time -o "$out" -w '%{http_code} %{content_type}' "$url" \
        >"$WORK/stream.status" || return 1
    grep -q '^200 text/event-stream' "$WORK/stream.status" || return 1
    [[ $(wc -c <"$out") -le 2097152 ]] || return 1
    # SSE events: content fragments, a final usage, the [DONE] marker; no error events.
    sed -n 's/^data: *//p' "$out" | grep -v '^\[DONE\]$' | jq -s -e '
        (map(select(.error)) | length) == 0
        and ([.[].usage | select(.)] | last | .total_tokens // 0) > 0' >/dev/null || return 1
    grep -q '^data: *\[DONE\]' "$out" || return 1
    # Receive timestamps (HH:MM:SS.micro) of data chunks; at least two distinct, at least 20 ms apart.
    grep -E '^[0-9:.]+ <= Recv data' "$trace" | awk '{split($1, t, ":"); print t[1] * 3600 + t[2] * 60 + t[3]}' |
        awk 'NR == 1 {first = $1} {last = $1; n++} END {exit !(n >= 2 && last - first >= 0.02)}' || return 1
    sed -n 's/^data: *//p' "$out" | grep -v '^\[DONE\]$' | jq -s -c --arg sha "$(sed -n 's/^data: *//p' "$out" | grep -v '^\[DONE\]$' |
        jq -j '.choices[]?.delta | (.content // .reasoning_content // "")' | shasum -a 256 | cut -d' ' -f1)" '{
        content_chunks: ([.[].choices[]?.delta | select((.content // .reasoning_content // "") != "")] | length),
        total_tokens: ([.[].usage | select(.)] | last | .total_tokens), response_sha256: $sha,
        delivery: "incremental (curl receive timestamps)"}'
}

while IFS= read -r ref; do
    name=$(jq -r '.metadata.name' <<<"$ref")
    ns=$(jq -r '.metadata.namespace' <<<"$ref")
    external=false; [[ "$ns" == external-models ]] && external=true
    if [[ "$external" == true && $(tr '[:upper:]' '[:lower:]' <<<"${RHOAI_STAGE040_TEST_EXTERNAL:-true}") != true ]]; then
        PENDING_EXTERNAL=true; continue
    fi
    if [[ "$external" == true ]]; then
        model_id=$(jq -r '.spec.modelRef.name' <<<"$ref")
        host=$API_HOST
    else
        model_id=$(jq -r --arg ns "$ns" --arg n "$(jq -r '.spec.modelRef.name' <<<"$ref")" '[.[] | select(.kind == "LLMInferenceService"
            and .metadata.namespace == $ns and .metadata.name == $n)] | if length == 1 then "publishers/\($ns)/models/\(.[0].spec.model.name)" else "" end' <<<"$DESIRED")
        [[ -n "$model_id" && $(oc --request-timeout=10s get maasmodelrefs.maas.opendatahub.io "$name" -n "$ns" \
            -o jsonpath='{.status.resolvedModelAlias}') == "$model_id" ]] || { echo "[FAIL] Native local model alias differs"; exit 1; }
        host=$LOCAL_HOST
    fi
    endpoint=$(jq -r --arg m "$model_id" '.data[] | select(.id == $m and .ready == true) | .url' <<<"$CATALOG")
    [[ -n "$endpoint" ]] || { echo "[FAIL] Approved model $name is missing or not ready in the persona catalog"; exit 1; }
    [[ "$endpoint" == "https://$host"* ]] || { echo "[FAIL] Native model discovery selects the wrong listener hostname"; exit 1; }
    case "${endpoint%/}" in */v1) url="${endpoint%/}/chat/completions" ;; *) url="${endpoint%/}/v1/chat/completions" ;; esac
    payload=$(jq -n --arg m "$model_id" --arg name "$name" --argjson ext "$external" '{model: $m,
        messages: [{role: "user", content: "Reply with exactly OK."}]}
        + (if $name == "gpt-6-luna" then {max_completion_tokens: 32, reasoning_effort: "none"} else {max_tokens: 8} end)
        + (if $ext then {} else {chat_template_kwargs: {enable_thinking: false}} end)')
    body=$(json_file <<<"$payload")
    [[ $(http POST "$url" none "$body") =~ ^40[13]$ ]] || { echo "[FAIL] Unauthenticated inference did not fail closed"; exit 1; }
    [[ $(http POST "$url" invalid "$body") =~ ^40[13]$ ]] || { echo "[FAIL] Invalid synthetic key did not fail closed"; exit 1; }
    if [[ "$SINGLE" == true || ( "$external" == false && -z "$REVOKE_URL" ) ]]; then
        REVOKE_URL=$url
        REVOKE_BODY=$( [[ "$SINGLE" == true ]] && echo "$body" || jq '.max_tokens = 1' <<<"$payload" | json_file)
    fi
    before=0; [[ "$external" == false ]] && before=$(counter "$name")
    phase=completion
    result=""
    if response=$(api POST "$url" key "$body" 2>"$WORK/status"); then
        if ! jq -e '(.choices[0].message.content // "") != "" and (.usage.total_tokens // 0) > 0' <<<"$response" >/dev/null; then
            echo "[FAIL] Bounded completion or usage is absent for $name"; exit 1
        fi
        result=$(jq -c --arg n "$name" --arg id "$model_id" '{model: $n, catalog_id: $id, unauthenticated_denied: true,
            invalid_key_denied: true, completion_with_usage: true,
            usage: (.usage | with_entries(select(.key == "prompt_tokens" or .key == "completion_tokens" or .key == "total_tokens")))}' <<<"$response")
        if [[ "$SINGLE" == true ]]; then
            evidence --argjson r "$(jq -c '.streaming_and_tools_tested = false' <<<"$result")" '.models += [$r]'
            continue
        fi
        phase=stream
        stream_body=$(jq --arg name "$name" '.stream = true | .stream_options = {include_usage: true}
            | .messages = [{role: "user", content: "Count from 1 to 20, separated by commas. Do not think."}]
            | if $name == "gpt-6-luna" then .max_completion_tokens = 64 else .max_tokens = 64 end' <<<"$payload" | json_file)
        if streamed=$(stream_check "$url" "$stream_body"); then
            result=$(jq -c --argjson s "$streamed" '. + $s' <<<"$result")
            if [[ "$name" == gpt-6-luna ]]; then
                phase=tool-call
                tools=$(jq '.max_completion_tokens = 128 | .messages = [{role: "user", content: "Call report_status with status OK."}]
                    | .tools = [{type: "function", function: {name: "report_status", description: "Return a status",
                        parameters: {type: "object", properties: {status: {type: "string"}}, required: ["status"], additionalProperties: false}}}]
                    | .tool_choice = {type: "function", function: {name: "report_status"}}' <<<"$payload" | json_file)
                if api POST "$url" key "$tools" 2>/dev/null | jq -e 'any(.choices[0].message.tool_calls[]?; .function.name == "report_status"
                    and (.function.arguments | fromjson | .status) == "OK")' >/dev/null; then
                    result=$(jq -c '.tool_call = true' <<<"$result")
                else
                    response=""
                fi
            fi
        else
            response=""
        fi
    else
        response=""
    fi
    if [[ -z "$response" || -z "$result" || ( "$phase" != completion && -z "$streamed" ) ]]; then
        evidence --arg n "$name" --arg id "$model_id" --arg p "$phase" '.model_http_failures += [{model: $n, catalog_id: $id, phase: $p}]'
        [[ -n "$result" ]] && evidence --argjson r "$result" '.models += [$r]'
        FAILED=true
        echo "[FAIL] Bounded $name $phase"
        continue
    fi
    if [[ "$external" == false ]]; then
        deadline=$((SECONDS + 90))
        until awk -v a="$(counter "$name")" -v b="$before" 'BEGIN {exit !(a > b)}'; do
            (( SECONDS < deadline )) || { echo "[FAIL] Local inference traffic counter did not increase"; exit 1; }
            sleep 5
        done
        # Observed topology fields, not proof that a request invoked the EPP.
        result=$(oc --request-timeout=10s get llminferenceservices.serving.kserve.io "$name" -n internal-models -o json |
            jq -c --argjson r "$result" '$r + {traffic_counter_increased: true, per_request_epp_selection: "not qualified by this API test",
                native_scheduler: {inference_pool: .status.router.scheduler.inferencePool.name, epp_service: .status.router.scheduler.service.name,
                    workload: .status.workloads.scheduler.name, ready_replicas: .status.workloads.scheduler.readyReplicas}}')
    fi
    evidence --argjson r "$result" '.models += [$r]'
    echo "[PASS] Bounded $name authentication, completion, incremental SSE and usage$([[ "$external" == false ]] && echo " with traffic metric")"
done < <(jq -c '.[]' <<<"$REFS")
