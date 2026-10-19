#!/usr/bin/env bash
# Two bounded Nemotron completions through a genuine existing demo-user login; no access changes or retries.
# Creates and revokes one owner-scoped ephemeral MaaS key. Raw HTTP evidence remains private.
# Usage: external-probe.sh [--execute --persona PRIVATE_KUBECONFIG --output NEW_PRIVATE_DIR] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SHOWBACK_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
source "$REPO_ROOT/scripts/lib.sh"
execute=false persona='' output='' insecure=false
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --execute) execute=true; shift ;;
        --persona) persona=${2:?}; shift 2 ;;
        --output) output=${2:?}; shift 2 ;;
        --insecure) insecure=true; shift ;;
        -h|--help) sed -n 's/^# Usage: //p' "$0"; exit 0 ;;
        *) fail 'Unknown argument' ;;
    esac
done
if [[ "$execute" == false ]]; then
    jq -n '{evidence_kind:"preview",network_requests:0,model:"nemotron-3-ultra-550b-a55b",
      inference_requests:2,max_output_tokens:128,request_timeout_seconds:60,retries:0,
      identity:"existing genuine ai-admin or ai-developer owner login",monthly_cost:"unknown"}'
    exit 0
fi
[[ -f "$persona" && ! -L "$persona" && "$output" == /private/tmp/* && ! -e "$output" && ! -L "$output" ]] ||
  fail 'Use an existing private persona login and a new output directory under /private/tmp'
[[ -z $(find "$persona" -maxdepth 0 \( -perm -001 -o -perm -002 -o -perm -004 -o -perm -010 -o -perm -020 -o -perm -040 \)) ]] ||
  fail 'Persona login must have owner-only permissions'
load_env
check_oc_logged_in >/dev/null
umask 077
mkdir -m 700 "$output"
tls=(--proto '=https'); [[ "$insecure" == false ]] || tls+=(--insecure)
oc --request-timeout=10s get gateway maas-default-gateway -n openshift-ingress -o json > "$output/gateway.json"
base="https://$(jq -er '.spec.listeners[]|select(.name=="api")|.hostname' "$output/gateway.json")"
oc --request-timeout=10s get externalmodels -n external-models -o json > "$output/models.json"
inventory_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq --arg at "$inventory_at" '[.items[]|.metadata.name as $model|.spec.externalProviderRefs[]|
  {model:$model,provider:.ref.name,upstream_model:.targetModel,inventory_at:$at,evidence_kind:"observed"}]' \
  "$output/models.json" > "$output/inventory.json"
jq -e 'any(.[];.model=="nemotron-3-ultra-550b-a55b" and .provider=="nvidia" and
  .upstream_model=="nvidia/nemotron-3-ultra-550b-a55b")' "$output/inventory.json" >/dev/null || fail 'Nemotron configuration differs'
export KUBECONFIG="$persona"
check_oc_logged_in >/dev/null
user=$(oc --request-timeout=10s whoami)
[[ "$user" == ai-admin || "$user" == ai-developer ]] || fail 'Only existing demo owner identities are supported'
subscription="personal-$user"
OWNER_TOKEN=$(oc --request-timeout=10s whoami -t)
key_id='' KEY='' completed=false
http() {
    local method=$1 url=$2 token=$3 body=${4:-} rc=0
    local args=(--config - --silent --show-error --connect-timeout 10 --max-time 60 --max-filesize 1048576
      "${tls[@]}" --request "$method" --output "$output/http-body" --dump-header "$output/http-headers"
      --write-out '%{http_code}')
    [[ -z "$body" ]] || args+=(--header 'Content-Type: application/json' --data-binary "@$body")
    : > "$output/http-body"
    : > "$output/http-headers"
    HTTP_STATUS=$(printf 'header = "Authorization: Bearer %s"\n' "$token" | curl "${args[@]}" "$url") || rc=$?
    TRANSPORT_STATUS=$rc
}
finish() {
    local rc=$?
    if [[ -n "$key_id" ]]; then
        http DELETE "$base/v1/api-keys/$(printf '%s' "$key_id" | jq -Rr @uri)" "$OWNER_TOKEN"
        jq -n --arg status "$HTTP_STATUS" --argjson transport "$TRANSPORT_STATUS" \
          '{http_status:$status,transport_status:$transport,revoked:($transport==0 and ($status=="200" or $status=="204"))}' \
          > "$output/key-revocation.json"
        if [[ "$TRANSPORT_STATUS" != 0 || ! "$HTTP_STATUS" =~ ^(200|204)$ ]]; then
            printf 'ERROR: Ephemeral key revocation failed; private evidence retained\n' >&2
            rc=1
        fi
    fi
    unset OWNER_TOKEN KEY
    [[ "$completed" == true ]] || rc=1
    exit "$rc"
}
trap finish EXIT
http GET "$base/v1/subscriptions" "$OWNER_TOKEN"
[[ "$TRANSPORT_STATUS" == 0 && "$HTTP_STATUS" == 200 ]] || fail 'Owner subscription discovery failed'
jq -e --arg s "$subscription" 'type=="array" and any(.[];.subscription_id_header==$s)' "$output/http-body" >/dev/null ||
  fail 'Genuine owner cannot discover the expected subscription'
http GET "$base/v1/models" "$OWNER_TOKEN"
[[ "$TRANSPORT_STATUS" == 0 && "$HTTP_STATUS" == 200 ]] || fail 'Owner catalog discovery failed'
jq -e '.data|any(.[];.id=="nemotron-3-ultra-550b-a55b" and .ready==true)' "$output/http-body" >/dev/null ||
  fail 'Nemotron is not ready in genuine owner catalog'
cp "$output/http-body" "$output/owner-catalog.json"
jq -n --arg s "$subscription" '{name:"showback-external-bounded-probe",subscription:$s,expiresIn:"1h",ephemeral:true}' > "$output/key-request.json"
http POST "$base/v1/api-keys" "$OWNER_TOKEN" "$output/key-request.json"
[[ "$TRANSPORT_STATUS" == 0 && "$HTTP_STATUS" == 201 ]] || fail 'Owner key creation failed'
cp "$output/http-body" "$output/key-created.json"
key_id=$(jq -er '.id|select(type=="string" and length>0)' "$output/key-created.json")
KEY=$(jq -er '.key|select(type=="string" and length>0)' "$output/key-created.json")
http GET "$base/v1/api-keys/$(printf '%s' "$key_id" | jq -Rr @uri)" "$OWNER_TOKEN"
[[ "$TRANSPORT_STATUS" == 0 && "$HTTP_STATUS" == 200 ]] || fail 'Key owner metadata lookup failed'
jq -e --arg u "$user" --arg s "$subscription" '.username==$u and .subscription==$s and .status=="active"' \
  "$output/http-body" >/dev/null || fail 'Server key ownership differs'
jq '{username,subscription,status,id,expirationDate,ephemeral}' "$output/http-body" > "$output/key-metadata.json"
probe_id="external-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"
period_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
: > "$output/receipts.jsonl"
for sequence in 1 2; do
    jq -n '{model:"nemotron-3-ultra-550b-a55b",max_tokens:128,temperature:0,stream:false,
      chat_template_kwargs:{enable_thinking:false},messages:[{role:"user",content:"Reply with exactly OK."}]}' > "$output/request.json"
    started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    http POST "$base/v1/chat/completions" "$KEY" "$output/request.json"
    ended_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    cp "$output/http-body" "$output/response-$sequence.json"
    cp "$output/http-headers" "$output/headers-$sequence"
    jq -n --arg user "$user" --arg subscription "$subscription" --arg started "$started_at" --arg ended "$ended_at" \
      --argjson sequence "$sequence" --arg status "$HTTP_STATUS" --argjson transport "$TRANSPORT_STATUS" \
      --rawfile body "$output/http-body" '(try ($body|fromjson) catch null) as $r|
      {sequence:$sequence,model:"nemotron-3-ultra-550b-a55b",provider:"nvidia",user:$user,subscription:$subscription,
       client_request_id:("nemotron-bounded-"+($sequence|tostring)+"-"+$started),
       started_at:$started,ended_at:$ended,http_status:$status,transport_status:$transport,
       provider_request_id:($r.id//null),response_model:($r.model//null),
       usage:(if $status=="200" and $transport==0 and $r.error==null and
         ($r.model=="nemotron-3-ultra-550b-a55b" or $r.model=="nvidia/nemotron-3-ultra-550b-a55b") and
         ($r.id|type)=="string" and ($r.id|length)>0 and ($r.choices|type)=="array" and ($r.choices|length)>0 and
         ($r.usage.prompt_tokens|type)=="number" and
         ($r.usage.completion_tokens|type)=="number" and $r.usage.prompt_tokens>=0 and $r.usage.completion_tokens>=0 and
         $r.usage.total_tokens==($r.usage.prompt_tokens+$r.usage.completion_tokens)
         then {input_tokens:$r.usage.prompt_tokens,output_tokens:$r.usage.completion_tokens,total_tokens:$r.usage.total_tokens}
         else null end)}' >> "$output/receipts.jsonl"
done
period_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq -n --arg id "$probe_id" --arg start "$period_start" --arg end "$period_end" \
  --slurpfile inventory "$output/inventory.json" --slurpfile receipts "$output/receipts.jsonl" \
  '{schema_version:1,evidence_kind:"observed",scope:"bounded_api_probe",probe_id:$id,period_start:$start,period_end:$end,
    inventory:$inventory[0],receipts:$receipts,price_state:"unknown",monthly_report_state:"unavailable",
    limitations:["Response usage receipts only; gateway token-counter reconciliation not performed",
      "No monthly invoice, tariff, cache billing, task quality or capacity qualification"]}' > "$output/probe.json"
completed=true
jq '{probe_id,period_start,period_end,requests:(.receipts|length),verified_usage_receipts:([.receipts[]|select(.usage!=null)]|length),
  users:([.receipts[].user]|unique),models:([.inventory[].model]|unique),price_state,monthly_report_state}' "$output/probe.json"
