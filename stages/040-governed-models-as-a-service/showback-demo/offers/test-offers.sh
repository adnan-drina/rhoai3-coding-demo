#!/usr/bin/env bash
# Offline offer-accounting regression suite; private temporary evidence only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
runner="$SCRIPT_DIR/service-report.sh"
fixture="$SCRIPT_DIR/fixtures/month.json"
number=0
last=''
# Any accidental transport/cluster invocation fails and leaves an independent trace.
mkdir "$tmp/bin"
for tool in oc kubectl curl; do
    cat > "$tmp/bin/$tool" <<'BLOCK'
#!/usr/bin/env bash
printf 'forbidden transport\n' >> "$OFFER_TEST_TRANSPORT_LOG"
exit 97
BLOCK
    chmod +x "$tmp/bin/$tool"
done
export OFFER_TEST_TRANSPORT_LOG="$tmp/transport.log"
export PATH="$tmp/bin:$PATH"
next_case() {
    number=$((number+1))
    last="$tmp/report-$number.json"
    jq "$1" "$fixture" > "$tmp/input.json"
}
accept() {
    local label=$1 filter=$2 expected=$3
    next_case "$filter"
    if "$runner" --input "$tmp/input.json" --output "$last" > "$tmp/log" 2>&1 && jq -e "$expected" "$last" >/dev/null; then
        record "$label" pass
    else
        cat "$tmp/log" >&2
        record "$label" fail
    fi
}
reject() {
    local label=$1 filter=$2
    next_case "$filter"
    if "$runner" --input "$tmp/input.json" --output "$last" > "$tmp/log" 2>&1 || [[ -e "$last" ]]; then
        record "$label" fail
    else
        record "$label" pass
    fi
}
accept 'Three offers preserve cost, charge, subsidy and recovery separately' '.' '
  .complete and .scope=="service-offers" and .totals.cost_cents==200847 and
  .totals.charge_cents==130852 and .totals.subsidy_cents==10000 and .totals.recovery_balance_cents== -59995'
base_report=$last
accept '31-day dedicated capacity includes 744 paid hours and idle sponsor' '.' '
  [.agreements[]|select(.offer=="dedicated")][0] | .usage.requests==0 and .cost_cents==100000 and .charge_cents==100000'
accept 'Effective provider rate boundary uses late tariff exactly at boundary' '.' '
  [.charge_lines[]|select(.id=="usage:ext-two:input_uncached")][0] | .rate_version=="fixture-late" and .charge_cents==300'
accept 'Two consumers retain separate usage and nonoverlapping cache categories' '.' '
  [.charge_lines[]|select(.offer=="external" and .kind=="usage")|.user]|unique|length==2'
accept 'Platform-fault retry has an explicit equal credit' '.' '
  [.charge_lines[]|select(.event_id=="ext-retry")|.charge_cents]|add==0'
accept 'Provider invoice delta remains visible without forcing charge equality' '.' '
  [.agreements[]|select(.offer=="external")][0]|.invoice_difference_cents==40 and .invoice_reconciled==false'
accept 'Shared fixed tariff records low-demand shortfall' '.' '
  [.agreements[]|select(.offer=="shared")][0]|.tariff.input_usd_per_million=="37.5" and .recovery_balance_cents== -60000'
accept 'Combined reservation, subsidy and included credit recover forecast cost once' '
  .events |= map(if .agreement_id=="shared" then .quantities|=map_values(.*5) else . end)' '
  [.agreements[]|select(.offer=="shared")][0]|.charge_cents==90000 and .subsidy_cents==10000 and .recovery_balance_cents==0'
accept 'Shared high demand exposes surplus at unchanged prospective rate' '
  .events |= map(if .agreement_id=="shared" then .quantities|=map_values(.*10) else . end)' '
  [.agreements[]|select(.offer=="shared")][0]|.tariff.input_usd_per_million=="37.5" and .recovery_balance_cents==75000'
accept 'Zero usage retains reservation fee but cannot redeem nonexistent usage' '
  .events |= map(select(.agreement_id!="shared"))' '
  [.agreements[]|select(.offer=="shared")][0]|.charge_cents==20000 and .recovery_balance_cents== -70000'
accept 'Usage-only zero demand has zero revenue and explicit platform shortfall' '
  .agreements[2].tariff.reservation_fees=[] | .events|=map(select(.agreement_id!="shared"))' '
  [.agreements[]|select(.offer=="shared")][0]|.charge_cents==0 and .recovery_balance_cents== -90000'
