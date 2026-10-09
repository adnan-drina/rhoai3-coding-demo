"""Generate two custom PersesDashboards (Cost per token, Tokenomics break-even) for the RHOAI observability page.
Structure mirrors the product Usage dashboard (spec.config: display, duration, variables, panels, layouts)."""
import sys, yaml
OUT = sys.argv[1]
DS = {"kind": "PrometheusDatasource", "name": "data-science-prometheus-datasource"}
CDS = {"kind": "PrometheusDatasource", "name": "cluster-prometheus-datasource"}
def q(expr, ds=DS, name=None):
    spec = {"datasource": ds, "query": expr}
    if name: spec["seriesNameFormat"] = name
    return {"kind": "TimeSeriesQuery", "spec": {"plugin": {"kind": "PrometheusTimeSeriesQuery", "spec": spec}}}
def stat(name, desc, expr, unit="decimal", decimals=2, ds=DS, calc="last"):
    fmt = {"unit": unit}
    if unit == "decimal": fmt["decimalPlaces"] = decimals
    return {"kind": "Panel", "spec": {"display": {"name": name, "description": desc}, "plugin": {"kind": "StatChart", "spec": {"calculation": calc, "format": fmt}}, "queries": [q(expr, ds)]}}
def ts(name, desc, queries, unit="decimal", ds=DS):
    return {"kind": "Panel", "spec": {"display": {"name": name, "description": desc}, "plugin": {"kind": "TimeSeriesChart", "spec": {"legend": {"mode": "list", "position": "bottom", "values": []}, "visual": {"areaOpacity": 0.1, "connectNulls": False, "display": "line", "lineWidth": 1.5}, "yAxis": {"format": {"unit": unit}, "min": 0}}}, "queries": [q(e, ds, n) for e, n in queries]}}
def table(name, desc, columns, queries):
    cols = [{"hide": True, "name": "timestamp"}] + columns
    return {"kind": "Panel", "spec": {"display": {"name": name, "description": desc}, "plugin": {"kind": "Table", "spec": {"columnSettings": cols, "density": "compact", "pagination": True, "transforms": [{"kind": "MergeSeries", "spec": {}}]}}, "queries": [q(e) for e in queries]}}
def gauge(name, desc, expr, max_=200):
    return {"kind": "Panel", "spec": {"display": {"name": name, "description": desc}, "plugin": {"kind": "GaugeChart", "spec": {"calculation": "last", "format": {"unit": "percent", "decimalPlaces": 0}, "max": max_, "thresholds": {"steps": [{"value": 0, "color": "#c9190b"}, {"value": 100, "color": "#3e8635"}]}}}, "queries": [q(expr)]}}
def listvar(name, label, matcher, display):
    return {"kind": "ListVariable", "spec": {"name": name, "allowAllValue": True, "allowMultiple": True, "customAllValue": ".*", "defaultValue": "$__all", "display": {"name": display, "hidden": False}, "plugin": {"kind": "PrometheusLabelValuesVariable", "spec": {"datasource": DS, "labelName": label, "matchers": [matcher]}}}}
def textvar(name, value, display, desc):
    return {"kind": "TextVariable", "spec": {"name": name, "value": value, "constant": False, "display": {"name": display, "description": desc, "hidden": False}}}
def grid(title, items):
    return {"kind": "Grid", "spec": {"display": {"title": title, "collapse": {"open": True}}, "items": [{"x": x, "y": y, "width": w, "height": h, "content": {"$ref": f"#/spec/panels/{p}"}} for p, x, y, w, h in items]}}
def dashboard(name, display, desc, variables, panels, layouts):
    return {"apiVersion": "perses.dev/v1alpha2", "kind": "PersesDashboard", "metadata": {"name": name, "namespace": "redhat-ods-monitoring",
            "labels": {"app.kubernetes.io/name": name, "app.kubernetes.io/part-of": "rhoai3-coding-demo", "app.kubernetes.io/component": "observability", "app.kubernetes.io/managed-by": "argocd"}},
            "spec": {"config": {"display": {"name": display, "description": desc}, "duration": "168h", "variables": variables, "panels": panels, "layouts": layouts}}}

