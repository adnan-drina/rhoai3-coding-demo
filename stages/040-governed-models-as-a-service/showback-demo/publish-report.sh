#!/usr/bin/env bash
# Validate one closed report and atomically render its gauges; no listener, network access or deployment.
# Optional ConfigMap output is the exact static snapshot for the disabled standard HTTP server.
# Usage: stages/040-governed-models-as-a-service/showback-demo/publish-report.sh --report FILE --output FILE [--scenario FILE] [--configmap-output FILE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
REPORT= OUTPUT= CONFIGMAP_OUTPUT=
SCENARIO="$SCRIPT_DIR/scenario.json"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --report) REPORT=${2:?}; shift 2 ;;
        --output) OUTPUT=${2:?}; shift 2 ;;
        --scenario) SCENARIO=${2:?}; shift 2 ;;
        --configmap-output) CONFIGMAP_OUTPUT=${2:?}; shift 2 ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
[[ -n "$REPORT" && -n "$OUTPUT" ]] || { log_error 'Report and output are required'; exit 1; }
[[ ! -d "$OUTPUT" && ( -z "$CONFIGMAP_OUTPUT" || ! -d "$CONFIGMAP_OUTPUT" ) ]] || {
    log_error 'Metrics and ConfigMap outputs must be files, not directories'; exit 1;
}
for cmd in jq shasum ruby; do command -v "$cmd" >/dev/null || { log_error "Missing command: $cmd"; exit 1; }; done

