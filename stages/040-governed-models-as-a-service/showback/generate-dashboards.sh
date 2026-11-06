#!/usr/bin/env bash
# Generate the custom Showback 5 · Break-even PersesDashboard for the OpenShift AI Observability page. Structure mirrors
# the product Usage dashboard (spec.config: display, duration, variables, panels, layouts). Offline, no cluster access.
# Default: print the file. --check: read-only, fails when the committed file differs from what this script generates.
# --write: replaces dashboard-6-tokenomics-break-even.yaml under
# gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/ (review and commit it); safe to rerun.
# Break-even reads worker prices from the showback offer catalog and reference prices from the external-metering price
# catalog; it shows euros through the catalog's rate.
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
# Colours follow the Red Hat brand colour standards information palette: danger-orange-50 #F0561D, yellow-30 #FFCC17,
# success-green-50 #63993D, orange-50 #CA6C0F (caution) and interaction-blue-50 #0066CC; never Red Hat red, the brand colour.
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
            thresholds: {steps: [{value: 0, color: "#F0561D"}, {value: 100, color: "#63993D"}]}}},
        queries: [q(expr; DS; null)]}};
def qgauge(name; desc; expr):
    {kind: "Panel", spec: {display: {name: name, description: desc},
        plugin: {kind: "GaugeChart", spec: {calculation: "last", format: {unit: "percent", decimalPlaces: 0}, max: 100,
            thresholds: {defaultColor: "#F0561D", steps: [{value: 70, color: "#FFCC17"}, {value: 90, color: "#63993D"}]}}},
        queries: [q(expr; DS; "{{model}}")]}};
# A stat whose tile turns red below zero and green at or above it.
def signed(name; desc; expr; decimals):
    stat(name; desc; expr; "decimal"; decimals)
    | .spec.plugin.spec += {colorMode: "background_solid", thresholds: {defaultColor: "#F0561D", steps: [{value: 0, color: "#63993D"}]}};
# queries: [[expr, series name], ...]; one bar per series, largest first.
def bar(name; desc; queries; decimals):
    {kind: "Panel", spec: {display: {name: name, description: desc},
        plugin: {kind: "BarChart", spec: {calculation: "last", format: {unit: "decimal", decimalPlaces: decimals, shortValues: false},
            mode: "value", sort: "desc"}},
        queries: [queries[] | q(.[0]; DS; .[1])]}};
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
     spec: {config: {display: {name: display, description: desc}, duration: (if name == "dashboard-offer-5-break-even-admin" then "30d" else "168h" end), variables: variables, panels: panels,
        layouts: layouts}}};
def single(name; title; label_name; matcher; default):
    {kind: "ListVariable", spec: {name: name, allowAllValue: false, allowMultiple: false, defaultValue: default,
        display: {name: title, hidden: false},
        plugin: {kind: "PrometheusLabelValuesVariable", spec: {datasource: DS, labelName: label_name, matchers: [matcher]}}}};
  def md(name; text): {kind: "Panel", spec: {display: {name: name, description: ""},
        plugin: {kind: "Markdown", spec: {text: text}}, queries: []}};
def column(header; name; fmt): {align: "right", enableSorting: true, format: fmt, header: header, name: name};
def short0: {decimalPlaces: 0, shortValues: true, unit: "decimal"};

# ── Break-even per use case ──
# Decision view: should one use case (a team subscription) move from an external model to a private one? The same
# subscription has run on both, so its tokens, its MLflow pass rates and its cost compare like for like. Usage in the
# time range is scaled to a month; worker prices, tariffs and capacity come from the showback offer catalog (current
# values for any range), external list prices and amounts from the metering ledger. No apostrophes below: this program
# sits in a single-quoted shell string.
def cat(x): "(last_over_time(\(x)[60d] offset -60d) or \(x) @ end())";
  "scalar(max(\(cat("showback_usd_per_eur"))))" as $rate