# ---------- Cost per token ----------
M = 'model_name=~"$model"'
tok_prompt = f'sum by (model_name) (increase(kserve_vllm:prompt_tokens_total{{{M}}}[$__range]))'
tok_gen = f'sum by (model_name) (increase(kserve_vllm:generation_tokens_total{{{M}}}[$__range]))'
cost_by_model = f'({tok_prompt} / 1e6 * $price_prompt) + ({tok_gen} / 1e6 * $price_completion)'
U = 'user!="", user=~"$user", subscription=~"$subscription"'
hits_user = f'sum by (user, subscription, model) (increase(authorized_hits_total{{{U}, model=~"$model"}}[$__range]))'
calls_user = f'sum by (user, subscription, model) (increase(authorized_calls_total{{{U}}}[$__range]))'
cost_vars = [listvar("model", "model_name", 'kserve_vllm:prompt_tokens_total', "Model"), listvar("user", "user", 'authorized_hits_total{user!=""}', "User"), listvar("subscription", "subscription", 'authorized_hits_total{subscription!=""}', "Subscription"),
             textvar("price_prompt", "0.10", "Price $/1M prompt tokens", "Showback price for prompt (input) tokens, USD per million; edit per model or contract."),
             textvar("price_completion", "0.40", "Price $/1M completion tokens", "Showback price for generated (output) tokens, USD per million."),
             textvar("price_blended", "0.25", "Blended $/1M tokens (per user)", "MaaS counts total tokens per user and subscription without an input/output split; this blended price values them.")]
cost_panels = {
    "totalCost": stat("Total cost", "Prompt and completion tokens served by the private models over the Range window, priced with the dashboard's price variables.", f'sum({cost_by_model})', "decimal", 2),
    "totalTokens": stat("Total tokens", "Prompt plus completion tokens over the Range window.", f'sum({tok_prompt}) + sum({tok_gen})', "decimal", 0),
    "blendedCost": stat("Observed $/1M tokens", "Total cost divided by total tokens: the blended price actually realised with the current input/output mix.", f'sum({cost_by_model}) / clamp_min(sum({tok_prompt}) + sum({tok_gen}), 1) * 1e6', "decimal", 3),
    "costPer1kRequests": stat("$ per 1K requests", "Total cost divided by governed requests (MaaS authorized calls) over the Range window.", f'sum({cost_by_model}) / clamp_min(sum(increase(authorized_calls_total{{user!=""}}[$__range])), 1) * 1000', "decimal", 3),
    "costOverTime": ts("Cost rate by model", "Hourly spend by model at the dashboard prices.", [(f'(sum by (model_name) (rate(kserve_vllm:prompt_tokens_total{{{M}}}[$__rate_interval])) * 3600 / 1e6 * $price_prompt) + (sum by (model_name) (rate(kserve_vllm:generation_tokens_total{{{M}}}[$__rate_interval])) * 3600 / 1e6 * $price_completion)', "{{model_name}} $/h")]),
    "tokensOverTime": ts("Token rate by model", "Prompt and completion tokens per second by model.", [(f'sum by (model_name) (rate(kserve_vllm:prompt_tokens_total{{{M}}}[$__rate_interval]))', "{{model_name}} prompt"), (f'sum by (model_name) (rate(kserve_vllm:generation_tokens_total{{{M}}}[$__rate_interval]))', "{{model_name}} completion")]),
    "costByModel": table("Cost by model", "Tokens and cost per model over the Range window.", [
        {"align": "left", "enableSorting": True, "header": "Model", "name": "model_name"},
        {"align": "right", "enableSorting": True, "format": {"decimalPlaces": 0, "shortValues": True, "unit": "decimal"}, "header": "Prompt tokens", "name": "value #1"},
        {"align": "right", "enableSorting": True, "format": {"decimalPlaces": 0, "shortValues": True, "unit": "decimal"}, "header": "Completion tokens", "name": "value #2"},
        {"align": "right", "enableSorting": True, "format": {"decimalPlaces": 2, "unit": "decimal"}, "header": "Cost ($)", "name": "value #3", "sort": "desc"}],
        [tok_prompt, tok_gen, cost_by_model]),
    "costByUser": table("Cost by user and subscription", "Governed MaaS tokens per user, subscription and model over the Range window, valued at the blended price.", [
        {"align": "left", "enableSorting": True, "header": "User", "name": "user"}, {"align": "left", "enableSorting": True, "header": "Subscription", "name": "subscription"}, {"align": "left", "enableSorting": True, "header": "Model", "name": "model"},
        {"align": "right", "enableSorting": True, "format": {"decimalPlaces": 0, "shortValues": True, "unit": "decimal"}, "header": "Tokens", "name": "value #1"},
        {"align": "right", "enableSorting": True, "format": {"decimalPlaces": 0, "unit": "decimal"}, "header": "Requests", "name": "value #2"},
        {"align": "right", "enableSorting": True, "format": {"decimalPlaces": 2, "unit": "decimal"}, "header": "Cost ($)", "name": "value #3", "sort": "desc"}],
        [f'round({hits_user})', f'round({calls_user})', f'{hits_user} / 1e6 * $price_blended']),
}
cost_layouts = [grid("Overview", [("totalCost", 0, 0, 6, 5), ("totalTokens", 6, 0, 6, 5), ("blendedCost", 12, 0, 6, 5), ("costPer1kRequests", 18, 0, 6, 5)]),
                grid("Trends", [("costOverTime", 0, 0, 12, 8), ("tokensOverTime", 12, 0, 12, 8)]),
                grid("Breakdown", [("costByModel", 0, 0, 24, 8), ("costByUser", 0, 8, 24, 10)])]
