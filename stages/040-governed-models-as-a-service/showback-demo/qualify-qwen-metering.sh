#!/usr/bin/env bash
# Explicit foreground qualification: current Qwen only, two real owner keys, six successful and two denied requests.
# Primes counters, retains raw labels and isolated before/after snapshots, and requires exact response/counter deltas.
# No retries, provisioning, quota exhaustion, model/GPU changes or external providers. Raw responses stay private.
# Usage: qualify-qwen-metering.sh [--execute --identities PRIVATE_DIR --output NEW_PRIVATE_DIR] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SHOWBACK_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
source "$REPO_ROOT/scripts/lib.sh"
execute=false identities='' output='' insecure=false
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --execute) execute=true; shift ;;
        --identities) identities=${2:?}; shift 2 ;;
        --output) output=${2:?}; shift 2 ;;
        --insecure) insecure=true; shift ;;
        -h|--help) sed -n 's/^# Usage: //p' "$0"; exit 0 ;;
        *) fail 'Unknown argument' ;;
    esac
done
if [[ "$execute" == false ]]; then
    jq -n '{evidence_kind:"preview",network_requests:0,model:"qwen3-8-27b",teams:["engineering","support"],
      inference_ceiling:8,successful_ceiling:6,denial_probes:2,max_output_tokens:32,max_wall_seconds:660,
      request_timeout_seconds:45,quota_exhaustion:false,protocols:["JSON","SSE"]}'
    exit 0
