#!/usr/bin/env bash
# Offline real-shell integration tests with PATH-injected curl/oc stand-ins. No network.
set -euo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$TEST_DIR/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/bin" "$work/calls"
export MOCK_ROOT="$work" MOCK_KIND=normal
cat > "$work/bin/oc" <<'MOCK_OC'
#!/usr/bin/env bash
printf '%s\n' called >> "$MOCK_ROOT/oc-calls"
[[ "$*" != *--show-server* ]] || printf '%s\n' https://api.showback-shell-test.invalid:6443
MOCK_OC
cat > "$work/bin/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
set -euo pipefail
for argument in "$@"; do
    [[ "$argument" != *test-private-key* ]] || { touch "$MOCK_ROOT/credential-in-argv"; exit 91; }
done
config=""; output=""; retry=""; redirect=false; max_time=""; request_id=""; data=""
while (($#)); do
    case "$1" in
        --config) config="$2"; shift 2 ;;
        --data-binary) data="${2#@}"; shift 2 ;;
        --output) output="$2"; shift 2 ;;
        --retry) retry="$2"; shift 2 ;;
        --max-time) max_time="$2"; shift 2 ;;
        --header) [[ "$2" != X-Request-ID:* ]] || request_id="${2#X-Request-ID: }"; shift 2 ;;
        --connect-timeout|--max-filesize|--max-redirs|--proto|--write-out) shift 2 ;;
        --no-location) redirect=true; shift ;;
        *) shift ;;
    esac
done
[[ "$retry" == 0 && "$redirect" == true && -n "$max_time" && "$config" == - ]]
header="$(cat)"
case "$header" in
    *test-private-key-engineering*) team=engineering ;;
    *test-private-key-marketing*) team=marketing ;;
    *test-private-key-support*) team=support ;;
    *) exit 92 ;;
