#!/usr/bin/env bash
# Offline collector regression checks against synthetic evidence and mocked HTTP; creates only temporary files.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-collection.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT
reset_inputs() {
    cp "$SCRIPT_DIR/fixtures/run.json" "$WORK_DIR/run.json"
    cp "$SCRIPT_DIR/fixtures/receipts.jsonl" "$WORK_DIR/receipts.jsonl"
    cp "$SCRIPT_DIR/fixtures/samples.json" "$WORK_DIR/samples.json"
    cp "$SCRIPT_DIR/fixtures/metering.json" "$WORK_DIR/metering.json"
    rm -f "$WORK_DIR/result.json"
}
change() {
    jq "$2" "$WORK_DIR/$1" >"$WORK_DIR/changed.json"
    mv "$WORK_DIR/changed.json" "$WORK_DIR/$1"
}
prepare() {
    "$SCRIPT_DIR/collect-usage.sh" prepare --run "$WORK_DIR/run.json" --receipts "$WORK_DIR/receipts.jsonl" \
        --samples "$WORK_DIR/samples.json" --metering "$WORK_DIR/metering.json" \
        --intervals "$SCRIPT_DIR/fixtures/instance-intervals.json" --output "$WORK_DIR/result.json" \
        >"$WORK_DIR/stdout" 2>"$WORK_DIR/stderr"
}
expect_result() {
    if prepare && jq -e "$2" "$WORK_DIR/result.json" >/dev/null; then record "$1" pass
    else record "$1" 'Unexpected reconciliation result'; cat "$WORK_DIR/stderr" >&2; fi
}
expect_rejection() {
    if prepare; then record "$1" 'Invalid evidence accepted'; else record "$1" pass; fi
}
incomplete='all(.windows[].usage[]; .coverage=="missing_usage")'
qwen_incomplete='.windows[0].usage["qwen3-8-27b"].coverage=="missing_usage"'
reset_inputs
expect_result 'Complete busy/quiet/idle evidence with exact token deltas' '
  .evidence_kind=="synthetic_fixture" and all(.windows[].usage[]; .coverage=="complete")
  and .windows[0].usage["qwen3-8-27b"].tokens["team-engineering"]==100
  and .windows[2].usage["qwen3-8-27b"].tokens["team-support"]==0'
expect_rejection 'Existing output refused'
reset_inputs
change samples.json '.data.result=[]'
expect_result 'Missing series never prove idle' "$incomplete"
reset_inputs
change samples.json '.data.result += [.data.result[0]]'
expect_result 'Duplicate canonical resource is not summed' "$qwen_incomplete"
reset_inputs
change samples.json '.data.result[0].values += [.data.result[0].values[0]]'
expect_result 'Duplicate sample timestamp stays unresolved' '
  .windows[0].usage["qwen3-8-27b"].coverage=="missing_usage" and
  (.windows[0].usage["qwen3-8-27b"].issues|index("duplicate_timestamp:team-engineering"))!=null'
reset_inputs
change samples.json '.data.result[0].values |= map(select(.[0]!=1792065600)) | .data.result[0].values[1][1]="999"'
expect_result 'Activity across a boundary is never extrapolated' '
  .windows[0].usage["qwen3-8-27b"].coverage=="missing_usage" and
  (.windows[0].usage["qwen3-8-27b"].issues|index("boundary_activity:team-engineering"))!=null'
reset_inputs
change samples.json '.data.result += [(.data.result[0]|.metric.limitador_namespace="another-policy")]'
expect_result 'Different limiter resource is excluded explicitly' 'all(.windows[].usage[];.coverage=="complete")'
reset_inputs
change samples.json '.data.result[0].metric.__name__="authorized_calls_total"'
expect_rejection 'A request counter cannot masquerade as the canonical token counter'
reset_inputs
cp "$SCRIPT_DIR/metering.json" "$WORK_DIR/metering.json"
expect_result 'Unverified canonical identities fail closed' "$incomplete"
reset_inputs
change samples.json '.data.result[0].metric.user="different-user"'
expect_result 'Wrong user stays unresolved' "$qwen_incomplete"
reset_inputs
change metering.json '.canonical_series[0].user="different-user"'
change samples.json '.data.result[0].metric.user="different-user"'
expect_rejection 'Matching but incorrect canonical user cannot override frozen team identity'
reset_inputs
change metering.json '.canonical_series += [{subscription:"research-sub",model:"qwen3-8-27b",
  user:"research-user",limitador_namespace:"fixture-research-qwen"}]'
