#!/usr/bin/env bash
# Offline integration and negative tests; synthetic fixtures only, no HTTP, deployment or inference.
# Usage: stages/040-governed-models-as-a-service/showback-demo/service-views/test-views.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../../.." && pwd)"
WORK=$(mktemp -d)
# Bash 3.2 can reset a fatal unset-variable exit to zero while running an EXIT cleanup.
completed=false
trap 'result=$?; [[ "$completed" == true ]] || result=1; rm -rf "$WORK"; exit "$result"' EXIT
passed=0
pass() { passed=$((passed + 1)); printf 'PASS %s\n' "$1"; }
reject() {
    local description="$1"
    shift
    if "$@" > "$WORK/rejection.log" 2>&1; then printf 'FAIL %s\n' "$description" >&2; exit 1; fi
    pass "$description"
}
money() { awk -v name="$1" '$0 ~ "^" name "\\{" {sum += $NF;found=1} END {if(found) print sum}' "$2"; }
render() { bash "$SCRIPT_DIR/render-report.sh" --report "$1" --output "$2"; }
statement() {
    bash "$SCRIPT_DIR/export-statement.sh" --report "$1" --authorization "$2" --scope "$3" --id "$4" --output-dir "$5"
}
authorize() {
    local report="$1" output="$2" hash
    hash=$(jq -cS . "$report" | shasum -a 256 | awk '{print $1}')
    jq --arg hash "$hash" '.report_sha256=$hash' "$SCRIPT_DIR/fixtures/authorization.json" > "$output"
}
bash "$PACKAGE_DIR/offers/service-report.sh" --input "$PACKAGE_DIR/offers/fixtures/month.json" --output "$WORK/report.json"
bash "$PACKAGE_DIR/analysis/analyze.sh" --input "$PACKAGE_DIR/analysis/fixtures/tasks.json" --output "$WORK/advice.json"
bash "$SCRIPT_DIR/render-report.sh" --report "$WORK/report.json" --output "$WORK/report.prom" \
    --analysis "$WORK/advice.json" --configmap-output "$WORK/selected.yaml"
[[ $(money service_report_charge_cents "$WORK/report.prom") == $(jq '.totals.charge_cents' "$WORK/report.json") ]]
[[ $(money service_consumer_charge_cents "$WORK/report.prom") == $(jq '.totals.charge_cents' "$WORK/report.json") ]]
[[ $(money service_agreement_cost_cents "$WORK/report.prom") == $(jq '.totals.cost_cents' "$WORK/report.json") ]]
pass 'report, consumer rollup and agreement metrics reconcile to canonical cent totals'
[[ $(money service_advice_accepted_tasks "$WORK/report.prom") == 1 ]]
[[ $(money service_advice_cost_per_accepted_task_cents "$WORK/report.prom") == 10500 ]]
! rg '^service_sourcing_savings_cents\{.*capacity_eligible="false"' "$WORK/report.prom" >/dev/null
pass 'optional advice preserves outcome cost and omits infeasible savings'
rg 'price_basis=.+cost|cost_scope=' "$WORK/report.prom" >/dev/null
rg 'rate_version="fixture-(early|late)"' "$WORK/report.prom" >/dev/null
rg '^# TYPE service_.* gauge$' "$WORK/report.prom" >/dev/null
! rg '^# TYPE .* (counter|histogram)' "$WORK/report.prom" >/dev/null
pass 'snapshot identity, rate provenance and gauge-only contract retained'
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$WORK/selected.yaml" > "$WORK/selected.json"
jq -e '.metadata.name=="showback-selected-report" and .metadata.labels["app.kubernetes.io/part-of"]=="observability"
  and (.data["metrics.prom"]|contains("service_report_info"))' "$WORK/selected.json" >/dev/null
