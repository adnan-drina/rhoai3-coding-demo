#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
fixture="$ROOT/fixtures/tasks.json"
run_case() { bash "$ROOT/analyze.sh" --input "$1" --output "$2" >/dev/null 2>&1; }
reject() {
    jq "$1" "$fixture" >"$WORK/bad.json"
    rm -f "$WORK/rejected.json"
    if run_case "$WORK/bad.json" "$WORK/rejected.json"; then echo "Accepted invalid evidence: $1" >&2; exit 1; fi
    [[ ! -e "$WORK/rejected.json" ]]
}
run_case "$fixture" "$WORK/base.json"
jq -e '.totals.total_cost_cents==10500 and .totals.cost_per_accepted_task_cents==10500
 and .totals.corrective_retries==1 and .totals.planned_turns==1 and .totals.fallbacks==1
 and .totals.service_cost_outside_attempts_cents==9730
 and .sourcing.scenarios[0].external_cost_cents==10000
 and .sourcing.scenarios[1].savings_cents==4500
 and .sourcing.scenarios[2].private_cost_cents==23000
 and .sourcing.scenarios[3].private_cost_cents==null
 and any(.sourcing.break_even_candidates[];.branch=="usage" and .accepted_tasks==10000 and .valid)' "$WORK/base.json" >/dev/null
if run_case "$fixture" "$WORK/base.json"; then echo 'Overwrote existing evidence' >&2; exit 1; fi
jq '.tasks[].accepted=false' "$fixture" >"$WORK/none.json"
run_case "$WORK/none.json" "$WORK/none-report.json"
jq -e '.totals.cost_per_accepted_task_cents==null' "$WORK/none-report.json" >/dev/null
jq '.sourcing.comparability.quality=false' "$fixture" >"$WORK/quality.json"
run_case "$WORK/quality.json" "$WORK/quality-report.json"
jq -e '.sourcing.recommendation=="insufficient_comparison_evidence" and all(.sourcing.scenarios[];.private_cost_cents==null)' "$WORK/quality-report.json" >/dev/null
jq '.sourcing.private_steps[].peak_qualified=false' "$fixture" >"$WORK/peak.json"
run_case "$WORK/peak.json" "$WORK/peak-report.json"
jq -e 'all(.sourcing.scenarios[];.capacity_eligible==false) and all(.sourcing.break_even_candidates[];.valid==false)' "$WORK/peak-report.json" >/dev/null
jq '.sourcing.private_steps[].variable_microusd_per_task=20000 | .sourcing.external.minimum_monthly_cents=0' "$fixture" >"$WORK/no-saving.json"
run_case "$WORK/no-saving.json" "$WORK/no-saving-report.json"
jq -e '.sourcing.recommendation=="no_demonstrated_private_savings"' "$WORK/no-saving-report.json" >/dev/null
jq '.tasks[0].user="alice@example.com"' "$fixture" >"$WORK/email-user.json"
run_case "$WORK/email-user.json" "$WORK/email-report.json"
jq -e '.tasks[0].user=="alice@example.com"' "$WORK/email-report.json" >/dev/null
reject '.tasks += [.tasks[0]]'
reject '.tasks[1].attempts[0].attempt_id="a1"'
reject '.costs.service_total_cents=1'
reject '.tasks[0].accepted="HTTP-200"'
reject 'del(.tasks[0].attempts[0].model_profile_ref)'
reject '.sourcing.private_steps |= reverse'
reject '.period.start="2026-02-31T00:00:00Z"'
reject '.sourcing.scenarios[0].accepted_tasks=1000000000 | .sourcing.external.variable_microusd_per_task=1000000000'
printf '%s\n' '{"schema_version":1,"schema_version":1}' >"$WORK/duplicate.json"
if run_case "$WORK/duplicate.json" "$WORK/duplicate-report.json"; then exit 1; fi
printf '%s\n' 'PASS: task outcomes, full costs, commitment floor, capacity steps, no crossover, unknown quality and immutable analysis.'
