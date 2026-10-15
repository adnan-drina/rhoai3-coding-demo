#!/usr/bin/env bash
# Exports measured MaaS usage for a UTC window from the native RHOAI Thanos (local port-forward) to a private CSV
# plus a coverage receipt (<output>.json). Per user, subscription and model: governed tokens, authorized and limited
# calls, each as the window's counter increase with the window-start baseline. Unpriced: not a native dashboard CSV,
# billing or invoice reconciliation. Writes new files only (mode 0600); never commit identity-bearing reports.
# Usage: stages/040-governed-models-as-a-service/export-maas-usage.sh --from 2026-10-06T00:00:00Z --to 2026-10-07T00:00:00Z --output report.csv
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env >&2
check_oc_logged_in >&2

fail() { echo "ERROR: $*" >&2; exit 1; }
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
FROM="" TO="" OUTPUT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --from) FROM=${2:-}; shift 2 ;;
        --to) TO=${2:-}; shift 2 ;;
        --output) OUTPUT=${2:-}; shift 2 ;;
        *) usage ;;
    esac
done
[[ -n "$FROM" && -n "$TO" && -n "$OUTPUT" ]] || usage
# fromdateiso8601 accepts only YYYY-MM-DDTHH:MM:SSZ, which is the UTC-only contract.
start=$(jq -rn --arg t "$FROM" '$t | fromdateiso8601') || fail "UTC timestamps required (YYYY-MM-DDTHH:MM:SSZ)"
end=$(jq -rn --arg t "$TO" '$t | fromdateiso8601') || fail "UTC timestamps required (YYYY-MM-DDTHH:MM:SSZ)"
now=$(date +%s)
seconds=$((end - start))
(( seconds >= 60 && seconds <= 89 * 86400 && start >= now - 89 * 86400 && end <= now + 60 )) ||
    fail "Window must be 1 minute to 89 days, within the native 90-day retention and not in the future"
jq -e '.pricing_status == "unpriced" and .currency == null and .rates == {}' "$SCRIPT_DIR/showback-ratecard.json" >/dev/null ||
    fail "Only the reviewed unpriced ratecard is supported"
RECEIPT="$OUTPUT.json"
[[ ! -e "$OUTPUT" && ! -e "$RECEIPT" ]] || fail "Output or receipt already exists; preserve earlier reports"
oc --request-timeout=10s auth can-i create pods/portforward -n redhat-ods-monitoring | grep -qx yes ||
    fail "monitoring tunnel authorization required"

WORK=$(mktemp -d)
oc -n redhat-ods-monitoring port-forward service/thanos-querier-data-science-thanos-querier :10902 \
    --address=127.0.0.1 >"$WORK/forward.log" 2>&1 &
FORWARD=$!
trap 'kill "$FORWARD" 2>/dev/null && wait "$FORWARD" 2>/dev/null; rm -rf "$WORK"' EXIT
for _ in $(seq 1 30); do
    PORT=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$WORK/forward.log" | head -1)
    [[ -n "$PORT" ]] && break
    kill -0 "$FORWARD" 2>/dev/null || fail "Native monitoring tunnel failed"
    sleep 0.1
done
[[ -n "${PORT:-}" ]] || fail "Native monitoring tunnel timed out"