| " Converted from USD at 1 EUR = 1.1179 USD (ECB reference rate, 2026-11-03)." as $eur_note
| "{subscription=\"$usecase\", model=\"$reference\"}" as $ext
| "{subscription=\"$usecase\", model=~\"$reference|$private\"}" as $both
| "scalar(count_over_time((sum(increase(authorized_hits_total\($both)[1h])) > 0)[$__range:1h]) or vector(1))" as $win
| "* scalar(clamp_min(vector($usage_hours * $users / \($win) * (scalar(count_over_time(vector(1)[$__range:1m]) / 60) < bool 168)), 730 * $users / scalar(count_over_time(vector(1)[$__range:1m]) / 60)))" as $monthly
| "sum(increase(authorized_hits_total\($both)[$__range]))" as $tok_all
| "(\($tok_all)) \($monthly)" as $vol
| "(sum(increase(showback_external_metering_input_tokens\($ext)[$__range])) + sum(increase(showback_external_metering_output_tokens\($ext)[$__range])))" as $e_tok
| "sum(increase(showback_external_metering_estimated_usd\($ext)[$__range]))" as $e_usd
| "min(showback_external_metering_rate_usd_per_million{model=\"$reference\", category=\"input_uncached\"})" as $p_in
| "min(showback_external_metering_rate_usd_per_million{model=\"$reference\", category=\"output\"})" as $p_out
| "((\($e_usd)) / ((\($e_tok)) > 0) * 1e6 or (\($p_in) + \($p_out)) / 2)" as $blended
| "(max(\(cat("showback_offer_tariff_usd_per_million{model=\"$private\"}"))) * scalar(max(\(cat("showback_platform_coefficient")))))" as $tariff
| "max(\(cat("showback_offer_worker_usd_per_hour{model=\"$private\"}")))" as $wprice
| "max(\(cat("showback_offer_capacity_tokens_per_second{model=\"$private\"}"))) * 3600 * $worker_hours" as $capacity
| "clamp_min(ceil((\($vol)) / ((\($capacity)) * $planning_load / 100)), 1)" as $workers
| "(\($workers)) * \($wprice) * $worker_hours" as $worker_cost
| "(\($worker_cost)) / (\($blended)) * 1e6" as $breakeven
# The private candidate is a dedicated model the use case team already sponsors: its worker is paid already.
| "(count(label_replace(\(cat("showback_offer_info{offer=\"dedicated\", model=\"$private\"}")), \"team\", \"$1\", \"sponsor\", \"(.+)\") and on(team) \(cat("showback_subscription_team{subscription=\"$usecase\"}"))) > 0)" as $own
| "((\($vol)) * (\($blended)) / 1e6)" as $ext_cost
| def options(f): "label_replace(\($ext_cost | f), \"option\", \"Stay external on $reference\", \"\", \"\")"
      + " or label_replace(\("((\($vol)) * \($tariff) / 1e6)" | f), \"option\", \"Shared $private at its tariff\", \"\", \"\")"
      + " or label_replace(\("((\($worker_cost)) unless on() \($own))" | f), \"option\", \"A dedicated $private worker\", \"\", \"\")"
      + " or label_replace(\("(vector(0) and on() \($own))" | f), \"option\", \"$private, already paid by the team\", \"\", \"\")";
  def moves(f): "label_replace(\("((\($vol)) * \($tariff) / 1e6)" | f), \"option\", \"shared\", \"\", \"\")"
      + " or label_replace(\("((\($worker_cost)) unless on() \($own))" | f), \"option\", \"worker\", \"\", \"\")"
      + " or label_replace(\("(vector(0) and on() \($own))" | f), \"option\", \"own\", \"\", \"\")";
  "max(\(moves("((\($ext_cost)) - " + . + ") / \($rate)")))" as $best_savings
# MLflow judges on this use case only, per model, in the time range.
| "judge=~\"relevance|completeness|team_guidelines|finished\"" as $J
| def verdicts(m; extra): "sum by (judge) (increase(showback_quality_verdicts_total{subscription=\"$usecase\", model=\"\(m)\", \($J)\(extra)}[$__range]))";
  def passrate(m): "round(100 * (\(verdicts(m; ", result=\"pass\"")) or 0 * \(verdicts(m; ""))) / (\(verdicts(m; "")) > 0))";
  "(\(passrate("$private")) - \(passrate("$reference")))" as $gap
| def mverdicts(sel): "sum by (model) (increase(showback_quality_verdicts_total{subscription=\"$usecase\", model=~\"$reference|$private\", \(sel)}[$__range]))";
  def mpass(judge): "round(100 * (\(mverdicts("judge=\"" + judge + "\", result=\"pass\"")) or 0 * \(mverdicts("judge=\"" + judge + "\""))) / (\(mverdicts("judge=\"" + judge + "\"")) > 0))";
  [{value: 0, max: 89.999, color: "#F0561D"}, {value: 90, max: 94.999, color: "#B98412"}, {value: 95, max: 100, color: "#4394E5"}]
  | map({condition: {kind: "Range", spec: {min: .value, max: .max}}, textColor: .color}) as $qcolours
| [{min: -1000, max: -8.001, color: "#F0561D", text: "Not ready"}, {min: -8, max: -3.001, color: "#CA6C0F", text: "Check"},
   {min: -3, max: 1000, color: "#63993D", text: "Good enough"}] as $bands
