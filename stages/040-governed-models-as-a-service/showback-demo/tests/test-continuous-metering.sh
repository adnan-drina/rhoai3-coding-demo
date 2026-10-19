#!/usr/bin/env bash
# Test an explicitly named disposable local backend/database with synthetic events. No cluster or model traffic.
# Restarts the named backend and temporarily stops/restores the named database; retains private test receipts.
# Usage: test-continuous-metering.sh --url http://127.0.0.1:PORT --connection NAME --backend NAME --database NAME --catalog DISPOSABLE_CATALOG --output NEW_PRIVATE_DIR
set -euo pipefail
umask 077
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if (($# == 0)); then
    # The package gate must remain entirely offline. Runtime checks require all
    # explicit disposable-target options and are recorded separately as evidence.
    jq -e '.schema_version==1 and .currency=="USD" and (.catalog_version|length)>0
      and (.rates|length)==4 and all(.rates[];
        (.price_version|length)>0 and .estimate_policy.invoice_actual==false)
      and any(.rates[];.provider=="nvidia" and .provider_protocol=="openai"
        and .upstream_model=="nvidia/nemotron-3-ultra-550b-a55b" and .basis=="provider_free_prototype")
      and any(.rates[];.provider=="anthropic" and .api_format=="openai-chat"
        and .prices_usd_per_million.cache_read==null and .prices_usd_per_million.cache_write==null)' \
        "$SCRIPT_DIR/../native/provider-pricing.json" >/dev/null
    printf '%s\n' 'PASS Continuous metering offline catalog contract; disposable HTTP/storage qualification requires explicit target options.'
    exit 0
fi
url='' connection='' backend='' database='' catalog='' output=''
fail() { printf 'Continuous metering test: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    (($# >= 2)) || fail 'All options require values'
    case "$1" in
        --url) url=$2 ;;
        --connection) connection=$2 ;;
        --backend) backend=$2 ;;
        --database) database=$2 ;;
        --catalog) catalog=$2 ;;
        --output) output=$2 ;;
        *) fail 'Unknown option' ;;
    esac
    shift 2