fi
[[ "$output" == /private/tmp/* && ! -e "$output" && ! -L "$output" && "$identities" == /private/tmp/* ]] ||
  fail 'Use existing private identities and a new output directory under /private/tmp'
for team in engineering support; do
    [[ -f "$identities/$team/key-created.json" && -f "$identities/$team/key-metadata.json" ]] || fail 'Missing owner identity evidence'
    jq -e --arg u "showback-$team" --arg s "team-$team" '.username==$u and .subscription==$s and .status=="active"' \
      "$identities/$team/key-metadata.json" >/dev/null || fail 'Owner metadata differs'
done
load_env
check_oc_logged_in
umask 077
mkdir -m 700 "$output"
tls=(--proto '=https'); [[ "$insecure" == false ]] || tls+=(--insecure)
oc --request-timeout=15s get llminferenceservice qwen3-8-27b -n internal-models -o json > "$output/model-before.json"
jq -e '.spec.replicas==1 and any(.status.conditions[];.type=="Ready" and .status=="True")' \
  "$output/model-before.json" >/dev/null || fail 'Current single Qwen instance is not ready'
oc --request-timeout=15s get gateway maas-default-gateway -n openshift-ingress -o json > "$output/gateway.json"
GATEWAY="https://$(jq -er '.spec.listeners[]|select(.name=="qwen3-8")|.hostname' "$output/gateway.json")"
MONITOR="https://$(oc --request-timeout=15s get route data-science-thanos-querier-route -n redhat-ods-monitoring -o jsonpath='{.spec.host}')"
MONITOR_TOKEN=$(oc --request-timeout=15s whoami -t)
oc --request-timeout=15s get tokenratelimitpolicy maas-trlp-qwen3-8-27b -n internal-models -o json > "$output/limiter-policy.json"
CANONICAL_LIMITER=$(jq -er 'select(.spec.targetRef.kind=="HTTPRoute")|
  .metadata.namespace+"/"+.spec.targetRef.name' "$output/limiter-policy.json")
oc --request-timeout=15s get opentelemetrycollector data-science-collector -n redhat-ods-monitoring -o json \
  > "$output/collector-config.json"
jq -e 'any(.spec.config.receivers.prometheus.config.scrape_configs[];
  .job_name=="data-science-collector-prometheus" and .scrape_interval=="30s")' \
  "$output/collector-config.json" >/dev/null || fail 'Native collector cadence differs from the qualified 30s interval'
started=$SECONDS
: > "$output/checks.jsonl"
requests_started=0
completed=false
finish() {
    local rc=$?
    [[ "$completed" == true || "$rc" != 0 ]] || rc=1
    jq -s --argjson completed "$completed" --argjson requests "$requests_started" --argjson exit_code "$rc" '
      {schema_version:1,evidence_kind:"observed",model:"qwen3-8-27b",passed:($completed and all(.[];.passed)),
        completed:$completed,exit_code:$exit_code,checks:.,inference_requests:$requests,quota_exhaustion:false,
        cost_scope:"bounded tiny Qwen completions; existing worker continues accruing compute"}' \
      "$output/checks.jsonl" > "$output/summary.json"
    unset MONITOR_TOKEN KEY
    exit "$rc"
}
trap finish EXIT
bounded() { remaining=$((660-SECONDS+started)); ((remaining>0)) || fail 'Qualification wall clock bound reached'; }
snapshot() {
    bounded
    local timeout=20
    ((remaining>=timeout)) || timeout=$remaining
    printf 'header = "Authorization: Bearer %s"\n' "$MONITOR_TOKEN" |
      curl --config - --silent --show-error --connect-timeout 10 --max-time "$timeout" "${tls[@]}" --get \
        --data-urlencode 'query=authorized_hits_total{model=~"qwen3-8-27b|publishers/internal-models/models/qwen3-8-27b"}' \
        "$MONITOR/api/v1/query" > "$1" || fail 'Raw monitoring query failed'
    jq -e '.status=="success" and .data.resultType=="vector"' "$1" >/dev/null || fail 'Invalid monitoring response'
}
selected() {
    jq -ce --arg u "showback-$2" --arg s "team-$2" --arg limiter "$CANONICAL_LIMITER" '[.data.result[]|
      select(.metric.user==$u and .metric.subscription==$s and .metric.limitador_namespace==$limiter)]|
      if length==1 and (.[0].metric.limitador_namespace|type=="string" and length>0)
      then .[0] else error("missing or duplicate canonical series") end' "$1"
}
count() { selected "$1" "$2" | jq -er '.value[1]|tonumber'; }
request() {
    local team=$1 protocol=$2 scope=$3 auth=${4:-key} dir="$output/$3-$1-$2" status rc=0 parsed
    bounded
    local timeout=45
    ((remaining>=timeout)) || timeout=$remaining
    mkdir -m 700 "$dir"
    KEY=$(jq -er '.key' "$identities/$team/key-created.json")
    [[ "$auth" != invalid ]] || KEY=showback-deliberately-invalid-key
    [[ "$auth" != none ]] || KEY=''
    jq -n --argjson stream "$([[ "$protocol" == SSE ]] && printf true || printf false)" \
      '{model:"publishers/internal-models/models/qwen3-8-27b",max_tokens:32,temperature:0,stream:$stream,
        messages:[{role:"user",content:"Reply with the word ready."}],chat_template_kwargs:{enable_thinking:false}} +
        (if $stream then {stream_options:{include_usage:true}} else {} end)' > "$dir/request.json"
    requests_started=$((requests_started+1))
    ((requests_started<=8)) || fail 'Inference request ceiling exceeded'
    status=$({ [[ -z "$KEY" ]] || printf 'header = "Authorization: Bearer %s"\n' "$KEY"; true; } |
      curl --config - --silent --show-error --no-buffer --connect-timeout 10 --max-time "$timeout" --max-filesize 1048576 \
        "${tls[@]}" --header 'Content-Type: application/json' --data-binary "@$dir/request.json" \
        --output "$dir/response" --dump-header "$dir/headers" --write-out '%{http_code}' \
        "$GATEWAY/v1/chat/completions") || rc=$?
    unset KEY
    printf '%s\n' "$status" > "$dir/http-status"
    [[ "$rc" == 0 ]] || fail 'Bounded request transport failed; evidence retained'
    if [[ "$auth" != key ]]; then
        [[ "$status" == 401 || "$status" == 403 ]] || fail 'Invalid or absent key was not denied'
        jq -nc --arg probe "$auth" --argjson status "$status" \
          '{scope:"authentication-denial",probe:$probe,http_status:$status,passed:true}' >> "$output/checks.jsonl"
        return
    fi
    [[ "$status" == 200 && $(wc -c < "$dir/response") -le 1048576 ]] || fail 'Positive request did not complete successfully'
    if [[ "$protocol" == SSE ]]; then
        tr -d '\r' < "$dir/response" | sed -n 's/^data: *//p' > "$dir/events"
        [[ $(tail -1 "$dir/events") == '[DONE]' ]] || fail 'SSE missing final DONE'
        sed '$d' "$dir/events" | jq -s -e 'length>0 and all(.[];.error==null) and
          (.[-1].choices==[]) and (.[-1].usage.total_tokens|type=="number")' >/dev/null || fail 'SSE final usage missing'
        sed '$d' "$dir/events" | jq -s '.[-1]|{model,usage}' > "$dir/parsed.json"
    else
        jq -e '.error==null and (.choices|length)>0' "$dir/response" >/dev/null || fail 'Invalid JSON completion'
        jq '{model,usage}' "$dir/response" > "$dir/parsed.json"
    fi
    jq -e '(.model=="qwen3-8-27b" or .model=="publishers/internal-models/models/qwen3-8-27b") and
      (.usage|.prompt_tokens>=0 and .completion_tokens>=0 and .total_tokens>0 and
        .total_tokens==(.prompt_tokens+.completion_tokens))' "$dir/parsed.json" >/dev/null || fail 'Model or token usage differs'
    jq --arg scope "$scope" --arg team "$team" --arg protocol "$protocol" \
      '.+{scope:$scope,team:$team,protocol:$protocol,http_status:200,passed:true}' "$dir/parsed.json" >> "$output/checks.jsonl"
}

# Create a real nonzero baseline for each team before proving isolated deltas.
snapshot "$output/pre-prime.json"
engineering_initial=0
support_initial=0
if jq -e '.data.result|any(.[];.metric.subscription=="team-engineering")' "$output/pre-prime.json" >/dev/null; then
    engineering_initial=$(count "$output/pre-prime.json" engineering)
fi
if jq -e '.data.result|any(.[];.metric.subscription=="team-support")' "$output/pre-prime.json" >/dev/null; then
    support_initial=$(count "$output/pre-prime.json" support)
fi
for team in engineering support; do request "$team" JSON prime; done
engineering_prime=$(jq -er --argjson initial "$engineering_initial" '.usage.total_tokens+$initial' "$output/prime-engineering-JSON/parsed.json")
support_prime=$(jq -er --argjson initial "$support_initial" '.usage.total_tokens+$initial' "$output/prime-support-JSON/parsed.json")
for attempt in 1 2 3 4 5 6 7 8 9; do
    snapshot "$output/prime-$attempt.json"
    if selected "$output/prime-$attempt.json" engineering >/dev/null 2>&1 &&
       selected "$output/prime-$attempt.json" support >/dev/null 2>&1 &&
       [[ $(count "$output/prime-$attempt.json" engineering) == "$engineering_prime" &&
          $(count "$output/prime-$attempt.json" support) == "$support_prime" ]]; then
        cp "$output/prime-$attempt.json" "$output/primed.json"
        break
    fi
    sleep 5
done
[[ -f "$output/primed.json" ]] || fail 'Canonical per-user subscription counters did not appear'
for team in engineering support; do
    for protocol in JSON SSE; do
        snapshot "$output/before-$team-$protocol.json"
        before=$(count "$output/before-$team-$protocol.json" "$team")
        before_labels=$(selected "$output/before-$team-$protocol.json" "$team" | jq -c '.metric')
        other=engineering
        [[ "$team" != engineering ]] || other=support
        other_before=$(count "$output/before-$team-$protocol.json" "$other")
        other_labels=$(selected "$output/before-$team-$protocol.json" "$other" | jq -c '.metric')
        request "$team" "$protocol" isolated
        usage=$(jq -er '.usage.total_tokens' "$output/isolated-$team-$protocol/parsed.json")
        matched=false
        for attempt in 1 2 3 4 5 6 7 8 9; do
            snapshot "$output/after-$team-$protocol-$attempt.json"
            after=$(count "$output/after-$team-$protocol-$attempt.json" "$team")
            after_labels=$(selected "$output/after-$team-$protocol-$attempt.json" "$team" | jq -c '.metric')
            [[ "$before_labels" == "$after_labels" ]] || fail 'Canonical series labels changed during isolated request'
            [[ $(count "$output/after-$team-$protocol-$attempt.json" "$other") == "$other_before" &&
               $(selected "$output/after-$team-$protocol-$attempt.json" "$other" | jq -c '.metric') == "$other_labels" ]] ||
              fail 'Isolated request changed the other team counter or series'
            if jq -en --argjson a "$after" --argjson b "$before" --argjson u "$usage" '$a-$b==$u' >/dev/null; then
                matched=true
                break
            fi
            sleep 5
        done
        jq -nc --arg team "$team" --arg protocol "$protocol" --argjson before "$before" --argjson after "$after" \
          --argjson usage "$usage" --argjson passed "$matched" \
          '{scope:"isolated-token-delta",team:$team,protocol:$protocol,before:$before,after:$after,
            response_tokens:$usage,counter_delta:($after-$before),passed:$passed}' >> "$output/checks.jsonl"
        [[ "$matched" == true ]] || fail 'Exact isolated token delta did not match response usage'
    done