accept 'Dedicated busy use does not increase contracted fixed capacity cost' '
  .events += [{id:"dedicated-use",agreement_id:"dedicated",consumer_id:"market",at:"2026-10-12T00:00:00Z",
    status:"completed",retry_owner:"consumer",usage_complete:true,quantities:{input_uncached:1000000,output:1000000}}]' '
  [.agreements[]|select(.offer=="dedicated")][0]|.usage.requests==1 and .cost_cents==100000 and .charge_cents==100000'
accept 'Dedicated fixed quote shows actual-cost variance' '
  .agreements[1].billing_method="fixed_quote" | .agreements[1].quote={amount_usd:"1200",source:"SYNTHETIC QUOTE",
    evidence_kind:"synthetic_fixture",approved_at:"2026-09-01T00:00:00Z"}' '
  [.agreements[]|select(.offer=="dedicated")][0]|.cost_cents==100000 and .charge_cents==120000 and .recovery_balance_cents==20000'
accept 'Identical provider delivery replay is deduplicated' '.events += [.events[0]]' '
  .deduplicated_events==1 and .totals.charge_cents==130852'
reject 'Conflicting duplicate event is rejected' '.events += [(.events[0]|.quantities.output+=1)]'
reject 'Total input overlapping cache categories is rejected' '.events[0].quantities.input_tokens=1200000'
reject 'Unknown provider category is rejected' '.events[0].quantities.reasoning_tokens=10'
reject 'Negative usage is rejected' '.events[0].quantities.output= -1'
reject 'Unsafe count is rejected before pricing' '.events[0].quantities.output=9007199254740992'
reject 'Unsafe sum of individually valid token categories is rejected' '
  .events[0].quantities.input_uncached=4503599627370495 | .events[0].quantities.cache_read=1'
reject 'Overlapping external rate windows are rejected' '.agreements[0].rate_cards[0].end="2026-10-17T00:00:00Z"'
accept 'Missing provider rate remains unknown, never zero' '.agreements[0].rate_cards[0].prices.output=null' '
  .complete==false and .totals.charge_cents==null and
  any(.charge_lines[];.id=="usage:ext-one:output" and .charge_cents==null and .coverage=="missing_price")'
accept 'Gap in rate coverage stays unknown' '.agreements[0].rate_cards[1].start="2026-10-17T00:00:00Z"' '
  .complete==false and .totals.charge_cents==null'
accept 'Aborted stream with incomplete usage cannot become free' '.events[0].status="aborted"|.events[0].usage_complete=false' '
  .complete==false and .totals.charge_cents==null and any(.charge_lines[];.coverage=="missing_usage")'
accept 'Aborted event with authoritative final billing can still be priced' '.events[0].status="aborted"' '
  .complete and .totals.charge_cents==130852'
accept 'Missing whole-period coverage prevents partial counters becoming totals' '.agreements[0].usage_coverage="missing"' '
  .complete==false and .totals.charge_cents==null and .totals.known_charge_cents==130852'
accept 'Unknown invoice produces a labeled metered estimate' '.agreements[0].invoice.usd=null' '
  [.agreements[]|select(.offer=="external")][0]|.cost_basis=="metered_estimate" and .invoice_cents==null'
accept 'Missing overhead coverage cannot turn a known subtotal into full cost' '.agreements[2].cost_coverage="missing"' '
  .totals.cost_cents==null and .totals.known_cost_cents==200847 and .totals.recovery_balance_cents==null'
accept 'An unset shared tariff remains unpriced even with no usage' '
  .agreements[2].tariff.status="unpriced"|.events|=map(select(.agreement_id!="shared"))' '
  .totals.charge_cents==null and .complete==false'
reject 'Closed statement refuses unavailable invoice' '.statement_status="closed"|.agreements[0].invoice.usd=null'
reject 'Closed statement refuses missing usage' '.statement_status="closed"|.agreements[0].usage_coverage="missing"'
accept 'Closed complete statement can retain explicit invoice discrepancy' '.statement_status="closed"' '
  .statement_status=="closed" and .complete and any(.agreements[];.invoice_difference_cents==40)'
accept 'Missing private costs retain unknown total and known subtotal' '.cost_items[1].amount_usd=null' '
  .totals.cost_cents==null and .totals.known_cost_cents==193847 and .totals.charge_cents==null'
reject 'Complete private pool requires explicit cost evidence' '.cost_items|=map(select(.agreement_id!="dedicated"))'
reject 'A cost pool cannot be included twice' '.cost_items += [.cost_items[0]]'
reject 'Same instance time cannot be assigned to two offers' '
  .cost_items += [(.cost_items[0]|.id="duplicate-capacity"|.agreement_id="shared")]'
