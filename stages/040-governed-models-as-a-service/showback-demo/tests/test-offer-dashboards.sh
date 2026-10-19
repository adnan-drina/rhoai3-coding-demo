#!/usr/bin/env bash
# Offline offer-view and bounded-receipt checks. Synthetic test inputs only; no network or inference.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-offer-dashboards.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BASE/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
passed=0
pass() { passed=$((passed + 1)); printf 'PASS %s\n' "$1"; }
fail() { log_error "$*"; exit 1; }
parse() {
    jq -Rn '[inputs|select(startswith("#")|not)
      | capture("^(?<name>[A-Za-z_][A-Za-z0-9_:]*)\\{(?<labels>.*)\\} (?<value>[^ ]+)$")
      | .value |= tonumber
      | .labels |= ([scan("([A-Za-z_][A-Za-z0-9_]*)=(\"(?:[^\"\\\\]|\\\\.)*\")")
          | {key:.[0],value:(.[1]|fromjson)}]|from_entries)]' < "$1" > "$2"
}
render_probe() {
    bash "$BASE/render-external-probe.sh" --probe "$1" --output "$2"
    parse "$2" "$WORK/metrics.json"
}
assert_metrics() { jq -e "$1" "$WORK/metrics.json" >/dev/null || fail "$2"; }
reject_probe() {
    local mutation=$1 description=$2
    jq "$mutation" "$WORK/probe.json" > "$WORK/rejected.json"
    rm -f "$WORK/rejected.prom"
    if bash "$BASE/render-external-probe.sh" --probe "$WORK/rejected.json" \
        --output "$WORK/rejected.prom" > "$WORK/rejection.log" 2>&1; then
        fail "$description was accepted"
    fi
    [[ ! -e "$WORK/rejected.prom" ]] || fail 'Rejected input left a publishable output'
    pass "$description"
}

# These simulated observed-schema inputs exercise the renderer only; they are never published or live evidence.
jq -n '{schema_version:1,evidence_kind:"observed",scope:"bounded_api_probe",probe_id:"fixture-probe",
  period_start:"2026-01-01T12:00:01Z",period_end:"2026-01-01T12:00:03Z",
  inventory:[
    {model:"fixture-probed",provider:"fixture-provider",upstream_model:"fixture/upstream",
      inventory_at:"2026-01-01T12:00:00Z",evidence_kind:"observed"},
    {model:"fixture-unprobed",provider:"fixture-provider",upstream_model:"fixture/unprobed",
      inventory_at:"2026-01-01T12:00:00Z",evidence_kind:"observed"}],
  receipts:[
    {sequence:1,client_request_id:"fixture-request-1",provider_request_id:"fixture-provider-1",model:"fixture-probed",provider:"fixture-provider",
      user:"demo-observer",subscription:"fixture-subscription",started_at:"2026-01-01T12:00:01Z",
      ended_at:"2026-01-01T12:00:02Z",http_status:"200",transport_status:0,
      usage:{input_tokens:7,output_tokens:3,total_tokens:10}},
    {sequence:2,client_request_id:"fixture-request-2",provider_request_id:"fixture-provider-2",model:"fixture-probed",provider:"fixture-provider",
      user:"demo-observer",subscription:"fixture-subscription",started_at:"2026-01-01T12:00:02Z",
      ended_at:"2026-01-01T12:00:03Z",http_status:"200",transport_status:0,
      usage:{input_tokens:5,output_tokens:0,total_tokens:5}}]}' > "$WORK/probe.json"
render_probe "$WORK/probe.json" "$WORK/valid.prom"
hash=$(shasum -a 256 "$WORK/probe.json" | awk '{print $1}')
jq -e --arg hash "$hash" '
  ([.[]|select(.name=="showback_external_model_info")]|length)==2
  and ([.[]|select(.name=="showback_external_probe_info")]|length)==1
  and all(.[]|select(.name!="showback_external_model_info");
    .labels.probe_id=="fixture-probe" and .labels.probe_sha256==$hash
    and .labels.evidence_kind=="observed" and .labels.scope=="bounded_api_probe")
  and ([.[]|select(.name=="showback_external_probe_requests")|.value]==[2])
  and ([.[]|select(.name=="showback_external_probe_input_tokens")|.value]==[12])
  and ([.[]|select(.name=="showback_external_probe_output_tokens")|.value]==[3])
  and ([.[]|select(.name=="showback_external_probe_usage_complete")|.value]==[1])
  and all(.[]|select(.name!="showback_external_model_info");.labels.model!="fixture-unprobed")
  and all(.[];.name|test("(cost|charge|price|invoice|service_report)")|not)' \
  "$WORK/metrics.json" >/dev/null || fail 'Bounded receipt/inventory identity or absent-money contract'
