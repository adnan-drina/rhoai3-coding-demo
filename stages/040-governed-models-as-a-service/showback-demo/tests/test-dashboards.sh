#!/usr/bin/env bash
# Offline shell regression checks for publication, report identity, dashboards and selected-report static serving.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BASE/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
fail() { log_error "$*"; exit 1; }
reject() { if "$@" >"$WORK/rejected.log" 2>&1; then fail 'Expected rejection'; fi; }
parse() {
    jq -Rn '[inputs|select(startswith("#")|not)
      | capture("^(?<name>[A-Za-z_][A-Za-z0-9_:]*)\\{(?<labels>.*)\\} (?<value>[^ ]+)$")
      | .value |= tonumber
      | .labels |= ([scan("([A-Za-z_][A-Za-z0-9_]*)=(\"(?:[^\"\\\\]|\\\\.)*\")")
          | {key:.[0],value:(.[1]|fromjson)}]|from_entries)]' < "$1" > "$2"
}
render() {
    bash "$BASE/publish-report.sh" --report "$1" --output "$WORK/metrics.prom" "${@:2}"
    parse "$WORK/metrics.prom" "$WORK/metrics.json"
}
assert_metric() { jq -e "$1" "$WORK/metrics.json" >/dev/null || fail "$2"; }

bash "$BASE/allocate.sh" --input "$BASE/fixtures/accounting.json" --output "$WORK/report.json"
render "$WORK/report.json" --configmap-output "$WORK/selected.yaml"
assert_metric '[.[]|select(.name=="showback_report_cost_cents")|.value] == [135]' 'Bill parity'
assert_metric '[.[]|select(.name=="showback_model_allocated_cents")|.value]|add==135' 'Model allocation parity'
assert_metric 'all(.[]|select(.name=="showback_model_cost_cents");
  .labels.evidence_kind=="synthetic_fixture" and (.labels.report_sha256|length)==64)' 'Evidence identity'
assert_metric '[.[]|select(.name=="showback_report_model_cost_cents")|{key:.labels.model,value:.value}]|from_entries
  == {"qwen3-8-27b":67,"mistral-small4-119b":68}' 'Model full-cost rollup'
assert_metric '[.[]|select(.name=="showback_report_model_allocated_cents" and .labels.consumer=="engineering")|.value]==[32]' 'Closed-window cost policy'
assert_metric '[.[]|select(.name=="showback_report_team_model_tokens")|.value]|add==600200' 'Token rollup'
assert_metric 'all(.[]|select(.name=="showback_model_effective_worker_usd_per_hour");(.value-3.36312|fabs)<0.000001)' 'Unrounded worker rate'
assert_metric '[.[]|select(.name=="showback_model_tokens" and .labels.phase=="idle")|.value]==[0,0]' 'Covered idle zero'
assert_metric 'all(.[]|select(.name=="showback_model_effective_usd_per_million_tokens");.labels.phase!="idle")' 'Idle efficiency undefined'
assert_metric '[.[]|select(.name=="showback_config_model_access")|.value]|length==6 and add==4' 'Access matrix'
yaml_json < "$WORK/selected.yaml" | jq -jr '.[0].data["metrics.prom"]' > "$WORK/selected.prom"
cmp "$WORK/metrics.prom" "$WORK/selected.prom" || fail 'ConfigMap snapshot differs'
yaml_json < "$WORK/selected.yaml" | jq -e '.[0].metadata.labels |
  .["app.kubernetes.io/part-of"]=="observability" and .["app.kubernetes.io/name"]=="showback-report-publisher"
  and .["app.kubernetes.io/component"]=="observability" and .["app.kubernetes.io/managed-by"]=="argocd"' \
  >/dev/null || fail 'Generated ConfigMap labels'

jq '.rates[].usd_per_hour=null' "$BASE/fixtures/accounting.json" > "$WORK/unpriced-input.json"
bash "$BASE/allocate.sh" --input "$WORK/unpriced-input.json" --output "$WORK/unpriced.json"
render "$WORK/unpriced.json"
assert_metric 'all(.[];.name!="showback_report_cost_cents" and .name!="showback_model_cost_cents"
  and .name!="showback_model_effective_usd_per_million_tokens" and .name!="showback_report_rate_usd_per_hour")' 'Missing price withheld'
assert_metric '[.[]|select(.name=="showback_report_pricing_complete")|.value]==[0]' 'Missing-price flag'

jq '.windows[0].usage["qwen3-8-27b"].coverage="missing_usage"' "$BASE/fixtures/accounting.json" > "$WORK/missing-input.json"
bash "$BASE/allocate.sh" --input "$WORK/missing-input.json" --output "$WORK/missing.json"
render "$WORK/missing.json"
assert_metric 'all(.[]|select(.name=="showback_report_team_model_tokens");.labels.model!="qwen3-8-27b")' 'Unknown full usage withheld'
assert_metric 'any(.[];.name=="showback_model_allocated_cents" and .labels.model=="qwen3-8-27b"
  and .labels.phase=="busy" and .labels.consumer=="unresolved_allocation" and .value>0)' 'Missing usage unresolved'

