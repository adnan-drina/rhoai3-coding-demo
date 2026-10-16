#!/usr/bin/env bash
# Render one validated service report to static Prometheus gauges. Offline, atomic and safe to rerun.
# Optional ConfigMap replaces the existing stopped publisher's selection; this script never applies it.
# Usage: stages/040-governed-models-as-a-service/showback-demo/service-views/render-report.sh --report FILE --output FILE [--analysis FILE] [--configmap-output FILE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
source "$SCRIPT_DIR/report-lib.sh"
REPORT= OUTPUT= ANALYSIS= CONFIGMAP_OUTPUT=
while [[ $# -gt 0 ]]; do
    case "$1" in
        --report) REPORT=${2:?}; shift 2 ;;
        --output) OUTPUT=${2:?}; shift 2 ;;
        --analysis) ANALYSIS=${2:?}; shift 2 ;;
        --configmap-output) CONFIGMAP_OUTPUT=${2:?}; shift 2 ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
[[ -n "$REPORT" && -n "$OUTPUT" ]] || { log_error 'Report and output are required'; exit 1; }
umask 077
assert_output_path "$OUTPUT" "$REPORT" "$ANALYSIS"
if [[ -n "$CONFIGMAP_OUTPUT" ]]; then
    assert_output_path "$CONFIGMAP_OUTPUT" "$REPORT" "$ANALYSIS" "$OUTPUT"
fi
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
snapshot_json "$REPORT" "$WORK/report.json"
validate_report "$WORK/report.json"
report_hash=$(json_sha256 "$WORK/report.json")
analysis_hash=
if [[ -n "$ANALYSIS" ]]; then
    snapshot_json "$ANALYSIS" "$WORK/analysis.json"
    analysis_hash=$(json_sha256 "$WORK/analysis.json")
else
    printf 'null\n' > "$WORK/analysis.json"