canonical_path() {
    local path="$1" target count=0
    while [[ -L "$path" ]]; do
        count=$((count + 1))
        [[ $count -le 40 ]] || { log_error 'Symlink cycle'; return 1; }
        target=$(readlink "$path")
        case "$target" in /*) path="$target" ;; *) path="$(dirname "$path")/$target" ;; esac
    done
    printf '%s/%s\n' "$(cd -P "$(dirname "$path")" && pwd)" "$(basename "$path")"
}

umask 077
mkdir -p "$(dirname "$OUTPUT")"
[[ -z "$CONFIGMAP_OUTPUT" ]] || mkdir -p "$(dirname "$CONFIGMAP_OUTPUT")"
report_path=$(canonical_path "$REPORT")
scenario_path=$(canonical_path "$SCENARIO")
output_path=$(canonical_path "$OUTPUT")
[[ "$output_path" != "$report_path" && "$output_path" != "$scenario_path" ]] || {
    log_error 'Metrics output must differ from report and scenario inputs'; exit 1;
}
if [[ -n "$CONFIGMAP_OUTPUT" ]]; then
    configmap_path=$(canonical_path "$CONFIGMAP_OUTPUT")
    [[ "$configmap_path" != "$report_path" && "$configmap_path" != "$scenario_path" && "$configmap_path" != "$output_path" ]] || {
        log_error 'ConfigMap output must differ from all other inputs and outputs'; exit 1;
    }
fi
WORK=$(mktemp -d)
TEMP_METRICS= TEMP_CONFIGMAP=
trap 'rm -rf "$WORK"; [[ -z "$TEMP_METRICS" ]] || rm -f "$TEMP_METRICS"; [[ -z "$TEMP_CONFIGMAP" ]] || rm -f "$TEMP_CONFIGMAP"' EXIT
# Snapshot both inputs once; no path can change halfway through label/value generation.
cp "$REPORT" "$WORK/report.json"
cp "$SCENARIO" "$WORK/scenario.json"
for input in report scenario; do
    jq -se 'length == 1 and (.[0]|type) == "object"' "$WORK/$input.json" >/dev/null || {
        log_error "Expected one JSON object in $input input"; exit 1;
    }
done
report_hash=$(jq -cS . "$WORK/report.json" | shasum -a 256 | awk '{print $1}')
scenario_hash=$(jq -cS . "$WORK/scenario.json" | shasum -a 256 | awk '{print $1}')
PROGRAM=$(cat <<'JQ'
# jq implementation of the closed-report publication contract. Integer money is
# checked before rendering; floats are only display ratios, never allocations.
def fail($message): error($message);
def check($condition; $message): if $condition then . else fail($message) end;
def uint: type == "number" and . >= 0 and . == floor and . <= 9007199254740991;
def number: if type == "string" then tonumber else . end | check(type == "number" and isfinite and . >= 0; "Invalid decimal");
def stamp:
  check(type == "string" and test("(Z|\\+00:00)$"); "UTC timestamp required")
  | sub("\\+00:00$"; "Z") as $s
  | ($s | sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601)
    + ((try ($s | capture("(?<f>\\.[0-9]+)Z$").f | tonumber) catch 0) // 0);
def sum_values: [.[]] | add // 0;
def nonzero: with_entries(select(.value != 0));
def valid_map: type == "object" and all(.[]; uint);
def valid_model:
  (.coverage == "complete" or .coverage == "missing_usage" or .coverage == "partial_period")
  and (.model | type == "string" and length > 0)
  and (.instance_hours | number) >= 0
  and (.tokens | valid_map)
  and (if .coverage == "complete" then (.total_tokens | uint) and .total_tokens == (.tokens | sum_values)
       else .total_tokens == null end)
  and (.known_cost_cents | uint)
  and (.cost_cents == null or ((.cost_cents | uint) and .cost_cents == .known_cost_cents))
  and (.raw_cost_usd == null or (.raw_cost_usd | number) >= 0)
  and (.allocations | valid_map) and (.allocations | sum_values) == .known_cost_cents
  and all([.receipt_input_tokens,.receipt_output_tokens,.request_counts,.error_counts,.quota_rejections][];
          . == null or valid_map);
def validate:
  . as $r
  | check(.schema_version == 1 and .currency == "USD"; "Unsupported report schema/currency")
  | check(all([.report_id,.scope,.policy_version][]; type == "string" and length > 0); "Missing report identity")
  | check(.evidence_kind == "observed" or .evidence_kind == "synthetic_fixture"; "Invalid evidence kind")
  | check(all([.pricing_complete,.allocation_complete][]; type == "boolean"); "Completeness must be boolean")
  | check((.end|stamp) > (.start|stamp); "Invalid report period")
  | check((.windows|type) == "array" and (.windows|length) > 0; "No windows")
  | check(all(.windows[]; all([.id,.phase][];type == "string" and length > 0)
       and (.models|type) == "array" and (.models|length) > 0 and all(.models[]; valid_model)
       and ([.models[].model]|length) == ([.models[].model]|unique|length)
       and ([.models[].model]|sort) == ([$r.windows[0].models[].model]|sort)
       and (.known_total_cents|uint) and .known_total_cents == ([.models[].known_cost_cents]|add)
       and ((.total_cents != null) == all(.models[]; .cost_cents != null))
       and (.total_cents == null or ((.total_cents|uint) and .total_cents == .known_total_cents)));
       "Invalid model/window accounting")
  | check((reduce .windows[] as $w ({last:($r.start|stamp),ids:[],ok:true};
       .ok = (.ok and .last == ($w.start|stamp) and ($w.end|stamp) > .last and (.ids|index($w.id)|not))
       | .last=($w.end|stamp) | .ids += [$w.id]) | .ok and .last == ($r.end|stamp)); "Window gap/overlap")
  | check((.known_total_cents|uint) and .known_total_cents == ([.windows[].known_total_cents]|add); "Known total mismatch")
  | check((.totals_by_consumer|valid_map) and (.totals_by_consumer|nonzero) ==
      (reduce [.windows[].models[].allocations|to_entries[]][] as $a ({}; .[$a.key] += $a.value)|nonzero);
      "Consumer total mismatch")
  | check(.pricing_complete == all(.windows[].models[]; .cost_cents != null); "Price coverage mismatch")
  | check(if .pricing_complete then (.total_cents|uint) and .total_cents == .known_total_cents
          else .total_cents == null and (.allocation_complete|not) end; "Unknown price published as total")
  | check((.allocation_complete|not) or all(.windows[].models[]; .coverage == "complete"); "Incomplete usage allocated")
  | check((.subscription_teams|type) == "object" and (.rates|type) == "object"; "Missing report snapshots")
  | check(all(.subscription_teams[];type == "string" and length > 0); "Invalid subscription/team mapping")
  | check((.metadata // {} | type) == "object"; "Invalid metadata")
  | check(all(.windows[].models[] | select(.coverage == "complete") | .tokens | keys[];
       $r.subscription_teams[.] != null); "Unknown certified subscription")
  | .;

validate as $r
| $scenario[0] as $s
| {report_id:$r.report_id,scope:$r.scope,evidence_kind:$r.evidence_kind,policy_version:$r.policy_version,
   currency:$r.currency,period_start:$r.start,period_end:$r.end,report_sha256:$report_hash} as $base
| def metric($name; $value; $extra):
    if $value == null then empty else {name:$name,value:$value,labels:($base+$extra)} end;
  def config($name; $value; $extra):
    {name:$name,value:$value,labels:({scenario_id:$s.scenario_id,configuration_status:$s.quota_status,
      scenario_sha256:$scenario_hash}+$extra)};
  def ml($w; $m): {window_id:$w.id,phase:$w.phase,window_start:$w.start,window_end:$w.end,
      model:$m.model,coverage:$m.coverage};
  def sl($w; $m; $subscription): ml($w;$m)+{subscription:$subscription,
      team:($r.subscription_teams[$subscription] // "unresolved_identity")};
  def labels_text:
    to_entries | sort_by(.key) | map(.value |= tostring
      | check((.value|test("[\u0000-\u0009\u000b-\u001f]")|not); "Control character in label")
      | "\(.key)=\(.value|@json)") | join(",");
  def emit:
    group_by(.name)[] | "# HELP \(.[0].name) Selected snapshot; not a counter.",
      "# TYPE \(.[0].name) gauge", (.[] | "\(.name){\(.labels|labels_text)} \(.value)");
[
  metric("showback_selected_report_info";1;{}),
  metric("showback_report_price_basis_info";1;{
    price_basis:($r.price_basis // $r.metadata.price_basis // "unspecified in report"),
    cost_basis:($r.cost_basis // "unspecified in report")}),
  (($r.excluded_costs // $r.metadata.cost_exclusions // ["unspecified in report"])
    | check(type == "array" and all(.[];type == "string");"Invalid exclusions")
    | if length == 0 then ["none declared"] else . end | unique[]
    | metric("showback_report_exclusion_info";1;{excluded_cost:.})),
  ([$r.instance_intervals[]? | select((.start|stamp) < ($r.end|stamp) and (.end|stamp) > ($r.start|stamp))
    | .rate_id] | unique[] as $id | ($r.rates[$id] // {}) as $rate
    | {rate_id:$id,rate_source:($rate.source // "unspecified in report"),
       instance_type:($rate.instance_type // "unspecified in report"),region:($rate.region // "unspecified in report"),
       effective_date:($rate.effective_date // "unspecified in report"),
       price_state:(if $rate.usd_per_hour == null then "missing_price" else "priced" end)} as $labels
    | metric("showback_report_rate_info";1;$labels),
      (if $rate.usd_per_hour != null then metric("showback_report_rate_usd_per_hour";($rate.usd_per_hour|number);$labels) else empty end)),
  metric("showback_report_start_timestamp_seconds";($r.start|stamp);{}),
  metric("showback_report_end_timestamp_seconds";($r.end|stamp);{}),
  metric("showback_report_pricing_complete";(if $r.pricing_complete then 1 else 0 end);{}),
  metric("showback_report_allocation_complete";(if $r.allocation_complete then 1 else 0 end);{}),
  metric("showback_report_known_cost_cents";$r.known_total_cents;{}),
  metric("showback_report_cost_cents";$r.total_cents;{}),
  ($r.totals_by_consumer|to_entries[]|metric("showback_report_allocated_cents";.value;{consumer:.key})),
  ($r.windows[] as $w
    | {window_id:$w.id,phase:$w.phase,window_start:$w.start,window_end:$w.end} as $wl
    | metric("showback_window_info";1;$wl), metric("showback_window_cost_cents";$w.total_cents;$wl),
      ($w.models[] as $m | ml($w;$m) as $l
        | metric("showback_model_coverage_complete";(if $m.coverage == "complete" then 1 else 0 end);$l),
          metric("showback_model_pricing_complete";(if $m.cost_cents != null then 1 else 0 end);$l),
          metric("showback_model_known_cost_cents";$m.known_cost_cents;$l),
          metric("showback_model_cost_cents";$m.cost_cents;$l),
          metric("showback_model_instance_hours";($m.instance_hours|number);$l),
          metric("showback_model_tokens";$m.total_tokens;$l),
          (if $m.cost_cents != null and $m.raw_cost_usd != null and ($m.instance_hours|number) > 0 then
             metric("showback_model_effective_worker_usd_per_hour";(($m.raw_cost_usd|number)/($m.instance_hours|number));$l) else empty end),
          ($m.allocations|to_entries[]|metric("showback_model_allocated_cents";.value;($l+{consumer:.key}))),
          ($m.tokens|to_entries[] as $t
            | metric((if $m.coverage == "complete" then "showback_subscription_tokens"
                      else "showback_subscription_observed_tokens" end);$t.value;sl($w;$m;$t.key)),
              (if $m.coverage == "complete" and $m.total_tokens > 0 then
                 metric("showback_subscription_token_share_ratio";($t.value/$m.total_tokens);sl($w;$m;$t.key)) else empty end)),
          ([{field:"receipt_input_tokens",name:"showback_receipt_input_tokens"},
            {field:"receipt_output_tokens",name:"showback_receipt_output_tokens"},
            {field:"request_counts",name:"showback_receipt_requests"},
            {field:"error_counts",name:"showback_receipt_errors"},
            {field:"quota_rejections",name:"showback_receipt_quota_rejections"}][] as $map
            | ($m[$map.field] // {} | to_entries[]) as $entry
            | metric($map.name;$entry.value;sl($w;$m;$entry.key))),
          (if $m.cost_cents != null and $m.total_tokens != null and $m.total_tokens > 0 then
             metric("showback_model_effective_usd_per_million_tokens";($m.cost_cents*10000/$m.total_tokens);$l) else empty end))),
  ([$r.windows[].models[]] | group_by(.model)[] as $rows
    | all($rows[];.cost_cents != null) as $priced | all($rows[];.coverage == "complete") as $covered
    | {model:$rows[0].model,pricing_complete:($priced|tostring),usage_complete:($covered|tostring)} as $l
    | ([$rows[].instance_hours|number]|add) as $hours
    | metric("showback_report_model_known_cost_cents";([$rows[].known_cost_cents]|add);$l),
      metric("showback_report_model_instance_hours";$hours;$l),
      (if $priced then metric("showback_report_model_cost_cents";([$rows[].cost_cents]|add);$l),
         (if $hours > 0 and all($rows[];.raw_cost_usd != null) then
           metric("showback_report_model_effective_worker_usd_per_hour";(([$rows[].raw_cost_usd|number]|add)/$hours);$l)
          else empty end) else empty end),
      (reduce [$rows[].allocations|to_entries[]][] as $entry ({};.[$entry.key]+=$entry.value)
        | to_entries[] | metric("showback_report_model_allocated_cents";.value;($l+{consumer:.key}))),
      (if $covered then reduce [$rows[].tokens|to_entries[]][] as $entry ({};.[$r.subscription_teams[$entry.key]]+=$entry.value)
        | to_entries[] | metric("showback_report_team_model_tokens";.value;($l+{team:.key})) else empty end)),
  ($s.teams|to_entries[] as $team | $s.models|keys[] as $model
    | {team:$team.key,subscription:$team.value.subscription,model:$model} as $l
    | ($team.value.models[$model] // null) as $budget
    | config("showback_config_model_access";(if $budget != null then 1 else 0 end);$l),
      (if $budget != null then
        check($budget.token_limit|uint;"Invalid allowance")
        | ($l+{quota_window:$budget.window}) as $ql
        | ([$s.teams[].models[$model] | select(.window == $budget.window) | .token_limit]|add) as $denom
        | config("showback_config_allowance_tokens";$budget.token_limit;$ql),
          (if $denom > 0 then config("showback_config_allowance_share_ratio";($budget.token_limit/$denom);$ql) else empty end)
       else empty end))
]
| "# One selected closed report. All values are GAUGES; never integrate over scrape time.", emit
JQ
)
jq -r --arg report_hash "$report_hash" --arg scenario_hash "$scenario_hash" \
    --slurpfile scenario "$WORK/scenario.json" "$PROGRAM" "$WORK/report.json" > "$WORK/metrics.prom"
[[ -s "$WORK/metrics.prom" ]] || { log_error 'Empty report metrics refused'; exit 1; }
if [[ -n "$CONFIGMAP_OUTPUT" ]]; then
    jq -n --rawfile metrics "$WORK/metrics.prom" --arg sha "$report_hash" '{
      apiVersion:"v1",kind:"ConfigMap",metadata:{name:"showback-selected-report",namespace:"redhat-ods-monitoring",
      labels:{"app.kubernetes.io/name":"showback-report-publisher","app.kubernetes.io/part-of":"observability",
      "app.kubernetes.io/component":"observability","app.kubernetes.io/managed-by":"argocd"},
      annotations:{"showback.demo.rhoai.io/report-sha256":$sha}},data:{"metrics.prom":$metrics}}' > "$WORK/configmap.json"
    [[ $(wc -c < "$WORK/configmap.json") -lt 900000 ]] || {
        log_error 'Selected snapshot exceeds the demo ConfigMap budget; keep this report file/artifact-backed'; exit 1;
    }
    ruby -ryaml -rjson -e 'puts YAML.dump(JSON.parse(STDIN.read))' < "$WORK/configmap.json" > "$WORK/configmap.yaml"
    TEMP_CONFIGMAP=$(mktemp "$(dirname "$CONFIGMAP_OUTPUT")/.showback-configmap.XXXXXX")
    cp "$WORK/configmap.yaml" "$TEMP_CONFIGMAP"
fi
TEMP_METRICS=$(mktemp "$(dirname "$OUTPUT")/.showback-metrics.XXXXXX")
cp "$WORK/metrics.prom" "$TEMP_METRICS"
mv -f "$TEMP_METRICS" "$OUTPUT"
TEMP_METRICS=
if [[ -n "$CONFIGMAP_OUTPUT" ]]; then
    mv -f "$TEMP_CONFIGMAP" "$CONFIGMAP_OUTPUT"
    TEMP_CONFIGMAP=
fi