jq '.price_basis="historical-basis" | .excluded_costs=["historical-exclusion"]
  | .rates[].source="historical-source"' "$WORK/report.json" > "$WORK/provenance.json"
render "$WORK/provenance.json"
assert_metric 'any(.[];.name=="showback_report_price_basis_info" and .labels.price_basis=="historical-basis")' 'Historical basis'
assert_metric 'any(.[];.name=="showback_report_exclusion_info" and .labels.excluded_cost=="historical-exclusion")' 'Historical exclusions'
assert_metric 'any(.[];.name=="showback_report_rate_info" and .labels.rate_source=="historical-source")' 'Historical source'

jq '.teams.engineering.subscription="current-budget-only"' "$BASE/scenario.json" > "$WORK/current-scenario.json"
render "$WORK/report.json" --scenario "$WORK/current-scenario.json"
assert_metric 'any(.[];.name=="showback_subscription_tokens" and .labels.subscription=="team-engineering"
  and .labels.team=="engineering")' 'Historical subscription mapping preserved'
assert_metric 'any(.[];.name=="showback_config_allowance_tokens" and .labels.subscription=="current-budget-only")
  and all(.[]|select(.name=="showback_config_allowance_tokens");.labels.report_id==null)' 'Current allowances separate'

jq '.windows[0].models[0].request_counts={"team-support":3}
  | .windows[0].models[0].quota_rejections={"team-support":1}' "$WORK/report.json" > "$WORK/receipts.json"
render "$WORK/receipts.json"
assert_metric '[.[]|select(.name=="showback_receipt_requests")|.value]==[3]' 'Receipt requests'
assert_metric '[.[]|select(.name=="showback_receipt_quota_rejections")|.value]==[1]' 'Receipt quota rejection'

render "$WORK/report.json"
cp "$WORK/metrics.prom" "$WORK/previous.prom"
jq '.report_id="broken-new-report"|.known_total_cents+=1' "$WORK/report.json" > "$WORK/bad.json"
reject bash "$BASE/publish-report.sh" --report "$WORK/bad.json" --output "$WORK/metrics.prom"
cmp "$WORK/previous.prom" "$WORK/metrics.prom" || fail 'Invalid selection replaced previous metrics'
for mutation in '.windows[1].start=.windows[0].start' '.windows[1].models=[]' \
    '.windows[0].models[0].total_tokens+=1' '.windows[0].models[0].coverage="partial_period"' \
    '.windows[0].id=null' '.subscription_teams["team-engineering"]=42'; do
    jq "$mutation" "$WORK/report.json" > "$WORK/invalid-window.json"
    reject bash "$BASE/publish-report.sh" --report "$WORK/invalid-window.json" --output "$WORK/metrics.prom"
    cmp "$WORK/previous.prom" "$WORK/metrics.prom" || fail 'Invalid accounting changed published metrics'
done
jq '.report_id="valid-new-report"' "$WORK/report.json" > "$WORK/new.json"
render "$WORK/new.json"
assert_metric 'all(.[]|select(.labels.report_id!=null);.labels.report_id=="valid-new-report")' 'Atomic report identity'
printf '{}\n' > "$WORK/empty.json"
reject bash "$BASE/publish-report.sh" --report "$WORK/empty.json" --output "$WORK/empty.prom"
[[ ! -e "$WORK/empty.prom" ]] || fail 'Empty selection published metrics'
cat "$WORK/report.json" "$WORK/report.json" > "$WORK/multiple.json"
reject bash "$BASE/publish-report.sh" --report "$WORK/multiple.json" --output "$WORK/multiple.prom"
cat "$BASE/scenario.json" "$BASE/scenario.json" > "$WORK/multiple-scenarios.json"
reject bash "$BASE/publish-report.sh" --report "$WORK/report.json" --scenario "$WORK/multiple-scenarios.json" \
  --output "$WORK/multiple.prom"
[[ ! -e "$WORK/multiple.prom" ]] || fail 'Multiple JSON inputs published a snapshot'
mkdir "$WORK/output-directory"
reject bash "$BASE/publish-report.sh" --report "$WORK/report.json" --output "$WORK/output-directory"
reject bash "$BASE/publish-report.sh" --report "$WORK/report.json" --output "$WORK/new.prom" \
  --configmap-output "$WORK/output-directory"
[[ ! -e "$WORK/new.prom" ]] || fail 'Invalid ConfigMap output changed metric selection'