pass 'All configured models retained; only observed receipt groups have requests and exact tokens'

jq '.receipts[].usage={input_tokens:0,output_tokens:0,total_tokens:0}' "$WORK/probe.json" > "$WORK/zero.json"
render_probe "$WORK/zero.json" "$WORK/zero.prom"
assert_metrics '[.[]|select(.name=="showback_external_probe_input_tokens"
  or .name=="showback_external_probe_output_tokens")|.value]==[0,0]' 'Reported zero usage disappeared'
pass 'Explicitly reported zero remains zero rather than missing'

jq '.receipts[1].usage=null|.receipts[1].http_status="503"' "$WORK/probe.json" > "$WORK/missing.json"
render_probe "$WORK/missing.json" "$WORK/missing.prom"
assert_metrics 'all(.[];.name!="showback_external_probe_input_tokens" and .name!="showback_external_probe_output_tokens")
  and ([.[]|select(.name=="showback_external_probe_requests")|.value]==[2])
  and ([.[]|select(.name=="showback_external_probe_usage_complete")|.value]==[0])
  and ([.[]|select(.name=="showback_external_probe_request_status")|.value]|add)==2' 'Partial usage became complete tokens'
pass 'Failed receipt retains request/status counts and withholds incomplete token aggregates'

jq '.receipts[]|=. + {usage:null,http_status:"000",transport_status:28}' "$WORK/probe.json" > "$WORK/failed.json"
render_probe "$WORK/failed.json" "$WORK/failed.prom"
assert_metrics 'all(.[];.name!="showback_external_probe_input_tokens" and .name!="showback_external_probe_output_tokens")
  and ([.[]|select(.name=="showback_external_probe_requests")|.value]==[2])' 'Transport failures became zero token usage'
pass 'Unavailable transport evidence cannot create zero-priced or zero-token success'

jq '.inventory[0].private_test_marker="not-a-metric-label"' "$WORK/probe.json" > "$WORK/extra.json"
render_probe "$WORK/extra.json" "$WORK/extra.prom"
assert_metrics 'all(.[];.labels|has("private_test_marker")|not)' 'Unapproved inventory fields leaked into metrics'
pass 'Inventory renderer emits only approved label fields'

reject_probe '.evidence_kind="synthetic_fixture"' 'Non-observed publication input rejected'
reject_probe '.period_start="not-a-date"' 'Invalid UTC period rejected'
reject_probe '.period_end="2026-01-01T11:59:59Z"' 'Reversed report period rejected'
reject_probe '.receipts[0].started_at="2026-01-01T11:59:59Z"' 'Receipt outside report period rejected'
reject_probe '.inventory += [.inventory[0]]' 'Duplicate configured model/provider rejected'
reject_probe '.receipts[1]=.receipts[0]' 'Duplicate request sequence rejected'
reject_probe '.receipts[1].client_request_id=.receipts[0].client_request_id' 'Duplicate client request identity rejected'
reject_probe '.receipts[1].provider_request_id=.receipts[0].provider_request_id' 'Duplicate provider receipt identity rejected'
reject_probe '.receipts[0].model="not-configured"' 'Receipt outside configured inventory rejected'
reject_probe '.receipts[0].usage.total_tokens+=1' 'Inconsistent provider usage rejected'
reject_probe '.receipts[0].http_status="503"' 'Fabricated failed-request usage rejected'
before=$(shasum -a 256 "$WORK/valid.prom")
if bash "$BASE/render-external-probe.sh" --probe "$WORK/probe.json" --output "$WORK/valid.prom" \
    > "$WORK/rejection.log" 2>&1; then fail 'Existing output was replaced'; fi
[[ $(shasum -a 256 "$WORK/valid.prom") == "$before" ]] || fail 'Rejected replay changed existing evidence'
pass 'Replay refuses to overwrite a selected output'

publisher="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo/publisher-report.yaml"
bash "$BASE/render-external-probe.sh" --probe "$WORK/probe.json" --publisher "$publisher" --output "$WORK/composed.yaml"
bash "$BASE/render-external-probe.sh" --probe "$WORK/probe.json" --publisher "$WORK/composed.yaml" \
    --output "$WORK/replayed.yaml"