esac
unset header
payload="$(cat "$data")"
model="$(printf '%s' "$payload" | jq -r .model)"
[[ "$model" == publishers/internal-models/models/* ]]
printf '%s' "$payload" | jq -e --arg team "$team" '
    .messages[0].content | contains({engineering:"fictional Java change",marketing:"short campaign",
      support:"fictional customer question"}[$team])' >/dev/null
stream="$(printf '%s' "$payload" | jq -r .stream)"
reply_model="$model"
[[ "$MOCK_KIND" != wrong-model ]] || reply_model=unexpected-model
if [[ -f "$MOCK_ROOT/active-$team" ]]; then
    previous="$(cat "$MOCK_ROOT/active-$team")"
    if kill -0 "$previous" 2>/dev/null; then touch "$MOCK_ROOT/overlap"; exit 93; fi
fi
printf '%s\n' "$$" > "$MOCK_ROOT/active-$team"
trap 'rm -f "$MOCK_ROOT/active-$team"' EXIT
jq -n --arg id "$request_id" --arg team "$team" --arg model "$model" --arg timeout "$max_time" \
    '{request_id:$id,team:$team,model:$model,timeout:$timeout}' > "$MOCK_ROOT/calls/$request_id.json"
if [[ "$MOCK_KIND" == hang ]]; then while :; do :; done; fi
code=200
if [[ "$team:$model" == engineering:*mistral* || "$team:$model" == marketing:*qwen* ]]; then code=403; fi
case "$MOCK_KIND" in
    429) code=429 ;;
    401|404|403) code="$MOCK_KIND" ;;
    redirect) code=302 ;;
esac
if [[ "$code" != 200 ]]; then
    printf '%s' 'PRIVATE_ERROR_BODY_DO_NOT_RETAIN' > "$output"
elif [[ "$MOCK_KIND" == oversized ]]; then
    head -c 5000 /dev/zero | tr '\0' x > "$output" || true
elif [[ "$stream" == true ]]; then
    {
        printf 'data: %s\n\n' "$(jq -cn --arg model "$reply_model" '{model:$model,choices:[{delta:{content:"private reply"}}]}')"
        if [[ "$MOCK_KIND" != missing-usage ]]; then
            printf 'data: %s\n\n' "$(jq -cn --arg model "$reply_model" '{model:$model,choices:[],usage:{prompt_tokens:3,completion_tokens:2,total_tokens:5}}')"
        fi
        [[ "$MOCK_KIND" == missing-done ]] || printf 'data: [DONE]\n\n'
    } > "$output"
else
    jq -cn --arg model "$reply_model" --arg kind "$MOCK_KIND" \
        '{model:$model,choices:[{message:{content:"private reply"}}],usage:{prompt_tokens:3,completion_tokens:2,total_tokens:5}} |
         if $kind=="invalid-usage" then .usage.total_tokens=-1 else . end' > "$output"
fi
printf '%s' "$code"
MOCK_CURL
chmod +x "$work/bin/oc" "$work/bin/curl"
export PATH="$work/bin:$PATH"
export RHOAI_EXPECTED_API_SERVER=showback-shell-test.invalid
export SHOWBACK_GATEWAY_URL=https://maas.showback-shell-test.invalid
export SHOWBACK_ENGINEERING_KEY=test-private-key-engineering
export SHOWBACK_MARKETING_KEY=test-private-key-marketing
export SHOWBACK_SUPPORT_KEY=test-private-key-support

# Preview must not read credentials, write output or even invoke the mocked guard.
bash "$DEMO_DIR/run-workload.sh" --output "$work/must-not-exist" > "$work/preview.json"
jq -e '.network_requests==0 and .evidence_kind=="preview" and .phases[0].submit_after_offset==45' \
    "$work/preview.json" >/dev/null
[[ ! -e "$work/must-not-exist" && ! -e "$work/oc-calls" ]]
[[ "$(find "$work/calls" -type f | wc -l | tr -d ' ')" == 0 ]]

# Mock processes also parse JSON and synthesize SSE, so allow host scheduling time.
# Deadline, phase containment and weighted model-selection assertions remain explicit.
jq '.status="synthetic_fixture" | .limits.start_delay_seconds=0 | .limits.drain_seconds=4 |
    .limits.request_timeout_seconds=4 | .limits.max_wall_seconds=24 | .limits.max_response_bytes=1024 |
    .phases[].duration_seconds=6 | .teams[].spacing_seconds=1' \
    "$DEMO_DIR/scenario.json" > "$work/scenario.json"
run_case() {
    local name="$1" expected="$2"
    shift 2
    local result=0
    bash "$DEMO_DIR/run-workload.sh" --scenario "$work/scenario.json" --execute --output "$work/$name" "$@" \
        > "$work/$name.stdout" 2> "$work/$name.stderr" || result=$?
    [[ "$result" == "$expected" ]] || {
        printf 'FAIL: %s expected exit %s, got %s\n' "$name" "$expected" "$result" >&2
        cat "$work/$name.stderr" >&2
        [[ ! -f "$work/$name/receipts.jsonl" ]] || jq -c \
            '{team,status,http_status,error_code,expected_access,actual_model,requested_model,access_check}' \
            "$work/$name/receipts.jsonl" >&2
        exit 1
    }
    [[ ! -d "$work/$name/.requests" ]]
    jq -e '.evidence_kind=="synthetic_fixture"' "$work/$name/run.json" >/dev/null
    jq -s -e --slurpfile run "$work/$name/run.json" \
        'length==$run[0].requests_started and ([.[].request_id]|unique|length)==length' "$work/$name/receipts.jsonl" >/dev/null
    if grep -rEq 'test-private-key|PRIVATE_ERROR_BODY|private reply|Fictional context|Northstar notebook|fictional Java change' \
        "$work/$name"; then
        printf '%s\n' 'FAIL: sensitive payload retained' >&2
        exit 1
    fi
    [[ ! -f "$MOCK_ROOT/overlap" && ! -f "$MOCK_ROOT/credential-in-argv" ]]
}

run_case access 0 --mode access-probe
jq -e '.access_probe_passed==true and .requests_started==6' "$work/access/run.json" >/dev/null
jq -s -e '[.[]|select(.expected_access=="allow")]|length==4' "$work/access/receipts.jsonl" >/dev/null
jq -s -e '[.[]|select(.expected_access=="deny" and .http_status==403)]|length==2' "$work/access/receipts.jsonl" >/dev/null
if bash "$DEMO_DIR/run-workload.sh" --scenario "$work/scenario.json" --execute --output "$work/access" >/dev/null 2>&1; then
    printf '%s\n' 'FAIL: reused output directory accepted' >&2
    exit 1
fi
for code in 401 404 403; do
    export MOCK_KIND="$code"
    run_case "denial-$code" 1 --mode access-probe
    jq -e '.access_probe_passed==false' "$work/denial-$code/run.json" >/dev/null
done
export MOCK_KIND=wrong-model
run_case wrong-model 1 --mode access-probe
jq -s -e 'all(.[]|select(.expected_access=="allow");.status=="success" and .access_check=="failed")' \
    "$work/wrong-model/receipts.jsonl" >/dev/null
export MOCK_KIND=429
run_case quota 0 --mode quota-probe --quota-model qwen3-8-27b
jq -e '.quota_probe_passed==true and .requests_started==1' "$work/quota/run.json" >/dev/null
export MOCK_KIND=normal
run_case quota-no-rejection 1 --mode quota-probe --quota-model qwen3-8-27b --quota-requests 2
jq -e '.quota_probe_passed==false' "$work/quota-no-rejection/run.json" >/dev/null
run_case streaming 0 --mode access-probe --stream
jq -s -e 'all(.[]|select(.expected_access=="allow");.usage_status=="known" and .total_tokens==5)' \
    "$work/streaming/receipts.jsonl" >/dev/null
export MOCK_KIND=missing-usage
run_case stream-unknown 0 --mode access-probe --stream
jq -s -e 'all(.[];.usage_status=="unknown" and .total_tokens==null)' "$work/stream-unknown/receipts.jsonl" >/dev/null
export MOCK_KIND=missing-done
run_case stream-incomplete 1 --mode access-probe --stream
export MOCK_KIND=invalid-usage
run_case invalid-usage 0 --mode access-probe
jq -s -e 'all(.[];.usage_status=="unknown" and .total_tokens==null)' "$work/invalid-usage/receipts.jsonl" >/dev/null
export MOCK_KIND=redirect
run_case redirect 1 --mode access-probe
jq -s -e 'all(.[];.error_code=="redirect_rejected")' "$work/redirect/receipts.jsonl" >/dev/null
export MOCK_KIND=oversized
run_case too-large 1 --mode access-probe
jq -s -e 'any(.[];.error_code=="response_too_large")' "$work/too-large/receipts.jsonl" >/dev/null
export MOCK_KIND=hang
run_case timeout 1 --mode access-probe
jq -s -e 'all(.[];.usage_status=="unknown") and any(.[];.status=="timeout")' "$work/timeout/receipts.jsonl" >/dev/null
export MOCK_KIND=normal
jq '.limits.max_requests=3' "$work/scenario.json" > "$work/capped.json"
bash "$DEMO_DIR/run-workload.sh" --scenario "$work/capped.json" --execute --output "$work/capped" \
    > "$work/capped.stdout" 2> "$work/capped.stderr"
jq -e '.requests_started==3 and .status=="completed"' "$work/capped/run.json" >/dev/null
jq -s -e --slurpfile run "$work/capped/run.json" \
    'all(.[];.phase!="idle" and .duration_seconds<=($run[0].limits.request_timeout_seconds+1))' \
    "$work/capped/receipts.jsonl" >/dev/null
permissions="$(ls -l "$work/capped/receipts.jsonl" | cut -c 1-10)"
[[ "$permissions" == '-rw-------' ]]
hash="$(shasum -a 256 "$work/capped.json")"
hash="${hash%% *}"
jq -e --arg hash "$hash" '.scenario_sha256==$hash' "$work/capped/run.json" >/dev/null
jq '.limits.start_delay_seconds=1 | .limits.max_wall_seconds=49 | .phases[0].duration_seconds=30 |
    .phases[1].duration_seconds=12 | .phases[2].duration_seconds=6' \
    "$work/scenario.json" > "$work/timed.json"
bash "$DEMO_DIR/run-workload.sh" --scenario "$work/timed.json" --execute --output "$work/timed" \
    > "$work/timed.stdout" 2> "$work/timed.stderr"
jq -s -e --slurpfile run "$work/timed/run.json" '
  any(.[];.phase=="busy") and any(.[];.phase=="quiet") and
  all(.[]; . as $receipt | [$run[0].phase_windows[]|select(.id==$receipt.phase)][0] as $window |
    ($receipt.started_at|fromdateiso8601)>=($window.submit_after|fromdateiso8601) and
    ($receipt.started_at|fromdateiso8601)<($window.submit_until|fromdateiso8601) and
    ($receipt.ended_at|fromdateiso8601)<=($window.end|fromdateiso8601) and
    $receipt.phase!="idle" and ($receipt.phase!="quiet" or $receipt.team!="support"))
' "$work/timed/receipts.jsonl" >/dev/null
jq -s -e '[.[]|select(.team=="support")][0:5] as $requests |
    ($requests|length)==5 and
    ([$requests[]|select(.requested_model=="qwen3-8-27b")]|length)==1 and
    ([$requests[]|select(.requested_model=="mistral-small4-119b")]|length)==4' \
    "$work/timed/receipts.jsonl" >/dev/null
jq '.limits.max_requests=201' "$work/scenario.json" > "$work/unbounded.json"
if bash "$DEMO_DIR/run-workload.sh" --scenario "$work/unbounded.json" >/dev/null 2>&1; then
    printf '%s\n' 'FAIL: unbounded scenario accepted' >&2
    exit 1
fi
for mutation in '.models["qwen3-8-27b"].namespace={}' '.teams.support.subscription=null'; do
    jq "$mutation" "$work/scenario.json" > "$work/invalid-identity.json"
    if bash "$DEMO_DIR/run-workload.sh" --scenario "$work/invalid-identity.json" >/dev/null 2>&1; then
        printf '%s\n' 'FAIL: invalid namespace or subscription accepted' >&2
        exit 1
    fi
done

# Existing-model qualification must never need Marketing credentials or schedule Mistral traffic.
unset SHOWBACK_MARKETING_KEY
bash "$DEMO_DIR/run-workload.sh" --scenario "$DEMO_DIR/qualification-qwen-only.json" --mode access-probe \
    >"$work/qwen-preview.json"
jq -e '.max_requests==2 and (.access_cases|length)==2
  and all(.access_cases[]; .model=="qwen3-8-27b" and .expected_access=="allow"
    and (.team=="engineering" or .team=="support"))
  and .limits.max_requests==24 and .limits.max_wall_seconds==360' "$work/qwen-preview.json" >/dev/null
jq -e '(.teams|keys)==["engineering","support"] and (.models|keys)==["qwen3-8-27b"]
  and [.phases[].duration_seconds]==[120,120,120]
  and .phases[0].teams==["engineering","support"] and .phases[1].teams==["engineering"]
  and .phases[2].teams==[] and all(.teams[]; .input_target_tokens==128 and .max_output_tokens==32)' \
    "$DEMO_DIR/qualification-qwen-only.json" >/dev/null
cp "$work/scenario.json" "$work/original-scenario.json"
jq '.status="synthetic_fixture" | .limits.start_delay_seconds=0 | .limits.drain_seconds=4 |
    .limits.request_timeout_seconds=4 | .limits.max_wall_seconds=24 | .limits.max_response_bytes=1024 |
    .phases[].duration_seconds=6 | .teams[].spacing_seconds=1' \
    "$DEMO_DIR/qualification-qwen-only.json" >"$work/scenario.json"
run_case qwen-access 0 --mode access-probe
jq -e '.access_probe_passed==true and .requests_started==2' "$work/qwen-access/run.json" >/dev/null
jq -s -e 'length==2 and all(.[]; .requested_model=="qwen3-8-27b" and .access_check=="passed")
  and ([.[].team]|sort)==["engineering","support"]' "$work/qwen-access/receipts.jsonl" >/dev/null
export MOCK_KIND=wrong-model
run_case qwen-wrong-model 1 --mode access-probe
export MOCK_KIND=normal
jq '.limits.max_requests=3' "$work/scenario.json" >"$work/qwen-capped.json"
bash "$DEMO_DIR/run-workload.sh" --scenario "$work/qwen-capped.json" --execute --output "$work/qwen-capped" \
    >"$work/qwen-capped.stdout" 2>"$work/qwen-capped.stderr"
jq -e '.requests_started==3 and .status=="completed"' "$work/qwen-capped/run.json" >/dev/null
jq -s -e 'length==3 and all(.[]; .requested_model=="qwen3-8-27b"
  and (.team=="engineering" or .team=="support") and .phase!="idle")' "$work/qwen-capped/receipts.jsonl" >/dev/null
for mutation in \
    '.teams.marketing=.teams.engineering' \
    '.teams.support.models["mistral-small4-119b"]={weight:1}' \
    '.models["qwen3-8-27b"].namespace=null' \
    '.phases[0].teams+=["marketing"]' \
    '.teams.support.subscription=null'; do
    jq "$mutation" "$work/scenario.json" >"$work/invalid-qwen.json"
    if bash "$DEMO_DIR/run-workload.sh" --scenario "$work/invalid-qwen.json" >/dev/null 2>&1; then
        printf 'FAIL: invalid Qwen-only scenario accepted: %s\n' "$mutation" >&2
        exit 1
    fi
done
printf '%s\n' 'Workload shell tests passed: preview, guarded mock HTTP, access, quota, streaming, bounds, privacy, deadlines and receipts.'