accept 'Instance rate transition integrates each interval exactly' '
  .cost_items[0].end="2026-10-16T00:00:00Z" |
  .cost_items += [(.cost_items[0]|.id="late-compute"|.start="2026-10-16T00:00:00Z"|
    .end="2026-11-01T00:00:00Z"|.usd_per_hour="2.5")]' '
  [.agreements[]|select(.offer=="dedicated")][0]|.cost_cents==148000 and .charge_cents==148000'
reject 'Known prices cannot claim unavailable provenance' '.agreements[0].rate_cards[0].evidence_kind="unavailable"'
reject 'Unpriced tariff cannot invoice a reservation from unavailable evidence' '
  .agreements[2].tariff |= (.status="unpriced"|.evidence_kind="unavailable"|.subsidy_usd=null)'
reject 'Unpriced tariff cannot fund a subsidy from unavailable evidence' '
  .agreements[2].tariff |= (.status="unpriced"|.evidence_kind="unavailable"|.reservation_fees=[])'
reject 'Unavailable evidence cannot assert a zero subsidy either' '
  .agreements[2].tariff |= (.status="unpriced"|.evidence_kind="unavailable"|.reservation_fees=[]|.subsidy_usd="0")'
accept 'Unavailable tariff without fees or subsidy retains unknown recovery' '
  .agreements[2].tariff |= (.status="unpriced"|.evidence_kind="unavailable"|.reservation_fees=[]|.subsidy_usd=null)' '
  .complete==false and any(.agreements[];.offer=="shared" and .subsidy_cents==null and .recovery_balance_cents==null) and
  all(.charge_lines[]|select(.offer=="shared");.charge_cents==null)'
reject 'Observed report cannot consume synthetic prices' '.evidence_kind="observed"'
reject 'Money rates must be decimal strings' '.agreements[0].rate_cards[0].prices.output=0.1'
reject 'Unbounded monetary precision fails closed' '.agreements[0].rate_cards[0].prices.output="99999999999999999"'
reject 'Shared zero forecast is rejected' '.agreements[2].tariff.forecast.input_tokens=0|.agreements[2].tariff.forecast.output_tokens=0'
reject 'Shared approval after usage is rejected' '.agreements[2].tariff.approved_at="2026-10-10T00:00:00Z"'
reject 'Dedicated fixed quote cannot be invented after usage' '
  .agreements[1].billing_method="fixed_quote" | .agreements[1].quote={amount_usd:"1200",source:"SYNTHETIC QUOTE",
    evidence_kind:"synthetic_fixture",approved_at:"2026-10-15T00:00:00Z"}'
reject 'Reservation plus subsidy cannot produce a negative tariff' '.agreements[2].tariff.subsidy_usd="999"'
reject 'Duplicate reservation cannot redeem usage credit twice' '
  .agreements[2].tariff.reservation_fees += [.agreements[2].tariff.reservation_fees[0]]'
reject 'Reservation cannot target a nonmember team' '.agreements[2].tariff.reservation_fees[0].team="marketing"'
reject 'Included credit cannot exceed reservation payment' '.agreements[2].tariff.reservation_fees[0].included_usage_credit_usd="201"'
reject 'Unknown consumer is not attributed' '.events[0].consumer_id="missing"'
accept 'Email-shaped authenticated user identity is retained' '.consumers.eng.user="engineer@example.invalid"' '
  any(.charge_lines[];.event_id=="ext-one" and .user=="engineer@example.invalid")'
reject 'Nonmember consumer cannot use a contract' '.events[0].consumer_id="market"'
reject 'User adjustment cannot borrow another team identity' '.adjustments[1].team="engineering"'
reject 'Old membership cannot attribute later events' '.consumers.eng.end="2026-10-15T00:00:00Z"'
accept 'Effective identity mapping change retains correct historical team' '
  .consumers.eng.end="2026-10-16T00:00:00Z" |
  .consumers.eng_late=(.consumers.eng|.start="2026-10-16T00:00:00Z"|.end="2026-11-01T00:00:00Z"|.team="new-team") |
  .agreements[0].members += ["eng_late"] | .agreements[2].members += ["eng_late"] |
  .events|=map(if .consumer_id=="eng" and .at>="2026-10-16T00:00:00Z" then .consumer_id="eng_late" else . end)' '
  any(.charge_lines[];.event_id=="ext-one" and .team=="engineering") and
  any(.charge_lines[];.event_id=="ext-retry" and .team=="new-team")'
