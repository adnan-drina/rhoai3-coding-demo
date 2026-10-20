#!/usr/bin/env bash
# Generate the two custom PersesDashboards (Cost per token, Tokenomics break-even) for the OpenShift AI Observability
# page. Structure mirrors the product Usage dashboard (spec.config: display, duration, variables, panels, layouts).
# Offline, no cluster access. Default: print both files. --check: read-only, fails when a committed file differs from
# what this script generates. --write: replaces dashboard-5-cost-per-token.yaml and dashboard-6-tokenomics-break-even.yaml
# under gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/ (review and commit them); safe
# to rerun. Cost per token prices are dashboard text variables; Tokenomics reads worker prices from the showback offer
# catalog and reference prices from the external-metering price catalog.
# Usage: stages/040-governed-models-as-a-service/showback/generate-dashboards.sh [--write|--check]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
MODE=print
while [[ $# -gt 0 ]]; do
    case "$1" in
        --write) MODE=write; shift ;;
        --check) MODE=check; shift ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
for cmd in jq ruby; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done
OUTPUT_DIR="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability"

# ── Dashboard model (jq) ─────────────────────────────────────────────────────────
# One object: file name -> PersesDashboard. Key order is the emitted key order.
DASHBOARDS='
def DS: {kind: "PrometheusDatasource", name: "data-science-prometheus-datasource"};
def CDS: {kind: "PrometheusDatasource", name: "cluster-prometheus-datasource"};
def q(expr; ds; name):
    {kind: "TimeSeriesQuery", spec: {plugin: {kind: "PrometheusTimeSeriesQuery",
        spec: ({datasource: ds, query: expr} + (if name then {seriesNameFormat: name} else {} end))}}};
def stat(name; desc; expr; unit; decimals):
    {kind: "Panel", spec: {display: {name: name, description: desc},
        plugin: {kind: "StatChart", spec: {calculation: "last",
            format: ({unit: unit} + (if unit == "decimal" then {decimalPlaces: decimals} else {} end))}},
        queries: [q(expr; DS; null)]}};
# queries: [[expr, seriesNameFormat], ...]
def ts(name; desc; queries; unit; ds):
    {kind: "Panel", spec: {display: {name: name, description: desc},
        plugin: {kind: "TimeSeriesChart", spec: {legend: {mode: "list", position: "bottom", values: []},
            visual: {areaOpacity: 0.1, connectNulls: false, display: "line", lineWidth: 1.5},
            yAxis: {format: {unit: unit}, min: 0}}},
        queries: [queries[] | q(.[0]; ds; .[1])]}};
def table(name; desc; columns; queries):
    {kind: "Panel", spec: {display: {name: name, description: desc},
        plugin: {kind: "Table", spec: {columnSettings: ([{hide: true, name: "timestamp"}] + columns), density: "compact",
            pagination: true, transforms: [{kind: "MergeSeries", spec: {}}]}},
        queries: [queries[] | q(.; DS; null)]}};
def gauge(name; desc; expr):
    {kind: "Panel", spec: {display: {name: name, description: desc},
        plugin: {kind: "GaugeChart", spec: {calculation: "last", format: {unit: "percent", decimalPlaces: 0}, max: 200,
            thresholds: {steps: [{value: 0, color: "#c9190b"}, {value: 100, color: "#3e8635"}]}}},
        queries: [q(expr; DS; null)]}};
def listvar(name; label_name; matcher; display):
    {kind: "ListVariable", spec: {name: name, allowAllValue: true, allowMultiple: true, customAllValue: ".*",
        defaultValue: "$__all", display: {name: display, hidden: false},
        plugin: {kind: "PrometheusLabelValuesVariable", spec: {datasource: DS, labelName: label_name, matchers: [matcher]}}}};
def textvar(name; value; display; desc):
    {kind: "TextVariable", spec: {name: name, value: value, constant: false,
        display: {name: display, description: desc, hidden: false}}};
# items: [[panel, x, y, width, height], ...]
def grid(title; items):
    {kind: "Grid", spec: {display: {title: title, collapse: {open: true}},
        items: [items[] | {x: .[1], y: .[2], width: .[3], height: .[4], content: {"$ref": ("#/spec/panels/" + .[0])}}]}};
