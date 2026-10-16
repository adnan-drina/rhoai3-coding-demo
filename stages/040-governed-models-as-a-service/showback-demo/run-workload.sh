#!/usr/bin/env bash
# Preview bounded showback traffic, or explicitly execute against the guarded MaaS environment.
# New run directories only. No provisioning, deployment, retries, or credentials in arguments/files.
# Usage: run-workload.sh [--scenario FILE] [--mode workload|access-probe|quota-probe] [--execute --output NEW_DIR]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

scenario="$SCRIPT_DIR/scenario.json"
mode=workload
execute=false
output=""
stream=false
insecure=false
quota_model=""
quota_requests=3
quota_seconds=120
usage() {
    cat <<'USAGE'
Usage: run-workload.sh [--scenario FILE] [--execute --output NEW_DIR]
  [--mode workload|access-probe|quota-probe] [--stream] [--insecure]
  [--quota-model MODEL] [--quota-requests 1..20] [--quota-seconds 120..300]
Default: offline JSON preview, no credentials, files, login or HTTP.
Execute: guarded MaaS requests; keys and gateway are read from scenario-named environment variables.
Quota probe: Support only; no limit changes; exit 1 unless a 429 was observed.
USAGE
}
fail() { printf '%s\n' "$1" >&2; exit 2; }
while (($#)); do
    case "$1" in
        --scenario|--output|--mode|--quota-model|--quota-requests|--quota-seconds)
            (($# >= 2)) || { usage >&2; exit 2; }
            case "$1" in
                --scenario) scenario="$2" ;;
                --output) output="$2" ;;
                --mode) mode="$2" ;;
                --quota-model) quota_model="$2" ;;
                --quota-requests) quota_requests="$2" ;;
                --quota-seconds) quota_seconds="$2" ;;
            esac
            shift 2
            ;;
        --execute) execute=true; shift ;;
        --stream) stream=true; shift ;;
        --insecure) insecure=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
case "$mode" in workload|access-probe|quota-probe) ;; *) fail 'Invalid mode.' ;; esac
case "$quota_requests:$quota_seconds" in *[!0-9:]*|:*|*:) fail 'Invalid quota bounds.' ;; esac
((quota_requests >= 1 && quota_requests <= 20 && quota_seconds >= 120 && quota_seconds <= 300)) || fail 'Invalid quota bounds.'
command -v jq >/dev/null

# Validate every operator-controlled admission bound before reading credentials.
validation='def integer: type=="number" and .==floor;
 def bounded($low;$high): integer and . >= $low and . <= $high;
 def name: type=="string" and test("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$");
 . as $s | .limits as $l |
 .schema_version==1 and (.teams|keys)==["engineering","marketing","support"] and
 (.models|length)==2 and all(.models[];.namespace|name) and
 ($l.max_requests|bounded(1;200)) and ($l.request_timeout_seconds|bounded(1;45)) and
 ($l.drain_seconds|bounded(1;50)) and ($l.start_delay_seconds|bounded(0;60)) and
 ($l.max_wall_seconds|bounded(1;780)) and ($l.max_response_bytes|bounded(1024;2000000)) and
 $l.max_retries==0 and $l.drain_seconds >= $l.request_timeout_seconds and
 (.seed|bounded(0;2147483647)) and (.gateway_env|test("^[A-Z][A-Z0-9_]*$")) and
 ([.phases[].id]==["busy","quiet","idle"]) and (.phases[-1].teams|length)==0 and
 ([.phases[].duration_seconds]|add) <= $l.max_wall_seconds and
 all(.phases[]; (.duration_seconds|bounded(1;240)) and
   .duration_seconds > ($l.drain_seconds+$l.start_delay_seconds) and
   (.spacing_multiplier|bounded(1;100)) and (.teams|length)==(.teams|unique|length) and
   all(.teams[]; . as $team | $s.teams|has($team))) and
 all(.teams[]; (.subscription|name) and .concurrency==1 and (.input_target_tokens|bounded(1;8192)) and
   (.max_output_tokens|bounded(1;2048)) and (.spacing_seconds|bounded(1;120)) and
   (.key_env|test("^[A-Z][A-Z0-9_]*$")) and (.models|length)>0 and
   all(.models|to_entries[]; (.value.weight|bounded(1;20)) and
     (.key|test("^[a-z0-9][a-z0-9-]*$")) and (.key as $m | $s.models|has($m))))'