done
[[ "$url" =~ ^http://127\.0\.0\.1:[0-9]+$ ]] || fail 'Only an explicit loopback HTTP endpoint is allowed'
[[ "$connection" =~ ^[a-zA-Z0-9_.-]+$ ]] || fail 'Explicit local Podman connection required'
for name in "$backend" "$database"; do
    [[ "$name" =~ ^showback-continuous-[a-zA-Z0-9_.-]+$ ]] || fail 'Only named disposable continuous-metering containers are allowed'
done
[[ "$backend" != "$database" ]] || fail 'Backend and database must differ'
[[ "$output" == /private/tmp/* && ! -e "$output" ]] || fail 'Use a new private evidence directory'
[[ "$catalog" == /private/tmp/showback-continuous-*/runtime/catalog/provider-pricing.json && -f "$catalog" && ! -L "$catalog" ]] ||
    fail 'Use only the explicitly disposable runtime catalog'
for prerequisite in podman jq curl ruby; do command -v "$prerequisite" >/dev/null || fail "Missing $prerequisite"; done
podman system connection list --format json | jq -e --arg name "$connection" '
    any(.[];.Name==$name and (.URI|test("^ssh://[^/@]+@(127[.]0[.]0[.]1|localhost):[0-9]+/")))' >/dev/null ||
    fail 'Podman connection is not local'
engine=(podman --connection "$connection")
mkdir -m 700 "$output"
cp "$catalog" "$output/original-catalog.json"
run_id="independent-$(date -u +%Y%m%dT%H%M%SZ)-$$"
database_stopped=false
catalog_changed=false
checks=0
restore() {
    [[ "$database_stopped" == true ]] || return 0
    "${engine[@]}" start "$database" > "$output/database-restored.log" 2>&1 || return 1
    database_stopped=false
}
finish() {
    local code=$?
    trap - EXIT
    restore || code=1
    if [[ "$catalog_changed" == true ]]; then
        cp "$output/original-catalog.json" "$catalog" || code=1
        "${engine[@]}" restart "$backend" > "$output/catalog-recovery.log" 2>&1 || code=1
    fi
    exit "$code"
}
trap finish EXIT
pass() { checks=$((checks + 1)); printf '%s\n' "$1" >> "$output/checks.txt"; }
http() {
    local name=$1 method=$2 path=$3 file=${4:-}
    local args=(-q -sS --noproxy '*' --proto '=http' --connect-timeout 1 --max-time 5 --request "$method"
        --output "$output/$name.body" --write-out '%{http_code}')
    [[ -z "$file" ]] || args+=(--header 'Content-Type: application/json' --data-binary "@$file")
    curl "${args[@]}" "$url$path" > "$output/$name.status"
}
expect_status() { [[ $(cat "$output/$1.status") == "$2" ]] || fail "$1 returned unexpected HTTP status"; }
sql() {
    local name=$1 statement=$2
    printf '%s\n' "$statement" | "${engine[@]}" exec -i "$database" sh -c '
      export PGPASSWORD="${POSTGRES_PASSWORD:-${POSTGRESQL_PASSWORD:-}}"
      export PGCONNECT_TIMEOUT=3 PGOPTIONS="-c statement_timeout=5000"
      probe_user="${POSTGRES_USER:-${POSTGRESQL_USER:-postgres}}"
      exec psql -X -q -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$probe_user" \
        -d "${POSTGRES_DB:-${POSTGRESQL_DATABASE:-$probe_user}}"' > "$output/$name.json"
    jq -e . "$output/$name.json" >/dev/null
}
snapshot() {
    sql "$1" "SELECT COALESCE(json_agg(row_to_json(r)),'[]'::json) FROM (
      SELECT e.event_id,e.source,e.timestamp,e.username,e.subscription,c.provider,c.model,c.usage_state,c.price_state,
      c.price_version,c.catalog_sha256,c.input_tokens,c.output_tokens,c.estimated_usd::text
      FROM usage_events e LEFT JOIN showback_event_costs c ON c.source=e.source AND c.event_id=e.event_id
      WHERE e.username LIKE '$run_id%' ORDER BY e.id) r;"
}
ready() {
    local attempt
    for attempt in $(seq 1 20); do
        if curl -q -sf --noproxy '*' --max-time 1 "$url/ready" > /dev/null; then return 0; fi
        sleep 1
    done
    return 1
}
ready || fail 'Local backend is not ready'
"${engine[@]}" inspect "$backend" | jq -e '.[0] | .State.Running and
    all(.NetworkSettings.Ports["8080/tcp"][];.HostIp=="127.0.0.1" or .HostIp=="::1")' >/dev/null ||
    fail 'Named backend is not running with a loopback port'
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq -n --arg id "$run_id-base" --arg user "$run_id" --arg at "$now" \
  '{specversion:"1.0",id:$id,source:"maas-default-gateway",type:"inference.tokens.used",subject:$user,time:$at,
    datacontenttype:"application/json",data:{user:$user,subscription:"synthetic-owner",provider:"openai",model:"gpt-6-luna",
    prompt_tokens:10000,completion_tokens:1000,total_tokens:11000,cached_input_tokens:4000,
    cache_creation_tokens:2000,reasoning_tokens:500}}' > "$output/base.json"
post() { http "$1" POST /api/v1/events "$2"; expect_status "$1" "${3:-204}"; }
post normal "$output/base.json"
snapshot first
jq -e 'length==1 and .[0].estimated_usd=="0.001190000000" and .[0].price_state=="conditional_standard_estimate"' \
    "$output/first.json" >/dev/null || fail 'Cache or reasoning was counted twice'
pass 'disjoint cache categories and reasoning included once in output'
post replay "$output/base.json"
snapshot replay
cmp -s "$output/first.json" "$output/replay.json" || fail 'Identical replay changed frozen ledger'
jq '.data.prompt_tokens+=1 | .data.total_tokens+=1' "$output/base.json" > "$output/conflict.json"
post conflict "$output/conflict.json" 409
pass 'same source/id replays once and conflicting payload is rejected'
for mutation in \
    'del(.data.reasoning_tokens)' \
    '.subject="different-user"' \
    '.source="untrusted-source"' \
    '.data.subscription=""' \
    '.data.cached_input_tokens=10001' \
    '.data.reasoning_tokens=1001'; do
    jq "$mutation" "$output/base.json" > "$output/rejected.json"
    post rejected "$output/rejected.json" 400