fi
PROGRAM=$(cat <<'JQ'
def check($ok;$message): if $ok then . else error($message) end;
def labels_text:
  to_entries|sort_by(.key)|map(.value |= tostring
    | check((.value|test("[\u0000-\u0009\u000b-\u001f]")|not);"Control character in label")
    | "\(.key)=\(.value|@json)")|join(",");
def metric($name;$value;$labels):
  if $value == null then empty else
    check(($value|type)=="number" and ($value|isfinite);"Non-numeric metric")
    | {name:$name,value:$value,labels:$labels}
  end;
def bool: if . then 1 else 0 end;
. as $r
| {report_id:.report_id,report_sha256:$report_hash,revision:(.revision|tostring),
   evidence_kind:.evidence_kind,period_start:.period.start,period_end:.period.end,currency:.currency,
   policy_version:.policy_version,statement_status:.statement_status} as $base
| def emit($name;$value;$extra): metric($name;$value;($base+$extra));
[
  emit("service_report_info";1;{price_basis:$r.price_basis,cost_scope:$r.cost_scope}),
  emit("service_report_complete";($r.complete|bool);{}),
  emit("service_report_start_timestamp_seconds";($r.period.start|fromdateiso8601);{}),
  emit("service_report_end_timestamp_seconds";($r.period.end|fromdateiso8601);{}),
  (["cost_cents","known_cost_cents","charge_cents","known_charge_cents","subsidy_cents",
    "recovery_balance_cents","invoice_cents","invoice_difference_cents"][] as $field
    | emit("service_report_"+$field;$r.totals[$field];{})),
  ($r.agreements[] as $a
    | {agreement:$a.id,offer:$a.offer,model:$a.model,owner_team:($a.owner_team // "unassigned")} as $labels
    | emit("service_agreement_info";1;($labels+{price_basis:($a.price_basis // $r.price_basis),
        cost_basis:$a.cost_basis,contract_version:$a.contract_version})),
      (["pricing_complete","cost_complete","usage_complete"][] as $field
       | emit("service_agreement_"+$field;($a[$field]|bool);$labels)),
      (["cost_cents","known_cost_cents","charge_cents","known_charge_cents","subsidy_cents",
        "recovery_balance_cents","invoice_cents","invoice_difference_cents"][] as $field
       | emit("service_agreement_"+$field;$a[$field];$labels)),
      (if $a.cost_cents != null and $a.cost_cents > 0 and $a.charge_cents != null then
         emit("service_agreement_recovery_before_subsidy_ratio";($a.charge_cents/$a.cost_cents);$labels),
         (if $a.subsidy_cents != null then emit("service_agreement_recovery_after_subsidy_ratio";
           (($a.charge_cents+$a.subsidy_cents)/$a.cost_cents);$labels) else empty end)
       else empty end),
      (if $a.usage_complete then
         (["input_tokens","output_tokens","requests"][] as $field
          | emit("service_agreement_"+$field;$a.usage[$field];$labels)),
         (if $a.usage.input_tokens != null and $a.usage.output_tokens != null then
            emit("service_agreement_total_tokens";($a.usage.input_tokens+$a.usage.output_tokens);$labels) else empty end)
       else empty end)),
  ($r.charge_lines | group_by([.agreement_id,.offer,.model,.user,.team,.subscription,.category,.kind,.rate_version])[]
    | . as $lines | .[0] as $line
    | {agreement:$line.agreement_id,offer:$line.offer,model:$line.model,user:($line.user // "unattributed"),
       team:($line.team // "unattributed"),subscription:($line.subscription // "unattributed"),category:$line.category,
       charge_kind:$line.kind,rate_version:($line.rate_version // "unspecified")} as $labels
    | (any($r.agreements[];.id == $line.agreement_id and .pricing_complete)
       and all($lines[];.charge_cents != null)) as $priced
    | emit("service_consumer_known_charge_cents";([$lines[].charge_cents // empty]|add // 0);$labels),
      emit("service_consumer_price_complete";($priced|bool);$labels),
      (if $priced then
         emit("service_consumer_charge_cents";([$lines[].charge_cents]|add);$labels) else empty end),
      ([$lines[]|{unit,quantity,rate_usd,source}]|group_by([.unit,.rate_usd,.source])[] as $rated
        | ($labels+{unit:$rated[0].unit,rate_usd:($rated[0].rate_usd // "unknown"),
           rate_source:($rated[0].source // "unspecified")}) as $rate_labels
        | emit("service_rate_info";1;$rate_labels),
          (if all($rated[]; .quantity != null) then
             emit("service_consumer_quantity";([$rated[].quantity|tonumber]|add);$rate_labels) else empty end))),
  ($r.cost_lines|group_by([.agreement_id,.offer,.model,.category,.owner_team])[] as $lines
    | $lines[0] as $line
    | {agreement:$line.agreement_id,offer:$line.offer,model:$line.model,category:$line.category,
       owner_team:($line.owner_team // "unassigned")} as $labels
    | emit("service_cost_component_known_cents";([$lines[].cost_cents // empty]|add // 0);$labels),
      (if all($lines[];.cost_cents != null) then
         emit("service_cost_component_cents";([$lines[].cost_cents]|add);$labels) else empty end)),
  ($analysis[0] as $a | if $a == null then empty else
    check($a.schema_version == 1 and $a.report_type == "service_advice" and ($a.report_id|type)=="string";
      "Unsupported advice report")
    | check($a.period.start == $r.period.start and $a.period.end == $r.period.end
        and $a.currency == $r.currency and $a.evidence_kind == $r.evidence_kind;"Advice/report scope mismatch")
    | {analysis_report_id:$a.report_id,analysis_sha256:$analysis_hash} as $identity
    | emit("service_advice_info";1;($identity+{recommendation:$a.sourcing.recommendation,
        acceptance_definition:$a.acceptance_definition,calculation_basis:$a.calculation_basis})),
      (["tasks","accepted_tasks","attempts","corrective_retries","planned_turns","fallbacks",
        "total_cost_cents","cost_per_accepted_task_cents"][] as $field
        | emit("service_advice_"+$field;$a.totals[$field];$identity)),
      ($a.sourcing.scenarios[] as $scenario
        | ($identity+{scenario:$scenario.name,capacity_eligible:($scenario.capacity_eligible|tostring)}) as $labels
        | (["accepted_tasks","external_cost_cents","private_cost_cents","savings_cents","payback_months"][] as $field
          | emit("service_sourcing_"+$field;$scenario[$field];$labels))) end)
]
| "# One immutable service report; all values are GAUGES, never integrate over scrape time.",
  (group_by(.name)[] | "# HELP \(.[0].name) Selected service snapshot; not a counter.",
   "# TYPE \(.[0].name) gauge",(.[]|"\(.name){\(.labels|labels_text)} \(.value)"))
JQ
)
jq -r --arg report_hash "$report_hash" --arg analysis_hash "$analysis_hash" \
    --slurpfile analysis "$WORK/analysis.json" "$PROGRAM" "$WORK/report.json" > "$WORK/metrics.prom"
[[ -s "$WORK/metrics.prom" ]] || { log_error 'Empty metric selection refused'; exit 1; }
if [[ -n "$CONFIGMAP_OUTPUT" ]]; then
    jq -n --rawfile metrics "$WORK/metrics.prom" --arg sha "$report_hash" '{
      apiVersion:"v1",kind:"ConfigMap",metadata:{name:"showback-selected-report",namespace:"redhat-ods-monitoring",
      labels:{"app.kubernetes.io/name":"showback-report-publisher","app.kubernetes.io/part-of":"observability",
        "app.kubernetes.io/component":"observability","app.kubernetes.io/managed-by":"argocd"},
      annotations:{"showback.demo.rhoai.io/report-sha256":$sha}},data:{"metrics.prom":$metrics}}' > "$WORK/configmap.json"
    [[ $(wc -c < "$WORK/configmap.json") -lt 900000 ]] || { log_error 'Snapshot exceeds ConfigMap budget'; exit 1; }
    ruby -ryaml -rjson -e 'puts YAML.dump(JSON.parse(STDIN.read))' < "$WORK/configmap.json" > "$WORK/configmap.yaml"
fi
atomic_copy "$WORK/metrics.prom" "$OUTPUT"
[[ -z "$CONFIGMAP_OUTPUT" ]] || atomic_copy "$WORK/configmap.yaml" "$CONFIGMAP_OUTPUT"
