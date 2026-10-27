#!/usr/bin/env bash
# Generate demo load for one service offering with the team keys minted by team-keys.sh.
#   shared     Engineering (code reviews) and Support (customer questions) on Qwen 3.8, the shared private model
#   dedicated  Marketing (campaign copy) on Mistral Small 4, its dedicated private model
#   external   Support (customer questions) on an external model (default gpt-6-luna)
# Each team runs CONCURRENCY parallel request loops until MINUTES have passed, then prints a token summary.
# --pause SECONDS or MIN-MAX adds think time between a loop's requests (random within the range), like a person reading
# each answer before the next question.
# --team limits a run to one team of the offering, so teams can run with different pacing.
# Every request is also written to MLflow as one trace (workspace maas-observability, experiment team-<team>): a root
# span with the team, subscription and offering tags and a GenAI chat span with model, provider, tokens, messages and
# the cost from the offer catalog (private) or the provider price catalog (external). MLflow builds its experiment
# Overview (token usage, cost by model and provider, cost over time) from them. Tracing fails open; --no-trace skips it.
# Usage: generate-load.sh --offer shared|dedicated|external [--team NAME] [--minutes 5] [--concurrency 2] [--max-tokens 256] [--model NAME] [--pause SECONDS|MIN-MAX] [--no-trace] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
offer='' team_filter='' minutes=5 concurrency=2 max_tokens=256 external_model=gpt-6-luna pause=0 insecure=false trace=true
fail() { log_error "$*"; exit 1; }
while (($#)); do
    case "$1" in
        --offer) offer=${2:?}; shift 2 ;;
        --team) team_filter=${2:?}; shift 2 ;;
        --minutes) minutes=${2:?}; shift 2 ;;
        --concurrency) concurrency=${2:?}; shift 2 ;;
        --max-tokens) max_tokens=${2:?}; shift 2 ;;
        --model) external_model=${2:?}; shift 2 ;;
        --pause) pause=${2:?}; shift 2 ;;
        --insecure) insecure=true; shift ;;
        --no-trace) trace=false; shift ;;
        -h|--help) sed -n 's/^# Usage: //p' "$0"; exit 0 ;;
        *) fail "Unknown argument: $1" ;;
    esac
done
[[ "$minutes" =~ ^[0-9]+$ && "$minutes" -ge 1 && "$minutes" -le 60 ]] || fail '--minutes must be 1-60'
[[ "$concurrency" =~ ^[0-9]+$ && "$concurrency" -ge 1 && "$concurrency" -le 8 ]] || fail '--concurrency must be 1-8'
[[ "$pause" =~ ^[0-9]+(-[0-9]+)?$ ]] || fail '--pause must be SECONDS or MIN-MAX'
pause_min=${pause%-*} pause_max=${pause#*-}
(( pause_min <= pause_max && pause_max <= 300 )) || fail '--pause range must be ascending and at most 300 seconds'
[[ "$max_tokens" =~ ^[0-9]+$ && "$max_tokens" -ge 16 && "$max_tokens" -le 2048 ]] || fail '--max-tokens must be 16-2048'
case "$offer" in
    shared) runs=("engineering publishers/internal-models/models/qwen3-8-27b" "support publishers/internal-models/models/qwen3-8-27b") ;;
    dedicated) runs=("marketing publishers/internal-models/models/mistral-small4-119b") ;;
    external) runs=("support $external_model") ;;
    *) fail '--offer must be shared, dedicated or external' ;;