def dashboard(name; display; desc; variables; panels; layouts):
    {apiVersion: "perses.dev/v1alpha2", kind: "PersesDashboard",
     metadata: {name: name, namespace: "redhat-ods-monitoring",
        labels: {"app.kubernetes.io/name": name, "app.kubernetes.io/part-of": "rhoai3-coding-demo",
            "app.kubernetes.io/component": "observability", "app.kubernetes.io/managed-by": "argocd"}},
     spec: {config: {display: {name: display, description: desc}, duration: "168h", variables: variables, panels: panels,
        layouts: layouts}}};
def column(header; name; fmt): {align: "right", enableSorting: true, format: fmt, header: header, name: name};
def short0: {decimalPlaces: 0, shortValues: true, unit: "decimal"};

# ── Cost per token ──
"model_name=~\"$model\"" as $M
| "sum by (model_name) (increase(kserve_vllm:prompt_tokens_total{\($M)}[$__range]))" as $tok_prompt
| "sum by (model_name) (increase(kserve_vllm:generation_tokens_total{\($M)}[$__range]))" as $tok_gen
| "(\($tok_prompt) / 1e6 * $price_prompt) + (\($tok_gen) / 1e6 * $price_completion)" as $cost_by_model
| "user!=\"\", user=~\"$user\", subscription=~\"$subscription\"" as $U
| "sum by (user, subscription, model) (increase(authorized_hits_total{\($U), model=~\"$model\"}[$__range]))" as $hits_user
| "sum by (user, subscription, model) (increase(authorized_calls_total{\($U)}[$__range]))" as $calls_user
| [listvar("model"; "model_name"; "kserve_vllm:prompt_tokens_total"; "Model"),
   listvar("user"; "user"; "authorized_hits_total{user!=\"\"}"; "User"),
   listvar("subscription"; "subscription"; "authorized_hits_total{subscription!=\"\"}"; "Subscription"),
   textvar("price_prompt"; "0.10"; "Price $/1M prompt tokens";
       "Showback price for prompt (input) tokens, USD per million; edit per model or contract."),
   textvar("price_completion"; "0.40"; "Price $/1M completion tokens"; "Showback price for generated (output) tokens, USD per million."),
   textvar("price_blended"; "0.25"; "Blended $/1M tokens (per user)";
       "MaaS counts total tokens per user and subscription without an input/output split; this blended price values them.")] as $cost_vars
| {totalCost: stat("Total cost";
       "Prompt and completion tokens served by the private models over the Range window, priced with the dashboard'"'"'s price variables.";
       "sum(\($cost_by_model))"; "decimal"; 2),
   totalTokens: stat("Total tokens"; "Prompt plus completion tokens over the Range window.";
       "sum(\($tok_prompt)) + sum(\($tok_gen))"; "decimal"; 0),
   blendedCost: stat("Observed $/1M tokens";
       "Total cost divided by total tokens: the blended price actually realised with the current input/output mix.";
       "sum(\($cost_by_model)) / clamp_min(sum(\($tok_prompt)) + sum(\($tok_gen)), 1) * 1e6"; "decimal"; 3),
   costPer1kRequests: stat("$ per 1K requests"; "Total cost divided by governed requests (MaaS authorized calls) over the Range window.";
       "sum(\($cost_by_model)) / clamp_min(sum(increase(authorized_calls_total{user!=\"\"}[$__range])), 1) * 1000"; "decimal"; 3),
   costOverTime: ts("Cost rate by model"; "Hourly spend by model at the dashboard prices.";
       [["(sum by (model_name) (rate(kserve_vllm:prompt_tokens_total{\($M)}[$__rate_interval])) * 3600 / 1e6 * $price_prompt) + (sum by (model_name) (rate(kserve_vllm:generation_tokens_total{\($M)}[$__rate_interval])) * 3600 / 1e6 * $price_completion)",
         "{{model_name}} $/h"]]; "decimal"; DS),
   tokensOverTime: ts("Token rate by model"; "Prompt and completion tokens per second by model.";
       [["sum by (model_name) (rate(kserve_vllm:prompt_tokens_total{\($M)}[$__rate_interval]))", "{{model_name}} prompt"],
        ["sum by (model_name) (rate(kserve_vllm:generation_tokens_total{\($M)}[$__rate_interval]))", "{{model_name}} completion"]];
       "decimal"; DS),
   costByModel: table("Cost by model"; "Tokens and cost per model over the Range window.";
       [{align: "left", enableSorting: true, header: "Model", name: "model_name"},
        column("Prompt tokens"; "value #1"; short0), column("Completion tokens"; "value #2"; short0),
        column("Cost ($)"; "value #3"; {decimalPlaces: 2, unit: "decimal"}) + {sort: "desc"}];
       [$tok_prompt, $tok_gen, $cost_by_model]),
   costByUser: table("Cost by user and subscription";
       "Governed MaaS tokens per user, subscription and model over the Range window, valued at the blended price.";
       [{align: "left", enableSorting: true, header: "User", name: "user"},
        {align: "left", enableSorting: true, header: "Subscription", name: "subscription"},
        {align: "left", enableSorting: true, header: "Model", name: "model"},
        column("Tokens"; "value #1"; short0), column("Requests"; "value #2"; {decimalPlaces: 0, unit: "decimal"}),
        column("Cost ($)"; "value #3"; {decimalPlaces: 2, unit: "decimal"}) + {sort: "desc"}];
       ["round(\($hits_user))", "round(\($calls_user))", "\($hits_user) / 1e6 * $price_blended"])} as $cost_panels