cp "$BASE/scenario.json" "$WORK/scenario.json"
for input in "$WORK/report.json" "$WORK/scenario.json"; do
    before=$(shasum -a 256 "$input")
    ln -s "$input" "$input.alias"
    for output in "$input" "$input.alias"; do
        reject bash "$BASE/publish-report.sh" --report "$WORK/report.json" --scenario "$WORK/scenario.json" --output "$output"
        [[ $(shasum -a 256 "$input") == "$before" ]] || fail 'Input overwritten'
        [[ -L "$input.alias" ]] || fail 'Input alias overwritten'
    done
done
reject bash "$BASE/publish-report.sh" --report "$WORK/report.json" --output "$WORK/metrics.prom" --serve

bash "$BASE/generate-dashboards.sh" --check
jq -e 'all(.[].panels[]; all(.queries[];
  if (.query|contains("showback_")) then (.query|contains("@ end()"))
    and (.query|contains("up{showback_publisher="))
    and (.query|test("(sum_over_time|increase|rate|delta)\\(")|not)
  else true end))
  and all(.[].panels[]|select(.kind=="StatChart" or .kind=="BarChart");.options.calculation=="last")' \
  "$BASE/dashboard-definitions.json" >/dev/null || fail 'Snapshot query contract'
jq -e 'all(.[];
    .panels.reportIdentity.kind=="Table"
    and ([.panels.reportIdentity.options.columnSettings[].name]|sort)==["evidence_kind","period_end","period_start"]
    and ([.panels.reportAudit.options.columnSettings[].name]|sort)==["policy_version","report_id","report_sha256","scope"]
    and .layouts[0].spec.display.collapse.open)
  and all(.[].layouts[].spec.items[];.x==0 and .width==24)
  and all(.[].layouts[].spec.items; reduce .[] as $item ({end:0,valid:true};
    .valid=(.valid and $item.y>=.end) | .end=($item.y+$item.height))|.valid)
  and all(.[].panels[]|select(.kind=="Table");
    .options.defaultColumnHidden and .options.pagination==false
    and ([.options.columnSettings[].width]|add)<=560
    and all(.options.columnSettings[]|select(.format!=null);.format.shortValues==false))
  and all(.[].panels[]|select(.kind=="StatChart");.options.legendMode=="off" and .options.format.shortValues==false)
  and all(.[].panels[]|select(.kind=="Table")|.options.columnSettings[]|select(.format!=null);
    any(.cellSettings[];.condition.kind=="Misc" and .condition.spec.value=="null" and .text=="Unknown"))
  and .[0].panels.costComparison.kind=="BarChart"
  and .[0].panels.costComparison.options.format.shortValues==false
  and ([.[0].panels.consumers.options.columnSettings[0].cellSettings[].text]|unique|sort)
    ==["Engineering","Marketing","Other consumers","Platform idle","Support","Unresolved"]
  and .[1].panels.teamModelTokens.options.columnSettings[2].format
    =={unit:"decimal",decimalPlaces:0,shortValues:false}' \
  "$BASE/dashboard-definitions.json" >/dev/null || fail 'Readable closed-report presentation contract'
kustomize build "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo" | yaml_json > "$WORK/bundle.json"
jq -e 'all(.[]|select(.kind=="PersesDashboard" and (.metadata.name|test("^dashboard-[789]-showback-")))
  | .spec.config.panels[].spec|select(.plugin.kind=="Table");
    .plugin.spec.defaultColumnHidden and ([.plugin.spec.columnSettings[].width]|add)<=560)' \
  "$WORK/bundle.json" >/dev/null || fail 'Rendered compact-table contract'
jq -e '([.[]|select(.kind=="Deployment" and .metadata.name=="showback-report-publisher")][0].spec.replicas) as $replicas |
  [.[]|select(.kind=="ConfigMap" and .metadata.name=="showback-selected-report")][0] as $report |
  ($replicas|IN(0,1))
  and all(.[];.kind!="LLMInferenceService" and .kind!="MachineSet")
  and any(.[];.kind=="Deployment" and .metadata.name=="showback-report-publisher"
    and .spec.template.spec.containers[0].command==["/usr/bin/run-httpd"]
    and .spec.template.spec.containers[0].args==["-f","/etc/showback/httpd.conf"])
  and (if $replicas==0 then $report.data=={} else ($report.data|keys)==["metrics.prom"]
    and ($report.data["metrics.prom"]|test("(?m)^showback_selected_report_info\\{[^\\n]*evidence_kind=\"observed\"")) end)
  and any(.[];.kind=="ServiceMonitor" and .spec.endpoints[0].path=="/metrics.prom")
  and any(.[];.kind=="ConfigMap" and .metadata.name=="showback-report-httpd"
    and (.data["httpd.conf"]|startswith("Include /etc/httpd/conf/httpd.conf\n"))
    and (.data["httpd.conf"]|contains("ForceType text/plain")))' "$WORK/bundle.json" >/dev/null || fail 'Selected-report static-server contract'
echo 'PASS publisher/dashboard shell contracts (parity, provenance, unknown/idle, aliases, snapshot, static server)'