# One instant query; prints its result vector. Redirects are not followed.
query() {
    curl -sf --max-time 20 -G "http://127.0.0.1:$PORT/api/v1/query" --data-urlencode "query=$1" --data-urlencode dedup=true |
        jq -e -c 'if .status == "success" then .data.result else error("query failed") end' || fail "Native usage query failed"
}
# Series keyed by attribution dimensions; refuses non-finite or negative values, missing user/subscription,
# and duplicate series for one key (overlapping semantic resources must not be summed).
KEYED='def keyed: map({key: ([.metric | .user, .subscription, .model, .cost_center, .organization_id, .limitador_namespace]
        | map(. // "") | join("\u0001")), labels: .metric, value: (.value[1] | tonumber)})
    | if any(.[]; (.value | isinfinite or isnan) or .value < 0 or (.labels.user // "") == "" or (.labels.subscription // "") == "")
        or (map(.key) | length) != (map(.key) | unique | length)
      then error("Invalid attribution or duplicate underlying semantic resource series") else INDEX(.key) end;'

rows='[]'
coverage='{}'
for pair in authorized_hits_total:governed_total_tokens authorized_calls_total:authorized_calls limited_calls_total:limited_calls; do
    metric=${pair%%:*}
    category=${pair#*:}
    selector="$metric{user!=\"\",subscription!=\"\"}"
    # First-observed cumulative values are never added to a period: a key needs a window-start baseline.
    query "increase(${selector}[${seconds}s] @ $end)" >"$WORK/increase.json"
    query "$selector @ $start" >"$WORK/baseline.json"
    query "$selector @ $end" >"$WORK/latest.json"
    result=$(jq -n -c "$KEYED"' ($in[0] | keyed) as $inc | ($base[0] | keyed) as $base | ($latest[0] | keyed) as $latest
        | (if ($inc | length) > 0 then "observed delta with window-start baseline" else "unknown/no attributed increase series" end) as $cov0
        | [$latest[] | . as $l | $inc[$l.key].value as $n | ($base[$l.key] != null and $n != null) as $complete
            | {labels: $l.labels, cumulative: $l.value, n: $n, complete: $complete}] as $series
        | {coverage: (if any($series[]; .complete | not) then "partial/no baseline or increase samples for requested window" else $cov0 end),
           series: $series}' \
        --slurpfile in "$WORK/increase.json" --slurpfile base "$WORK/baseline.json" --slurpfile latest "$WORK/latest.json") ||
        fail "Invalid attribution or duplicate underlying semantic resource series"
    rows=$(jq -c --argjson rows "$rows" --arg c "$category" --arg from "$FROM" --arg to "$TO" '.coverage as $cov
        | $rows + [.series[] | [$from, $to, $c, .labels.user // "", .labels.subscription // "", .labels.model // "",
            .labels.cost_center // "", .labels.organization_id // "", .labels.limitador_namespace // "",
            (if .complete then .n else "" end), (.n // ""), .cumulative, "unknown", "unknown", "unpriced", "", "", $cov]]' \
        <<<"$result")
    coverage=$(jq -c --argjson cov "$coverage" --arg c "$category" '$cov + {($c): .coverage}' <<<"$result")
done

umask 077
set -o noclobber
mkdir -p "$(dirname "$OUTPUT")"
{
    echo "window_start_utc,window_end_utc,category,user,subscription,model,cost_center,organization_id,limiter_resource,measured_quantity,observed_counter_increase,latest_cumulative_counter,input_tokens,output_tokens,pricing_status,currency,estimated_cost,coverage"
    jq -r '.[] | @csv' <<<"$rows"
} >"$OUTPUT"
jq -n --arg from "$FROM" --arg to "$TO" --argjson coverage "$coverage" --argjson rows "$(jq length <<<"$rows")" '{
    source: "native RHOAI Thanos via authorized local tunnel", window: {from: $from, to: $to}, coverage: $coverage,
    rows: $rows, pricing_status: "unpriced",
    limitations: ["No input/output token split", "No MCP/agent trajectory accounting", "No GPU fixed-cost allocation",
        "Counter sampling/reset/retention can affect estimates",
        "Rows remain scoped to native limiter resources; overlapping policies must not be summed",
        "Duplicate underlying semantic resource series are rejected before aggregation",
        "Absent categories are unknown, not zero",
        "Missing window-start baseline leaves measured_quantity unknown; cumulative counters are not period usage",
        "Not billing-grade or provider invoice reconciliation"]}' >"$RECEIPT"
echo "Exported $(jq length <<<"$rows") measured usage rows; financial amounts remain unpriced. Coverage receipt: $RECEIPT"
