#!/usr/bin/env bash
# Exercise an already running, isolated local Noyitz backend and PostgreSQL database.
# Inserts synthetic events, restarts the named backend, and stops/starts ONLY the named disposable database.
# Restores the database on failure. Creates/removes no containers or VMs.
# Rerun with a new empty evidence directory; previous synthetic rows remain in the disposable database.
# Usage: test-backend-local.sh --url http://127.0.0.1:PORT --connection NAME --backend-container NAME --db-container NAME --output EMPTY_DIR
set -euo pipefail
umask 077
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
patch_file="$SCRIPT_DIR/backend/0001-metering-correctness.patch"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 2; }
fail() { printf 'Local backend test: %s\n' "$*" >&2; exit 1; }
url=''; connection=''; backend=''; database=''; output=''
while (($#)); do
    (($# >= 2)) || usage
    case "$1" in
        --url) url=$2 ;;
        --connection) connection=$2 ;;
        --backend-container) backend=$2 ;;
        --db-container) database=$2 ;;
        --output) output=$2 ;;
        *) usage ;;
    esac
    shift 2
done
for prerequisite in podman curl jq shasum; do
    command -v "$prerequisite" >/dev/null || fail "missing prerequisite: $prerequisite"
done
[[ -f "$patch_file" ]] || fail 'reviewed backend patch is missing'
patch_sha=$(shasum -a 256 "$patch_file" | awk '{print $1}')
[[ "$url" =~ ^http://(127\.0\.0\.1|localhost|\[::1\]):([0-9]+)$ ]] || fail 'URL must be an HTTP loopback origin with explicit port'
url_host=${BASH_REMATCH[1]}
port=${BASH_REMATCH[2]}
[[ ${#port} -le 5 ]] && ((10#$port >= 1 && 10#$port <= 65535)) || fail 'invalid port'
for name in "$connection" "$backend" "$database"; do
    [[ "$name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || fail 'explicit connection and container names are required'
done
[[ "$backend" != "$database" ]] || fail 'backend and database must be different containers'
[[ -d "$output" && ! -L "$output" ]] || fail 'output must be an existing, empty directory, not a symlink'
output=$(cd "$output" && pwd -P)
shopt -s nullglob dotglob
entries=("$output"/*)
[[ ${#entries[@]} == 0 ]] || fail 'output directory is not empty'
shopt -u nullglob dotglob
chmod 700 "$output"

# Reading connection configuration does not contact an engine. Reject remote targets first.
connection_json=$(podman system connection list --format json | jq -ce --arg name "$connection" '
  [.[]|select(.Name==$name)] | if length==1 then .[0] else error("connection not found or ambiguous") end')
printf '%s' "$connection_json" | jq -e '
  .URI | test("^ssh://[^/@[:space:]]+@(127[.]0[.]0[.]1|localhost|\\[::1\\]):[0-9]+/[^?#[:space:]]+$") or
         test("^unix:///[^?#[:space:]]+$")' >/dev/null || fail 'Podman connection must use loopback SSH or a local Unix socket'
printf '%s' "$connection_json" | jq '{Name,URI}' > "$output/connection.json"
engine=(podman --connection "$connection")
run_id="sb-probe-$(date -u +%Y%m%dT%H%M%SZ)-$$"
normal_user="$run_id-normal"
quota_user="$run_id-quota"
missing_user="$run_id-missing"
concurrent_user="$run_id-concurrent"
zero_user="$run_id-zero"
error_user="$run_id-error"
retry_user="$run_id-retry"
model=showback-synthetic-model
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
database_stopped=false
: > "$output/checks.jsonl"
cp "$0" "$output/probe.sh"
probe_sha=$(shasum -a 256 "$output/probe.sh" | awk '{print $1}')
restore_database() {
    [[ "$database_stopped" == true ]] || return 0
    "${engine[@]}" start "$database" > "$output/database-restore.txt" 2> "$output/database-restore.stderr" || return 1
    local deadline=$((SECONDS + 30))
    while ((SECONDS < deadline)); do
        if "${engine[@]}" exec "$database" sh -c '
          exec pg_isready -q -h 127.0.0.1 -U "${POSTGRES_USER:-${POSTGRESQL_USER:-postgres}}"' \
          >> "$output/database-restore.txt" 2>> "$output/database-restore.stderr"; then
            database_stopped=false
            return 0
        fi
        sleep 1
    done
    return 1
}
finish() {
    local code=$?
    trap - EXIT
    if ! restore_database; then
        printf 'Local backend test: disposable database could not be restored\n' >&2
        code=1
    fi
    jq -n --arg run_id "$run_id" --arg started "$started" --arg ended "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg url "$url" --arg connection "$connection" --arg backend "$backend" --arg database "$database" \
      --arg patch_sha "$patch_sha" --arg probe_sha "$probe_sha" --argjson database_stopped "$database_stopped" \
      --argjson code "$code" --slurpfile checks "$output/checks.jsonl" \
      '{schema_version:1,evidence_kind:"synthetic_local_runtime",expected_source_commit:"f9a56b1769b0933e3fe7454a174b1f42a229f07a",
        expected_patch_sha256:$patch_sha,probe_sha256:$probe_sha,database_restored:($database_stopped|not),
        run_id:$run_id,started:$started,ended:$ended,url:$url,connection:$connection,
        backend_container:$backend,database_container:$database,exit_code:$code,complete:($code==0),checks:$checks,
        boundary:"Local API/database probes only; no gateway, inference, SSO, deployment or financial-completeness qualification."}' \
      > "$output/result.json"
    exit "$code"
}
trap finish EXIT
record() {
    jq -nc --arg check "$1" --arg result "$2" --arg detail "$3" \
      '{check:$check,result:$result,assertion_passed:($result!="fail"),detail:$detail}' >> "$output/checks.jsonl"
}
expect() {
    local name=$1 result=$2 detail=$3
    shift 3
    if "$@"; then record "$name" "$result" "$detail"
    else record "$name" fail "$detail"; fail "$name"; fi
}

# Record image/container identity without persisting environment variables or database credentials.
for role in backend database; do
    if [[ "$role" == backend ]]; then container=$backend; else container=$database; fi
    "${engine[@]}" inspect "$container" | jq -e '.[0] | select(.State.Running==true) |
      {Id,Name,Image,ImageName,State:{Running:.State.Running},ports:.NetworkSettings.Ports,
       declared_source_revision:.Config.Labels["org.opencontainers.image.revision"],
       configured_quota:([.Config.Env[]? | select(startswith("MONTHLY_TOKEN_QUOTA="))] | first)}' \
      > "$output/$role-container.json"
done
image_id=$(jq -er '.Image' "$output/backend-container.json")
"${engine[@]}" image inspect "$image_id" | jq -e '.[0] |
  {Id,Os,Architecture,declared_source:(.Labels // .Config.Labels)["org.opencontainers.image.source"],
   declared_source_revision:(.Labels // .Config.Labels)["org.opencontainers.image.revision"],
   declared_patch_sha256:(.Labels // .Config.Labels)["io.showback.patch.sha256"]}' \
  > "$output/backend-image.json"
expect image_source_platform pass 'Image metadata identifies the reviewed Noyitz revision and linux/amd64 target.' \
  jq -e --arg image "$image_id" --arg patch "$patch_sha" '.Id==$image and .Os=="linux" and .Architecture=="amd64" and
    .declared_source=="https://github.com/noyitz/ai-gateway-metering-service" and
    .declared_source_revision=="f9a56b1769b0933e3fe7454a174b1f42a229f07a" and .declared_patch_sha256==$patch' \
  "$output/backend-image.json" >/dev/null
expect loopback_binding pass 'Supplied URL matches the named backend port 8080, published only on loopback.' \
  jq -e --arg host "$url_host" --argjson port "$((10#$port))" '
    .ports["8080/tcp"] as $bindings |
    ($bindings|type=="array" and length>0) and
    all($bindings[]; .HostIp=="127.0.0.1" or .HostIp=="::1") and
    any($bindings[]; (.HostPort|tonumber)==$port and
      ($host=="localhost" or ($host=="127.0.0.1" and .HostIp=="127.0.0.1") or
       ($host=="[::1]" and .HostIp=="::1")))' "$output/backend-container.json" >/dev/null
expect explicit_quota pass 'The supplied backend has MONTHLY_TOKEN_QUOTA=1000.' \
  jq -e '.configured_quota=="MONTHLY_TOKEN_QUOTA=1000"' "$output/backend-container.json" >/dev/null

http() {
    local name=$1 method=$2 path=$3 body=${4:-} header=${5:-} code elapsed
    jq -n --arg method "$method" --arg path "$path" --arg body "$body" --arg header "$header" \
      '{method:$method,path:$path,body_file:$body,extra_header:$header}' > "$output/$name.request.json"
    local args=(-q --silent --show-error --noproxy '*' --proto '=http' --connect-timeout 2 --max-time 5
      --max-redirs 0 --request "$method" --dump-header "$output/$name.headers"
      --output "$output/$name.body" --write-out '%{http_code} %{time_total}\n')
    [[ -z "$body" ]] || args+=(--header 'Content-Type: application/json' --data-binary "@$body")
    [[ -z "$header" ]] || args+=(--header "$header")
    curl "${args[@]}" "$url$path" > "$output/$name.transfer" 2> "$output/$name.stderr"
    read -r code elapsed < "$output/$name.transfer"
    printf '%s' "$code" > "$output/$name.status"
    printf '%s' "$elapsed" > "$output/$name.seconds"
}
status_is() { [[ $(cat "$output/$1.status") == "$2" ]]; }
balance() {
    http "$1" GET "/api/v1/customers/$2/entitlements/inference-tokens/value?model=$model"
    expect "$1-http" pass 'Entitlement endpoint returns HTTP 200, including denials.' status_is "$1" 200
}
sql() {
    local name=$1 query=$2
    printf '%s\n' "$query" > "$output/$name.sql"
    "${engine[@]}" exec -i "$database" sh -c '
      export PGPASSWORD="${POSTGRES_PASSWORD:-${POSTGRESQL_PASSWORD:-}}"
      export PGCONNECT_TIMEOUT=3 PGOPTIONS="-c statement_timeout=5000"
      probe_db_user="${POSTGRES_USER:-${POSTGRESQL_USER:-postgres}}"
      exec psql -X -q -A -t -v ON_ERROR_STOP=1 \
        -h 127.0.0.1 -U "$probe_db_user" \
        -d "${POSTGRES_DB:-${POSTGRESQL_DATABASE:-$probe_db_user}}"' \
      < "$output/$name.sql" > "$output/$name.json" 2> "$output/$name.stderr"
    jq -e . "$output/$name.json" >/dev/null
}
snapshot() {
    sql "$1" "SELECT json_build_object(
      'events',(SELECT COALESCE(json_agg(row_to_json(e)), '[]'::json) FROM
        (SELECT id,event_id,timestamp,username,group_name,subscription,provider,model,prompt_tokens,
          completion_tokens,total_tokens,cached_input_tokens,cache_creation_tokens,reasoning_tokens,
          source,user_agent,status_code,usage_complete,raw_event,cost_usd::text AS cost_usd
         FROM usage_events WHERE username LIKE '$run_id-%' ORDER BY id) e),
      'raw_by_user',(SELECT COALESCE(json_agg(row_to_json(r)), '[]'::json) FROM
        (SELECT username,COUNT(*) AS requests,SUM(total_tokens) AS total_tokens,
          COALESCE(SUM(cost_usd),0)::numeric(20,8)::text AS known_cost_usd
         FROM usage_events WHERE username LIKE '$run_id-%' GROUP BY username ORDER BY username) r),
      'hourly',(SELECT COALESCE(json_agg(row_to_json(h)), '[]'::json) FROM
        (SELECT username,SUM(requests) AS requests,SUM(total_tokens) AS total_tokens,
          COALESCE(SUM(cost_usd),0)::numeric(20,8)::text AS known_cost_usd
         FROM usage_hourly WHERE username LIKE '$run_id-%' GROUP BY username ORDER BY username) h));"
}
parity() {
    expect "$1" pass 'Per-user raw and hourly request/token/known-cost subtotals agree; incomplete rows remain marked separately.' \
      jq -e '.raw_by_user==.hourly' "$output/$2.json" >/dev/null
}
event() {
    jq -n --arg id "$run_id-$1" --arg user "$2" --arg model "$model" --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --argjson input "$3" --argjson output "$4" \
      '{specversion:"1.0",id:$id,source:"showback-local-validation",type:"inference.tokens.used",subject:$user,
        time:$time,datacontenttype:"application/json",data:{user:$user,group:"synthetic",subscription:"synthetic",
        provider:"synthetic",model:$model,prompt_tokens:$input,completion_tokens:$output,total_tokens:($input+$output),
        cached_input_tokens:0,cache_creation_tokens:0,reasoning_tokens:0,duration_ms:123,user_agent:"synthetic-local-validation"}}' \
      > "$output/$1.event.json"
}
wait_ready() {
    local prefix=$1 deadline=$((SECONDS + 45)) attempt=0 remaining
    while ((SECONDS < deadline)); do
        attempt=$((attempt + 1))
        remaining=$((deadline - SECONDS))
        ((remaining <= 2)) || remaining=2
        if curl -q --silent --show-error --noproxy '*' --proto '=http' --connect-timeout 1 --max-time "$remaining" \
          --output "$output/$prefix-$attempt.body" --dump-header "$output/$prefix-$attempt.headers" \
          --write-out '%{http_code}' "$url/ready" > "$output/$prefix-$attempt.status" \
          2> "$output/$prefix-$attempt.stderr" && status_is "$prefix-$attempt" 200; then
            return 0
        fi
        sleep 1
    done
    return 1
}
reject_variant() {
    local name=$1 filter=$2
    jq --arg id "$run_id-$name" "$filter | .id=\$id" "$output/invalid-seed.event.json" > "$output/$name.event.json"
    http "$name" POST /api/v1/events "$output/$name.event.json"
    expect "$name" pass 'Invalid event is rejected with 400 before ledger or quota changes.' status_is "$name" 400
}

http health GET /health
expect health pass 'Health endpoint returns 200 with the primary database available.' status_is health 200
http ready GET /ready
expect ready pass 'Readiness endpoint returns 200 with the primary database available.' status_is ready 200
balance baseline "$normal_user"
expect fresh_balance pass 'New synthetic user starts with 1000 tokens available.' \
  jq -e '.hasAccess==true and .usage==0 and .balance==1000 and .overage==0' "$output/baseline.body" >/dev/null

event valid "$normal_user" 100 20
http valid POST /api/v1/events "$output/valid.event.json"
expect valid_event pass 'Unauthenticated synthetic event is acknowledged with 204.' status_is valid 204
snapshot first
expect persisted_row pass 'The exact synthetic token and identity fields reach PostgreSQL.' \
  jq -e --arg user "$normal_user" --arg id "$run_id-valid" --arg model "$model" \
    --slurpfile original "$output/valid.event.json" '
    .events|length==1 and .[0].event_id==$id and .[0].username==$user and .[0].model==$model and
    .[0].source=="showback-local-validation" and .[0].prompt_tokens==100 and .[0].completion_tokens==20 and
    .[0].total_tokens==120 and .[0].status_code==200 and .[0].usage_complete==true and
    .[0].cost_usd!=null and .[0].raw_event==$original[0] and .[0].group_name=="synthetic" and
    .[0].subscription=="synthetic" and .[0].provider=="synthetic" and
    .[0].user_agent=="synthetic-local-validation"' "$output/first.json" >/dev/null
parity first_parity first
balance after_valid "$normal_user"
expect usage_increment pass 'Persisted usage is reflected immediately in the token entitlement.' \
  jq -e '.hasAccess==true and .usage==120 and .balance==880' "$output/after_valid.body" >/dev/null

http replay POST /api/v1/events "$output/valid.event.json"
expect replay_http pass 'An identical replay is acknowledged with 204.' status_is replay 204
snapshot replay
expect replay_unchanged pass 'Identical source/id replay leaves raw rows, tokens, costs and hourly aggregates unchanged.' \
  cmp -s "$output/first.json" "$output/replay.json"
jq -S . "$output/valid.event.json" > "$output/reordered.event.json"
http reordered POST /api/v1/events "$output/reordered.event.json"
expect reordered_http pass 'JSON member order does not change event identity.' status_is reordered 204
snapshot reordered
expect reordered_unchanged pass 'Semantically identical reordered JSON leaves all recorded amounts unchanged.' \
  cmp -s "$output/first.json" "$output/reordered.json"
jq '.audit_note="changed unrecognized metadata"' "$output/valid.event.json" > "$output/conflict.event.json"
http conflict POST /api/v1/events "$output/conflict.event.json"
expect conflict_http pass 'Changing an unrecognized field under the same source/id returns 409.' status_is conflict 409
snapshot conflict
expect conflict_unchanged pass 'A conflicting payload changes neither raw ledger nor hourly aggregates.' \
  cmp -s "$output/first.json" "$output/conflict.json"
balance after_replay "$normal_user"
expect replay_entitlement pass 'Replays and conflicts consume no additional quota.' \
  jq -e '.usage==120 and .balance==880 and .hasAccess==true' "$output/after_replay.body" >/dev/null

jq '.source="showback-local-other-source"' "$output/valid.event.json" > "$output/other-source.event.json"
http other_source POST /api/v1/events "$output/other-source.event.json"
expect different_source_http pass 'The same ID from a different source is a distinct event.' status_is other_source 204
snapshot other_source
expect different_source_recorded pass 'Both source/id pairs are persisted exactly once.' \
  jq -e --arg user "$normal_user" --arg id "$run_id-valid" '
    [.events[]|select(.username==$user)]|length==2 and all(.[];.event_id==$id and .usage_complete==true) and
    (map(.source)|sort)==["showback-local-other-source","showback-local-validation"]' "$output/other_source.json" >/dev/null
parity source_parity other_source

# Exercise concurrent first delivery, then compare the complete ledger snapshot after another replay.
event concurrent "$concurrent_user" 17 3
pids=()
for attempt in 1 2 3 4 5 6 7 8; do
    (trap - EXIT; http "concurrent-$attempt" POST /api/v1/events "$output/concurrent.event.json") &
    pids+=("$!")
done
deliveries_succeeded=true
for pid in "${pids[@]}"; do
    wait "$pid" || deliveries_succeeded=false
done
expect concurrent_transport pass 'All eight concurrent HTTP requests completed within their timeout.' test "$deliveries_succeeded" = true
for attempt in 1 2 3 4 5 6 7 8; do
    expect "concurrent-$attempt-http" pass 'Concurrent identical delivery returns 204.' status_is "concurrent-$attempt" 204
done
snapshot concurrent
expect concurrent_once pass 'Concurrent first deliveries persist one row, one request and 20 tokens.' \
  jq -e --arg user "$concurrent_user" '
    ([.events[]|select(.username==$user)]|length)==1 and
    ([.hourly[]|select(.username==$user)]|length==1 and .[0].requests==1 and .[0].total_tokens==20)' \
  "$output/concurrent.json" >/dev/null
parity concurrent_parity concurrent
http concurrent_replay POST /api/v1/events "$output/concurrent.event.json"
expect concurrent_replay_http pass 'A replay of the concurrently inserted event succeeds.' status_is concurrent_replay 204
snapshot concurrent_replay
expect concurrent_replay_unchanged pass 'Replay after concurrent delivery leaves tokens, costs and counts unchanged.' \
  cmp -s "$output/concurrent.json" "$output/concurrent_replay.json"
balance concurrent_balance "$concurrent_user"
expect concurrent_quota pass 'Eight concurrent deliveries consume exactly 20 tokens of quota.' \
  jq -e '.usage==20 and .balance==980 and .hasAccess==true' "$output/concurrent_balance.body" >/dev/null

event quota "$quota_user" 900 200
http quota POST /api/v1/events "$output/quota.event.json"
expect quota_event pass 'Over-budget usage ingestion still accepts the recorded event.' status_is quota 204
balance quota_denial "$quota_user"
expect quota_denial pass 'Backend returns hasAccess=false; no gateway-generated 429 is tested.' \
  jq -e '.usage==1100 and .balance==0 and .overage==100 and .hasAccess==false' "$output/quota_denial.body" >/dev/null

# The pinned handler asynchronously audits a denied balance check in the same ledger.
# Its stored status 429 is synthetic; the HTTP response above remains 200.
denial_filter='def is_denial:
  .source=="metering-quota" and .provider=="gateway" and .username==$user and .model==$model and
  (.event_id|startswith("deny-")) and .status_code==429 and .prompt_tokens==0 and
  .completion_tokens==0 and .total_tokens==0 and (.cost_usd|tonumber)==0;
  [.events[]|select(.source=="metering-quota")]|length==1 and all(.[];is_denial)'
denial_recorded=false
for attempt in 1 2 3 4; do
    snapshot "denial-audit-$attempt"
    if jq -e --arg user "$quota_user" --arg model "$model" "$denial_filter" \
      "$output/denial-audit-$attempt.json" >/dev/null; then
        denial_recorded=true
        break
    fi
    sleep 1
done
expect denial_audit observed-limitation \
  'The balance denial adds one zero-token audit row with stored status 429; no gateway HTTP 429 was exercised.' \
  test "$denial_recorded" = true

snapshot before_rejections
event invalid-seed "$missing_user" 1 1
reject_variant missing_usage 'del(.data.prompt_tokens,.data.completion_tokens,.data.total_tokens,
  .data.cached_input_tokens,.data.cache_creation_tokens,.data.reasoning_tokens)'
reject_variant null_usage '.data.total_tokens=null'
reject_variant partial_usage 'del(.data.completion_tokens)'
reject_variant negative_usage '.data.prompt_tokens=-1'
reject_variant wrong_type_usage '.data.prompt_tokens="1"'
reject_variant out_of_range_usage '.data.reasoning_tokens=2147483648'
reject_variant inconsistent_usage '.data.total_tokens=0'
reject_variant missing_model 'del(.data.model)'
reject_variant wrong_event_type '.type="inference.unknown"'
reject_variant error_partial '.type="inference.request.error" | .data.status_code=503 | del(.data.prompt_tokens)'
reject_variant error_null '.type="inference.request.error" | .data.status_code=503 | .data.prompt_tokens=null'
printf '{invalid json' > "$output/invalid-json.event.json"
cat "$output/invalid-seed.event.json" "$output/invalid-seed.event.json" > "$output/trailing-json.event.json"
# A JSON encoder cannot produce duplicate keys; preserve this literal wire-format rejection case.
jq -c --arg id "$run_id-duplicate_data" '.id=$id' "$output/invalid-seed.event.json" |
  sed 's/}$/,"data":{}}/' > "$output/duplicate-data.event.json"
for probe in invalid-json trailing-json duplicate-data; do
    http "$probe" POST /api/v1/events "$output/$probe.event.json"
    expect "$probe" pass 'Malformed JSON, trailing values or duplicate object keys are rejected.' status_is "$probe" 400
done
http wrong_method GET /api/v1/events
expect wrong_method pass 'Event ingestion rejects GET with 405.' status_is wrong_method 405
for probe in dashboard forged_header; do
    extra=''
    [[ "$probe" != forged_header ]] || extra="X-Forwarded-User: $normal_user"
    http "$probe" GET /dashboard '' "$extra"
    expect "$probe" pass 'A session cookie is required; a supplied identity header is insufficient.' status_is "$probe" 302
    expect "$probe-login" pass 'Unauthenticated requests redirect to the local login path.' \
      grep -Eiq '^Location: /login[[:space:]]*$' "$output/$probe.headers"
done
snapshot after_rejections
expect rejected_events_not_persisted pass 'Rejected requests added no usage rows.' \
  cmp -s "$output/before_rejections.json" "$output/after_rejections.json"
balance rejected_balance "$missing_user"
expect rejected_quota pass 'Rejected events consume no quota.' \
  jq -e '.usage==0 and .balance==1000 and .hasAccess==true' "$output/rejected_balance.body" >/dev/null

event zero "$zero_user" 0 0
http zero POST /api/v1/events "$output/zero.event.json"
expect zero_http pass 'Six explicit zero counters are valid measured usage.' status_is zero 204
event native-error "$error_user" 0 0
jq '.type="inference.request.error" | .data.status_code=503 | .data.error_type="synthetic-upstream-error" |
  del(.data.prompt_tokens,.data.completion_tokens,.data.total_tokens,.data.cached_input_tokens,
    .data.cache_creation_tokens,.data.reasoning_tokens)' "$output/native-error.event.json" > "$output/error-no-usage.event.json"
http native_error POST /api/v1/events "$output/error-no-usage.event.json"
expect native_error_http pass 'Native error events without token keys are retained as incomplete usage.' status_is native_error 204
snapshot before_restart
expect measured_zero pass 'Explicit zero remains usage_complete=true with known zero cost.' \
  jq -e --arg user "$zero_user" '[.events[]|select(.username==$user)]|length==1 and .[0].usage_complete==true and
    .[0].prompt_tokens==0 and .[0].completion_tokens==0 and .[0].total_tokens==0 and
    .[0].cost_usd!=null and (.[0].cost_usd|tonumber)==0' "$output/before_restart.json" >/dev/null
unknown_filter='[.events[]|select(.username==$user)]|length==1 and .[0].usage_complete==false and
  .[0].cost_usd==null and .[0].status_code==503 and .[0].raw_event==$original[0] and
  .[0].prompt_tokens==0 and .[0].completion_tokens==0 and .[0].total_tokens==0'
expect incomplete_usage pass 'Unknown usage retains its raw error and NULL cost; integer zeros are legacy sentinels, not measured usage.' \
  jq -e --arg user "$error_user" --slurpfile original "$output/error-no-usage.event.json" "$unknown_filter" \
  "$output/before_restart.json" >/dev/null
parity before_restart_parity before_restart
record audit_request_counts observed-limitation \
  'Hourly requests include denial and incomplete-error audit rows; known-cost sums do not assert total cost completeness.'

# The same database is retained during backend restart; replay must remain idempotent.
"${engine[@]}" restart --time 10 "$backend" > "$output/backend-restart.txt" 2> "$output/backend-restart.stderr"
expect restart_ready pass 'Backend readiness returns within the bounded restart probe.' wait_ready restart-ready
snapshot after_restart
expect restart_persistence pass 'Existing database rows and synthetic rollups survive backend restart unchanged.' \
  cmp -s "$output/before_restart.json" "$output/after_restart.json"
balance restart_balance "$normal_user"
expect restart_entitlement pass 'The restarted backend reads the retained usage.' \
  jq -e '.usage==240 and .balance==760 and .hasAccess==true' "$output/restart_balance.body" >/dev/null
http restart_replay POST /api/v1/events "$output/valid.event.json"
expect restart_replay_http pass 'Identical replay after backend restart is acknowledged.' status_is restart_replay 204
snapshot restart_replay
expect restart_replay_unchanged pass 'Restart and replay preserve every raw row, token, known cost and hourly aggregate.' \
  cmp -s "$output/before_restart.json" "$output/restart_replay.json"
expect incomplete_after_restart pass 'Unknown usage remains incomplete with NULL cost after restart.' \
  jq -e --arg user "$error_user" --slurpfile original "$output/error-no-usage.event.json" "$unknown_filter" \
  "$output/restart_replay.json" >/dev/null

# Stop only the explicitly named disposable database. The EXIT trap restores it on any failure.
database_stopped=true
"${engine[@]}" stop --time 10 "$database" > "$output/database-stop.txt" 2> "$output/database-stop.stderr"
for probe in health ready; do
    http "outage-$probe" GET "/$probe"
    expect "outage-$probe" pass 'Database unavailability produces HTTP 503.' status_is "outage-$probe" 503
    expect "outage-$probe-latency" pass 'Database health failure returns in no more than three seconds.' \
      jq -e 'type=="number" and .>=0 and .<=3' "$output/outage-$probe.seconds" >/dev/null
done
http outage_balance GET "/api/v1/customers/$normal_user/entitlements/inference-tokens/value?model=$model"
expect outage_balance pass 'Quota lookup fails with 500 instead of claiming a usable balance.' status_is outage_balance 500
event retry "$retry_user" 11 9
http outage_ingest POST /api/v1/events "$output/retry.event.json"
expect outage_ingest pass 'Ingestion fails with 500 while the database is unavailable.' status_is outage_ingest 500
expect outage_ingest_bounded pass 'Failed ingestion returns within three seconds under its two-second database deadline.' \
  jq -e 'type=="number" and .>=0 and .<=3' "$output/outage_ingest.seconds" >/dev/null
expect database_restarted pass 'The named disposable database is restored and accepts connections.' restore_database
expect database_recovery_ready pass 'Backend readiness recovers after database restart.' wait_ready database-recovery-ready
http recovered_health GET /health
expect recovered_health pass 'Health returns 200 after database recovery.' status_is recovered_health 200
snapshot after_outage
expect failed_ingest_absent pass 'Failed ingestion committed no raw or hourly changes.' \
  cmp -s "$output/restart_replay.json" "$output/after_outage.json"
http retry POST /api/v1/events "$output/retry.event.json"
expect retry_http pass 'The same failed delivery succeeds after database recovery.' status_is retry 204
snapshot retry
expect retry_once pass 'Recovery retry records exactly one event and 20 tokens.' \
  jq -e --arg user "$retry_user" '[.events[]|select(.username==$user)]|length==1 and
    .[0].usage_complete==true and .[0].total_tokens==20 and .[0].cost_usd!=null' "$output/retry.json" >/dev/null
http retry_replay POST /api/v1/events "$output/retry.event.json"
expect retry_replay_http pass 'Replaying the recovered delivery succeeds without a second charge.' status_is retry_replay 204
snapshot final
expect retry_replay_unchanged pass 'Recovery retry replay leaves rows, tokens, known costs and hourly aggregates unchanged.' \
  cmp -s "$output/retry.json" "$output/final.json"
parity final_parity final
balance recovery_balance "$retry_user"
expect recovery_quota pass 'A failed attempt, retry and replay consume exactly 20 tokens of quota.' \
  jq -e '.usage==20 and .balance==980 and .hasAccess==true' "$output/recovery_balance.body" >/dev/null
printf 'Local checks completed; evidence: %s/result.json\n' "$output"