cost = dashboard("dashboard-5-cost-per-token-admin", "Cost per token", "Showback: tokens served by the private models and governed MaaS users, priced with editable per-million-token prices.", cost_vars, cost_panels, cost_layouts)

# ---------- Tokenomics break-even ----------
burn = '($gpu_hourly_cost * $gpu_count)'
tps = 'sum(rate(kserve_vllm:prompt_tokens_total[$__rate_interval])) + sum(rate(kserve_vllm:generation_tokens_total[$__rate_interval]))'
tps_model = 'sum by (model_name) (rate(kserve_vllm:prompt_tokens_total[$__rate_interval]) + rate(kserve_vllm:generation_tokens_total[$__rate_interval]))'
tokens_range = 'sum(increase(kserve_vllm:prompt_tokens_total[$__range])) + sum(increase(kserve_vllm:generation_tokens_total[$__range]))'
hours_range = 'count_over_time(vector(1)[$__range:1h])'
api_blended = '(($api_price_prompt + $api_price_completion) / 2)'
api_spend_range = '(sum(increase(kserve_vllm:prompt_tokens_total[$__range])) / 1e6 * $api_price_prompt) + (sum(increase(kserve_vllm:generation_tokens_total[$__range])) / 1e6 * $api_price_completion)'
tok_vars = [textvar("gpu_hourly_cost", "2.24", "GPU $/hour (per node)", "Hourly infrastructure cost of one GPU worker; default is an AWS g6e.2xlarge (one L40S) on-demand list price."),
            textvar("gpu_count", "2", "GPU workers", "Number of GPU workers currently paid for."),
            textvar("api_price_prompt", "0.15", "Hosted API $/1M prompt tokens", "Reference price of a comparable hosted model for prompt tokens; the break-even is computed against it."),
            textvar("api_price_completion", "0.60", "Hosted API $/1M completion tokens", "Reference price of a comparable hosted model for completion tokens.")]