jq -e "$validation" "$scenario" >/dev/null 2>&1 || fail 'Invalid scenario or execution bounds.'
if [[ "$mode" == quota-probe ]]; then
    jq -e --arg model "$quota_model" '.teams.support.models|has($model)' "$scenario" >/dev/null || fail 'Quota probe needs an authorized --quota-model.'
elif [[ -n "$quota_model" ]]; then
    fail '--quota-model requires quota-probe mode.'
fi

plan="$(jq -c --arg mode "$mode" --argjson seconds "$quota_seconds" '
 .limits as $l |
 (if $mode=="workload" then .phases else
   [{id:$mode,duration_seconds:([($l.max_wall_seconds), (if $mode=="access-probe" then 180 else $seconds end)]|min),
     teams:(if $mode=="access-probe" then ["engineering","marketing","support"] else ["support"] end),
     spacing_multiplier:1}] end) |
 reduce .[] as $p ({offset:0,phases:[]};
   .phases += [$p + {start_offset:.offset,end_offset:(.offset+$p.duration_seconds),
     submit_after_offset:(.offset+$l.start_delay_seconds),
     submit_until_offset:(.offset+$p.duration_seconds-$l.drain_seconds)}] | .offset += $p.duration_seconds) | .phases
' "$scenario")"
cases="$(jq -c '. as $s | [.teams|to_entries[]| .key as $team | .value as $t | $s.models|keys[]| . as $model |
 {team:$team,model:$model,expected_access:(if $t.models|has($model) then "allow" else "deny" end)}]' "$scenario")"
if [[ "$execute" == false ]]; then
    jq -n --slurpfile s "$scenario" --argjson phases "$plan" --argjson cases "$cases" \
        --arg mode "$mode" --argjson count "$quota_requests" '
      {schema_version:1,evidence_kind:"preview",network_requests:0,mode:$mode,
       scenario_id:$s[0].scenario_id,parameters_status:"unqualified",phases:$phases,
       max_requests:(if $mode=="access-probe" then 6 elif $mode=="quota-probe" then $count else $s[0].limits.max_requests end),
       access_cases:$cases,limits:$s[0].limits}'
    exit 0
fi

# Only explicit execution reads the environment and verifies the target cluster.
[[ -n "$output" && ! -e "$output" && ! -L "$output" ]] || fail '--execute requires a new --output directory.'
load_env
check_oc_logged_in >&2
gateway_env="$(jq -r .gateway_env "$scenario")"
gateway="${!gateway_env:-}"
printf '%s' "$gateway" | jq -Re 'test("^https://[^/@?#[:space:]]+(:[0-9]+)?(/v1(/chat/completions)?)?/?$")' >/dev/null || fail 'Invalid HTTPS gateway base.'
gateway="${gateway%/}"
gateway="${gateway%/v1/chat/completions}"
gateway="${gateway%/v1}/v1/chat/completions"
teams=(engineering marketing support)
for team in "${teams[@]}"; do
    [[ "$mode" != quota-probe || "$team" == support ]] || continue
    key_env="$(jq -r --arg team "$team" '.teams[$team].key_env' "$scenario")"
    key="${!key_env:-}"
    [[ -n "$key" && "$key" != *$'\n'* && "$key" != *$'\r'* ]] || fail 'Missing or invalid team key environment.'
done
unset key
command -v curl >/dev/null
umask 077
mkdir -m 700 "$output"
state="$output/.requests"
mkdir -m 700 "$state"
: > "$output/receipts.jsonl"
iso() { jq -nr --argjson epoch "$1" '$epoch|todateiso8601'; }
started_epoch="$(date -u +%s)"
started_seconds=$SECONDS
run_id="showback-${started_epoch}-$$-${RANDOM}"
scenario_hash="$(shasum -a 256 "$scenario" | cut -d ' ' -f 1)"
kind="$(jq -r 'if .status=="synthetic_fixture" then "synthetic_fixture" else "observed" end' "$scenario")"
max_requests="$(jq -r .limits.max_requests "$scenario")"
request_timeout="$(jq -r .limits.request_timeout_seconds "$scenario")"
max_bytes="$(jq -r .limits.max_response_bytes "$scenario")"
stop_at="$(printf '%s' "$plan" | jq -r '.[-1].end_offset')"
run_status=running
request_count=0
pids=("" "" "")
ids=("" "" "")
deadlines=(0 0 0)
counts=(0 0 0)
next_due=(0 0 0)
stopped=(false false false)
last_phase=""
quota_observed=false