done
pass 'missing counts, identity/source mismatch and impossible subsets rejected'
jq --arg id "$run_id-zero" '.id=$id | .data|=with_entries(if (.key|endswith("tokens")) then .value=0 else . end)' \
    "$output/base.json" > "$output/zero.json"
post zero "$output/zero.json"
jq --arg id "$run_id-error" '.id=$id | .type="inference.request.error" |
    .data|=del(.prompt_tokens,.completion_tokens,.total_tokens,.cached_input_tokens,.cache_creation_tokens,.reasoning_tokens) |
    .data.status_code=503' "$output/base.json" > "$output/error.json"
post error "$output/error.json"
jq --arg id "$run_id-error-counts" '.id=$id|.type="inference.request.error"|.data.status_code=503' \
    "$output/base.json" > "$output/error-counts.json"
post error-counts "$output/error-counts.json"
snapshot missing
jq -e 'all(.[]|select(.event_id|test("-(zero|error|error-counts)$"));
    .usage_state=="unknown" and .input_tokens==null and .output_tokens==null and .estimated_usd==null)' \
    "$output/missing.json" >/dev/null || fail 'Unknown or failed usage became numeric'
pass 'all-zero and failed events retain Unknown tokens and amount'
jq --arg id "$run_id-nvidia" '.id=$id | .data.model="nvidia/nemotron-3-ultra-550b-a55b" |
    .data.prompt_tokens=21|.data.completion_tokens=2|.data.total_tokens=23|
    .data.cached_input_tokens=0|.data.cache_creation_tokens=0|.data.reasoning_tokens=0' \
    "$output/base.json" > "$output/nvidia.json"
post nvidia "$output/nvidia.json"
snapshot nvidia
jq -e 'any(.[];.model=="nemotron-3-ultra-550b-a55b" and .provider=="nvidia"
    and .price_state=="free_prototype" and (.estimated_usd|tonumber)==0)' "$output/nvidia.json" >/dev/null ||
    fail 'NVIDIA protocol identity or genuine free price lost'
pass 'NVIDIA upstream/protocol canonicalized and documented free amount preserved'
jq --arg id "$run_id-unmapped" '.id=$id|.data.model="synthetic-unmapped"' \
    "$output/base.json" > "$output/unmapped.json"
post unmapped "$output/unmapped.json"
snapshot unmapped
jq -e 'any(.[];.provider=="unmapped" and .input_tokens==10000 and .estimated_usd==null)' \
    "$output/unmapped.json" >/dev/null || fail 'Unmapped external usage silently disappeared'
pass 'unmapped external usage remains counted without an invented rate'
for count in 272000 272001; do
    jq --arg id "$run_id-band-$count" --argjson count "$count" '.id=$id | .data.prompt_tokens=$count |
      .data.completion_tokens=0|.data.total_tokens=$count|.data.cached_input_tokens=0|
      .data.cache_creation_tokens=0|.data.reasoning_tokens=0' "$output/base.json" > "$output/band-$count.json"
    post "band-$count" "$output/band-$count.json"
done
snapshot bands
jq -e 'any(.[];(.event_id|endswith("-272000")) and .estimated_usd=="0.027200000000") and
    any(.[];(.event_id|endswith("-272001")) and .estimated_usd=="0.054400200000")' "$output/bands.json" >/dev/null ||
    fail 'Whole-request context boundary priced incorrectly'
pass '272000/272001 input context price boundary'
for offset in 0 -1; do
    stamp=$(ruby -rtime -e 't=Time.now.utc;puts (Time.utc(t.year,t.month,1)+ARGV[0].to_i).iso8601' -- "$offset")
    jq --arg id "$run_id-month-$offset" --arg user "$run_id-month" --arg at "$stamp" \
      '.id=$id|.subject=$user|.data.user=$user|.time=$at' "$output/base.json" > "$output/month-$offset.json"
    post "month-$offset" "$output/month-$offset.json"
