#!/usr/bin/env bash
# Monthly archive tests use only synthetic files and the offline archive verbs.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/bundles"
fixture="$ROOT/offers/fixtures/month.json"
bash "$ROOT/offers/service-report.sh" --input "$fixture" --output "$WORK/statement.json" >/dev/null
bash "$ROOT/archive.sh" pack --report "$WORK/statement.json" --file "$fixture" --output "$WORK/bundles/october" >/dev/null
index() { bash "$ROOT/archive-index.sh" --bundles "$WORK/bundles" --start 2026-10-01T00:00:00Z --end "$1" --output "$2" >/dev/null 2>&1; }
index 2026-11-01T00:00:00Z "$WORK/october-index.json"
jq -e '.continuity_complete and (.financially_complete|not) and (.selected_reports|length)==1' "$WORK/october-index.json" >/dev/null
mkdir "$WORK/closed-bundles"
jq '.statement_status="closed"' "$fixture" >"$WORK/closed-input.json"
bash "$ROOT/offers/service-report.sh" --input "$WORK/closed-input.json" --output "$WORK/closed-report.json" >/dev/null
bash "$ROOT/archive.sh" pack --report "$WORK/closed-report.json" --file "$WORK/closed-input.json" --output "$WORK/closed-bundles/october" >/dev/null
bash "$ROOT/archive-index.sh" --bundles "$WORK/closed-bundles" --start 2026-10-01T00:00:00Z --end 2026-11-01T00:00:00Z --output "$WORK/closed-index.json" >/dev/null
jq -e '.statements_closed_complete and (.invoice_reconciliation_complete|not) and (.financially_complete|not)
 and .selected_reports[0].unreconciled_invoices[0].invoice_difference_cents==40' "$WORK/closed-index.json" >/dev/null
index 2027-01-01T00:00:00Z "$WORK/quarter-index.json"
jq -e '(.continuity_complete|not) and .missing_months==["2026-11-01T00:00:00Z","2026-12-01T00:00:00Z"]' "$WORK/quarter-index.json" >/dev/null

for month in 11 12; do
    if [[ "$month" == 11 ]]; then next_month='2026-12'; else next_month='2027-01'; fi
    jq --arg month "2026-$month" --arg next "$next_month" '
      walk(if type=="string" and startswith("2026-10-") then $month+.[7:]
           elif type=="string" and startswith("2026-11-") then $next+.[7:] else . end)
      | .report_id="synthetic-offers-"+$month+"-v1"' "$fixture" >"$WORK/input-$month.json"
    bash "$ROOT/offers/service-report.sh" --input "$WORK/input-$month.json" --output "$WORK/report-$month.json" >/dev/null
    bash "$ROOT/archive.sh" pack --report "$WORK/report-$month.json" --file "$WORK/input-$month.json" --output "$WORK/bundles/month-$month" >/dev/null
done
index 2027-01-01T00:00:00Z "$WORK/full-quarter-index.json"
jq -e '.continuity_complete and (.financially_complete|not) and (.selected_reports|length)==3' "$WORK/full-quarter-index.json" >/dev/null

jq '.report_id="synthetic-offers-2026-10-v2" | .revision=2 | .supersedes_report_id="synthetic-offers-2026-10-v1" | .correction_reason="Synthetic corrected provider invoice" | .agreements[0].invoice.usd="9.00"' "$fixture" >"$WORK/correction-input.json"
bash "$ROOT/offers/service-report.sh" --input "$WORK/correction-input.json" --previous "$WORK/statement.json" --output "$WORK/correction.json" >/dev/null
predecessor=$(shasum -a 256 "$WORK/bundles/october/manifest.json" | awk '{print $1}')
bash "$ROOT/archive.sh" pack --report "$WORK/correction.json" --file "$WORK/correction-input.json" \
    --predecessor-manifest-sha256 "$predecessor" --correction-reason 'Synthetic corrected provider invoice' \
    --output "$WORK/bundles/october-corrected" >/dev/null
index 2026-11-01T00:00:00Z "$WORK/corrected-index.json"
jq -e '(.selected_reports|length)==1 and .selected_reports[0].revision==2' "$WORK/corrected-index.json" >/dev/null

# Reopening the same initial period is ambiguous, even if its amounts happen to agree.
jq '.report_id="competing-initial-statement"' "$fixture" >"$WORK/competing-input.json"
bash "$ROOT/offers/service-report.sh" --input "$WORK/competing-input.json" --output "$WORK/competing.json" >/dev/null
bash "$ROOT/archive.sh" pack --report "$WORK/competing.json" --file "$WORK/competing-input.json" --output "$WORK/bundles/competing" >/dev/null
if index 2026-11-01T00:00:00Z "$WORK/competing-index.json"; then echo 'Accepted competing roots' >&2; exit 1; fi
rm -rf "$WORK/bundles/competing"
printf '\n' >>"$WORK/bundles/october-corrected/correction.json"
if index 2026-11-01T00:00:00Z "$WORK/corrupt-index.json"; then echo 'Accepted changed archived bytes' >&2; exit 1; fi
[[ ! -e "$WORK/corrupt-index.json" ]]
printf '%s\n' 'PASS: monthly continuity, missing months, superseding correction, competing roots and retained-input integrity.'