done
request engineering JSON absent-key none
request engineering JSON invalid-key invalid
snapshot "$output/final.json"
jq -n --slurpfile s "$output/final.json" --arg limiter "$CANONICAL_LIMITER" '{schema_version:1,status:"live verified canonical Qwen series",
  max_scrape_gap_seconds:45,boundary_tolerance_seconds:30,receipt_tolerance_fraction:"0.01",
  model_aliases:{"qwen3-8-27b":["qwen3-8-27b","publishers/internal-models/models/qwen3-8-27b"]},
  canonical_series:[$s[0].data.result[]|select(.metric.limitador_namespace==$limiter)|
    {subscription:.metric.subscription,user:.metric.user,model:"qwen3-8-27b",limitador_namespace:.metric.limitador_namespace}]}' \
  > "$output/metering.json"
oc --request-timeout=15s get llminferenceservice qwen3-8-27b -n internal-models -o json > "$output/model-after.json"
jq -e --slurpfile before "$output/model-before.json" '.spec==$before[0].spec and .metadata.uid==$before[0].metadata.uid' \
  "$output/model-after.json" >/dev/null || fail 'Serving configuration changed during qualification'
completed=true
printf 'Qwen JSON/SSE, authentication denials and exact per-owner token deltas passed. Private evidence: %s\n' "$output"