# Start from a priced external model (free ones have no break-even), then a use case that runs on it (not the quality judge
# or the playground test traffic).
| [single("reference"; "External model"; "model"; "showback_external_metering_events{price_state!=\"free_prototype\"}"; "claude-sonnet-5-5"),
   single("usecase"; "Use case"; "subscription"; "showback_external_metering_events{model=\"$reference\", subscription!~\"maas-quality-judge|playground-.*\"}"; "team-engineering-ci"),
   single("private"; "Private model"; "model"; "showback_offer_info"; "qwen3-8-27b"),
   (textvar("usage_hours"; "168"; "Usage hours / month"; "Hours a month the teams work at the pace seen in the time range (8 h x 21 working days = 168).") | .spec.constant = true | .spec.display.hidden = true),
   (textvar("users"; "1"; "Users per team"; "Scales the observed usage: 1 is the usage as measured.") | .spec.constant = true | .spec.display.hidden = true),
   (textvar("worker_hours"; "730"; "GPU hours / month"; "Hours a month a private GPU worker would run (always on).") | .spec.constant = true | .spec.display.hidden = true),
   (textvar("planning_load"; "70"; "Planning load %"; "Average share of its capacity a worker is planned to carry, leaving room for peaks.") | .spec.constant = true | .spec.display.hidden = true)] as $tok_vars
