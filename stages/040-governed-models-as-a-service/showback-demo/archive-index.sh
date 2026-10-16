#!/usr/bin/env bash
# Offline monthly archive continuity and correction selection; no upload, cleanup or scheduler.
# Usage: archive-index.sh --bundles DIR --start UTC-MONTH --end UTC-MONTH --output NEW.json
set -euo pipefail
umask 077
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fail() { printf 'Archive index failed: %s\n' "$*" >&2; exit 2; }
bundles='' start='' end='' output=''
while (($#)); do
    case "$1" in
        --bundles) (($#>=2)) || fail 'missing bundles'; bundles=$2; shift 2 ;;
        --start) (($#>=2)) || fail 'missing start'; start=$2; shift 2 ;;
        --end) (($#>=2)) || fail 'missing end'; end=$2; shift 2 ;;
        --output) (($#>=2)) || fail 'missing output'; output=$2; shift 2 ;;
        *) fail 'Usage: archive-index.sh --bundles DIR --start UTC-MONTH --end UTC-MONTH --output NEW.json' ;;
    esac
done
[[ -d "$bundles" && -n "$start" && -n "$end" && -n "$output" ]] || fail 'all arguments required'
[[ ! -e "$output" && ! -L "$output" ]] || fail 'refusing to replace an index'
for tool in jq shasum link; do command -v "$tool" >/dev/null || fail "$tool is required"; done
work=$(mktemp -d "$(dirname "$output")/.showback-index.XXXXXX")
trap 'rm -rf "$work"' EXIT
: >"$work/entries.jsonl"
# Work from one private copy so verification, hashes and selection use the same bytes.
mkdir "$work/bundles"
for source_directory in "$bundles"/*; do
    [[ -d "$source_directory" && ! -L "$source_directory" ]] || continue
    cp -R "$source_directory" "$work/bundles/"
done
for directory in "$work/bundles"/*; do
    [[ -d "$directory" && ! -L "$directory" ]] || continue
    [[ -f "$directory/manifest.json" ]] || fail 'unfinished bundle in archive root'
    "$ROOT/archive.sh" verify "$directory" > /dev/null
    report_file=$(jq -r '.report_file' "$directory/manifest.json")
    "$ROOT/offers/service-report.sh" --check-report "$directory/$report_file" > /dev/null
    manifest_hash=$(shasum -a 256 "$directory/manifest.json" | awk '{print $1}')
    report_hash=$(shasum -a 256 "$directory/$report_file" | awk '{print $1}')
    # The exact input document must be recoverable, not merely named in a report.
    jq -e --slurpfile report "$directory/$report_file" '
      any(.files[]; .sha256 == $report[0].input_sha256)' "$directory/manifest.json" >/dev/null || fail 'missing exact statement input in bundle'
    jq -n --arg path "$(basename "$directory")" --arg mh "$manifest_hash" --arg rh "$report_hash" \
      --slurpfile manifest "$directory/manifest.json" --slurpfile report "$directory/$report_file" \
      '{bundle:$path,manifest_sha256:$mh,report_sha256:$rh,manifest:$manifest[0],report:$report[0]}' >>"$work/entries.jsonl"
done
jq -s --arg start "$start" --arg end "$end" '
def require($c;$m): if $c then . else error($m) end;
def month: type=="string" and test("^[0-9]{4}-(0[1-9]|1[0-2])-01T00:00:00Z$");
def mi: (.[0:4]|tonumber)*12+(.[5:7]|tonumber)-1;
def month_text:
  ((./12|floor)|tostring) as $y | ((.%12)+1|tostring) as $m |
  $y+"-"+(if ($m|length)==1 then "0"+$m else $m end)+"-01T00:00:00Z";
require(($start|month) and ($end|month) and $start<$end;"expected UTC calendar-month bounds") |
require(length>0;"no archived statements") |
require(([.[].manifest_sha256]|unique|length)==length;"duplicate archive bundle") |
require(([.[].report.report_id]|unique|length)==length;"duplicate report identity") |
require(([.[].report.evidence_kind]|unique|length)==1 and ([.[].report.currency]|unique|length)==1 and
 ([.[].report.cost_scope]|unique|length)==1;"incompatible evidence/currency/cost scopes") |
require(all(.[];.report.scope=="service-offers" and (.report.period.start|month) and (.report.period.end|month) and
 (.report.period.end|mi)==((.report.period.start|mi)+1));"only one-calendar-month service statements can be indexed") |
require(all(.[]; .report.start==.report.period.start and .report.end==.report.period.end and
 .manifest.predecessor_manifest_sha256!=.manifest_sha256);"archive/report identity mismatch") |
. as $all |
require(all(.[]; . as $row |
 if .manifest.predecessor_manifest_sha256==null then
   .report.revision==1 and .report.previous_report_sha256==null and .report.supersedes_report_id==null
 else
   [$all[]|select(.manifest_sha256==$row.manifest.predecessor_manifest_sha256)] as $parent |
   ($parent|length)==1 and $parent[0].report.period==$row.report.period and
   $parent[0].report_sha256==$row.report.previous_report_sha256 and
   $parent[0].report.report_id==$row.report.supersedes_report_id and
   $row.report.revision==($parent[0].report.revision+1)
 end);"broken report/archive correction chain") |
require(all(.[]; .manifest_sha256 as $h |
 ([$all[]|select(.manifest.predecessor_manifest_sha256==$h)]|length)<=1);"forked corrections require operator resolution") |
(group_by(.report.period.start) | map(. as $group |
 require(([.[]|select(.manifest.predecessor_manifest_sha256==null)]|length)==1;"multiple or missing initial statements") |
 (sort_by(.report.revision)) as $ordered |
 require([$ordered[].report.revision]==[range(1;($ordered|length)+1)];"disconnected or cyclic correction chain") |
 $ordered[-1] | {start:.report.period.start,end:.report.period.end,report_id:.report.report_id,
 revision:.report.revision,complete:.report.complete,statement_status:.report.statement_status,
 unreconciled_invoices:[.report.agreements[]|select(.offer=="external" and .invoice_reconciled!=true)|
   {agreement_id:.id,invoice_difference_cents}],
 bundle,manifest_sha256,report_sha256,report_file:.manifest.report_file})) as $selected |
([range(($start|mi);($end|mi))|month_text]) as $expected |
([$selected[]|select(.start >= $start and .end <= $end)]) as $included |
([$expected[] as $m|select(any($included[];.start==$m)|not)|$m]) as $missing |
{schema_version:1,scope:"service-offers",start:$start,end:$end,
 currency:$all[0].report.currency,evidence_kind:$all[0].report.evidence_kind,cost_scope:$all[0].report.cost_scope,
 continuity_complete:($missing|length==0),
 statements_closed_complete:(($missing|length==0) and all($included[];.complete and .statement_status=="closed")),
 invoice_reconciliation_complete:(($missing|length==0) and all($included[];(.unreconciled_invoices|length)==0)),
 financially_complete:(($missing|length==0) and all($included[];.complete and .statement_status=="closed" and (.unreconciled_invoices|length)==0)),
 missing_months:$missing,selected_reports:$included,
 excluded_periods:[$selected[]|select(.start<$start or .end>$end)|{start,end,report_id}],
 retention_days_requested:400,retention_enforced:false,
 note:"Index selects one correction chain per month. It proves retained-file continuity, not completeness of unobserved requests or enforced storage retention."}
' "$work/entries.jsonl" >"$work/index.json" || fail 'archive continuity validation failed'
link "$work/index.json" "$output" || fail 'could not create index without overwrite'
printf 'Created archive continuity index: %s\n' "$output" >&2