reject 'Overlapping membership epochs are rejected' '.consumers.eng_again=.consumers.eng'
reject 'Month-end event belongs to next month' '.events[0].at="2026-11-01T00:00:00Z"'
reject 'Shortened month is rejected' '.period.end="2026-10-31T00:00:00Z"'
reject 'Invalid calendar date is rejected' '.events[0].at="2026-10-32T00:00:00Z"'
reject 'Non-UTC billing period is rejected' '.period.timezone="Europe/Amsterdam"'
accept 'Many fractional-cent rows conserve the exact rounded statement total' '
  .events=[range(0;101)|{id:("fraction-"+(.|tostring)),agreement_id:"external",consumer_id:"eng",
    at:"2026-10-10T00:00:00Z",status:"completed",retry_owner:"consumer",usage_complete:true,
    quantities:{input_uncached:1,output:0}}] |
  .adjustments=[] | .agreements[0].rate_cards[0].prices.input_uncached="0.0001"' '
  [.agreements[]|select(.offer=="external")][0]|.charge_cents==1'
next_case '.events|=reverse | .cost_items|=reverse | .adjustments|=reverse | .agreements|=reverse'
"$runner" --input "$tmp/input.json" --output "$last" >/dev/null
if diff -q <(jq -S '{agreements,charge_lines,cost_lines,totals}' "$last") \
    <(jq -S '{agreements,charge_lines,cost_lines,totals}' "$base_report") >/dev/null; then
    record 'Reordered full evidence produces identical financial results' pass
else record 'Reordered full evidence produces identical financial results' fail; fi
# Correction is a replacement with predecessor hash, never an additive bill.
next_case '.report_id="corrected-october"|.revision=2|.supersedes_report_id="synthetic-offers-2026-10-v1"|
  .correction_reason="Late provider invoice"|.agreements[0].invoice.usd="8.07"'
if "$runner" --input "$tmp/input.json" --output "$last" --previous "$base_report" >/dev/null &&
    jq -e '.revision==2 and (.previous_report_sha256|length)==64 and
      any(.agreements[];.offer=="external" and .invoice_reconciled)' "$last" >/dev/null; then
    record 'Correction links predecessor hash and replaces invoice evidence' pass
else record 'Correction links predecessor hash and replaces invoice evidence' fail; fi
reject 'Correction without predecessor rejected' '.revision=2|.supersedes_report_id="some-report"|.correction_reason="late"'
next_case '.report_id="wrong-correction"|.revision=3|.supersedes_report_id="synthetic-offers-2026-10-v1"|
  .correction_reason="Skipped revision"'
if "$runner" --input "$tmp/input.json" --output "$last" --previous "$base_report" >/dev/null 2>&1; then
    record 'Skipped correction revision rejected' fail
else record 'Skipped correction revision rejected' pass; fi
if "$runner" --input "$fixture" --output "$base_report" >/dev/null 2>&1; then
    record 'Existing statement cannot be overwritten' fail
else record 'Existing statement cannot be overwritten' pass; fi
"$runner" --input "$SCRIPT_DIR/month.example.json" --output "$tmp/unconfigured.json" >/dev/null
if jq -e '.complete==false and .evidence_kind=="observed" and .totals.cost_cents==null and
  .totals.charge_cents==null and .totals.known_cost_cents==0' "$tmp/unconfigured.json" >/dev/null; then
    record 'Observed editable template is unpriced and incomplete' pass
else record 'Observed editable template is unpriced and incomplete' fail; fi
"$runner" --input "$fixture" --output "$tmp/export.json" --csv "$tmp/export.csv" >/dev/null
if [[ $(ls -l "$tmp/export.json" | awk '{print $1}') == '-rw-------'* ]] &&
    [[ $(wc -l < "$tmp/export.csv" | tr -d ' ') == $(jq '.charge_lines|length+1' "$tmp/export.json") ]]; then
    record 'Private immutable CSV has exactly the statement lines' pass
else record 'Private immutable CSV has exactly the statement lines' fail; fi
if "$runner" --check-report "$tmp/export.json" >/dev/null; then record 'Shared report validator accepts full statement' pass; fi
jq '.totals.charge_cents+=1' "$tmp/export.json" > "$tmp/tampered.json"
if "$runner" --check-report "$tmp/tampered.json" >/dev/null 2>&1; then
    record 'Report validator rejects changed total' fail
else record 'Report validator rejects changed total' pass; fi
jq '.charge_lines[0].charge_cents+=1' "$tmp/export.json" > "$tmp/tampered-line.json"
if "$runner" --check-report "$tmp/tampered-line.json" >/dev/null 2>&1; then
    record 'Report validator rejects changed rounded line' fail