| [grid("Overview"; [["totalCost", 0, 0, 6, 5], ["totalTokens", 6, 0, 6, 5], ["blendedCost", 12, 0, 6, 5], ["costPer1kRequests", 18, 0, 6, 5]]),
   grid("Trends"; [["costOverTime", 0, 0, 12, 8], ["tokensOverTime", 12, 0, 12, 8]]),
   grid("Breakdown"; [["costByModel", 0, 0, 24, 8], ["costByUser", 0, 8, 24, 10]])] as $cost_layouts

# ── Tokenomics break-even ──
# Prices come from data, not variables: GPU worker $/hour per private model from the showback offer catalog
# (PrometheusRule showback-offer-catalog in the optional 040-showback-demo component) and the list
# prices from the external-metering price catalog. Catalog series are read @ end() so ranges before a rule existed work.
| "(showback_offer_info{model=~\"$model\"} @ end())" as $info
| "max by (model) (showback_offer_worker_usd_per_hour @ end())" as $worker
| "label_replace(count by (model_name) (kserve_vllm:num_requests_running), \"model\", \"$1\", \"model_name\", \"(.+)\")" as $running
| "sum((\($running)) * on(model) group_left \($worker) and on(model) \($info))" as $burn
| "label_replace(sum by (model_name) (rate(kserve_vllm:prompt_tokens_total[$__rate_interval]) + rate(kserve_vllm:generation_tokens_total[$__rate_interval])), \"model\", \"$1\", \"model_name\", \"(.+)\") and on(model) \($info)" as $tps_model
| "sum(\($tps_model))" as $tps
| "label_replace(sum_over_time(count by (model_name) (kserve_vllm:num_requests_running)[$__range:1m]), \"model\", \"$1\", \"model_name\", \"(.+)\") / 60" as $worker_hours
| "sum((\($worker_hours)) * on(model) group_left \($worker) and on(model) \($info))" as $spend
| "sum(label_replace(sum by (model_name) (increase(kserve_vllm:prompt_tokens_total[$__range])), \"model\", \"$1\", \"model_name\", \"(.+)\") and on(model) \($info))" as $ptok
| "sum(label_replace(sum by (model_name) (increase(kserve_vllm:generation_tokens_total[$__range])), \"model\", \"$1\", \"model_name\", \"(.+)\") and on(model) \($info))" as $gtok
| "min(showback_external_metering_rate_usd_per_million{model=\"$reference\", category=\"input_uncached\"})" as $ref_in
| "min(showback_external_metering_rate_usd_per_million{model=\"$reference\", category=\"output\"})" as $ref_out
| "((\($ref_in) + \($ref_out)) / 2)" as $ref_blended
| "(\($ptok)) / 1e6 * \($ref_in) + (\($gtok)) / 1e6 * \($ref_out)" as $api_spend_range
| "(\($burn)) / \($ref_blended) * 1e6 / 3600" as $break_even
| [listvar("model"; "model"; "showback_offer_info"; "Private model"),
   {kind: "ListVariable", spec: {name: "reference", allowAllValue: false, allowMultiple: false, defaultValue: "gpt-6-luna",
       display: {name: "Reference external model", hidden: false},
       plugin: {kind: "PrometheusLabelValuesVariable", spec: {datasource: DS, labelName: "model",
           matchers: ["showback_external_metering_rate_usd_per_million{category=\"output\"}"]}}}}] as $tok_vars