| {extTokens: (ts("Tokens on the external model (per hour)"; "Tokens of the selected use case on its external model in each trailing hour, from MaaS metering."; [["sum by (model) (increase(authorized_hits_total\($ext)[1h]))", "{{model}}"]]; "decimal"; DS)
       | .spec.plugin.spec.visual += {areaOpacity: 0.3} | .spec.plugin.spec.yAxis.format += {shortValues: true}
       | .spec.plugin.spec.querySettings = [{queryIndex: 0, colorMode: "fixed", colorValue: "#5E40BE"}]),
   privTokens: (ts("Tokens on the private model (per hour)"; "Tokens of the selected use case on the selected private model in each trailing hour, from MaaS metering."; [["sum by (model) (increase(authorized_hits_total{subscription=\"$usecase\", model=\"$private\"}[1h]))", "{{model}}"]]; "decimal"; DS)
       | .spec.plugin.spec.visual += {areaOpacity: 0.3} | .spec.plugin.spec.yAxis.format += {shortValues: true}
       | .spec.plugin.spec.querySettings = [{queryIndex: 0, colorMode: "fixed", colorValue: "#0066CC"}]),
   savings: (stat("Monthly savings if moved (EUR)"; "External cost of the monthly workload minus the cheapest private option. Zero is the break-even point: the private option costs as much as the external model (for a dedicated worker: its monthly cost divided by the external price per million tokens). Red below break-even (stay external), yellow up to 250 EUR a month (little to gain), green above.\($eur_note)"; $best_savings; "decimal"; 0)
       | .spec.plugin.spec.format.shortValues = false
       | .spec.plugin.spec += {colorMode: "background_solid", thresholds: {defaultColor: "#F0561D", steps: [{value: 0, color: "#FFCC17"}, {value: 250, color: "#63993D"}]}}),
   workload: {kind: "Panel", spec: {display: {name: "Workload vs break-even",
       description: "Monthly tokens of the use case as a share of the break-even volume of a dedicated private worker: its monthly cost divided by the external price per million tokens at this use case mix. 100% is break-even. Red below 90% (the external model is cheaper), yellow from 90% to 110% (about even), green above 110% (a dedicated worker pays off). The shared private model at its tariff has no break-even volume: it is cheaper at any volume when its tariff is below the external price."},
       plugin: {kind: "GaugeChart", spec: {calculation: "last", format: {unit: "percent", decimalPlaces: 0}, max: 200,
           thresholds: {defaultColor: "#F0561D", steps: [{value: 90, color: "#FFCC17"}, {value: 110, color: "#63993D"}]}}},
       queries: [q("100 * (\($vol)) / (\($breakeven))"; DS; "Break-even at 100%")]}},
   usecaseTable: (table("Per model (selected period)";
       "Tokens of the use case on each model, the share of its workload, the price per million tokens (external: list price at its mix; shared private: tariff with the platform coefficient) and the MLflow pass rates of this use case on each model. 95% and above shows blue, 90% to 95% yellow, below 90% red.\($eur_note)";
       [{align: "left", enableSorting: true, header: "Model", name: "model", width: 180},
        column("Tokens"; "value #1"; short0), column("Share %"; "value #2"; {decimalPlaces: 0, unit: "decimal"}),
        column("EUR / 1M"; "value #3"; {decimalPlaces: 2, unit: "decimal"}),
        (column("Relevance %"; "value #4"; {decimalPlaces: 0, unit: "decimal"}) + {cellSettings: $qcolours}),
        (column("Completeness %"; "value #5"; {decimalPlaces: 0, unit: "decimal"}) + {cellSettings: $qcolours}),
        (column("Guidelines %"; "value #6"; {decimalPlaces: 0, unit: "decimal"}) + {cellSettings: $qcolours}),
        (column("Finished %"; "value #7"; {decimalPlaces: 0, unit: "decimal"}) + {cellSettings: $qcolours}),
        column("Traces judged"; "value #8"; {decimalPlaces: 0, unit: "decimal"})];
       ["sum by (model) (increase(authorized_hits_total\($both)[$__range]))",
        "round(100 * sum by (model) (increase(authorized_hits_total\($both)[$__range])) / scalar(\($tok_all)))",
        "label_replace((\($blended)) / \($rate), \"model\", \"$reference\", \"\", \"\") or label_replace(\($tariff) / \($rate), \"model\", \"$private\", \"\", \"\")",
        mpass("relevance"), mpass("completeness"), mpass("team_guidelines"), mpass("finished"),
        mverdicts("judge=\"relevance\"")]) | .spec.plugin.spec.pagination = false),
   qualityCheck: (table("Quality check per judge";
       "Pass rate of this use case on each model per MLflow judge in the selected period, and the gap in points (private minus external). Good enough: no more than 3 points lower; Check: 3 to 8 lower; Not ready: more than 8 lower. A judge without verdicts on one of the models has no row. Different judges are not equally strict: compare with care.";
       [{align: "left", enableSorting: true, header: "Judge", name: "judge"},
        column("External %"; "value #1"; {decimalPlaces: 0, unit: "decimal"}), column("Private %"; "value #2"; {decimalPlaces: 0, unit: "decimal"}),
        (column("Gap (points)"; "value #3"; {decimalPlaces: 0, unit: "decimal"}) + {cellSettings: ($bands | map({condition: {kind: "Range", spec: {min: .min, max: .max}}, textColor: .color}))}),
        (column("Verdict"; "value #4"; {decimalPlaces: 0, unit: "decimal"}) + {align: "left", cellSettings: ($bands | map({condition: {kind: "Range", spec: {min: .min, max: .max}}, text: .text, textColor: .color}))})];
       [passrate("$reference"), passrate("$private"), $gap, $gap]) | .spec.plugin.spec.pagination = false),
   options: (table("Monthly cost of each option (EUR)";
       "The whole monthly workload of the use case on each option: the external model at its list price and observed mix, the shared private model at its tariff with the platform coefficient, a dedicated private worker (workers needed x worker price x GPU hours), or a dedicated model the team already sponsors (no extra cost). Savings are against staying external.\($eur_note)";
       [{align: "left", enableSorting: true, header: "Option", name: "option", width: 300},
        (column("Cost / month"; "value #1"; {decimalPlaces: 0, shortValues: false, unit: "decimal"}) + {sort: "asc"}),
        (column("Savings / month"; "value #2"; {decimalPlaces: 0, shortValues: false, unit: "decimal"})
         + {cellSettings: [{condition: {kind: "Range", spec: {min: -1000000000, max: -0.001}}, textColor: "#F0561D"}, {condition: {kind: "Range", spec: {min: 0, max: 1000000000}}, textColor: "#63993D"}]})];
       [options("round((" + . + ") / \($rate))"), options("round(((\($ext_cost)) - " + . + ") / \($rate))")]) | .spec.plugin.spec.pagination = false)} as $tok_panels
| [grid("Overview"; [["extTokens", 0, 0, 14, 8], ["privTokens", 0, 8, 14, 8], ["savings", 14, 0, 10, 6], ["workload", 14, 6, 10, 10]]),
   grid("Quality and cost"; [["qualityCheck", 0, 0, 12, 7], ["options", 12, 0, 12, 7]]),
   grid("Breakdown"; [["usecaseTable", 0, 0, 24, 6]])] as $tok_layouts

| {"dashboard-6-tokenomics-break-even.yaml": dashboard("dashboard-offer-5-break-even-admin"; "Showback 5 · Break-even";
       "Should a use case move from an external model to a private one? The same team subscription on both models: tokens, MLflow quality and the monthly cost of each option.";
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
for file in dashboard-6-tokenomics-break-even.yaml; do
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