else record 'Report validator rejects changed rounded line' pass; fi
jq 'del(.agreements[0].usage)' "$tmp/export.json" > "$tmp/tampered-usage.json"
if "$runner" --check-report "$tmp/tampered-usage.json" >/dev/null 2>&1; then
    record 'Report validator rejects missing usage summary' fail
else record 'Report validator rejects missing usage summary' pass; fi
# Replace caller files immediately after the first JSON syntax check. A statement
# must validate, hash and calculate its already-captured bytes, including previous revisions.
mkdir "$tmp/race-bin"
real_jq=$(command -v jq)
cat > "$tmp/race-bin/jq" <<'RACE'
#!/usr/bin/env bash
set -u
"$OFFER_REAL_JQ" "$@"
result=$?
if [[ "$result" == 0 && ! -e "$OFFER_RACE_MARKER" ]]; then
    for arg in "$@"; do
        if [[ "$arg" == --stream ]]; then
            cp "$OFFER_RACE_REPLACEMENT" "$OFFER_RACE_TARGET" || exit 98
            touch "$OFFER_RACE_MARKER"
            break
        fi
    done
fi
exit "$result"
RACE
chmod +x "$tmp/race-bin/jq"
race_run() {
    OFFER_REAL_JQ="$real_jq" OFFER_RACE_TARGET="$race_target" OFFER_RACE_REPLACEMENT="$race_replacement" \
      OFFER_RACE_MARKER="$race_marker" PATH="$tmp/race-bin:$PATH" "$runner" "$@" > "$tmp/race-log" 2>&1
}
race_target="$tmp/racing-input.json"
race_replacement="$tmp/replacement-input.json"
race_marker="$tmp/input-swapped"
cp "$fixture" "$race_target"
input_hash=$(shasum -a 256 "$race_target" | cut -d ' ' -f 1)
jq '.agreements[0].invoice.usd="999"' "$fixture" > "$race_replacement"
if race_run --input "$race_target" --output "$tmp/snapshot-input.json" && [[ -e "$race_marker" ]] &&
    cmp -s "$race_target" "$race_replacement" &&
    jq -e --arg hash "$input_hash" '.input_sha256==$hash and .totals.cost_cents==200847' "$tmp/snapshot-input.json" >/dev/null; then
    record 'Input validation, hash and calculation use one captured byte snapshot' pass
else record 'Input validation, hash and calculation use one captured byte snapshot' fail; fi
race_target="$tmp/racing-previous.json"
race_replacement="$tmp/replacement-previous.json"
race_marker="$tmp/previous-swapped"
cp "$base_report" "$race_target"
previous_hash=$(shasum -a 256 "$race_target" | cut -d ' ' -f 1)
jq '.report_id="swapped-predecessor"' "$base_report" > "$race_replacement"
next_case '.report_id="snapshot-correction"|.revision=2|.supersedes_report_id="synthetic-offers-2026-10-v1"|
  .correction_reason="Snapshot regression"'
if race_run --input "$tmp/input.json" --output "$last" --previous "$race_target" && [[ -e "$race_marker" ]] &&
    cmp -s "$race_target" "$race_replacement" &&
    jq -e --arg hash "$previous_hash" '.previous_report_sha256==$hash and
      .supersedes_report_id=="synthetic-offers-2026-10-v1"' "$last" >/dev/null; then
    record 'Predecessor validation, identity and hash use one captured byte snapshot' pass
else record 'Predecessor validation, identity and hash use one captured byte snapshot' fail; fi
race_target="$tmp/racing-check.json"
race_replacement="$tmp/tampered.json"
race_marker="$tmp/check-swapped"
cp "$base_report" "$race_target"
if race_run --check-report "$race_target" && [[ -e "$race_marker" ]] && cmp -s "$race_target" "$race_replacement"; then
    record 'Standalone report validation uses the same snapshot for both checks' pass
else record 'Standalone report validation uses the same snapshot for both checks' fail; fi
{ printf '{"schema_version":1,'; tail -c +2 "$fixture"; } > "$tmp/duplicate.json"
if "$runner" --input "$tmp/duplicate.json" --output "$tmp/duplicate-report.json" >/dev/null 2>&1; then
    record 'Duplicate JSON key rejected before normalization' fail
else record 'Duplicate JSON key rejected before normalization' pass; fi
if [[ ! -e "$OFFER_TEST_TRANSPORT_LOG" ]]; then record 'No live transport or cluster commands' pass; else
    record 'No live transport or cluster commands' fail; fi
validation_summary