pass 'static ConfigMap reuses the stopped publisher with required functional labels'
authorize "$WORK/report.json" "$WORK/access.json"
statement "$WORK/report.json" "$WORK/access.json" user demo-eng "$WORK/user"
jq -e --slurpfile full "$WORK/report.json" 'all(.charge_lines[];.user=="demo-eng")
  and .charge_cents==([$full[0].charge_lines[]|select(.user=="demo-eng")|.charge_cents]|add)
  and (.scope_notice|contains("Team availability"))' "$WORK/user/statement.json" >/dev/null
[[ $(find "$WORK/user" -type f | wc -l | tr -d ' ') == 3 ]]
! rg 'demo-support|SYNTHETIC INVOICE' "$WORK/user" >/dev/null
pass 'user export is scoped, reconciles and excludes fleet report and broader allowlist'
reject 'cross-user export denied' statement "$WORK/report.json" "$WORK/access.json" user demo-support "$WORK/denied-user"
reject 'consumer cannot request a team export' statement "$WORK/report.json" "$WORK/access.json" team engineering "$WORK/denied-team"
jq '.allowed_users="demo-eng-admin"' "$WORK/access.json" > "$WORK/string-users-access.json"
reject 'string user allowlist cannot authorize a substring' statement "$WORK/report.json" \
    "$WORK/string-users-access.json" user demo-eng "$WORK/string-users"
jq '.allowed_teams=null' "$WORK/access.json" > "$WORK/null-teams-access.json"
reject 'both allowlists must be arrays even for a user export' statement "$WORK/report.json" \
    "$WORK/null-teams-access.json" user demo-eng "$WORK/null-teams"
jq '.allowed_users += [""]' "$WORK/access.json" > "$WORK/empty-entry-access.json"
reject 'empty allowlist entries are rejected' statement "$WORK/report.json" \
    "$WORK/empty-entry-access.json" user demo-eng "$WORK/empty-entry"
jq '.principal="marketing-manager"|.role="team_manager"|.allowed_users=[]|.allowed_teams=["marketing"]' \
    "$WORK/access.json" > "$WORK/team-access.json"
statement "$WORK/report.json" "$WORK/team-access.json" team marketing "$WORK/team"
jq -e '.charge_cents==100000 and all(.charge_lines[];.team=="marketing")' "$WORK/team/statement.json" >/dev/null
pass 'team owner sees dedicated availability without fabricated user allocation'
jq '.consumers.eng.user="=demo-eng"' "$PACKAGE_DIR/offers/fixtures/month.json" > "$WORK/formula-input.json"
bash "$PACKAGE_DIR/offers/service-report.sh" --input "$WORK/formula-input.json" --output "$WORK/formula-report.json"
authorize "$WORK/formula-report.json" "$WORK/formula-access-base.json"
jq '.principal="=demo-eng"|.allowed_users=["=demo-eng"]' "$WORK/formula-access-base.json" > "$WORK/formula-access.json"
statement "$WORK/formula-report.json" "$WORK/formula-access.json" user '=demo-eng' "$WORK/formula-statement"
rg '"\x27=demo-eng"' "$WORK/formula-statement/statement.csv" >/dev/null
jq -e '.subject=="=demo-eng"' "$WORK/formula-statement/statement.json" >/dev/null
pass 'CSV protects formula-like string cells while JSON preserves the identity'
reject 'team manager cannot export another team' statement "$WORK/report.json" "$WORK/team-access.json" team support "$WORK/denied-team2"
jq '.allowed_teams="marketing-admin"' "$WORK/team-access.json" > "$WORK/string-teams-access.json"
reject 'string team allowlist cannot authorize a substring' statement "$WORK/report.json" \
    "$WORK/string-teams-access.json" team marketing "$WORK/string-teams"
jq '.allowed_teams += [null]' "$WORK/team-access.json" > "$WORK/null-entry-access.json"
reject 'non-string allowlist entries are rejected' statement "$WORK/report.json" \
    "$WORK/null-entry-access.json" team marketing "$WORK/null-entry"