tok_panels = {
    "burn": stat("Infrastructure burn $/h", "GPU workers times hourly cost.", f'vector({burn})', "decimal", 2),
    "throughput": stat("Live throughput (tokens/s)", "Prompt plus completion tokens per second across the private models.", tps, "decimal", 0),
    "effectiveLive": stat("Effective $/1M tokens (live)", "Burn divided by live throughput: what one million tokens cost right now.", f'{burn} / clamp_min(({tps}) * 3600 / 1e6, 0.001)', "decimal", 2),
    "effectiveRange": stat("Effective $/1M tokens (Range)", "Burn over the Range window divided by tokens served in it.", f'{burn} * {hours_range} / clamp_min(({tokens_range}) / 1e6, 0.001)', "decimal", 2),
    "breakEven": stat("Break-even throughput (tokens/s)", "Tokens per second at which self-hosting matches the hosted API's blended price.", f'vector({burn} / {api_blended} * 1e6 / 3600)', "decimal", 0),
    "utilisation": gauge("Throughput vs break-even", "Live throughput as a percentage of the break-even throughput; above 100% self-hosting is cheaper than the hosted API.", f'({tps}) / ({burn} / {api_blended} * 1e6 / 3600) * 100'),
    "apiEquivalent": stat("Hosted-API equivalent spend (Range)", "What the tokens served in the Range window would have cost at the hosted API prices.", api_spend_range, "decimal", 2),
    "infraSpend": stat("Infrastructure spend (Range)", "Burn over the Range window.", f'{burn} * {hours_range}', "decimal", 2),
    "savings": stat("Savings vs hosted API (Range)", "Hosted-API equivalent spend minus infrastructure spend; negative means the GPUs are under-utilised relative to the reference price.", f'{api_spend_range} - {burn} * {hours_range}', "decimal", 2),
    "throughputTrend": ts("Throughput by model vs break-even", "Tokens per second by model against the break-even line.", [(tps_model, "{{model_name}}"), (f'vector({burn} / {api_blended} * 1e6 / 3600)', "break-even")]),
    "gpuUtil": ts("GPU utilisation", "Accelerator utilisation from cluster monitoring (DCGM).", [("avg by (exported_pod) (accelerator_gpu_utilization)", "{{exported_pod}}")], "percent", CDS),
}
tok_layouts = [grid("Live", [("burn", 0, 0, 6, 5), ("throughput", 6, 0, 6, 5), ("effectiveLive", 12, 0, 6, 5), ("breakEven", 18, 0, 6, 5)]),
               grid("Break-even", [("utilisation", 0, 0, 8, 8), ("throughputTrend", 8, 0, 16, 8)]),
               grid("Range economics", [("effectiveRange", 0, 0, 6, 5), ("infraSpend", 6, 0, 6, 5), ("apiEquivalent", 12, 0, 6, 5), ("savings", 18, 0, 6, 5), ("gpuUtil", 0, 5, 24, 7)])]
tok = dashboard("dashboard-6-tokenomics-break-even-admin", "Tokenomics · break-even (live)", "Self-hosting economics: infrastructure burn, effective cost per million tokens, and the throughput at which the private models beat a hosted API.", tok_vars, tok_panels, tok_layouts)

hdr = "# Custom observability dashboard for the OpenShift AI Observability page (rendered as a tab because its name starts with\n# dashboard-). Generated by stages/040-governed-models-as-a-service/gen-cost-dashboards.py; edit the generator, not this file.\n"
open(f"{OUT}/dashboard-5-cost-per-token.yaml", "w").write(hdr + yaml.safe_dump(cost, sort_keys=False, width=200))
open(f"{OUT}/dashboard-6-tokenomics-break-even.yaml", "w").write(hdr + yaml.safe_dump(tok, sort_keys=False, width=200))
open(f"{OUT}/kustomization.yaml", "w").write("apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - dashboard-5-cost-per-token.yaml\n  - dashboard-6-tokenomics-break-even.yaml\n  - dcgm-accelerator-servicemonitor.yaml\n")
print("written", OUT)
