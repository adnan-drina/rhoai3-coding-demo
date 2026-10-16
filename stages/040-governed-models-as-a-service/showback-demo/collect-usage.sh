#!/usr/bin/env bash
# Capture raw monitoring samples explicitly, or reconcile retained evidence offline. Never deploys or generates load.
# Writes a new private JSON file; refuses overwrite. Prepare is offline; capture uses the repository cluster guard.
# Usage: stages/040-governed-models-as-a-service/showback-demo/collect-usage.sh capture|prepare --run FILE --output FILE [options]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
MODE=${1:-}
[[ "$MODE" == prepare || "$MODE" == capture ]] || usage
shift
RUN='' OUTPUT='' RECEIPTS='' SAMPLES='' INTERVALS='' URL='' MARGIN=60 INSECURE=false
SCENARIO="$SCRIPT_DIR/scenario.json"
METERING="$SCRIPT_DIR/metering.json"
COSTS="$SCRIPT_DIR/costs.json"
while (( $# )); do
    case "$1" in
        --run|--output|--receipts|--samples|--intervals|--url|--margin|--scenario|--metering|--costs)
            (( $# >= 2 )) || usage
            case "$1" in
                --run) RUN=$2 ;; --output) OUTPUT=$2 ;; --receipts) RECEIPTS=$2 ;; --samples) SAMPLES=$2 ;;
                --intervals) INTERVALS=$2 ;; --url) URL=$2 ;; --margin) MARGIN=$2 ;; --scenario) SCENARIO=$2 ;;
                --metering) METERING=$2 ;; --costs) COSTS=$2 ;;
            esac
            shift 2 ;;
        --insecure) INSECURE=true; shift ;;
        *) usage ;;
    esac
done
[[ -f "$RUN" && -n "$OUTPUT" ]] || usage
[[ ! -e "$OUTPUT" && ! -L "$OUTPUT" ]] || fail 'Output exists; preserve the original evidence'
command -v jq >/dev/null || fail 'jq required'
umask 077
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# Inspect stream paths before jq normalizes objects. Otherwise duplicate fields
# or an extra JSON document can disappear before the allocator sees the evidence.
JSON_CHECK=$(cat <<'JQ'
reduce inputs as $event ({closed:{},documents:0};
  if ($event|length)==2 then
    if .documents==0 or .closed["[]"] then
      if .documents>0 and ($multiple|not) then error("multiple JSON documents") else . end |
      .closed={} | .documents+=1
    else . end |
    $event[0] as $path |
    reduce range(0;($path|length)+1) as $n (. ;
      if .closed[($path[0:$n]|tojson)] then error("duplicate JSON object key") else . end) |
    if ($event[1]|type)=="number" and (($event[1]|isnan) or ($event[1]|isinfinite))
    then error("non-finite JSON number") else . end |
    .closed[($path|tojson)]=true
  else .closed[($event[0][0:-1]|tojson)]=true end)
| if .documents==0 and ($multiple|not) then error("empty JSON evidence") else true end
JQ
)
check_evidence_json() {
    jq -en --stream --argjson multiple "$2" "$JSON_CHECK" "$1" >/dev/null || fail 'Invalid JSON evidence'
}
check_evidence_json "$RUN" false