| {about: {kind: "Panel", spec: {display: {name: "How this is calculated", description: ""},
       plugin: {kind: "Markdown", spec: {text: ("**Private cost** counts only GPU workers that are serving: each running model costs its "
           + "worker price per hour from the offer catalog. Parked workers cost nothing.\n\n**Reference cost** prices the same "
           + "input and output tokens at the published list price of the selected external model.\n\n**Break-even throughput** is "
           + "the token rate at which the private workers cost the same as the reference model; above it, running privately "
           + "is cheaper.")}}, queries: []}},
   burn: stat("Infrastructure burn $/h"; "Worker price of every serving private model, from the offer catalog."; $burn; "decimal"; 2),
   throughput: stat("Live throughput (tokens/s)"; "Prompt plus completion tokens per second across the selected private models.";
       $tps; "decimal"; 0),
   effectiveLive: stat("Effective $/1M tokens (live)"; "Burn divided by live throughput; blank below 1 token per second.";
       "(\($burn)) / ((\($tps) > 1) * 3600 / 1e6)"; "decimal"; 2),
   effectiveRange: stat("Effective $/1M tokens (Range)"; "Worker spend over the Range window divided by tokens served in it.";
       "(\($spend)) / (((\($ptok)) + (\($gtok))) / 1e6)"; "decimal"; 2),
   breakEven: stat("Break-even throughput (tokens/s)"; "Token rate at which the serving workers cost the same as the reference model.";
       $break_even; "decimal"; 0),
   utilisation: gauge("Throughput vs break-even";
       "Live throughput as a percentage of the break-even throughput; above 100% running privately is cheaper than the reference model.";
       "(\($tps)) / (\($break_even)) * 100"),
   apiEquivalent: stat("Reference-model spend (Range)"; "What the tokens served in the Range window would cost at the list prices.";
       $api_spend_range; "decimal"; 2),
   infraSpend: stat("Infrastructure spend (Range)"; "Serving hours of each private model in the Range window times its worker price."; $spend; "decimal"; 2),
   savings: stat("Savings vs reference (Range)";
       "Reference-model spend minus infrastructure spend; negative means the workers are under-used for this price.";
       "(\($api_spend_range)) - (\($spend))"; "decimal"; 2),
   throughputTrend: ts("Throughput by model vs break-even"; "Tokens per second by private model against the break-even line.";
       [[$tps_model, "{{model}}"], [$break_even, "break-even"]]; "decimal"; DS),
   gpuUtil: ts("GPU utilisation"; "Accelerator utilisation from cluster monitoring (DCGM).";
       [["avg by (exported_pod) (accelerator_gpu_utilization)", "{{exported_pod}}"]]; "percent"; CDS)} as $tok_panels
| [grid("How this is calculated"; [["about", 0, 0, 24, 5]]) | .spec.display.collapse.open = false,
   grid("Live"; [["burn", 0, 0, 6, 5], ["throughput", 6, 0, 6, 5], ["effectiveLive", 12, 0, 6, 5], ["breakEven", 18, 0, 6, 5]]),
   grid("Break-even"; [["utilisation", 0, 0, 8, 8], ["throughputTrend", 8, 0, 16, 8]]),
   grid("Range economics"; [["effectiveRange", 0, 0, 6, 5], ["infraSpend", 6, 0, 6, 5], ["apiEquivalent", 12, 0, 6, 5],
       ["savings", 18, 0, 6, 5], ["gpuUtil", 0, 5, 24, 7]])] as $tok_layouts