cmp -s "$WORK/composed.yaml" "$WORK/replayed.yaml" || fail 'Probe composition replay changed its selected output'
yaml_json < "$publisher" > "$WORK/original-publisher.json"
yaml_json < "$WORK/composed.yaml" > "$WORK/composed-publisher.json"
jq -e --slurpfile original "$WORK/original-publisher.json" '
  def bounded:split("\n")|map(select(test("^(showback_external_|# showback_external_:)")|not))|join("\n");
  .[0].metadata==$original[0][0].metadata and (.[0].data|keys)==["metrics.prom"]
  and (.[0].data["metrics.prom"]|bounded)==($original[0][0].data["metrics.prom"]|bounded)' \
  "$WORK/composed-publisher.json" >/dev/null || fail 'Additive probe composition changed bounded report bytes or metadata'
pass 'Additive composition preserves bounded report bytes/metadata and is deterministic on replay'

DEFINITIONS="$BASE/offer-dashboard-definitions.json"
bash "$BASE/generate-dashboards.sh" --check
jq -e 'length==3 and ([.[].name]|sort)==[
    "dashboard-offer-dedicated-private-admin","dashboard-offer-external-model-admin","dashboard-offer-shared-private-admin"]
  and all(.[].layouts[].spec.items[];.x==0 and .width==24)
  and all(.[];.panels as $panels|all(.layouts[].spec.items[];
    (.content["$ref"]|split("/")|last) as $key|if $panels[$key].kind=="Table" then .height>=5 else true end))
  and all(.[].layouts[].spec.items;reduce .[] as $item ({end:0,valid:true};
    .valid=(.valid and $item.y>=.end)|.end=($item.y+$item.height))|.valid)
  and all(.[].panels[]|select(.kind=="Table");
    .options.defaultColumnHidden and .options.pagination==false
    and ([.options.columnSettings[].width]|add)<=555
    and all(.options.columnSettings[]|select(.format!=null);.format.shortValues==false)
    and all(.options.columnSettings[];
      .format==null or any(.cellSettings[];.condition.kind=="Misc" and .condition.spec.value=="null" and .text=="Unknown")))
  and all(.[].panels[].queries[];.query|test("vector\\(0\\)")|not)' \
  "$DEFINITIONS" >/dev/null || fail 'Offer layout or explicit unknown-state contract'
pass 'Three offer views render compact full-width tables with explicit unknown values'

jq -e 'all(.[];
    (if (.name|contains("external")) then "external" elif (.name|contains("dedicated")) then "dedicated" else "shared" end) as $offer
    | all(.panels[].queries[]|select(.query|contains("service_"));
      (.query|contains("service_report_info{evidence_kind=\"observed\"}"))
      and (.query|contains("offer=\""+$offer+"\",evidence_kind=\"observed\""))
      and (.query|contains("on(report_id, report_sha256, job, instance)"))
      and (.query|contains("up{showback_publisher=\"selected-report\"}"))
      and (.query|contains("@ end()"))
      and (.query|test("(sum_over_time|increase|rate|delta)\\(")|not)))
  and all(.[].panels[]|select(any(.queries[];.query|contains("service_")));
    .kind!="Table" or
    (if (.queries|length)>1 then
      (.queries|length) as $fallback|
      (.queries[-1].query|contains("absent("))
      and (.queries[-1].query|contains("\"evidence_kind\", \"unavailable\""))
      and (.queries[-1].query|contains("Publisher unavailable"))
      and all(.options.columnSettings[];.name!=("value #"+($fallback|tostring)) or .hide==true)
    else all(.options.columnSettings[];.name!="value") end))' \
  "$DEFINITIONS" >/dev/null || fail 'Offer-scoped immutable monthly selection or hidden fallback value'
pass 'Monthly money requires observed offer/report identity; fallback metadata never becomes a monetary value'

jq -e '.[]|select(.name=="dashboard-offer-external-model-admin")|
  .panels.modelUsage as $models|
  ($models.queries[0].query|contains("showback_external_model_info{evidence_kind=\"observed\"}"))
  and ($models.queries[0].query|contains("model=\"")|not)
  and all($models.queries[1:4][];
    (.query|contains("on(probe_id, probe_sha256, job, instance)"))
    and (.query|contains("showback_external_probe_info{"))
    and (.query|contains("scope=\"bounded_api_probe\"")))
  and any($models.options.transforms[];.kind=="JoinByColumnValue" and .spec.columns==["model","provider"])
  and all($models.options.columnSettings[];.name!="value #1" and .name!="value #5")
  and all(.panels.consumerUsage.queries[0:3][];
    (.query|contains("on(probe_id, probe_sha256, job, instance)")))' \
  "$DEFINITIONS" >/dev/null || fail 'External inventory/probe identity contract'