jq '.report_sha256="wrong"' "$WORK/access.json" > "$WORK/wrong-access.json"
reject 'authorization bound to another report denied' statement "$WORK/report.json" "$WORK/wrong-access.json" user demo-eng "$WORK/wrong"
reject 'statement directory cannot be overwritten' statement "$WORK/report.json" "$WORK/access.json" user demo-eng "$WORK/user"
jq '.role="platform_admin"|.allowed_users=["nonexistent"]' "$WORK/access.json" > "$WORK/no-evidence-access.json"
reject 'authorized subject without evidence cannot become a zero bill' statement "$WORK/report.json" \
    "$WORK/no-evidence-access.json" user nonexistent "$WORK/no-evidence"
jq '(.agreements[]|select(.offer=="external")|.rate_cards[].prices.input_uncached)=null' \
    "$PACKAGE_DIR/offers/fixtures/month.json" > "$WORK/unpriced-input.json"
bash "$PACKAGE_DIR/offers/service-report.sh" --input "$WORK/unpriced-input.json" --output "$WORK/unpriced.json"
render "$WORK/unpriced.json" "$WORK/unpriced.prom"
[[ -z $(money service_report_charge_cents "$WORK/unpriced.prom") ]]
[[ -n $(money service_report_known_charge_cents "$WORK/unpriced.prom") ]]
authorize "$WORK/unpriced.json" "$WORK/unpriced-access.json"
statement "$WORK/unpriced.json" "$WORK/unpriced-access.json" user demo-eng "$WORK/unpriced-user"
jq -e '.charge_cents==null and (.pricing_complete|not) and .known_charge_cents!=null' \
    "$WORK/unpriced-user/statement.json" >/dev/null
pass 'unknown pricing omits full metric and statement totals while preserving known portions'
jq '(.agreements[]|select(.offer=="external")|.usage_coverage)="missing"' \
    "$PACKAGE_DIR/offers/fixtures/month.json" > "$WORK/missing-input.json"
bash "$PACKAGE_DIR/offers/service-report.sh" --input "$WORK/missing-input.json" --output "$WORK/missing.json"
render "$WORK/missing.json" "$WORK/missing.prom"
! rg '^service_agreement_(input_tokens|output_tokens|requests)\{.*offer="external"' "$WORK/missing.prom" >/dev/null
! rg '^service_consumer_charge_cents\{.*offer="external"' "$WORK/missing.prom" >/dev/null
pass 'incomplete usage is not rendered as certified totals or a complete consumer charge'
render "$WORK/report.json" "$WORK/no-advice.prom"
! rg '^service_advice_' "$WORK/no-advice.prom" >/dev/null
pass 'missing analysis does not create zero task outcomes'
jq '.tasks |= map(.accepted=false)' "$PACKAGE_DIR/analysis/fixtures/tasks.json" > "$WORK/no-success-input.json"
bash "$PACKAGE_DIR/analysis/analyze.sh" --input "$WORK/no-success-input.json" --output "$WORK/no-success.json"
bash "$SCRIPT_DIR/render-report.sh" --report "$WORK/report.json" --analysis "$WORK/no-success.json" \
    --output "$WORK/no-success.prom"
[[ $(money service_advice_accepted_tasks "$WORK/no-success.prom") == 0 ]]
[[ -z $(money service_advice_cost_per_accepted_task_cents "$WORK/no-success.prom") ]]
pass 'zero accepted tasks yields no cost-per-success value'
jq '(.cost_items[]|select(.id=="dedicated-compute")|.usd_per_hour)="0"
  | (.cost_items[]|select(.id=="dedicated-ops")|.amount_usd)="0"' \
    "$PACKAGE_DIR/offers/fixtures/month.json" > "$WORK/zero-cost-input.json"
