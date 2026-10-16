#!/usr/bin/env bash
# Produce an immutable private JSON/CSV/Markdown statement directory from a report-bound operator authorization record.
# Offline filtering only: the trusted operator verifies identity/authority first. This is not an authentication service.
# Usage: stages/040-governed-models-as-a-service/showback-demo/service-views/export-statement.sh --report FILE --authorization FILE --scope user|team --id ID --output-dir NEW_DIRECTORY
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
source "$SCRIPT_DIR/report-lib.sh"
REPORT= AUTHORIZATION= SCOPE= SUBJECT= OUTPUT=
while [[ $# -gt 0 ]]; do
    case "$1" in
        --report) REPORT=${2:?}; shift 2 ;;
        --authorization) AUTHORIZATION=${2:?}; shift 2 ;;
        --scope) SCOPE=${2:?}; shift 2 ;;
        --id) SUBJECT=${2:?}; shift 2 ;;
        --output-dir) OUTPUT=${2:?}; shift 2 ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
[[ -n "$REPORT" && -n "$AUTHORIZATION" && -n "$SUBJECT" && -n "$OUTPUT" ]] || {
    log_error 'Report, authorization, scope, subject and output directory are required'; exit 1;
}
[[ "$SCOPE" == user || "$SCOPE" == team ]] || { log_error 'Scope must be user or team'; exit 1; }
[[ ! -e "$OUTPUT" && ! -L "$OUTPUT" ]] || { log_error 'Refusing to overwrite a statement directory'; exit 1; }
umask 077
mkdir -p "$(dirname "$OUTPUT")"
WORK=$(mktemp -d "$(dirname "$OUTPUT")/.statement.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
snapshot_json "$REPORT" "$WORK/report.json"
snapshot_json "$AUTHORIZATION" "$WORK/authorization.json"
validate_report "$WORK/report.json"
report_hash=$(json_sha256 "$WORK/report.json")
PROGRAM=$(cat <<'JQ'
def check($ok;$message): if $ok then . else error($message) end;
def text: type == "string" and length > 0;
. as $r | $authorization[0] as $auth
| check($auth.schema_version == 1 and $auth.report_sha256 == $report_hash
    and all([$auth.principal,$auth.verified_by,$auth.authorization_evidence,$auth.verified_at][];text);
    "Authorization must identify a verified principal and this exact report")
| check(($auth.verified_at|fromdateiso8601)>0;"Invalid authorization timestamp")
| check(all([$auth.allowed_users,$auth.allowed_teams][];type == "array" and all(.[];text));
    "Authorization allowlists must be arrays of nonempty strings")
| check(if $scope == "user" then
    ($auth.role == "consumer" and $auth.principal == $subject and ($auth.allowed_users|index($subject)) != null)
    or ($auth.role == "platform_admin" and ($auth.allowed_users|index($subject)) != null)
  else ($auth.role == "team_manager" or $auth.role == "platform_admin")
    and ($auth.allowed_teams|index($subject)) != null end;"Requested subject is not authorized")
| [.charge_lines[] | select(.[$scope] == $subject)] as $lines
| check(($lines|length)>0;"No attributable charge evidence for requested subject; do not invent zero")
| (all($lines[];.charge_cents != null) and all($lines[];.agreement_id as $id
    | any($r.agreements[];.id == $id and .pricing_complete))) as $priced
| {schema_version:1,report_type:"service_statement",report_id:$r.report_id,revision:$r.revision,
   report_sha256:$report_hash,scope:$scope,subject:$subject,period:$r.period,currency:$r.currency,
   evidence_kind:$r.evidence_kind,statement_status:$r.statement_status,policy_version:$r.policy_version,
   price_basis:$r.price_basis,cost_scope:$r.cost_scope,report_complete:$r.complete,
   pricing_complete:$priced,known_charge_cents:([$lines[].charge_cents // empty]|add // 0),
   charge_cents:(if $priced then ([$lines[].charge_cents]|add) else null end),
   authorization:{principal:$auth.principal,role:$auth.role,verified_by:$auth.verified_by,
     verified_at:$auth.verified_at,authorization_evidence:$auth.authorization_evidence},
   charge_lines:$lines,
   scope_notice:(if $scope == "user" then
     "Only charges explicitly attributed to this user. Team availability/reservation fees are excluded, not redistributed."
     else "Only charges explicitly attributed to this team. Platform/unassigned charges and other teams are excluded." end)}
JQ
)
jq --arg report_hash "$report_hash" --arg scope "$SCOPE" --arg subject "$SUBJECT" \
    --slurpfile authorization "$WORK/authorization.json" "$PROGRAM" "$WORK/report.json" > "$WORK/statement.json"
CSV_PROGRAM=$(cat <<'JQ'
def cell: if type == "string" and test("^[=+@\t\r-]") then "'"+. else . end;
["report_id","scope","subject","currency","agreement","offer","model","category","kind",
 "quantity","unit","rate_usd","rate_version","charge_cents","coverage"],
(. as $s | .charge_lines[] | [$s.report_id,$s.scope,$s.subject,$s.currency,.agreement_id,.offer,.model,
 .category,.kind,.quantity,.unit,.rate_usd,.rate_version,.charge_cents,.coverage]) | map(cell)|@csv
JQ
)
jq -r "$CSV_PROGRAM" "$WORK/statement.json" > "$WORK/statement.csv"
MARKDOWN_PROGRAM=$(cat <<'JQ'
def clean: tostring|gsub("[\r\n|\u0060]";" ");
"# Service statement — \(.evidence_kind|clean)","",
"Report: \(.report_id|clean), revision \(.revision|clean), status **\(.statement_status|clean)**.",
"Period: \(.period.start|clean) to \(.period.end|clean), \(.period.timezone|clean).",
"Scope: \(.scope|clean) **\(.subject|clean)**. Currency: \(.currency|clean).",
"Price basis: \(.price_basis|clean). Cost scope: \(.cost_scope|clean). Policy: \(.policy_version|clean).","",
"Charge: \(if .charge_cents == null then "UNKNOWN; known portion "+(.known_charge_cents|tostring)
  else (.charge_cents|tostring) end) cents. Report complete: \(.report_complete).","",.scope_notice,"",
"| Offer | Model | Category | Rate version | Charge (cents) |",
"|---|---|---|---|---:|",
(.charge_lines[]|"| \(.offer|clean) | \(.model|clean) | \(.category|clean) | \(.rate_version|clean) | \(.charge_cents // "unknown") |"),
"","The JSON and CSV retain quantities, rates and coverage. This offline export is not an authenticated web service."
JQ
)
jq -r "$MARKDOWN_PROGRAM" "$WORK/statement.json" > "$WORK/statement.md"
# Do not deliver the full fleet report or the broader authorization allowlist with a scoped statement.
rm "$WORK/report.json" "$WORK/authorization.json"
# Reserve the new destination atomically, so concurrent writers cannot overwrite or nest an export.
mkdir "$OUTPUT"
mv "$WORK/statement.json" "$WORK/statement.csv" "$WORK/statement.md" "$OUTPUT/"