esac
if [[ -n "$team_filter" ]]; then
    selected=()
    for run in "${runs[@]}"; do [[ "${run%% *}" != "$team_filter" ]] || selected+=("$run"); done
    (( ${#selected[@]} )) || fail "Team $team_filter does not use the $offer offering"
    runs=("${selected[@]}")
fi
STATE=${SHOWBACK_STATE_DIR:-$HOME/.config/rhoai3-showback}
[[ -s "$STATE/gateway-url" ]] || fail "No gateway URL in $STATE; run team-keys.sh first"
URL="$(cat "$STATE/gateway-url")/v1/chat/completions"
if [[ "$offer" == dedicated ]]; then  # the dedicated model has its own Gateway listener
    [[ -s "$STATE/dedicated-url" ]] || fail "No dedicated model URL in $STATE; run team-keys.sh again"
    URL="$(cat "$STATE/dedicated-url")/v1/chat/completions"
fi
tls=(); [[ "$insecure" == false ]] || tls=(--insecure)

prompts() {
    case "$1" in
        engineering) printf '%s\n' \
            'Review this Java method and list concrete improvements: public List<Order> open(List<Order> all) { List<Order> r = new ArrayList<>(); for (Order o : all) { if (o.getStatus() == "OPEN") r.add(o); } return r; }' \
            'Review this REST endpoint for error handling and security: @GET @Path("/users/{id}") public User get(@PathParam("id") String id) { return em.createQuery("from User where id = " + id, User.class).getSingleResult(); }' \
            'Suggest unit tests for a function that splits an invoice total across line items and must always sum to the original amount in cents.' ;;
        support) printf '%s\n' \
            'A customer says their order shows "delivered" but nothing arrived. Draft a short, empathetic reply with next steps.' \
            'A customer asks how to reset their account password and says the email never arrives. Draft a helpful answer.' \
            'Summarize this complaint and propose a resolution: "I was charged twice for my subscription this month and nobody answers the phone."' ;;
        marketing) printf '%s\n' \
            'Write three subject lines and a 60-word email for the spring launch of an energy-efficient smart thermostat.' \
            'Draft a LinkedIn post announcing a free webinar on hybrid cloud cost control for IT leaders.' \
            'Create a short product description and two taglines for a reusable stainless steel water bottle aimed at hikers.' ;;
    esac
}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
deadline=$(( $(date +%s) + minutes * 60 ))