write_manifest() {
    local ended=null
    [[ "$run_status" == running ]] || ended="$(iso "$((started_epoch+SECONDS-started_seconds))" | jq -R .)"
    jq -n --slurpfile s "$scenario" --slurpfile receipts "$output/receipts.jsonl" \
        --arg run "$run_id" --arg hash "$scenario_hash" --arg mode "$mode" --arg kind "$kind" \
        --arg status "$run_status" --argjson start "$started_epoch" --argjson end "$ended" \
        --argjson phases "$plan" --argjson count "$request_count" --argjson stream "$stream" \
        --argjson quota "$quota_observed" '
      {schema_version:1,run_id:$run,scenario_id:$s[0].scenario_id,policy_version:$s[0].policy_version,
       scenario_sha256:$hash,mode:$mode,evidence_kind:$kind,status:$status,parameters_status:"unqualified",
       started_at:($start|todateiso8601),ended_at:$end,limits:$s[0].limits,stream:$stream,
       phase_windows:[$phases[]|{id,start:($start+.start_offset|todateiso8601),end:($start+.end_offset|todateiso8601),
         submit_after:($start+.submit_after_offset|todateiso8601),submit_until:($start+.submit_until_offset|todateiso8601)}],
       requests_started:$count,outcomes:($receipts|group_by(.status)|map({key:.[0].status,value:length})|from_entries),
       quota_429_observed:$quota,usage_source:"response usage; prompts approximate input size only"} +
       (if $mode=="access-probe" then {access_probe_passed:($status=="completed" and ($receipts|length)==6 and
         all($receipts[];.access_check=="passed"))} elif $mode=="quota-probe" then
         {quota_probe_passed:($status=="completed" and $quota)} else {} end)' > "$state/run.new"
    mv "$state/run.new" "$output/run.json"
}

