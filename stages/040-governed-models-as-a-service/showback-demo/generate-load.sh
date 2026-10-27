#!/usr/bin/env bash
# Generate demo load with the team keys minted by team-keys.sh: the three showback teams working on the Coolstore
# application, with the tasks in prompts.json.
#   shared     Engineering (code reviews and agent tasks) and Support (customer conversations) on Qwen 3.8, the shared
#              private model
#   dedicated  Marketing (campaign copy with revision rounds) on Mistral Small 4, its dedicated private model
#   external   Support (customer conversations) on an external model (default gpt-6-luna)
#   all        every team and offering at once, each team at its own pace
# Engineering agent tasks give the model read_file and run_tests tools and play the tools from prompts.json (model call,
# tool calls, model call). Support and Marketing tasks with follow-ups are conversations: each turn is sent with the
# whole history. Each team runs CONCURRENCY parallel loops until MINUTES have passed, then prints a token summary.
# --pause SECONDS or MIN-MAX sets the think time between a loop's requests for every team (default per team:
# Engineering 2-6, Support 5-15, Marketing 10-30). --team limits a run to one team.
# Every request turn is also written to MLflow as one trace (workspace models-as-a-service, one experiment per MaaS
# model, internal-<model> or external-<model>): a root span with the team, subscription, offering and finish_reason
# tags (AGENT when tools were used), one GenAI chat span per model call with model, provider, tokens, messages and the
# cost from the offer catalog (private) or the provider price catalog (external), and one TOOL span per tool call. The
# turns of a conversation share a session.id (the experiment's Sessions tab). Tracing fails open; --no-trace skips it.
# Usage: generate-load.sh --offer shared|dedicated|external|all [--team NAME] [--minutes 5] [--concurrency 2] [--max-tokens N] [--model NAME] [--pause SECONDS|MIN-MAX] [--no-trace] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
offer='' team_filter='' minutes=5 concurrency=2 max_tokens='' external_model=gpt-6-luna pause='' insecure=false trace=true
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
[[ -z "$pause" || "$pause" =~ ^[0-9]+(-[0-9]+)?$ ]] || fail '--pause must be SECONDS or MIN-MAX'
[[ -z "$max_tokens" || ( "$max_tokens" =~ ^[0-9]+$ && "$max_tokens" -ge 16 && "$max_tokens" -le 4096 ) ]] || fail '--max-tokens must be 16-4096'
PROMPTS="$SCRIPT_DIR/prompts.json"
jq -e '.engineering.tasks and .support.tasks and .marketing.tasks' "$PROMPTS" >/dev/null || fail "Invalid $PROMPTS"
QWEN=publishers/internal-models/models/qwen3-8-27b MISTRAL=publishers/internal-models/models/mistral-small4-119b
# A run is "TEAM MODEL OFFERING": one team on one model.
case "$offer" in
    shared) runs=("engineering $QWEN shared" "support $QWEN shared") ;;
    dedicated) runs=("marketing $MISTRAL dedicated") ;;
    external) runs=("support $external_model external") ;;
    all) runs=("engineering $QWEN shared" "support $QWEN shared" "marketing $MISTRAL dedicated" "support $external_model external") ;;
    *) fail '--offer must be shared, dedicated, external or all' ;;