# UTC timestamps at millisecond precision; input counters stay below jq's exact-integer ceiling.
COMMON=$(cat <<'JQ'
def ensure($condition; $message): if $condition then . else error($message) end;
def integer: type == "number" and isfinite and . >= 0 and . <= 4503599627370495 and floor == .;
def sum_count($left;$right):
  ensure(($left|integer) and ($right|integer) and $left<=4503599627370495-$right;
         "Receipt token sum exceeds exact integer bound") | $left+$right;
def ts:
  ensure(type == "string"; "UTC timestamp must be a string")
  | ensure(test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,3})?Z$");
           "UTC timestamp with at most millisecond precision required")
  | capture("^(?<whole>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\\.(?<fraction>[0-9]{1,3}))?Z$")
  | . as $parts | ($parts.whole + "Z" | fromdateiso8601) as $seconds
  | ensure(($seconds|strftime("%Y-%m-%dT%H:%M:%SZ")) == $parts.whole+"Z"; "Invalid UTC calendar date")
  | ($seconds * 1000 + ((($parts.fraction // "") + "000")[0:3] | tonumber));
def key($subscription; $model): [$subscription, $model] | tojson;
JQ
)

if [[ "$MODE" == capture ]]; then
    [[ -n "$URL" && "$MARGIN" =~ ^[0-9]+$ ]] || usage
    (( MARGIN >= 1 && MARGIN <= 3600 )) || fail 'Capture margin must be 1–3600 seconds'
    jq -en --arg url "$URL" '
      ($url | test("^https://[^/?#@]+(/[^?#]*)?$")) or
      ($url | test("^http://(localhost|127\\.0\\.0\\.1|\\[::1\\])(:[0-9]+)?(/[^?#]*)?$"))' >/dev/null ||
        fail 'Use HTTPS or a localhost monitoring tunnel, without credentials/query/fragment'
    load_env >&2
    check_oc_logged_in >&2
    range=$(jq -er --argjson margin "$MARGIN" "$COMMON"'
      [.phase_windows[] | {start:((.start|ts)/1000),end:((.end|ts)/1000)}] as $w
      | ensure(($w|length)>0; "No windows")
      | (($w|map(.start)|min)-$margin) as $start
      | (($w|map(.end)|max)+$margin) as $end
      | ensure($end <= now; "Wait for trailing scrapes before capture")
      | "authorized_hits_total[\(($end-$start)|ceil)s] @ \($end)"' "$RUN") || fail 'Invalid capture period'
    token=${SHOWBACK_PROMETHEUS_TOKEN:-}
    [[ "$token" != *$'\n'* && "$token" != *$'\r'* ]] || fail 'Invalid monitoring credential'
    token=${token//\\/\\\\}
    token=${token//\"/\\\"}
    tls=(--retry 0)
    [[ "$INSECURE" == false ]] || tls+=(--insecure)
    status=$(curl --silent --show-error --fail --max-time 30 --max-filesize 20971520 \
        "${tls[@]}" --config <(if [[ -n "$token" ]]; then printf 'header = "Authorization: Bearer %s"\n' "$token"; fi) \
        --get --data-urlencode "query=$range" --data-urlencode dedup=true \
        --output "$WORK_DIR/response.json" --write-out '%{http_code}' \
        "${URL%/}/api/v1/query" 2>"$WORK_DIR/http-error") || fail 'Monitoring request failed'
    [[ "$status" == 200 ]] || fail 'Monitoring response was not HTTP 200; redirects are refused'
    check_evidence_json "$WORK_DIR/response.json" false
    jq -e --arg query "$range" '
      if .status == "success" and .data.resultType == "matrix" and (.data.result|type) == "array"
         and ((.warnings // [])|length)==0
      then {schema_version:1,evidence_kind:"observed",source:{kind:"native RHOAI raw range query",
            query:$query,captured_at:(now|floor|todateiso8601),infos:(.infos // [])},data:.data}
      else error("Complete raw range-vector matrix without query warnings required") end' \
      "$WORK_DIR/response.json" >"$WORK_DIR/result.json"
else
    [[ -f "$RECEIPTS" ]] || fail 'Required receipt file missing'
    check_evidence_json "$RECEIPTS" true
    for input in "$SAMPLES" "$INTERVALS" "$SCENARIO" "$METERING" "$COSTS"; do
        [[ -f "$input" ]] || fail 'Required input file missing'
        check_evidence_json "$input" false
    done
    scenario_sha=$(shasum -a 256 "$SCENARIO" | cut -d ' ' -f 1)
    jq -e --arg sha "$scenario_sha" '.scenario_sha256 == $sha' "$RUN" >/dev/null ||
        fail 'Frozen scenario hash differs from the run'
    PROGRAM=$(cat <<'JQ'
def delta($values; $start; $end; $gap; $tolerance):
  [$values[] | ensure(type=="array" and length==2; "Counter sample must be a timestamp/value pair") |
    ensure((.[0]|type)=="number" and (.[0]|isfinite) and .[0]>=0 and .[0]<=4503599627370;
           "Invalid sample timestamp") | {t:(.[0]*1000),v:(.[1]|tonumber)}] | sort_by(.t) as $points
  | ensure(all($points[]; (.t|integer) and (.v|integer)); "Invalid or unsafe token-counter sample")
  | if ($points|map(.t)|unique|length) != ($points|length) then {issue:"duplicate_timestamp"}
    else [[$start,$end][] as $boundary
      | ($points|map(select(.t <= $boundary))|last) as $lo
      | ($points|map(select(.t >= $boundary))|first) as $hi
      | if $lo == null or $hi == null then {issue:"missing_boundary_sample"}
        elif $boundary-$lo.t > $tolerance or $hi.t-$boundary > $tolerance then {issue:"stale_boundary_sample"}
        elif $lo.v != $hi.v then {issue:"boundary_activity"}
        else {lo:$lo,hi:$hi} end] as $brackets
      | if any($brackets[]; has("issue")) then ($brackets|map(select(has("issue")))|first)
        else ($points|map(select(.t >= $brackets[0].lo.t and .t <= $brackets[1].hi.t))) as $p
          | if any(range(1; $p|length); $p[.].t-$p[.-1].t > $gap) then {issue:"scrape_gap"}
            elif any(range(1; $p|length); $p[.].v < $p[.-1].v) then {issue:"counter_reset_requires_epoch_reconciliation"}
            else {delta:($brackets[1].hi.v-$brackets[0].lo.v)} end
        end
    end;
$run[0] as $run | $scenario[0] as $scenario | $metering[0] as $metering
| $samples[0] as $samples | $costs[0] as $costs | $intervals[0] as $intervals
| ensure(all([$run,$scenario,$metering,$samples,$costs,$intervals][];.schema_version==1); "Unsupported evidence schema")
| ($metering.receipt_tolerance_fraction|tonumber) as $receipt_tolerance
| ensure(($receipt_tolerance|isfinite) and $receipt_tolerance>=0 and $receipt_tolerance<=1; "Invalid receipt tolerance")
| ensure(($metering.max_scrape_gap_seconds|integer) and $metering.max_scrape_gap_seconds>0
          and $metering.max_scrape_gap_seconds<=4503599627370
          and ($metering.boundary_tolerance_seconds|integer)
          and $metering.boundary_tolerance_seconds<=4503599627370; "Invalid scrape/boundary tolerance")
| ensure($run.mode == "workload" and $run.status == "completed"; "Completed workload required; probes remain separate")
| ensure($run.scenario_id==$scenario.scenario_id and $run.policy_version==$scenario.policy_version;
         "Run scenario/policy differs from frozen configuration")
| ensure(($run.phase_windows|type)=="array" and ($run.phase_windows|length)>0
          and ($run.phase_windows|map(.id))==($scenario.phases|map(.id)); "Run must include every frozen scenario phase")
| ensure(all(range(0;$run.phase_windows|length); . as $i |
    ($run.phase_windows[$i].end|ts)-($run.phase_windows[$i].start|ts)==$scenario.phases[$i].duration_seconds*1000
    and ($i==0 or ($run.phase_windows[$i-1].end|ts)==($run.phase_windows[$i].start|ts)));
    "Run windows must preserve frozen durations and form one contiguous period")
| ensure(($run.started_at|ts)==($run.phase_windows[0].start|ts)
          and ($run.ended_at|ts)>=($run.phase_windows[-1].end|ts); "Run did not complete its declared reporting period")
| ([$run.evidence_kind,$samples.evidence_kind,$intervals.evidence_kind]|unique) as $kinds
| ensure(($kinds|length)==1 and ($kinds[0]=="observed" or $kinds[0]=="synthetic_fixture"); "Evidence kinds differ")
| ($scenario.models|keys) as $models
| ($scenario.teams|to_entries|map({key:.value.subscription,value:(.value+{team:.key})})|from_entries) as $teams
| ($teams|with_entries(.value=.value.team)) as $subscriptions
| (reduce ($metering.model_aliases|to_entries[]) as $entry ({};
     reduce $entry.value[] as $alias (.; .[$alias]=$entry.key))) as $aliases
| ensure(($run.requests_started|integer) and $run.requests_started==($receipts|length); "Receipt count mismatch")
| ensure(($receipts|map(.request_id)|unique|length)==($receipts|length); "Duplicate request identity")
| ensure(all($receipts[]; (.request_id|type)=="string" and (.request_id|length)>0); "Missing request identity")
| ensure(all($run.phase_windows[]; (.start|ts)<(.end|ts)); "Invalid window boundaries")
| reduce $receipts[] as $r (.;
    ensure($r.schema_version==1 and $r.scope=="workload" and $r.run_id==$run.run_id; "Receipt schema/scope/run mismatch")
    | ensure(($models|index($r.requested_model))!=null and $teams[$r.subscription]!=null
         and $subscriptions[$r.subscription]==$r.team; "Unknown receipt model/subscription/team")
    | ensure($teams[$r.subscription].models|has($r.requested_model); "Receipt outside permitted model matrix")
    | ($r.started_at|ts) as $start | ($r.ended_at|ts) as $end
    | ensure($end >= $start; "Receipt end precedes start")
    | [$run.phase_windows[] | select((.start|ts)<=$start and $start<(.end|ts))] as $w
    | ensure(($w|length)==1 and $w[0].id==$r.phase; "Receipt not assigned to exactly one phase")
    | if $r.usage_status=="known" then
        ensure($r.status=="success" and $r.http_status==200
          and all([$r.input_tokens,$r.output_tokens,$r.total_tokens][]; integer)
          and sum_count($r.input_tokens;$r.output_tokens)==$r.total_tokens; "Invalid known token usage") else . end)
| ensure(($metering.canonical_series|map(key(.subscription;.model))|unique|length)
          ==($metering.canonical_series|length); "Duplicate canonical-series key")
| ensure(all($metering.canonical_series[]; (.subscription|type)=="string" and (.subscription|length)>0
          and (.model as $m|$models|index($m))!=null); "Invalid canonical series")
| ensure(all($metering.canonical_series[];
    $teams[.subscription]==null or .user==$teams[.subscription].user);
    "Canonical user differs from the frozen team identity")
| ($metering.canonical_series|map({key:key(.subscription;.model),value:.})|from_entries) as $expected
| ensure(all($teams|to_entries[]; .key as $sub | all(.value.models|keys[]; $expected[key($sub;.)]!=null));
         "Every allowed team/model needs a canonical series")
| (reduce $metering.canonical_series[] as $c ($subscriptions; .[$c.subscription] //= "other_consumers")) as $subscriptions
| ensure($samples.data.resultType=="matrix" and ($samples.data.result|type)=="array"
          and (($samples.warnings // [])|length)==0; "Complete raw range matrix without query warnings required")
| ensure(all($samples.data.result[];.metric.__name__=="authorized_hits_total"); "Canonical token metric must be authorized_hits_total")
| (reduce $samples.data.result[] as $s ({selected:{},issues:($models|map({key:.,value:[]})|from_entries)};
    $s.metric as $labels | $aliases[$labels.model // ""] as $model | ($labels.subscription // "") as $sub
    | if $model==null then
        if $teams[$sub]!=null or ($labels.model // "")=="" then
          .issues |= with_entries(.value += ["demo_subscription_has_unknown_model_label"]) else . end
      else $expected[key($sub;$model)] as $canonical
        | if $canonical==null then .issues[$model] += ["unmapped_subscription_or_limiter"]
          elif ($canonical.limitador_namespace // "")=="" then .issues[$model] += ["canonical_limiter_not_verified"]
          elif $labels.limitador_namespace!=$canonical.limitador_namespace then .
          elif ($labels.user // "")=="" or $labels.user!=$canonical.user then .issues[$model] += ["unresolved_user_identity"]
          else .selected[key($sub;$model)] += [$s] end
      end)) as $indexed
| [$run.phase_windows[] as $phase | ($phase.start|ts) as $start | ($phase.end|ts) as $end
   | {id:$phase.id,phase:$phase.id,start:$phase.start,end:$phase.end,usage:
      (reduce $models[] as $model ({};
        ($teams|to_entries|map(select($expected[key(.key;$model)]!=null)|{key:.key,value:0})|from_entries) as $zeros
        | (reduce ($expected|to_entries[].value|select(.model==$model)) as $canonical
           ({tokens:{},issues:$indexed.issues[$model],receipt_tokens:{},receipt_input_tokens:$zeros,
             receipt_output_tokens:$zeros,request_counts:$zeros,error_counts:$zeros,quota_rejections:$zeros};
              $canonical.subscription as $sub | ($indexed.selected[key($sub;$model)] // []) as $series
              | if ($series|length)!=1 then .issues += ["missing_or_duplicate_canonical_series:"+$sub]
                else delta($series[0].values;$start;$end;$metering.max_scrape_gap_seconds*1000;
                           $metering.boundary_tolerance_seconds*1000) as $d
                  | if $d|has("issue") then .issues += [$d.issue+":"+$sub] else .tokens[$sub]=$d.delta end end)
           | reduce ($receipts[]|select(.requested_model==$model)) as $r (.;
               ($r.started_at|ts) as $rs | ($r.ended_at|ts) as $re
               | if (($start<=$rs and $rs<$end) or ($rs<$start and $start<$re))|not then .
                 elif $rs<$start or $re>$end or $r.phase!=$phase.id then .issues += ["inflight_boundary_request"]
                 else $r.subscription as $sub
                   | .request_counts[$sub] += 1
                   | if $r.status!="success" then .error_counts[$sub] += 1 else . end
                   | if $r.http_status==429 then .quota_rejections[$sub] += 1 else . end
                   | if $aliases[$r.actual_model // ""]!=$model then .issues += ["response_model_unverified"] else . end
                   | if $r.usage_status!="known" then .issues += ["missing_request_usage"]
                     else .receipt_tokens[$sub]=sum_count((.receipt_tokens[$sub]//0);$r.total_tokens)
                       | .receipt_input_tokens[$sub]=sum_count(.receipt_input_tokens[$sub];$r.input_tokens)
                       | .receipt_output_tokens[$sub]=sum_count(.receipt_output_tokens[$sub];$r.output_tokens) end end)
           | reduce ($teams|keys[]|select($expected[key(.;$model)]!=null)) as $sub (.;
               (.receipt_tokens[$sub] // 0) as $wanted | .tokens[$sub] as $actual
               | if $actual==null or (($actual-$wanted)|fabs)>($receipt_tolerance*$wanted)
                 then .issues += ["receipt_counter_mismatch:"+$sub] else . end)
           | if $phase.id=="idle" and (((.tokens|add)//0)>0 or (.receipt_tokens|length)>0)
             then .issues += ["intended_idle_window_has_activity"] else . end
           | .issues |= unique | .coverage=(if (.issues|length)==0 then "complete" else "missing_usage" end)) as $usage
        | .[$model]=$usage))}] as $windows
| {schema_version:1,report_id:$run.run_id,scope:$costs.scope,evidence_kind:$kinds[0],policy_version:$scenario.policy_version,
   currency:$costs.currency,models:$models,subscriptions:$subscriptions,rates:$costs.rates,
   instance_intervals:$intervals.instance_intervals,windows:$windows,excluded_costs:$costs.excluded_costs,
   price_basis:$costs.price_basis,scenario_sha256:$run.scenario_sha256,source:$samples.source,metering:$metering,
   limitations:["Sampled showback, not billing-grade metering",
     "Cross-boundary activity, resets or gaps remain unresolved rather than extrapolated"]}
JQ
)
    jq -ne --slurpfile run "$RUN" --slurpfile receipts "$RECEIPTS" --slurpfile samples "$SAMPLES" \
        --slurpfile scenario "$SCENARIO" --slurpfile metering "$METERING" --slurpfile costs "$COSTS" \
        --slurpfile intervals "$INTERVALS" "$COMMON $PROGRAM" >"$WORK_DIR/prepared.json"
    hashes=$(for entry in "run:$RUN" "receipts:$RECEIPTS" "samples:$SAMPLES" "scenario:$SCENARIO" \
        "metering:$METERING" "costs:$COSTS" "intervals:$INTERVALS"; do
        hash=$(shasum -a 256 "${entry#*:}" | cut -d ' ' -f 1) || exit 1
        printf '%s\t%s\n' "${entry%%:*}" "$hash"
    done | jq -Rn '[inputs|split("\t")|{key:.[0],value:.[1]}]|from_entries')
    jq --argjson hashes "$hashes" '.+{input_sha256:$hashes}' "$WORK_DIR/prepared.json" >"$WORK_DIR/result.json"
fi
mkdir -p "$(dirname "$OUTPUT")"
set -o noclobber
cat "$WORK_DIR/result.json" >"$OUTPUT"