change samples.json '.data.result += [(.data.result[0] | .metric += {subscription:"research-sub",
  user:"research-user",limitador_namespace:"fixture-research-qwen"})]'
expect_result 'Explicit non-demo user remains in the metered denominator' '
  .subscriptions["research-sub"]=="other_consumers" and all(.windows[].usage[];.coverage=="complete") and
  .windows[0].usage["qwen3-8-27b"].tokens["research-sub"]==100'
reset_inputs
change samples.json '.data.result[0].metric.subscription=""'
expect_result 'Missing subscription stays unresolved' "$qwen_incomplete"
reset_inputs
change samples.json '.data.result[0].values[8][1]="2"'
expect_result 'Counter reset remains unresolved' "$qwen_incomplete"
reset_inputs
change samples.json '.data.result[0].values |= map(if (.[1]|tonumber)>=1100 then .[1]=((.[1]|tonumber)+100|tostring) else . end)'
expect_result 'Monotonic counter/receipt mismatch remains unresolved' '
  .windows[0].usage["qwen3-8-27b"].coverage=="missing_usage"
  and (.windows[0].usage["qwen3-8-27b"].issues|index("receipt_counter_mismatch:team-engineering"))!=null'
reset_inputs
change metering.json '.receipt_tolerance_fraction="invalid"'
expect_rejection 'Invalid receipt tolerance rejected'
reset_inputs
change samples.json '.warnings=["partial response"]'
expect_rejection 'Retained partial-query warnings rejected'
reset_inputs
change samples.json '.data.result[0].values |= .[0:4]+.[9:]'
expect_result 'Scrape gaps remain unresolved' "$qwen_incomplete"
reset_inputs
change samples.json '.data.result[0].values |= .[0:3]'
expect_result 'Disappearing series are not zero usage' "$qwen_incomplete"
reset_inputs
change samples.json '.data.result[0].values[8][1]="1.5"'
expect_rejection 'Fractional token counter rejected'
reset_inputs
change samples.json '.data.result[0].values[8][1]="9007199254740993"'
expect_rejection 'Unsafe integer counter rejected'
reset_inputs
change samples.json '.data.result[].values |= map(.[0]+=0.001)'
expect_result 'Fractional millisecond scrape timestamps remain exact' 'all(.windows[].usage[];.coverage=="complete")'
reset_inputs
change samples.json '.data.result[0].values[0][0]+=0.0001'
expect_rejection 'Sub-millisecond samples cannot be rounded across a boundary'
reset_inputs
change samples.json '.evidence_kind="observed"'
expect_rejection 'Mixed live and synthetic evidence rejected'
reset_inputs
: >"$WORK_DIR/receipts.jsonl"
expect_rejection 'Missing request receipt rejected'
reset_inputs
jq -cs '.[0].requested_model="mistral-small4-119b"|.[]' "$WORK_DIR/receipts.jsonl" >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/receipts.jsonl"
expect_rejection 'Forbidden model receipt rejected'
reset_inputs
jq -cs '.[0].started_at="2026-10-15T12:00:00.000Z"|.[0].ended_at=.[0].started_at|.[]' \
    "$WORK_DIR/receipts.jsonl" >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/receipts.jsonl"
expect_result 'Zero-duration receipt at window boundary retained' 'all(.windows[].usage[];.coverage=="complete")'
reset_inputs
jq -cs '.[0].ended_at="2026-10-15T12:04:01Z"|.[]' "$WORK_DIR/receipts.jsonl" >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/receipts.jsonl"
expect_result 'In-flight request marks both adjacent windows unresolved' '
  .windows[0].usage["qwen3-8-27b"].coverage=="missing_usage"
  and .windows[1].usage["qwen3-8-27b"].coverage=="missing_usage"'
reset_inputs
change run.json '.requests_started+=1'
jq -cs '.+[.[0]+{request_id:"overflow",input_tokens:4503599627370495,output_tokens:0,total_tokens:4503599627370495}]|.[]' \
    "$WORK_DIR/receipts.jsonl" >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/receipts.jsonl"
