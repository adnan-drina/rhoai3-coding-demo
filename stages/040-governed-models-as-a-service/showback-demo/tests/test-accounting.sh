#!/usr/bin/env bash
# Offline tests for exact allocation, carry, lifecycle and immutable evidence.
# Usage: tests/test-accounting.sh
set -euo pipefail
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$TEST_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BASE/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077
TEST_TMP=$(mktemp -d "${TMPDIR:-/tmp}/showback-accounting-tests.XXXXXX")
trap 'rm -rf "$TEST_TMP"' EXIT
passed=0
serial=0
base_input="$TEST_TMP/base.json"

pass() {
    passed=$((passed+1))
    echo "PASS: $1"
}
die() { echo "FAIL: $*" >&2; exit 1; }
make_evidence() {
    local minutes=$1 window=$2 models=$3 rate=$4 destination=$5
    jq --argjson minutes "$minutes" --argjson step "$window" --argjson models "$models" --arg rate "$rate" '
      .models=.models[0:$models] | .rates={test:{usd_per_hour:$rate,source:"synthetic rate",currency:"USD"}} |
      ("2026-10-16T09:00:00Z"|fromdateiso8601) as $start | ($start+$minutes*60) as $end |
      .instance_intervals=[.models[]|{instance_id:("fixture-"+.),model:.,start:($start|todateiso8601),
        end:($end|todateiso8601),rate_id:"test",source:"synthetic lifecycle"}] |
      .models as $ids | .windows=[range(0;$minutes;$step) as $minute |
        {id:($minute|tostring),phase:"busy",start:($start+$minute*60|todateiso8601),
         end:([$end,$start+($minute+$step)*60]|min|todateiso8601),
         usage:(reduce $ids[] as $model ({};.[$model]={coverage:"complete",tokens:{"team-engineering":1,"team-support":1}}))}]
    ' "$BASE/fixtures/accounting.json" > "$destination"
}
conserved() {
    jq -e '
      .known_total_cents==([.totals_by_consumer[]]|add) and
      .known_total_cents==([.windows[].known_total_cents]|add) and
      all(.windows[]; .known_total_cents==([.models[].known_cost_cents]|add) and
        all(.models[];.known_cost_cents==([.allocations[]]|add//0) and
          all(.allocations[];type=="number" and floor==. and .>=0)))
    ' "$1" >/dev/null || die 'cent conservation/nonnegativity'
}
run_case() {
    local label=$1 edit=$2 assertion=$3
    serial=$((serial+1))
    jq "$edit" "$base_input" > "$TEST_TMP/input-$serial.json"
    REPORT="$TEST_TMP/report-$serial.json"
    bash "$BASE/allocate.sh" --input "$TEST_TMP/input-$serial.json" --output "$REPORT" > "$TEST_TMP/stdout" 2> "$TEST_TMP/stderr" || {
        cat "$TEST_TMP/stderr" >&2
        die "$label"
    }
    jq -e "$assertion" "$REPORT" >/dev/null || die "$label (result)"
    conserved "$REPORT"
    pass "$label"
}
reject_case() {
    local label=$1 edit=$2
    serial=$((serial+1))
    jq "$edit" "$base_input" > "$TEST_TMP/input-$serial.json"
    if bash "$BASE/allocate.sh" --input "$TEST_TMP/input-$serial.json" --output "$TEST_TMP/rejected-$serial.json" \
        > "$TEST_TMP/stdout" 2> "$TEST_TMP/stderr"; then
        die "$label was accepted"
    fi
    [[ ! -e "$TEST_TMP/rejected-$serial.json" ]] || die "$label emitted a report"
    pass "$label rejected"
}

make_evidence 60 60 2 3.36312 "$base_input"
run_case 'two workers one hour: round combined bill once' '.' '
  .total_cents==673 and .raw_total_usd=="6.72624" and ([.windows[0].models[].cost_cents]|sort)==[336,337]'
run_case 'metadata, identity mapping and source provenance retained' '
  .scenario_sha256="fixture-scenario" | .source_hashes={usage:"fixture-hash"} |
  .input_sha256={samples:"sample-hash"} | .excluded_costs=["storage"] |
  .price_basis="public-list-estimate" | .source={kind:"synthetic_fixture"} |
  .metering={selected_series:[{limitador_namespace:"fixture"}]} | .limitations=["synthetic"]' '
  .scenario_sha256=="fixture-scenario" and .source_hashes.usage=="fixture-hash" and
  .input_sha256.samples=="sample-hash" and .excluded_costs==["storage"] and
  .price_basis=="public-list-estimate" and .metering.selected_series[0].limitador_namespace=="fixture" and
  .source.kind=="synthetic_fixture" and .limitations==["synthetic"] and .subscription_teams["team-support"]=="support"'
run_case 'missing price is unknown, never zero' '.instance_intervals[1].rate_id="missing"' '
  .pricing_complete==false and .allocation_complete==false and .total_cents==null and
  .raw_total_usd==null and .known_total_cents==336 and
  ([.windows[].models[]|select(.pricing_complete==false)|.cost_cents]==[null])'

make_evidence 12 4 2 3.36312 "$base_input"
run_case 'two workers twelve minutes: 135 cents and three 45-cent windows' '.' '
  .total_cents==135 and .raw_total_usd=="1.345248" and [.windows[].total_cents]==[45,45,45]'
first="$REPORT"
run_case 'unordered input replays in chronological deterministic order' '
  .models|=reverse | .windows|=reverse | .instance_intervals|=reverse' '.total_cents==135'
jq -S '{windows,totals_by_consumer}' "$first" > "$TEST_TMP/order-one"
jq -S '{windows,totals_by_consumer}' "$REPORT" > "$TEST_TMP/order-two"
cmp "$TEST_TMP/order-one" "$TEST_TMP/order-two" || die 'input order changed allocations'
run_case 'corrected rate replay clears missing-price state' '
  .instance_intervals[0].rate_id="revised" | .rates.revised=.rates.test | .report_id="correction-v2" |
  .supersedes_report_id="unpriced-v1"' '
  .total_cents==135 and .pricing_complete and .allocation_complete and
  .totals_by_consumer.unresolved_allocation==0 and all(.windows[].models[];.missing_price_intervals==[])'

cp "$BASE/fixtures/accounting.json" "$base_input"
run_case 'busy quiet idle with separate preparation and background consumer' '.' '
  .total_cents==135 and .totals_by_consumer.platform_idle==45 and .totals_by_consumer.other_consumers>0 and
  (.out_of_scope_intervals|length)==4 and all(.out_of_scope_intervals[];.included_in_total==false) and
  all(.windows[1].models[];(.allocations|length)==1)'

make_evidence 120 1 2 0.30 "$base_input"
run_case 'hierarchical carry balances 120 tied model/consumer windows' '.' '
  .total_cents==120 and
  ([.windows[].models[]]|group_by(.model)|all(.[];
    ([.[].cost_cents]|add)==60 and ([.[].allocations.engineering]|add)==30 and
    ([.[].allocations.support]|add)==30))'
run_case 'zero-priced model never receives a rounding cent' '
  .rates.free={usd_per_hour:"0",source:"explicit synthetic zero"} | .instance_intervals[1].rate_id="free"' '
  .total_cents==60 and all(.windows[].models[]|select(.model=="mistral-small4-119b");.cost_cents==0)'

make_evidence 60 60 1 1 "$base_input"
run_case 'known non-demo consumer remains in denominator' '
  .subscriptions["other-sub"]="research" |
  .windows[0].usage[.models[0]].tokens={"team-engineering":1,"other-sub":3}' '
  .totals_by_consumer.engineering==25 and .totals_by_consumer.other_consumers==75 and
  .subscription_teams["other-sub"]=="other_consumers"'
run_case '70/30 quota is independent of actual 40/60 cost split' '
  .quotas={engineering:700000,support:300000} |
  .windows[0].usage[.models[0]].tokens={"team-engineering":200000,"team-support":300000}' '
  .totals_by_consumer.engineering==40 and .totals_by_consumer.support==60'
first="$REPORT"
run_case 'changing quota leaves allocation unchanged' '
  .quotas={engineering:900000,support:100000} |
  .windows[0].usage[.models[0]].tokens={"team-engineering":200000,"team-support":300000}' '
  .totals_by_consumer.engineering==40 and .totals_by_consumer.support==60'
jq -S .windows "$first" > "$TEST_TMP/quota-one"
jq -S .windows "$REPORT" > "$TEST_TMP/quota-two"
cmp "$TEST_TMP/quota-one" "$TEST_TMP/quota-two" || die 'quota changed window allocation'
run_case 'rate transition and replacement are split exactly' '
  .rates.new={usd_per_hour:"2",source:"synthetic changed rate"} |
  .instance_intervals[0] as $old | .instance_intervals[0].end="2026-10-16T09:30:00Z" |
  .instance_intervals += [$old+{instance_id:"replacement",start:"2026-10-16T09:30:00Z",rate_id:"new"}]' '
  .total_cents==150 and .windows[0].models[0].instance_hours=="1"'
run_case 'partially unpriced pool holds known fragment unresolved' '
  .instance_intervals[0] as $old | .instance_intervals[0].end="2026-10-16T09:30:00Z" |
  .instance_intervals += [$old+{start:"2026-10-16T09:30:00Z",rate_id:"unknown"}]' '
  .total_cents==null and .known_total_cents==50 and .totals_by_consumer.unresolved_allocation==50'
run_case 'covered empty usage is idle' '.windows[0].usage[.models[0]].tokens={}' '
  .totals_by_consumer.platform_idle==100 and .allocation_complete and
  .windows[0].models[0].usage_state=="no_activity_with_valid_coverage"'
run_case 'measured zero is distinct from empty covered usage' '.windows[0].usage[.models[0]].tokens={"team-engineering":0}' '
  .totals_by_consumer.platform_idle==100 and .windows[0].models[0].usage_state=="measured_zero"'
for coverage in missing_usage partial_period; do
    run_case "$coverage holds whole pool unresolved" \
        ".windows[0].usage[.models[0]]={coverage:\"$coverage\",tokens:{\"team-engineering\":900,unidentified:50},
          issues:[\"counter reset\"]}" '
      .pricing_complete and .allocation_complete==false and .totals_by_consumer.unresolved_allocation==100 and
      .totals_by_consumer.engineering==0 and .windows[0].models[0].total_tokens==null and
      .windows[0].models[0].observed_tokens==950 and .windows[0].models[0].coverage_issues==["counter reset"]'
done
run_case 'receipt summary maps retained' '
  .windows[0].usage[.models[0]] += {receipt_input_tokens:{"team-engineering":3},
    receipt_output_tokens:{"team-engineering":4},request_counts:{"team-engineering":1},
    error_counts:{"team-engineering":0},quota_rejections:{"team-engineering":0}}' '
  .windows[0].models[0] | .receipt_input_tokens["team-engineering"]==3 and
  .receipt_output_tokens["team-engineering"]==4 and .request_counts["team-engineering"]==1 and
  .error_counts["team-engineering"]==0 and .quota_rejections["team-engineering"]==0'
run_case 'fractional millisecond timestamp interval costs remain exact' '
  .instance_intervals[0].start="2026-10-16T09:00:00.123Z" |
  .instance_intervals[0].end="2026-10-16T09:00:36.123+00:00" |
  .windows[0].start=.instance_intervals[0].start | .windows[0].end=.instance_intervals[0].end' '
  .total_cents==1 and .raw_total_usd=="0.01" and .start=="2026-10-16T09:00:00.123Z"'

make_evidence 4 1 1 0.60 "$base_input"
run_case 'inactive consumers cannot cash prior residuals' '
  .models[0] as $m | .windows[1].usage[$m].tokens={"team-engineering":1,"team-support":0} |
  .windows[2].usage[$m].tokens={}' '
  .windows[1].models[0].allocations=={engineering:1} and
  .windows[2].models[0].allocations=={platform_idle:1} and
  .windows[3].models[0].allocations=={engineering:0,support:1}'

make_evidence 4 1 2 0.30 "$base_input"
run_case 'free interval cannot cash prior model residual' '
  .rates.free={usd_per_hour:"0",source:"explicit synthetic zero"} |
  .instance_intervals[0] as $old | .instance_intervals[0].end="2026-10-16T09:01:00Z" |
  .instance_intervals += [$old+{start:"2026-10-16T09:01:00Z",end:"2026-10-16T09:03:00Z",rate_id:"free"},
    $old+{start:"2026-10-16T09:03:00Z"}]' '
  .total_cents==3 and all(.windows[1:3][].models[]|select(.model=="qwen3-8-27b");.cost_cents==0)'

make_evidence 6 1 1 0.60 "$base_input"
run_case 'repeat replay is byte deterministic' '.' '.total_cents==6'
first="$REPORT"
run_case 'same evidence second replay' '.' '.total_cents==6'
cmp "$first" "$REPORT" || die 'replay bytes differ'
run_case 'correction replay changes later residual allocations' '
  .report_id="correction-v2" | .supersedes_report_id="prior" |
  .windows[0].usage[.models[0]].tokens={"team-support":1}' '.total_cents==6 and .supersedes_report_id=="prior"'
if [[ "$(jq -c '.windows[1].models[0].allocations' "$first")" == \
      "$(jq -c '.windows[1].models[0].allocations' "$REPORT")" ]]; then
    die 'correction did not replay carry'
fi

# A real calendar-quarter duration, not an extrapolated twelve-minute run. Usage
# remains synthetic. Hourly replay retains model/consumer carry over all 2208 hours.
make_evidence 132480 60 2 3.36312 "$base_input"
run_case '92-day quarter with 2208 hourly windows and two workers' '.' '
  (.windows|length)==2208 and .total_cents==1485154 and .raw_total_usd=="14851.53792"'
run_case 'quarter replay with varying coprime usage totals has bounded carry precision' '
  .windows |= (to_entries|map(.key as $i | .value |
    .usage |= with_entries(.key as $model | .value.tokens={
      "team-support":(($i*13007%99991)+1),"background-evaluation":(($i*31%997)+1)} |
      .value.tokens[(if $model=="qwen3-8-27b" then "team-engineering" else "team-marketing" end)]=(($i*7919%100003)+1))))' '
  (.windows|length)==2208 and .total_cents==1485154 and .raw_total_usd=="14851.53792" and
  all(.windows[-1].models[];.consumer_share_rounding_error_bound_cents.support=="0.000001104")'

make_evidence 12 4 2 3.36312 "$base_input"
reject_case 'negative rate' '.rates.test.usd_per_hour="-1"'
reject_case 'NaN rate' '.rates.test.usd_per_hour="NaN"'
reject_case 'infinite rate' '.rates.test.usd_per_hour="Infinity"'
reject_case 'numeric rate' '.rates.test.usd_per_hour=1.5'
reject_case 'explicit null rate currency' '.rates.test.currency=null'
reject_case 'explicit false rate currency' '.rates.test.currency=false'
reject_case 'negative tokens' '.windows[0].usage[.models[0]].tokens["team-engineering"]=-1'
reject_case 'boolean tokens' '.windows[0].usage[.models[0]].tokens["team-engineering"]=true'
reject_case 'unsafe token precision' '.windows[0].usage[.models[0]].tokens["team-engineering"]=4503599627370496'
reject_case 'unknown complete identity' '.windows[0].usage[.models[0]].tokens.unknown=1'
reject_case 'empty lifecycle' '.instance_intervals=[]'
reject_case 'lifecycle gap' '.instance_intervals[0].start="2026-10-16T09:00:01Z"'
reject_case 'instance assignment overlap' '.instance_intervals += [.instance_intervals[0]]'
reject_case 'duplicate windows' '.windows += [.windows[0]]'
reject_case 'overlapping windows' '.windows[1].start="2026-10-16T09:03:59Z"'
reject_case 'window gap' '.windows[1].start="2026-10-16T09:04:01Z"'
reject_case 'timezone absent' '.windows[0].start="2026-10-16T09:00:00"'
reject_case 'non-UTC offset' '.windows[0].start="2026-10-16T10:00:00+01:00"'
reject_case 'unsupported timestamp precision' '.windows[0].start="2026-10-16T09:00:00.1234Z"'
reject_case 'invalid calendar date' '.windows[0].start="2026-02-30T09:00:00Z"'
reject_case 'missing model usage' 'del(.windows[0].usage[.models[0]])'
reject_case 'reserved accounting identity' '.subscriptions.evil="platform_idle"'
reject_case 'unsupported policy' '.policy_version="some-other-policy"'
reject_case 'input output mismatch' '.windows[0].usage[.models[0]] += {
  input_tokens:{"team-engineering":1},output_tokens:{"team-engineering":1}}'
reject_case 'receipt negative integer' '.windows[0].usage[.models[0]].request_counts={"team-engineering":-1}'
reject_case 'receipt fractional integer' '.windows[0].usage[.models[0]].receipt_input_tokens={"team-engineering":1.5}'
reject_case 'receipt boolean integer' '.windows[0].usage[.models[0]].quota_rejections={"team-engineering":true}'
reject_case 'receipt unknown identity' '.windows[0].usage[.models[0]].error_counts={unknown:1}'
reject_case 'rate outside exact bound' '.rates.test.usd_per_hour="4503599627370496"'
reject_case 'multiplication outside exact bound' '.rates.test.usd_per_hour="4503599627370495"'

# Duplicate object detection includes nonidentical child keys and nested arrays.
for invalid in '{"schema_version":1,"schema_version":1}' '{"a":{"x":1},"a":{"y":2}}' \
    '{"a":[1,2],"a":[3]}' '{"x":NaN}' '{} {}'; do
    serial=$((serial+1))
    printf '%s\n' "$invalid" > "$TEST_TMP/invalid.json"
    if bash "$BASE/allocate.sh" --input "$TEST_TMP/invalid.json" --output "$TEST_TMP/bad-$serial.json" \
        > "$TEST_TMP/stdout" 2> "$TEST_TMP/stderr"; then die 'invalid JSON accepted'; fi
    if ! grep -q 'invalid or duplicate-key JSON' "$TEST_TMP/stderr"; then
        cat "$TEST_TMP/stderr" >&2
        die 'JSON rejected too late'
    fi
done
pass 'duplicate keys, closed duplicate containers, NaN and multiple JSON documents rejected'

bash "$BASE/allocate.sh" --input "$BASE/fixtures/accounting.json" --output "$TEST_TMP/private.json" \
    --csv "$TEST_TMP/private.csv" >/dev/null
[[ "$(stat -f %Lp "$TEST_TMP/private.json" 2>/dev/null || stat -c %a "$TEST_TMP/private.json")" == 600 ]] || die 'JSON mode is not 0600'
[[ "$(stat -f %Lp "$TEST_TMP/private.csv" 2>/dev/null || stat -c %a "$TEST_TMP/private.csv")" == 600 ]] || die 'CSV mode is not 0600'
[[ "$(head -n 1 "$TEST_TMP/private.csv")" == *'"allocated_cents"'* ]] || die 'CSV columns missing'
before=$(shasum -a 256 "$TEST_TMP/private.json")
if bash "$BASE/allocate.sh" --input "$base_input" --output "$TEST_TMP/private.json" \
    > "$TEST_TMP/stdout" 2> "$TEST_TMP/stderr"; then die 'existing report replaced'; fi
[[ "$before" == "$(shasum -a 256 "$TEST_TMP/private.json")" ]] || die 'existing bytes changed'
ln -s "$TEST_TMP/private.json" "$TEST_TMP/report-link"
if bash "$BASE/allocate.sh" --input "$base_input" --output "$TEST_TMP/report-link" \
    > "$TEST_TMP/stdout" 2> "$TEST_TMP/stderr"; then die 'symlink replaced'; fi
if bash "$BASE/allocate.sh" --input "$base_input" --output "$TEST_TMP/same.json" --csv "$TEST_TMP/./same.json" \
    > "$TEST_TMP/stdout" 2> "$TEST_TMP/stderr"; then die 'same output paths accepted'; fi
pass 'private immutable JSON/CSV; existing paths, symlinks and path aliases refused'
echo "Accounting tests: $passed passed (offline Bash + jq)"