bash "$PACKAGE_DIR/offers/service-report.sh" --input "$WORK/zero-cost-input.json" --output "$WORK/zero-cost.json"
render "$WORK/zero-cost.json" "$WORK/zero-cost.prom"
rg '^service_agreement_cost_cents\{.*offer="dedicated".* 0$' "$WORK/zero-cost.prom" >/dev/null
! rg '^service_agreement_recovery_(before|after)_subsidy_ratio\{.*offer="dedicated"' "$WORK/zero-cost.prom" >/dev/null
pass 'measured zero cost is explicit while recovery ratios remain undefined'
jq '.totals.known_charge_cents+=1' "$WORK/report.json" > "$WORK/bad.json"
cp "$WORK/report.prom" "$WORK/before.prom"
reject 'nonconserving report rejected' render "$WORK/bad.json" "$WORK/report.prom"
cmp "$WORK/report.prom" "$WORK/before.prom"
pass 'failed rendering preserves previously selected report atomically'
jq '.report_id="synthetic-offers-selected-replacement"' "$WORK/report.json" > "$WORK/replacement.json"
render "$WORK/replacement.json" "$WORK/report.prom"
rg 'report_id="synthetic-offers-selected-replacement"' "$WORK/report.prom" >/dev/null
! rg 'report_id="synthetic-offers-2026-10-v1"' "$WORK/report.prom" >/dev/null
cp "$WORK/report.prom" "$WORK/replaced.prom"
render "$WORK/replacement.json" "$WORK/report.prom"
cmp "$WORK/replaced.prom" "$WORK/report.prom"
pass 'reselection replaces all identities atomically and repeated rendering is deterministic'
reject 'output cannot overwrite input' render "$WORK/report.json" "$WORK/report.json"
ln -s "$WORK/report.json" "$WORK/alias.json"
reject 'symlink input/output alias rejected' render "$WORK/report.json" "$WORK/alias.json"
printf '{}\n' > "$WORK/empty.json"
reject 'empty report cannot become a valid zero snapshot' render "$WORK/empty.json" "$WORK/empty.prom"
printf '{"schema_version":1,"schema_version":2}\n' > "$WORK/duplicates.json"
reject 'ambiguous duplicate keys rejected' render "$WORK/duplicates.json" "$WORK/duplicates.prom"
jq '.period.start="2026-09-01T00:00:00Z"' "$WORK/advice.json" > "$WORK/wrong-advice.json"
reject 'advice period mismatch rejected' bash "$SCRIPT_DIR/render-report.sh" --report "$WORK/report.json" \
    --analysis "$WORK/wrong-advice.json" --output "$WORK/wrong.prom"
bash "$SCRIPT_DIR/generate-dashboards.sh" --check || { printf '%s\n' 'FAIL dashboard generator check' >&2; exit 1; }
kustomize build "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo/service-views" > "$WORK/dashboards.yaml" || {
    printf '%s\n' 'FAIL service dashboard render' >&2; exit 1;
}
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' \
    < "$WORK/dashboards.yaml" > "$WORK/dashboards.json"
jq -e 'length==5 and all(.[];.kind=="PersesDashboard" and .metadata.labels["app.kubernetes.io/part-of"]=="observability"
    and (.spec.config.variables|length)==0 and (.spec.config.display.description|contains("PLATFORM ONLY")))' \
    "$WORK/dashboards.json" >/dev/null
jq -e 'all(.[]|.spec.config.panels[];.spec.plugin.kind=="StatChart" and .spec.plugin.spec.calculation=="last")' \
    "$WORK/dashboards.json" >/dev/null
! rg 'sum_over_time\(|increase\(|rate\(' "$WORK/dashboards.yaml" >/dev/null
! rg 'kind: (Deployment|Service|RoleBinding|ClusterRoleBinding)' "$WORK/dashboards.yaml" >/dev/null
pass 'five detached platform dashboards render with current gauges and no fabricated access or server'
printf '%s service-view tests passed. Synthetic offline validation only.\n' "$passed"
completed=true