done
http metrics GET /metrics
expect_status metrics 200
grep '^showback_external_metering_events{' "$output/metrics.body" | grep "user=\"$run_id-month\"" > "$output/month-metrics.txt"
[[ $(wc -l < "$output/month-metrics.txt" | tr -d ' ') == 1 ]] || fail 'UTC month created extra event groups'
[[ $(awk '{print $NF}' "$output/month-metrics.txt") == 1 ]] || fail 'Previous UTC month was included'
pass 'UTC month excludes previous-month row while retaining current-month row'
http entitlement GET "/api/v1/customers/$run_id/entitlements/inference-tokens/value?model=gpt-6-luna"
expect_status entitlement 200
jq -e '.hasAccess==true' "$output/entitlement.body" >/dev/null || fail 'Meter adds a quota policy'
pass 'metering-only entitlement leaves MaaS authorization unchanged'
snapshot before_restart
"${engine[@]}" restart "$backend" > "$output/backend-restart.log"
ready || fail 'Backend did not recover after restart'
snapshot after_restart
cmp -s "$output/before_restart.json" "$output/after_restart.json" || fail 'Restart changed ledger or frozen prices'
pass 'backend restart preserves durable rows and frozen estimates'

# Only the disposable catalog is changed. The tracked catalog is never edited.
jq '.independent_test_marker="changed bytes, same version"' "$output/original-catalog.json" > "$catalog"
catalog_changed=true
"${engine[@]}" restart "$backend" > "$output/catalog-conflict-restart.log"
for attempt in $(seq 1 15); do
    [[ $("${engine[@]}" inspect "$backend" --format '{{.State.Running}}') != true ]] && break
    sleep 1
done
[[ $("${engine[@]}" inspect "$backend" --format '{{.State.Running}}') == false ]] ||
    fail 'Changed bytes reused an immutable catalog version'
cp "$output/original-catalog.json" "$catalog"
"${engine[@]}" start "$backend" > "$output/catalog-restore-start.log"
ready || fail 'Original catalog did not restore service'
jq --arg suffix "$run_id" '.catalog_version+=("-"+$suffix) |
    .rates|=map(.price_version+=("-"+$suffix) |
      .prices_usd_per_million|=with_entries(if .value==null then . else .value=(.value|tonumber*2|tostring) end))' \
    "$output/original-catalog.json" > "$catalog"
"${engine[@]}" restart "$backend" > "$output/new-catalog-restart.log"
ready || fail 'New catalog version did not start'
post replay-after-price-change "$output/base.json"
snapshot frozen_price
jq -e --arg id "$run_id-base" 'any(.[];.event_id==$id and .estimated_usd=="0.001190000000")' \
    "$output/frozen_price.json" >/dev/null || fail 'New catalog repriced a historical replay'
jq --arg id "$run_id-new-price" '.id=$id' "$output/base.json" > "$output/new-price.json"
post new-price "$output/new-price.json"
snapshot new_price
jq -e --arg id "$run_id-new-price" 'any(.[];.event_id==$id and .estimated_usd=="0.002380000000")' \
    "$output/new_price.json" >/dev/null || fail 'New event did not retain new version price'
cp "$output/original-catalog.json" "$catalog"
"${engine[@]}" restart "$backend" > "$output/final-catalog-restore.log"
ready || fail 'Original catalog did not recover'
catalog_changed=false
pass 'immutable catalog version rejected; new-version replay preserves old frozen estimate'
"${engine[@]}" stop "$database" > "$output/database-stop.log"
database_stopped=true
http unavailable GET /metrics
expect_status unavailable 503
! grep -q '^showback_external_metering_' "$output/unavailable.body" || fail 'Unavailable DB emitted fabricated gauges'
jq --arg id "$run_id-outage" '.id=$id' "$output/base.json" > "$output/outage.json"
post outage "$output/outage.json" 500
restore
ready || fail 'Backend did not recover after database restore'
post outage-retry "$output/outage.json"
snapshot final
jq -e --arg id "$run_id-outage" '[.[]|select(.event_id==$id)]|length==1' "$output/final.json" >/dev/null ||
    fail 'Failed write acknowledged or retry duplicated'
pass 'DB outage emits503, never acknowledges failed writes, and permits one durable retry'
jq -n --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg run "$run_id" --argjson checks "$checks" \
    --rawfile cases "$output/checks.txt" '{schema_version:1,evidence_kind:"synthetic_local_runtime",verified_at:$at,
      run_id:$run,passed:$checks,failed:0,database_restored:true,inference_requests:0,cluster_mutations:0,
      checks:($cases|split("\n")|map(select(length>0)))}' > "$output/result.json"
cat "$output/result.json"