# ── MLflow traces ─────────────────────────────────────────────────────────────
# Prices: shared private models pay the on-demand tariff; a dedicated model is priced at its worker cost per token at
# demonstrated capacity (the sponsor pays the worker, busy or idle; the Offer dashboard shows the real charge);
# external models at the provider list price of the versioned catalog. Never a price table looked up by model name.
COMPONENT="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo"
WORKSPACE=maas-observability
now_ns() { perl -MTime::HiRes=time -e 'printf "%.0f\n", time * 1e9'; }
# price MODEL -> JSON {model, provider, input, output} (USD per token), or nothing when the model has no price.
price() {
    local name=${1##*/}
    if [[ "$1" == publishers/* ]]; then
        yaml_json < "$COMPONENT/offer-catalog.yaml" | jq -c --arg m "$name" '
            [.[0].spec.groups[].rules[] | select(.labels.model == $m)
             | {(.record): (.expr | capture("vector\\((?<v>[0-9.]+)\\)").v | tonumber)}] | (add // {}) as $r
            | if $r.showback_offer_tariff_usd_per_million then ($r.showback_offer_tariff_usd_per_million / 1e6) as $t
                | {model: $m, provider: "openshift-ai", input: $t, output: $t}
              elif $r.showback_offer_worker_usd_per_hour and $r.showback_offer_capacity_tokens_per_second then
                ($r.showback_offer_worker_usd_per_hour / ($r.showback_offer_capacity_tokens_per_second * 3600)) as $t
                | {model: $m, provider: "openshift-ai", input: $t, output: $t}
              else empty end'
    else
        jq -c --arg m "$name" '[.rates[] | select(.gateway_model == $m)] | first // empty
            | {model: $m, provider: .provider, input: (.prices_usd_per_million.input_uncached | tonumber / 1e6),
               output: (.prices_usd_per_million.output | tonumber / 1e6)}' "$COMPONENT/metering/provider-pricing.json"
    fi
}
# mlflow_api PATH [BODY]: authenticated MLflow REST call in the trace workspace through the local port-forward.
mlflow_api() {
    printf 'header = "Authorization: Bearer %s"\nheader = "X-MLFLOW-WORKSPACE: %s"\n' "$MLFLOW_TOKEN" "$WORKSPACE" |
        curl --config - -sk --max-time 20 -H 'Content-Type: application/json' ${2:+--data "$2"} \
            "https://127.0.0.1:$MLFLOW_PORT/mlflow/api/2.0/mlflow/$1"
}
if [[ "$trace" == true ]]; then
    oc --request-timeout=10s get namespace "$WORKSPACE" >/dev/null 2>&1 ||
        fail "Project $WORKSPACE is missing; deploy the 040-showback-demo component (or use --no-trace)"
    MLFLOW_TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin
    MLFLOW_PORT=$((20000 + RANDOM % 10000))
    oc port-forward -n redhat-ods-applications svc/mlflow "$MLFLOW_PORT:8443" >/dev/null 2>&1 & pf=$!; disown "$pf"
    trap 'kill $pf 2>/dev/null; rm -rf "$work"' EXIT
    for _ in $(seq 1 20); do curl -sk -o /dev/null "https://127.0.0.1:$MLFLOW_PORT/" && break; sleep 1; done
    for run in "${runs[@]}"; do
        read -r team model <<<"$run"
        exp=$(mlflow_api "experiments/get-by-name?experiment_name=team-$team" | jq -r '.experiment.experiment_id // empty')
        [[ -n "$exp" ]] || exp=$(mlflow_api experiments/create "{\"name\":\"team-$team\"}" | jq -r '.experiment_id // empty')
        [[ -n "$exp" ]] || fail "Could not open MLflow experiment team-$team in $WORKSPACE (or use --no-trace)"
        echo "$exp" > "$work/$team.exp"
        price "$model" > "$work/$team.price"
        [[ -s "$work/$team.price" ]] || log_warn "No price for $model: its traces carry no cost"
    done
fi
# export_trace TEAM MODEL REQUEST RESPONSE CODE START_NS END_NS: one trace, two spans, OTLP/HTTP JSON; fails open.
export_trace() {
    local team=$1 model=$2 req=$3 out=$4 code=$5 t0=$6 t1=$7 tid sid cid otlp
    tid=$(openssl rand -hex 16) sid=$(openssl rand -hex 8) cid=$(openssl rand -hex 8)
    otlp=$(jq -n --slurpfile req "$req" --slurpfile out "$out" --slurpfile price "$work/$team.price" \
        --arg team "$team" --arg offer "$offer" --arg model "${model##*/}" --arg code "$code" \
        --arg tid "$tid" --arg sid "$sid" --arg cid "$cid" --arg t0 "$t0" --arg t1 "$t1" '
        def s($k; $v): {key: $k, value: {stringValue: ($v | tostring)}};
        def i($k; $v): {key: $k, value: {intValue: ($v | tostring)}};
        ($out[0] // {}) as $o | ($price[0] // null) as $p | ($o.usage.prompt_tokens // 0) as $in
        | ($o.usage.completion_tokens // 0) as $outt | ($o.choices[0].message // {}) as $msg
        | (if $code == "200" then {code: 1} else {code: 2, message: "HTTP \($code)"} end) as $status
        | {resourceSpans: [{resource: {attributes: [s("service.name"; "showback-load")]},
           scopeSpans: [{scope: {name: "rhoai3-showback"}, spans: [
            {traceId: $tid, spanId: $sid, name: "team-\($team) request", kind: 1,
             startTimeUnixNano: $t0, endTimeUnixNano: $t1, status: $status,
             attributes: [s("mlflow.spanType"; "\"CHAIN\""), s("user.id"; "showback-\($team)"),
               s("mlflow.traceTag.team"; $team), s("mlflow.traceTag.subscription"; "team-\($team)"),
               s("mlflow.traceTag.offering"; $offer), s("mlflow.traceTag.source"; "showback-load"),
               s("mlflow.spanInputs"; ({prompt: $req[0].messages[-1].content} | tojson)),
               s("mlflow.spanOutputs"; ({response: ($msg.content // "")} | tojson))]},
            {traceId: $tid, spanId: $cid, parentSpanId: $sid, name: "chat \($model)", kind: 3,
             startTimeUnixNano: $t0, endTimeUnixNano: $t1, status: $status,
             attributes: ([s("gen_ai.operation.name"; "chat"), s("gen_ai.request.model"; $model),
               s("gen_ai.response.model"; ($o.model // $model)), s("gen_ai.provider.name"; ($p.provider // "unknown")),
               s("gen_ai.input.messages"; ($req[0].messages | tojson)),
               s("gen_ai.output.messages"; ([$msg] | tojson)), i("http.response.status_code"; ($code | tonumber))]
              + (if $code == "200" then [i("gen_ai.usage.input_tokens"; $in), i("gen_ai.usage.output_tokens"; $outt)] else [] end)
              + (if $p and $code == "200" then [s("mlflow.llm.cost"; ({input_cost: ($in * $p.input),
                  output_cost: ($outt * $p.output), total_cost: ($in * $p.input + $outt * $p.output)} | tojson))] else [] end))}
           ]}]}]}') || return 1
    printf 'header = "Authorization: Bearer %s"\nheader = "X-MLFLOW-WORKSPACE: %s"\nheader = "x-mlflow-experiment-id: %s"\n' \
        "$MLFLOW_TOKEN" "$WORKSPACE" "$(cat "$work/$team.exp")" |
        curl --config - -sk --max-time 20 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
            --data-binary "$otlp" "https://127.0.0.1:$MLFLOW_PORT/v1/traces" | grep -qx 200
}
worker() {
    local team=$1 model=$2 log=$3 id=$4 prompt body code line t0 t1 traced
    local -a list=()
    while IFS= read -r line; do list+=("$line"); done < <(prompts "$team")
    while (( $(date +%s) < deadline )); do
        prompt=${list[RANDOM % ${#list[@]}]}
        jq -n --arg m "$model" --arg p "$prompt" --argjson n "$max_tokens" --argjson qwen "$([[ "$model" == *qwen* ]] && echo true || echo false)" \
            '{model: $m, messages: [{role: "user", content: $p}]}
             + (if ($m | startswith("gpt-")) then {max_completion_tokens: $n} else {max_tokens: $n} end)
             + (if ($m | startswith("publishers/")) then {temperature: 0.7} else {} end)
             + (if $qwen then {chat_template_kwargs: {enable_thinking: false}} else {} end)' > "$work/$id.json"
        t0=$(now_ns)
        code=$(printf 'header = "Authorization: Bearer %s"\n' "$(cat "$STATE/$team.key")" |
            curl --config - --silent --connect-timeout 10 --max-time 120 "${tls[@]}" \
                --header 'Content-Type: application/json' --data-binary "@$work/$id.json" \
                --output "$work/$id.out" --write-out '%{http_code}' "$URL") || code=000
        body=$(jq -c '{p: (.usage.prompt_tokens // 0), c: (.usage.completion_tokens // 0)}' "$work/$id.out" 2>/dev/null ||
            echo '{"p":0,"c":0}')
        t1=$(now_ns) traced=-
        if [[ "$trace" == true ]]; then
            export_trace "$team" "$model" "$work/$id.json" "$work/$id.out" "$code" "$t0" "$t1" && traced=1 || traced=0
        fi
        printf '%s %s %s %s\n' "$code" "$(jq -r '.p' <<<"$body")" "$(jq -r '.c' <<<"$body")" "$traced" >> "$log"
        [[ "$code" == 200 ]] || sleep 2
        (( pause_max == 0 )) || sleep $(( pause_min + RANDOM % (pause_max - pause_min + 1) ))
    done
}

for run in "${runs[@]}"; do
    read -r team model <<<"$run"
    [[ -s "$STATE/$team.key" ]] || fail "No key for $team in $STATE; run team-keys.sh --teams $team"
done
workers=()
log_info "Offer $offer: ${#runs[@]} team(s) x $concurrency loops for $minutes min against $URL"
for run in "${runs[@]}"; do
    read -r team model <<<"$run"
    log_info "  $team -> $model"
    for ((i = 0; i < concurrency; i++)); do worker "$team" "$model" "$work/$team.log" "$team-$i" & workers+=($!); done
done
wait "${workers[@]}"  # not the MLflow port-forward
for run in "${runs[@]}"; do
    read -r team model <<<"$run"
    [[ -f "$work/$team.log" ]] || continue
    awk -v t="$team" -v m="$model" '{n++; if ($1 == 200) {ok++; p += $2; c += $3} else e[$1]++; if ($4 == 1) tr++; if ($4 == 0) tf++}
        END {printf "%-12s %-45s requests=%d ok=%d input=%d output=%d", t, m, n, ok, p, c;
             for (k in e) printf " http_%s=%d", k, e[k]; if (tr + tf) printf " traced=%d trace_failed=%d", tr, tf; printf "\n"}' "$work/$team.log"
done
log_info "Dashboards: Observe & monitor -> Dashboard -> Offer tabs (metrics arrive within about a minute)"
[[ "$trace" != true ]] || log_info "Traces: MLflow, workspace $WORKSPACE, experiments team-<team> -> Overview"