| {"dashboard-5-cost-per-token.yaml": dashboard("dashboard-5-cost-per-token-admin"; "Cost per token";
       "Showback: tokens served by the private models and governed MaaS users, priced with editable per-million-token prices.";
       $cost_vars; $cost_panels; $cost_layouts),
   "dashboard-6-tokenomics-break-even.yaml": dashboard("dashboard-6-tokenomics-break-even-admin"; "Tokenomics · break-even (live)";
       "Self-hosting economics: infrastructure burn of the serving private models, effective cost per million tokens, and the throughput at which they beat a reference external model.";
       $tok_vars; $tok_panels; $tok_layouts),
   shared: DS}
'

# ── YAML emitter (Ruby, libyaml) ─────────────────────────────────────────────────
# The committed files carry PyYAML safe_dump formatting (width 200, block style, folded long plain scalars, the shared
# datasource as anchor &id001, non-ASCII escaped in double quotes). Ruby's YAML.dump chooses its own scalar styles, so
# this builds the libyaml node tree directly and lets libyaml (whose emitter PyYAML ports) pick each scalar's style.
# A string may be plain only when it would read back as a string. ARGV[0] is the value emitted once as &id001 and
# afterwards as *id001.
YAML_EMITTER='
shared = JSON.parse(ARGV[0])
scanner = Psych::ScalarScanner.new(Psych::ClassLoader.new)
anchored = false
string = lambda do |s|
  if s =~ /[^\x00-\x7F]/
    Psych::Nodes::Scalar.new(s, nil, nil, false, true, Psych::Nodes::Scalar::DOUBLE_QUOTED)
  else
    plain = [String, Symbol].include?(scanner.tokenize(s).class)
    Psych::Nodes::Scalar.new(s, nil, nil, plain, true, Psych::Nodes::Scalar::ANY)
  end
end
node = lambda do |v|
  case v
  when Hash
    anchor = nil
    if v == shared
      next Psych::Nodes::Alias.new("id001") if anchored
      anchored = true
      anchor = "id001"
    end
    m = Psych::Nodes::Mapping.new(anchor, nil, true, Psych::Nodes::Mapping::BLOCK)
    v.each { |k, x| m.children << string.(k) << node.(x) }
    m
  when Array
    s = Psych::Nodes::Sequence.new(nil, nil, true, Psych::Nodes::Sequence::BLOCK)
    v.each { |x| s.children << node.(x) }
    s
  when String then string.(v)
  when nil then Psych::Nodes::Scalar.new("null", nil, nil, true, false, Psych::Nodes::Scalar::ANY)
  else Psych::Nodes::Scalar.new(v.to_s, nil, nil, true, false, Psych::Nodes::Scalar::ANY)
  end
end
document = Psych::Nodes::Document.new([], [], true)
document.children << node.(JSON.parse(STDIN.read))
stream = Psych::Nodes::Stream.new
stream.children << document
print stream.yaml(nil, line_width: 200).gsub(/[^\x00-\x7F]/) { |c|
  c.ord <= 0xFF ? format("\\x%02X", c.ord) : c.ord <= 0xFFFF ? format("\\u%04X", c.ord) : format("\\U%08X", c.ord) }
'

HEADER="# Custom observability dashboard for the OpenShift AI Observability page (rendered as a tab because its name starts with
# dashboard-). Generated by stages/040-governed-models-as-a-service/showback/generate-dashboards.sh; edit the generator, not this file."

# ── Generate, then print, check or write ─────────────────────────────────────────
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
jq -n "$DASHBOARDS" >"$WORK/dashboards.json"
shared=$(jq -c '.shared' "$WORK/dashboards.json")
status=0
for file in dashboard-5-cost-per-token.yaml dashboard-6-tokenomics-break-even.yaml; do
    {
        printf '%s\n' "$HEADER"
        jq -c --arg f "$file" '.[$f]' "$WORK/dashboards.json" | ruby -ryaml -rjson -e "$YAML_EMITTER" "$shared"
    } >"$WORK/$file"
    case "$MODE" in
        print) cat "$WORK/$file" ;;
        write) cp "$WORK/$file" "$OUTPUT_DIR/$file"; echo "Wrote $OUTPUT_DIR/$file" ;;
        check)
            if cmp -s "$WORK/$file" "$OUTPUT_DIR/$file"; then
                echo "PASS $file matches the generator"
            else
                echo "FAIL $file differs from the generator (run --write and review the diff)"
                status=1
            fi ;;
    esac
done
exit "$status"
