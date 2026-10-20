#!/usr/bin/env bash
# Generate demo load for one service offering with the team keys minted by team-keys.sh.
#   shared     Engineering (code reviews) and Support (customer questions) on Qwen 3.8, the shared private model
#   dedicated  Marketing (campaign copy) on Mistral Small 4, its dedicated private model
#   external   Support (customer questions) on an external model (default gpt-6-luna)
# Each team runs CONCURRENCY parallel request loops until MINUTES have passed, then prints a token summary.
# --pause SECONDS or MIN-MAX adds think time between a loop's requests (random within the range), like a person reading
# each answer before the next question.
# --team limits a run to one team of the offering, so teams can run with different pacing.
# Usage: generate-load.sh --offer shared|dedicated|external [--team NAME] [--minutes 5] [--concurrency 2] [--max-tokens 256] [--model NAME] [--pause SECONDS|MIN-MAX] [--insecure]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
offer='' team_filter='' minutes=5 concurrency=2 max_tokens=256 external_model=gpt-6-luna pause=0 insecure=false
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
worker() {
    local team=$1 model=$2 log=$3 id=$4 prompt body code line
    local -a list=()
    while IFS= read -r line; do list+=("$line"); done < <(prompts "$team")
    while (( $(date +%s) < deadline )); do
        prompt=${list[RANDOM % ${#list[@]}]}
        jq -n --arg m "$model" --arg p "$prompt" --argjson n "$max_tokens" --argjson qwen "$([[ "$model" == *qwen* ]] && echo true || echo false)" \
            '{model: $m, messages: [{role: "user", content: $p}]}
             + (if ($m | startswith("gpt-")) then {max_completion_tokens: $n} else {max_tokens: $n} end)
             + (if ($m | startswith("publishers/")) then {temperature: 0.7} else {} end)
             + (if $qwen then {chat_template_kwargs: {enable_thinking: false}} else {} end)' > "$work/$id.json"
        code=$(printf 'header = "Authorization: Bearer %s"\n' "$(cat "$STATE/$team.key")" |
            curl --config - --silent --connect-timeout 10 --max-time 120 "${tls[@]}" \
                --header 'Content-Type: application/json' --data-binary "@$work/$id.json" \
                --output "$work/$id.out" --write-out '%{http_code}' "$URL") || code=000
        body=$(jq -c '{p: (.usage.prompt_tokens // 0), c: (.usage.completion_tokens // 0)}' "$work/$id.out" 2>/dev/null ||
            echo '{"p":0,"c":0}')
        printf '%s %s %s\n' "$code" "$(jq -r '.p' <<<"$body")" "$(jq -r '.c' <<<"$body")" >> "$log"
        [[ "$code" == 200 ]] || sleep 2
        (( pause_max == 0 )) || sleep $(( pause_min + RANDOM % (pause_max - pause_min + 1) ))
    done
}

for run in "${runs[@]}"; do
    read -r team model <<<"$run"
    [[ -s "$STATE/$team.key" ]] || fail "No key for $team in $STATE; run team-keys.sh --teams $team"
done
log_info "Offer $offer: ${#runs[@]} team(s) x $concurrency loops for $minutes min against $URL"
for run in "${runs[@]}"; do
    read -r team model <<<"$run"
    log_info "  $team -> $model"
    for ((i = 0; i < concurrency; i++)); do worker "$team" "$model" "$work/$team.log" "$team-$i" & done
done
wait
for run in "${runs[@]}"; do
    read -r team model <<<"$run"
    [[ -f "$work/$team.log" ]] || continue
    awk -v t="$team" -v m="$model" '{n++; if ($1 == 200) {ok++; p += $2; c += $3} else e[$1]++}
        END {printf "%-12s %-45s requests=%d ok=%d input=%d output=%d", t, m, n, ok, p, c;
             for (k in e) printf " http_%s=%d", k, e[k]; printf "\n"}' "$work/$team.log"
done
log_info "Dashboards: Observe & monitor -> Dashboard -> Offer tabs (metrics arrive within about a minute)"