expect_rejection 'Accumulated receipt usage cannot exceed the exact integer bound'
reset_inputs
change run.json '.scenario_sha256="wrong"'
expect_rejection 'Frozen scenario mismatch refused'
reset_inputs
change run.json '.scenario_id="different-scenario"'
expect_rejection 'Run identity must match frozen scenario'
reset_inputs
change run.json '.phase_windows |= .[0:2]'
expect_rejection 'An omitted idle phase cannot silently reduce the hosting bill'
reset_inputs
change run.json '.phase_windows[2].end="2026-10-15T12:11:00Z"'
expect_rejection 'A shortened phase cannot silently reduce the hosting bill'
reset_inputs
change run.json '.ended_at="2026-10-15T12:11:00Z"'
expect_rejection 'A completed status cannot hide an unfinished reporting period'
reset_inputs
change samples.json '.schema_version=2'
expect_rejection 'Unknown evidence schema rejected'
reset_inputs
change run.json '.phase_windows[2].start="not-a-UTC-timestamp"'
expect_rejection 'Malformed idle window cannot disappear'
reset_inputs
change run.json '.phase_windows[2].start="2026-02-31T12:08:00Z"'
expect_rejection 'Invalid calendar date rejected'
reset_inputs
change run.json '.phase_windows[2].start="2026-10-15T12:08:00.0001Z"'
expect_rejection 'Excess timestamp precision rejected'
reset_inputs
change metering.json '.max_scrape_gap_seconds="45"'
expect_rejection 'Text scrape-gap threshold rejected'
reset_inputs
change metering.json '.max_scrape_gap_seconds=4503599627371'
expect_rejection 'Scrape threshold cannot overflow millisecond arithmetic'
reset_inputs
jq -c . "$WORK_DIR/run.json" | sed 's/^{/{"schema_version":1,/' >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/run.json"
expect_rejection 'Duplicate JSON run fields cannot be normalized away'
reset_inputs
jq -c . "$WORK_DIR/receipts.jsonl" | sed '1s/^{/{"request_id":"shadow",/' >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/receipts.jsonl"
expect_rejection 'Duplicate fields in a JSONL receipt are rejected'
reset_inputs
cat "$WORK_DIR/samples.json" "$WORK_DIR/samples.json" >"$WORK_DIR/changed.json"
mv "$WORK_DIR/changed.json" "$WORK_DIR/samples.json"
expect_rejection 'Extra sample documents cannot be silently ignored'

# Mock guard and curl; no socket or live cluster call is permitted in this test.
mkdir "$WORK_DIR/bin"
cat >"$WORK_DIR/bin/oc" <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"whoami --show-server"*) printf '%s\n' 'https://showback-test.invalid' ;;
  *whoami*) printf '%s\n' 'synthetic-test-user' ;;
  *) exit 90 ;;
esac
SH
cat >"$WORK_DIR/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
output=''
for arg in "$@"; do [[ "$arg" != *synthetic-secret* ]] || exit 91; done
while (( $# )); do
  case "$1" in
    --output) output=$2; shift 2 ;;
    --config) cat "$2" >/dev/null; shift 2 ;;
    *) shift ;;
  esac
done
[[ -n "$output" ]] || exit 92
jq --arg warning "${SHOWBACK_TEST_WARNINGS:-}" '.+{status:"success"}
  | if $warning!="" then .warnings=[$warning] else . end' "$SHOWBACK_TEST_SAMPLES" >"$output"
printf '%s' "${SHOWBACK_TEST_STATUS:-200}"
SH
chmod +x "$WORK_DIR/bin/oc" "$WORK_DIR/bin/curl"
reset_inputs
capture() {
    PATH="$WORK_DIR/bin:$PATH" RHOAI_EXPECTED_API_SERVER=showback-test.invalid \
        SHOWBACK_PROMETHEUS_TOKEN=synthetic-secret SHOWBACK_TEST_SAMPLES="$SCRIPT_DIR/fixtures/samples.json" \
        SHOWBACK_TEST_STATUS="${1:-200}" SHOWBACK_TEST_WARNINGS="${2:-}" "$SCRIPT_DIR/collect-usage.sh" capture \
        --url http://127.0.0.1:10902 --run "$WORK_DIR/run.json" --output "$WORK_DIR/captured.json" \
        >"$WORK_DIR/stdout" 2>"$WORK_DIR/stderr"
}
if capture && jq -e '.evidence_kind=="observed" and .data.resultType=="matrix"' "$WORK_DIR/captured.json" >/dev/null; then
    record 'Mocked capture validates range response and keeps token out of argv' pass
else
    record 'Mocked capture validates range response and keeps token out of argv' 'Capture failed'
    cat "$WORK_DIR/stderr" >&2
fi
rm -f "$WORK_DIR/captured.json"
if capture 302; then record 'Capture refuses redirects' 'Redirect accepted'; else record 'Capture refuses redirects' pass; fi
if capture 200 partial-response; then record 'Capture refuses partial-query warnings' 'Warnings accepted'
else record 'Capture refuses partial-query warnings' pass; fi
validation_summary
