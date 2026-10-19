#!/usr/bin/env bash
# Offline one-model qualification close using scaled synthetic fixtures; no cluster or HTTP calls.
set -euo pipefail
DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fixture="$DEMO_DIR/fixtures"
scenario="$DEMO_DIR/qualification-qwen-only.json"
hash=$(shasum -a 256 "$scenario" | cut -d ' ' -f 1)
# Compress the original 12-minute evidence into the qualification's six-minute period.
scale='def epoch: (1792065600+((.-1792065600)/2|floor));
  def dates: walk(if type=="string" and test("^2026-10-15T.*Z$") then fromdateiso8601|epoch|todateiso8601 else . end);'
jq "$scale"' dates | .scenario_id="qwen-only-live-qualification-v1" | .scenario_sha256=$hash
  | .requests_started=3' --arg hash "$hash" "$fixture/run.json" >"$work/run.json"
jq -c "$scale"' select(.requested_model=="qwen3-8-27b") | dates' "$fixture/receipts.jsonl" >"$work/receipts.jsonl"
jq "$scale"' .data.result|=map(select(.metric.model=="qwen3-8-27b") | .values|=map(.[0]|=epoch))' \
    "$fixture/samples.json" >"$work/samples.json"
jq '.canonical_series|=map(select(.model=="qwen3-8-27b")) | .model_aliases|={"qwen3-8-27b":.["qwen3-8-27b"]}' \
    "$fixture/metering.json" >"$work/metering.json"
jq "$scale"' .instance_intervals|=map(select(.model=="qwen3-8-27b") | dates)' \
    "$fixture/instance-intervals.json" >"$work/intervals.json"
bash "$DEMO_DIR/collect-usage.sh" prepare --scenario "$scenario" --run "$work/run.json" \
    --receipts "$work/receipts.jsonl" --samples "$work/samples.json" --metering "$work/metering.json" \
    --intervals "$work/intervals.json" --output "$work/evidence.json"
jq -e '.models==["qwen3-8-27b"] and (.subscriptions|keys)==["team-engineering","team-support"]
  and all(.windows[].usage[]; .coverage=="complete")
  and .windows[2].usage["qwen3-8-27b"].tokens=={"team-engineering":0,"team-support":0}' \
    "$work/evidence.json" >/dev/null
bash "$DEMO_DIR/allocate.sh" --input "$work/evidence.json" --output "$work/report.json"
jq -e '.evidence_kind=="synthetic_fixture" and .allocation_complete
  and (.totals_by_consumer.platform_idle>0) and ([.windows[].models[].model]|unique)==["qwen3-8-27b"]' \
    "$work/report.json" >/dev/null
bash "$DEMO_DIR/publish-report.sh" --scenario "$scenario" --report "$work/report.json" --output "$work/report.prom"
if rg -q '(model="mistral[^\"]*"|team="marketing"|subscription="team-marketing")' "$work/report.prom"; then
    echo 'Qwen-only publisher retained an excluded team or model' >&2
    exit 1
fi
printf '%s\n' 'PASS Qwen-only synthetic close: two subscriptions, one model, reconciled idle cost and scoped gauges.'