pass 'All configured external models remain visible while selected bounded receipts retain their own identity'

jq -e '(.[]|select(.name=="dashboard-offer-dedicated-private-admin")) as $dedicated|
  (.[]|select(.name=="dashboard-offer-shared-private-admin")) as $shared|
  all($dedicated.panels[].queries[];.query|contains("showback_report_")|not)
  and ($dedicated.panels.economics.queries[0].query|contains("service_agreement_cost_cents{offer=\"dedicated\""))
  and ($dedicated.panels.economics.queries[1].query|contains("service_agreement_charge_cents{offer=\"dedicated\""))
  and all($shared.panels|to_entries[]|select(.key|IN("reportIdentity","allocation","usage","capacity"))|.value.queries[];
    (.query|contains("showback_selected_report_info{evidence_kind=\"observed\"}"))
    and (.query|contains("service_")|not))
  and all($shared.panels.recovery.queries[];.query|contains("showback_report_")|not)' \
  "$DEFINITIONS" >/dev/null || fail 'Dedicated/full-cost or shared bounded/monthly separation'
pass 'Dedicated sponsor economics never borrow Qwen allocations; shared bounded costs stay separate from monthly recovery'

kustomize build "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo" | yaml_json > "$WORK/bundle.json"
jq -e --slurpfile definitions "$DEFINITIONS" '
  [.[]|select(.kind=="PersesDashboard" and (.metadata.name|startswith("dashboard-offer-")))] as $views|
  ($views|length)==3 and ([.[]|select(.kind=="PersesDashboard")]|length)==11
  and all($definitions[0][];. as $expected|
    any($views[];.metadata.name==$expected.name
      and .metadata.namespace=="redhat-ods-monitoring"
      and .spec.config.layouts==$expected.layouts
      and (.spec.config.panels|keys)==($expected.panels|keys)))' \
  "$WORK/bundle.json" >/dev/null || fail 'Offer resources missing from the canonical component'
pass 'Canonical component includes the three new views alongside the existing eight dashboards'

# Existing service-report fixtures qualify only the offline producer/query contract, never current financial data.
bash "$BASE/offers/service-report.sh" --input "$BASE/offers/fixtures/month.json" --output "$WORK/month.json"
bash "$BASE/service-views/render-report.sh" --report "$WORK/month.json" --output "$WORK/month.prom"
parse "$WORK/month.prom" "$WORK/month-metrics.json"
jq -e --slurpfile definitions "$DEFINITIONS" '
  [.[]|.name]|unique as $produced|
  all([$definitions[0][].panels[].queries[].query|scan("service_[A-Za-z0-9_]+")]|unique[];
    . as $name|$produced|index($name)!=null)' \
  "$WORK/month-metrics.json" >/dev/null || fail 'Dashboard references a monthly metric not emitted by the producer'
jq -e 'any(.agreements[];.offer=="dedicated" and .owner_team=="marketing"
  and .usage.requests==0 and .cost_cents>0 and .charge_cents==100000)' \
  "$WORK/month.json" >/dev/null || fail 'Dedicated idle availability lost its sponsor/full-cost evidence'
pass 'Future monthly metrics exist in the real producer schema; dedicated zero use retains full sponsor availability cost'

jq '(.agreements[]|select(.offer=="external")|.rate_cards[].prices.input_uncached)=null' \
  "$BASE/offers/fixtures/month.json" > "$WORK/unpriced-month-input.json"
bash "$BASE/offers/service-report.sh" --input "$WORK/unpriced-month-input.json" --output "$WORK/unpriced-month.json"
bash "$BASE/service-views/render-report.sh" --report "$WORK/unpriced-month.json" --output "$WORK/unpriced-month.prom"
parse "$WORK/unpriced-month.prom" "$WORK/unpriced-month-metrics.json"
jq -e 'all(.[]|select(.labels.offer=="external");
    .name!="service_agreement_charge_cents" and .name!="service_consumer_charge_cents")
  and any(.[];.name=="service_agreement_pricing_complete" and .labels.offer=="external" and .value==0)' \
  "$WORK/unpriced-month-metrics.json" >/dev/null || fail 'Unverified external rates became a full charge or a zero bill'
pass 'Missing monthly rates withhold full external charges while explicitly retaining incomplete pricing'

printf 'PASS %s offline offer-dashboard and bounded-receipt checks; no network, deployment or inference\n' "$passed"