# Response parsing never emits content, error bodies, headers or keys.
response_filter='def integer: type=="number" and .==floor and .>=0;
 def model: if type=="string" and test("^[A-Za-z0-9_./:@+\\-]{1,512}$") then . else null end;
 def usage: if type=="object" and (.prompt_tokens|integer) and (.completion_tokens|integer) and
   (.total_tokens|integer) and .prompt_tokens+.completion_tokens==.total_tokens then
   {input_tokens:.prompt_tokens,output_tokens:.completion_tokens,total_tokens:.total_tokens} else null end;
 if $stream then
   ($body|gsub("\r\n";"\n")|split("\n\n")|map(split("\n")|map(select(startswith("data:"))|ltrimstr("data:")|ltrimstr(" "))|
     join("\n"))|map(select(length>0))) as $events |
   if ($events|length)>0 and $events[-1]=="[DONE]" and all($events[0:-1][];. != "[DONE]") then
     ([$events[0:-1][]|try fromjson catch null]) as $chunks |
     ([$chunks[]|.model? // empty|model]|unique) as $models |
     {complete:(($chunks|length)>0 and all($chunks[];type=="object") and ($models|length)==1 and $models[0]!=null),
      actual_model:(if ($models|length)==1 then $models[0] else null end),
      usage:(if $chunks[-1].choices?==[] and ($models|length)==1 and $models[0]!=null then
        $chunks[-1].usage|usage else null end)}
   else {complete:false,actual_model:null,usage:null} end
 else
   ($body|try fromjson catch null) as $value |
   ($value.model|model) as $model |
   ($model!=null and ($value.choices|type)=="array" and ($value.choices|length)>0) as $complete |
   {complete:$complete,actual_model:$model,usage:(if $complete then $value.usage|usage else null end)}
 end'

finish_receipt() {
    local directory="$1" status="$2" code="$3" error="$4" parsed="$5"
    local elapsed=$((SECONDS-started_seconds))
    jq -n --slurpfile meta "$directory/meta.json" --arg status "$status" --argjson http "$code" \
        --arg error "$error" --argjson parsed "$parsed" --argjson now "$((started_epoch+elapsed))" '
      $meta[0] + {status:$status,http_status:$http,error_code:(if $error=="" then null else $error end),
       actual_model:$parsed.actual_model,first_event_seconds:null,ended_at:($now|todateiso8601),
       duration_seconds:($now-($meta[0].started_at|fromdateiso8601)),
       usage_status:(if $parsed.usage==null then "unknown" else "known" end),
       input_tokens:null,output_tokens:null,total_tokens:null} + ($parsed.usage // {}) |
       if .scope=="access-probe" then . + {access_check:(if
         (.expected_access=="allow" and .status=="success" and .http_status==200 and
           (.actual_model==.requested_model or .actual_model==.api_model)) or
         (.expected_access=="deny" and .http_status==403) then "passed" else "failed" end)} else . end
    ' > "$directory/result.new"
    mv "$directory/result.new" "$directory/result.json"
}

attempt() {
    local directory="$1" team="$2" attempt_number="$3"
    local key_env key escaped_key curl_pid="" reader_pid="" curl_rc=0 code status error parsed
    trap '[[ -z "$curl_pid" ]] || kill -KILL "$curl_pid" 2>/dev/null || true;
          [[ -z "$reader_pid" ]] || kill -KILL "$reader_pid" 2>/dev/null || true; exit 1' TERM INT
    key_env="$(jq -r --arg team "$team" '.teams[$team].key_env' "$scenario")"
    key="${!key_env}"
    escaped_key="${key//\\/\\\\}"
    escaped_key="${escaped_key//\"/\\\"}"
    # The reader caps the response even when the server omits Content-Length.
    mkfifo "$directory/body.pipe"
    exec 8<> "$directory/body.pipe"
    head -c "$((max_bytes+1))" < "$directory/body.pipe" > "$directory/body" 8>&- &
    reader_pid=$!
    printf '%s\n' "$reader_pid" > "$directory/reader.pid"
    local tls=()
    [[ "$insecure" == false ]] || tls=(--insecure)
    jq -n --slurpfile s "$scenario" --slurpfile meta "$directory/meta.json" --arg team "$team" \
        --argjson number "$attempt_number" --argjson stream "$stream" '
      $meta[0] as $m |
      {engineering:{
         task:"Review this fictional Java change for correctness and suggest focused tests: int total(int a, int b) { return a-b; }",
         words:["method","input","output","test","boundary","review","integer","assertion"]},
       marketing:{
         task:"Create a short campaign for the fictional Northstar notebook: headline, audience, three benefits and a call to action.",
         words:["campaign","audience","message","notebook","benefit","launch","channel","creative"]},
       support:{
         task:"Answer this fictional customer question: How can I reset my Northstar notebook preferences without deleting saved notes?",
         words:["customer","question","settings","preferences","saved","notes","steps","help"]}}[$team] as $template |
      $template.words as $words |
      ("Synthetic "+$team+" demo "+($number|tostring)+". "+$template.task+"\nFictional context: " +
        ([range(0;$m.input_target_tokens)|$words[(.+$s[0].seed+$number)%($words|length)]]|join(" ")) |
        .[0:($m.input_target_tokens*4)]) as $prompt |
      {model:$m.api_model,messages:[{role:"user",content:$prompt}],max_tokens:$m.max_output_tokens,stream:$stream} +
      (if $stream then {stream_options:{include_usage:true}} else {} end)' > "$directory/payload.json"
    printf 'header = "Authorization: Bearer %s"\n' "$escaped_key" |
        curl --silent --no-location --max-redirs 0 --retry 0 --proto '=https' \
            --connect-timeout "$request_timeout" --max-time "$request_timeout" --max-filesize "$max_bytes" \
            --config - \
            --header 'Content-Type: application/json' --header "X-Request-ID: $(jq -r .request_id "$directory/meta.json")" \
            --data-binary "@$directory/payload.json" --output "$directory/body.pipe" --write-out '%{http_code}' \
            ${tls[@]+"${tls[@]}"} "$gateway" > "$directory/http-code" 2>/dev/null 8>&- &
    curl_pid=$!
    printf '%s\n' "$curl_pid" > "$directory/curl.pid"
    wait "$curl_pid" || curl_rc=$?
    exec 8>&-
    wait "$reader_pid" || true
    code="$(cat "$directory/http-code")"
    [[ "$code" =~ ^[1-5][0-9][0-9]$ ]] || code=null
    parsed='{"actual_model":null,"usage":null}'
    status=transport_error
    error=transport_error
    if ((curl_rc==28)); then status=timeout; error=request_timeout
    elif (($(wc -c < "$directory/body") > max_bytes || curl_rc==63)); then status=invalid_response; error=response_too_large
    elif [[ "$code" != null ]] && ((code>=300)); then
        status=http_error
        error="http_$code"
        ((code<300 || code>=400)) || error=redirect_rejected
    elif ((curl_rc==0)) && [[ "$code" == 200 ]]; then
        parsed="$(jq -n --rawfile body "$directory/body" --argjson stream "$stream" "$response_filter" 2>/dev/null)" || \
            parsed='{"complete":false,"actual_model":null,"usage":null}'
        if [[ "$(printf '%s' "$parsed" | jq -r .complete)" == true ]]; then status=success; error=""
        else status=invalid_response; error=incomplete_response; fi
    fi
    finish_receipt "$directory" "$status" "$code" "$error" "$parsed"
    rm -f "$directory/body" "$directory/body.pipe" "$directory/payload.json" "$directory/http-code" \
        "$directory/curl.pid" "$directory/reader.pid"
}

stop_attempt() {
    local index="$1" reason="$2" directory="$state/${ids[$1]}" child
    kill -TERM "${pids[$index]}" 2>/dev/null || true
    for file in "$directory/curl.pid" "$directory/reader.pid"; do
        [[ -f "$file" ]] || continue
        child="$(cat "$file")"
        [[ "$child" =~ ^[0-9]+$ ]] && kill -KILL "$child" 2>/dev/null || true
    done
    kill -KILL "${pids[$index]}" 2>/dev/null || true
    wait "${pids[$index]}" 2>/dev/null || true
    finish_receipt "$directory" timeout null "$reason" '{"actual_model":null,"usage":null}'
}
collect_attempt() {
    local index="$1" directory="$state/${ids[$1]}" code
    wait "${pids[$index]}" 2>/dev/null || true
    cat "$directory/result.json" >> "$output/receipts.jsonl"
    code="$(jq -r .http_status "$directory/result.json")"
    if [[ "$code" == 429 ]]; then stopped[$index]=true; quota_observed=true; fi
    rm -rf "$directory"
    pids[$index]=""
}
finalize() {
    local index
    trap - EXIT INT TERM
    [[ "$run_status" != running ]] || run_status=interrupted
    for index in 0 1 2; do
        [[ -n "${pids[$index]}" ]] || continue
        stop_attempt "$index" run_interrupted
        collect_attempt "$index"
    done
    write_manifest
    rm -rf "$state"
}
trap finalize EXIT
trap 'run_status=interrupted; exit 1' INT TERM
write_manifest

# A single parent owns admission and receipt append order; each team has one child.
while true; do
    now=$((SECONDS-started_seconds))
    for index in 0 1 2; do
        [[ -n "${pids[$index]}" ]] || continue
        directory="$state/${ids[$index]}"
        if [[ -f "$directory/result.json" ]]; then collect_attempt "$index"
        elif ((now>=deadlines[index])); then stop_attempt "$index" request_timeout; collect_attempt "$index"
        elif ! kill -0 "${pids[$index]}" 2>/dev/null; then
            finish_receipt "$directory" transport_error null worker_exit '{"actual_model":null,"usage":null}'
            collect_attempt "$index"
        fi
    done
    ((now<stop_at)) || break
    # Probe scopes can close early after all checks finish; workload windows never do.
    if [[ "$mode" != workload && -z "${pids[0]}${pids[1]}${pids[2]}" ]]; then
        if [[ "$mode" == access-probe ]] && ((request_count>=6)); then break; fi
        if [[ "$mode" == quota-probe ]] && { [[ "$quota_observed" == true ]] || ((counts[2]>=quota_requests)); }; then break; fi
    fi
    phase="$(printf '%s' "$plan" | jq -c --argjson now "$now" '.[]|select(.start_offset<=$now and $now<.end_offset)')"
    phase_id="$(printf '%s' "$phase" | jq -r .id)"
    if [[ "$last_phase" != "$phase_id" ]]; then next_due=(0 0 0); last_phase="$phase_id"; fi
    for index in 0 1 2; do
        now=$((SECONDS-started_seconds))
        team="${teams[$index]}"
        [[ -z "${pids[$index]}" && "${stopped[$index]}" == false ]] || continue
        ((request_count<max_requests && now>=next_due[index])) || continue
        printf '%s' "$phase" | jq -e --arg team "$team" --argjson now "$now" \
            '.teams|index($team)' >/dev/null || continue
        printf '%s' "$phase" | jq -e --argjson now "$now" \
            '.submit_after_offset <= $now and $now < .submit_until_offset' >/dev/null || continue
        expected=""
        if [[ "$mode" == access-probe ]]; then
            ((counts[index]<2)) || continue
            case_row="$(printf '%s' "$cases" | jq -c --arg team "$team" --argjson n "${counts[$index]}" '[.[]|select(.team==$team)][$n]')"
            model="$(printf '%s' "$case_row" | jq -r .model)"
            expected="$(printf '%s' "$case_row" | jq -r .expected_access)"
        elif [[ "$mode" == quota-probe ]]; then
            ((counts[index]<quota_requests)) || continue
            model="$quota_model"
        else
            model="$(jq -r --arg team "$team" --argjson n "${counts[$index]}" '
              .seed as $seed | [.teams[$team].models|to_entries[]|.key as $m|range(0;.value.weight)|$m] as $cycle |
              $cycle[($n+$seed)%($cycle|length)]' "$scenario")"
        fi
        request_count=$((request_count+1))
        identifier="$run_id-$request_count"
        directory="$state/$identifier"
        mkdir "$directory"
        jq -n --slurpfile s "$scenario" --arg team "$team" --arg model "$model" --arg run "$run_id" \
            --arg id "$identifier" --arg phase "$phase_id" --arg scope "$mode" --arg expected "$expected" \
            --argjson start "$((started_epoch+now))" --argjson stream "$stream" '
          $s[0].teams[$team] as $t |
          {schema_version:1,run_id:$run,request_id:$id,team:$team,subscription:$t.subscription,phase:$phase,scope:$scope,
           requested_model:$model,api_model:("publishers/"+$s[0].models[$model].namespace+"/models/"+$model),
           started_at:($start|todateiso8601),input_target_tokens:(if $scope=="access-probe" then 64 else $t.input_target_tokens end),
           max_output_tokens:(if $scope=="access-probe" then 16 else $t.max_output_tokens end),stream:$stream} +
           (if $expected!="" then {expected_access:$expected} else {} end)' > "$directory/meta.json"
        ids[$index]="$identifier"
        deadlines[$index]=$((now+request_timeout))
        attempt "$directory" "$team" "${counts[$index]}" &
        pids[$index]=$!
        counts[$index]=$((counts[index]+1))
        spacing="$(jq -r --arg team "$team" '.teams[$team].spacing_seconds' "$scenario")"
        multiplier="$(printf '%s' "$phase" | jq -r .spacing_multiplier)"
        [[ "$mode" != access-probe ]] || spacing=0
        next_due[$index]=$((now+spacing*multiplier))
    done
    sleep 0.1
done
run_status=completed
for index in 0 1 2; do
    [[ -n "${pids[$index]}" ]] || continue
    stop_attempt "$index" run_deadline
    collect_attempt "$index"
done
finalize
jq '{run_id,status,requests_started,outcomes,access_probe_passed,quota_probe_passed,quota_429_observed}' "$output/run.json"
jq -e '.status=="completed" and .access_probe_passed!=false and .quota_probe_passed!=false' "$output/run.json" >/dev/null