esac
if [[ -n "$team_filter" ]]; then
    selected=()
    for run in "${runs[@]}"; do [[ "${run%% *}" != "$team_filter" ]] || selected+=("$run"); done
    (( ${#selected[@]} )) || fail "Team $team_filter does not use the $offer offering"
    runs=("${selected[@]}")
fi
team_tokens() {  # answer cap: --max-tokens for everyone, else the team's own (code answers are longer)
    [[ -z "$max_tokens" ]] || { echo "$max_tokens"; return; }
    case "$1" in engineering) echo 2048 ;; *) echo 1024 ;; esac
}
team_pause() {  # think time between requests: --pause for everyone, else the team's own pace
    [[ -z "$pause" ]] || { echo "$pause"; return; }
    case "$1" in engineering) echo 2-6 ;; support) echo 5-15 ;; marketing) echo 10-30 ;; esac
}
for run in "${runs[@]}"; do
    p=$(team_pause "${run%% *}"); (( ${p%-*} <= ${p#*-} && ${p#*-} <= 300 )) || fail '--pause range must be ascending and at most 300 seconds'
done
STATE=${SHOWBACK_STATE_DIR:-$HOME/.config/rhoai3-showback}
[[ -s "$STATE/gateway-url" ]] || fail "No gateway URL in $STATE; run team-keys.sh first"
for run in "${runs[@]}"; do
    read -r team model _ <<<"$run"
    [[ -s "$STATE/$team.key" ]] || fail "No key for $team in $STATE; run team-keys.sh --teams $team"
    [[ "$model" != "$MISTRAL" || -s "$STATE/dedicated-url" ]] || fail "No dedicated model URL in $STATE; run team-keys.sh again"
done
endpoint() {  # the dedicated model has its own Gateway listener
    if [[ "$1" == "$MISTRAL" ]]; then echo "$(cat "$STATE/dedicated-url")/v1/chat/completions"
    else echo "$(cat "$STATE/gateway-url")/v1/chat/completions"; fi
}
tls=(); [[ "$insecure" == false ]] || tls=(--insecure)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
deadline=$(( $(date +%s) + minutes * 60 ))

# ── MLflow traces ─────────────────────────────────────────────────────────────
# Prices: shared private models pay the on-demand tariff; a dedicated model is priced at its worker cost per token at
# demonstrated capacity (the sponsor pays the worker, busy or idle; the Offer dashboard shows the real charge);
# external models at the provider list price of the versioned catalog. Never a price table looked up by model name.
COMPONENT="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo"
WORKSPACE=models-as-a-service  # the MaaS project is the MLflow workspace of request traces
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
        fail "Project $WORKSPACE is missing; deploy Stage 040 (or use --no-trace)"
    MLFLOW_TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin
    MLFLOW_PORT=$((20000 + RANDOM % 10000))
    oc port-forward -n redhat-ods-applications svc/mlflow "$MLFLOW_PORT:8443" >/dev/null 2>&1 & pf=$!; disown "$pf"
    trap 'kill $pf 2>/dev/null; rm -rf "$work"' EXIT
    for _ in $(seq 1 20); do curl -sk -o /dev/null "https://127.0.0.1:$MLFLOW_PORT/" && break; sleep 1; done
    for idx in "${!runs[@]}"; do
        read -r team model offering <<<"${runs[$idx]}"
        price "$model" > "$work/run$idx.price"
        [[ -s "$work/run$idx.price" ]] || log_warn "No price for $model: its traces carry no cost"
        # One experiment per MaaS model: internal- for models served in internal-models, external- for provider models.
        # The offering and provider are experiment tags (the scorer keeps them current), so a model's offering can
        # change while its experiment keeps its history.
        if [[ "$model" == publishers/* ]]; then name="internal-${model##*/}"; else name="external-$model"; fi
        exp=$(mlflow_api "experiments/get-by-name?experiment_name=$name" | jq -r '.experiment.experiment_id // empty')
        [[ -n "$exp" ]] || exp=$(mlflow_api experiments/create "$(jq -cn --arg n "$name" --arg o "$offering" \
            --arg p "$(jq -r '.provider // "unknown"' "$work/run$idx.price")" --arg m "${model##*/}" \
            '{name: $n, tags: [{key: "offering", value: $o}, {key: "provider", value: $p}, {key: "model", value: $m},
              {key: "cost_basis", value: ({shared: "tariff", dedicated: "capacity-equivalent"}[$o] // "list-price")},
              {key: "mlflow.note.content", value: ("Requests to the MaaS model \($m) (\($o) offering, provider \($p)). Costs here are"
                + " indicative unit costs per request (" + ({shared: "tariff", dedicated: "capacity-equivalent"}[$o] // "list-price")
                + " basis); charges per subscription are on the OpenShift AI Observability Offer dashboards.")}]}')" |
            jq -r '.experiment_id // empty')
        [[ -n "$exp" ]] || fail "Could not open MLflow experiment $name in $WORKSPACE (or use --no-trace)"
        echo "$exp" > "$work/run$idx.exp"
    done
fi
# export_trace RUN TEAM MODEL OFFERING STEPS SESSION T0 T1: one trace for one request turn, OTLP/HTTP JSON; fails open.
# STEPS holds one JSON line per model call ({kind: chat, sid, t0, t1, code, req, out}) or tool call ({kind: tool, sid,
# t0, t1, name, args, result}), in order.
export_trace() {
    local idx=$1 team=$2 model=$3 offering=$4 steps=$5 session=$6 t0=$7 t1=$8 otlp
    otlp=$(jq -n --slurpfile st "$steps" --slurpfile price "$work/run$idx.price" --arg team "$team" --arg offer "$offering" \
        --arg model "${model##*/}" --arg tid "$(openssl rand -hex 16)" --arg rid "$(openssl rand -hex 8)" \
        --arg session "$session" --arg t0 "$t0" --arg t1 "$t1" '
        def s($k; $v): {key: $k, value: {stringValue: ($v | tostring)}};
        def i($k; $v): {key: $k, value: {intValue: ($v | tostring)}};
        def ok($c): if $c == "200" then {code: 1} else {code: 2, message: "HTTP \($c)"} end;
        ($price[0] // null) as $p | [$st[] | select(.kind == "chat")] as $chats | $chats[-1] as $last
        | ($last.out.choices[0] // {}) as $final | ([$st[] | select(.kind == "tool")] | length > 0) as $agent
        | ([$chats[] | select(.code != "200") | .code] | first // "200") as $code
        | {resourceSpans: [{resource: {attributes: [s("service.name"; "showback-load")]},
           scopeSpans: [{scope: {name: "rhoai3-showback"}, spans: ([
            {traceId: $tid, spanId: $rid, name: "team-\($team) request", kind: 1,
             startTimeUnixNano: $t0, endTimeUnixNano: $t1, status: ok($code),
             attributes: ([s("mlflow.spanType"; if $agent then "\"AGENT\"" else "\"CHAIN\"" end), s("user.id"; "showback-\($team)"),
               s("mlflow.traceTag.team"; $team), s("mlflow.traceTag.subscription"; "team-\($team)"),
               s("mlflow.traceTag.offering"; $offer), s("mlflow.traceTag.source"; "showback-load"),
               s("mlflow.traceTag.finish_reason"; ($final.finish_reason // "none")),
               # What the cost figure means: an indicative unit cost, not a charge (the Offer dashboards show charges).
               s("mlflow.traceTag.cost_basis"; ({shared: "tariff", dedicated: "capacity-equivalent"}[$offer] // "list-price")),
               s("mlflow.spanInputs"; ({prompt: ($chats[0].req.messages | map(select(.role == "user")) | last | .content)} | tojson)),
               s("mlflow.spanOutputs"; ({response: ($final.message.content // "")} | tojson))]
              + (if $session != "" then [s("session.id"; $session)] else [] end))}]
           + [$st[] | if .kind == "tool" then
                {traceId: $tid, spanId: .sid, parentSpanId: $rid, name: "tool \(.name)", kind: 1,
                 startTimeUnixNano: .t0, endTimeUnixNano: .t1, status: {code: 1},
                 attributes: [s("mlflow.spanType"; "\"TOOL\""), s("gen_ai.operation.name"; "execute_tool"),
                   s("gen_ai.tool.name"; .name), s("mlflow.spanInputs"; (.args | tojson)),
                   s("mlflow.spanOutputs"; ({result: .result} | tojson))]}
              else (.out // {}) as $o | ($o.usage.prompt_tokens // 0) as $in | ($o.usage.completion_tokens // 0) as $out
                | ($o.choices[0] // {}) as $c |
                {traceId: $tid, spanId: .sid, parentSpanId: $rid, name: "chat \($model)", kind: 3,
                 startTimeUnixNano: .t0, endTimeUnixNano: .t1, status: ok(.code),
                 attributes: ([s("gen_ai.operation.name"; "chat"), s("gen_ai.request.model"; $model),
                   s("gen_ai.response.model"; ($o.model // $model)), s("gen_ai.provider.name"; ($p.provider // "unknown")),
                   s("gen_ai.input.messages"; (.req.messages | tojson)), s("gen_ai.output.messages"; ([$c.message // {}] | tojson)),
                   i("http.response.status_code"; (.code | tonumber))]
                  + (if .req.tools then [s("gen_ai.tool.definitions"; (.req.tools | tojson))] else [] end)
                  # Why the answer stopped: "length" means the max-tokens cap cut it off (a client setting).
                  + (if $c.finish_reason then [{key: "gen_ai.response.finish_reasons",
                      value: {arrayValue: {values: [{stringValue: $c.finish_reason}]}}}] else [] end)
                  + (if .code == "200" then [i("gen_ai.usage.input_tokens"; $in), i("gen_ai.usage.output_tokens"; $out)] else [] end)
                  + (if $p and .code == "200" then [s("mlflow.llm.cost"; ({input_cost: ($in * $p.input),
                      output_cost: ($out * $p.output), total_cost: ($in * $p.input + $out * $p.output)} | tojson))] else [] end))}
              end])}]}]}') || return 1
    printf 'header = "Authorization: Bearer %s"\nheader = "X-MLFLOW-WORKSPACE: %s"\nheader = "x-mlflow-experiment-id: %s"\n' \
        "$MLFLOW_TOKEN" "$WORKSPACE" "$(cat "$work/run$idx.exp")" |
        curl --config - -sk --max-time 20 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
            --data-binary "$otlp" "https://127.0.0.1:$MLFLOW_PORT/v1/traces" | grep -qx 200
}
TOOLS='[{"type":"function","function":{"name":"read_file","description":"Read a file of the Coolstore repository","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Path from the repository root"}},"required":["path"]}}},
 {"type":"function","function":{"name":"run_tests","description":"Run Coolstore tests and return the output","parameters":{"type":"object","properties":{"target":{"type":"string","description":"Test class or method"}},"required":["target"]}}}]'
# chat ID TEAM MODEL MESSAGES_FILE [TOOLS]: one model call; appends a chat step to $work/ID.steps, prints the reply file.
chat() {
    local id=$1 team=$2 model=$3 msgs=$4 tools=${5:-} n t0 t1 code
    n=$(wc -l < "$work/$id.steps" 2>/dev/null || echo 0); n=${n// /}
    jq -n --arg m "$model" --slurpfile msgs "$msgs" --argjson n "$(team_tokens "$team")" --argjson tools "${tools:-null}" \
        '{model: $m, messages: $msgs[0]}
         + (if ($m | startswith("gpt-")) then {max_completion_tokens: $n} else {max_tokens: $n} end)
         + (if ($m | startswith("publishers/")) then {temperature: 0.7} else {} end)
         + (if ($m | contains("qwen")) then {chat_template_kwargs: {enable_thinking: false}} else {} end)
         + (if $tools then {tools: $tools, tool_choice: "auto"} else {} end)' > "$work/$id.req$n"
    t0=$(now_ns)
    code=$(printf 'header = "Authorization: Bearer %s"\n' "$(cat "$STATE/$team.key")" |
        curl --config - --silent --connect-timeout 10 --max-time 180 "${tls[@]}" \
            --header 'Content-Type: application/json' --data-binary "@$work/$id.req$n" \
            --output "$work/$id.out$n" --write-out '%{http_code}' "$(endpoint "$model")") || code=000
    t1=$(now_ns)
    jq -cn --slurpfile req "$work/$id.req$n" --rawfile out "$work/$id.out$n" --arg code "$code" --arg sid "$(openssl rand -hex 8)" \
        --arg t0 "$t0" --arg t1 "$t1" '{kind: "chat", sid: $sid, t0: $t0, t1: $t1, code: $code, req: $req[0],
          out: ($out | try fromjson catch {})}' >> "$work/$id.steps"
    echo "$work/$id.out$n"
}
# turn RUN TEAM MODEL OFFERING ID TASK MESSAGES_FILE SESSION: one request turn (with tool calls for an agent task),
# traced as one trace; appends the assistant reply to MESSAGES_FILE and a summary line to the team log.
turn() {
    local idx=$1 team=$2 model=$3 offering=$4 id=$5 task=$6 msgs=$7 session=$8 out t0 t1 tools='' call name args result
    : > "$work/$id.steps"
    [[ "$(jq -r '.agent // false' <<<"$task")" == true ]] && tools=$TOOLS
    t0=$(now_ns)
    out=$(chat "$id" "$team" "$model" "$msgs" "$tools")
    # An agent task: play each requested tool from the task's fixtures, then ask the model again with the results.
    if [[ -n "$tools" ]] && jq -e '.choices[0].message.tool_calls | length > 0' "$out" >/dev/null 2>&1; then
        jq -c '.choices[0].message | {role: "assistant", content: (.content // ""), tool_calls}' "$out" > "$work/$id.assistant"
        jq --slurpfile a "$work/$id.assistant" '. + $a' "$msgs" > "$msgs.tmp" && mv "$msgs.tmp" "$msgs"
        while IFS= read -r call; do
            name=$(jq -r '.function.name' <<<"$call") args=$(jq -c '.function.arguments | try fromjson catch {}' <<<"$call")
            result=$(jq -r --arg n "$name" --argjson a "$args" 'if $n == "read_file" then (.files[$a.path // ""] // "No such file: \($a.path // "")")
                elif $n == "run_tests" then (.test_output // "No tests found") else "Unknown tool \($n)" end' <<<"$task")
            jq -cn --arg sid "$(openssl rand -hex 8)" --arg t "$(now_ns)" --arg n "$name" --argjson a "$args" --arg r "$result" \
                '{kind: "tool", sid: $sid, t0: $t, t1: $t, name: $n, args: $a, result: $r}' >> "$work/$id.steps"
            jq --arg c "$(jq -r '.id' <<<"$call")" --arg r "$result" '. + [{role: "tool", tool_call_id: $c, content: $r}]' \
                "$msgs" > "$msgs.tmp" && mv "$msgs.tmp" "$msgs"
        done < <(jq -c '.choices[0].message.tool_calls[]' "$out")
        out=$(chat "$id" "$team" "$model" "$msgs" "$tools")
    fi
    t1=$(now_ns)
    jq --rawfile o "$out" '. + [{role: "assistant", content: (($o | try fromjson catch {}) | .choices[0].message.content // "")}]' \
        "$msgs" > "$msgs.tmp" && mv "$msgs.tmp" "$msgs"
    local traced=-
    if [[ "$trace" == true ]]; then
        export_trace "$idx" "$team" "$model" "$offering" "$work/$id.steps" "$session" "$t0" "$t1" && traced=1 || traced=0
    fi
    # Summary line: HTTP code of the turn, input and output tokens over its model calls, tool calls, traced.
    jq -rs --arg tr "$traced" '[.[] | select(.kind == "chat")] as $c
        | "\([$c[] | select(.code != "200") | .code] | first // "200") \([$c[].out.usage.prompt_tokens // 0] | add)" +
          " \([$c[].out.usage.completion_tokens // 0] | add) \([.[] | select(.kind == "tool")] | length) \($tr)"' \
        "$work/$id.steps" >> "$work/run$idx.log"
}
worker() {
    local idx=$1 team=$2 model=$3 offering=$4 id=$5 pace task followup session ntasks
    pace=$(team_pause "$team") ntasks=$(jq --arg t "$team" '.[$t].tasks | length' "$PROMPTS")
    while (( $(date +%s) < deadline )); do
        task=$(jq -c --arg t "$team" --argjson k $((RANDOM % ntasks)) '.[$t].tasks[$k]' "$PROMPTS")
        # A conversation (task with follow-ups) shares one MLflow session; a single question has none.
        session=''; jq -e '.followups | length > 0' <<<"$task" >/dev/null && session="$team-$(openssl rand -hex 6)"
        jq -n --arg t "$team" --slurpfile p "$PROMPTS" --argjson task "$task" \
            '[{role: "system", content: $p[0][$t].system}, {role: "user", content: $task.prompt}]' > "$work/$id.msgs"
        turn "$idx" "$team" "$model" "$offering" "$id" "$task" "$work/$id.msgs" "$session"
        while IFS= read -r followup; do
            (( $(date +%s) < deadline )) || break
            sleep $(( ${pace%-*} + RANDOM % (${pace#*-} - ${pace%-*} + 1) ))  # the user reads the answer, then replies
            jq --arg f "$followup" '. + [{role: "user", content: $f}]' "$work/$id.msgs" > "$work/$id.msgs.tmp" &&
                mv "$work/$id.msgs.tmp" "$work/$id.msgs"
            turn "$idx" "$team" "$model" "$offering" "$id" "$task" "$work/$id.msgs" "$session"
        done < <(jq -r '.followups[]?' <<<"$task")
        sleep $(( ${pace%-*} + RANDOM % (${pace#*-} - ${pace%-*} + 1) ))
    done
}

workers=()
log_info "Offer $offer: ${#runs[@]} run(s) x $concurrency loops for $minutes min (tasks: $PROMPTS)"
for idx in "${!runs[@]}"; do
    read -r team model offering <<<"${runs[$idx]}"
    log_info "  $team -> $model ($offering, pause $(team_pause "$team") s, max $(team_tokens "$team") tokens)"
    for ((i = 0; i < concurrency; i++)); do worker "$idx" "$team" "$model" "$offering" "run$idx-$i" & workers+=($!); done
done
wait "${workers[@]}"  # not the MLflow port-forward
for idx in "${!runs[@]}"; do
    read -r team model offering <<<"${runs[$idx]}"
    [[ -f "$work/run$idx.log" ]] || continue
    awk -v t="$team" -v m="${model##*/}" '{n++; if ($1 == 200) {ok++; p += $2; c += $3} else e[$1]++; tools += $4
            if ($5 == 1) tr++; if ($5 == 0) tf++}
        END {printf "%-12s %-28s turns=%d ok=%d input=%d output=%d tool_calls=%d", t, m, n, ok, p, c, tools;
             for (k in e) printf " http_%s=%d", k, e[k]; if (tr + tf) printf " traced=%d trace_failed=%d", tr, tf; printf "\n"}' \
        "$work/run$idx.log"
done
log_info "Dashboards: Observe & monitor -> Dashboard -> Offer tabs (metrics arrive within about a minute)"
[[ "$trace" != true ]] || log_info "Traces: MLflow, workspace $WORKSPACE, experiments internal-<model> / external-<model> (Overview, Traces, Sessions)"
