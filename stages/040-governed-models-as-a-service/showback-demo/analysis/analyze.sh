#!/usr/bin/env bash
# Offline task economics and capacity-bounded sourcing advice; never prices invoices or calls a model.
# Usage: analyze.sh --input EVIDENCE.json --output NEW-REPORT.json
set -euo pipefail
umask 077
fail() { printf 'Service analysis failed: %s\n' "$*" >&2; exit 2; }
input='' output=''
while (($#)); do
    case "$1" in
        --input) (($# >= 2)) || fail 'missing input'; input=$2; shift 2 ;;
        --output) (($# >= 2)) || fail 'missing output'; output=$2; shift 2 ;;
        *) fail 'Usage: analyze.sh --input EVIDENCE.json --output NEW-REPORT.json' ;;
    esac
done
[[ -f "$input" && -n "$output" ]] || fail 'input and output are required'
[[ ! -e "$output" && ! -L "$output" ]] || fail 'output must be a new file'
for tool in jq shasum link; do command -v "$tool" >/dev/null || fail "$tool is required"; done
work_dir=$(mktemp -d "$(dirname "$output")/.service-analysis.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
cp "$input" "$work_dir/input.json"
# Reject repeated keys/documents before jq's ordinary parser could hide them.
jq -en --stream '
reduce inputs as $e ({closed:{},leaves:0};
 if ($e|length)==2 then $e[0] as $p |
  reduce range(0;($p|length)+1) as $n (.;
   if .closed[($p[0:$n]|tojson)] then error("duplicate key/document") else . end) |
  if ($e[1]|type)=="number" and (($e[1]|isnan) or ($e[1]|isinfinite)) then error("nonfinite") else . end |
  .closed[($p|tojson)]=true | .leaves+=1
 else .closed[($e[0][0:-1]|tojson)]=true end) | select(.leaves>0)' "$work_dir/input.json" >/dev/null || fail 'ambiguous JSON'
input_hash=$(shasum -a 256 "$work_dir/input.json" | awk '{print $1}')
jq --arg hash "$input_hash" '
def require($c;$m): if $c then . else error($m) end;
def id: type=="string" and test("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,200}$");
def user_identity: type=="string" and length<=512 and test("\\S") and (test("[\\x00-\\x1f\\x7f]")|not);
def count: type=="number" and isfinite and floor==. and .>=0 and .<=1000000000;
def cents: type=="number" and isfinite and floor==. and .>=0 and .<=100000000000;
def utc: type=="string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$") and (try ((fromdateiso8601|todateiso8601)==.) catch false);
def summed: add // 0;
def ratio($a;$b): if $b>0 then $a/$b else null end;
require(.schema_version==1 and (.report_id|id);"invalid report identity") |
require(.evidence_kind=="synthetic_fixture" or .evidence_kind=="observed";"unknown evidence kind") |
require(.currency=="USD";"this analysis requires USD; convert separately with evidenced rates") |
require((.period.start|utc) and (.period.end|utc) and .period.start<.period.end;"invalid UTC period") |
require((.acceptance_definition|type)=="string" and (.acceptance_definition|length)>0;"explicit task acceptance definition required") |
require((.evidence_refs|type)=="array" and (.evidence_refs|length)>0 and all(.evidence_refs[];id);"retained usage/outcome/cost evidence references required") |
require((.costs.service_total_cents|cents) and (.costs.workflow_extra_cents|cents) and (.costs.human_rework_cents|cents);"nonnegative integer cost pools required") |
require((.tasks|type)=="array" and all(.tasks[];
 (.task_id|id) and (.user|user_identity) and (.team|id) and (.subscription|id) and (.accepted|type)=="boolean" and
 (.outcome_evidence|id) and (.attempts|type)=="array" and (.attempts|length)>0 and all(.attempts[];
  (.attempt_id|id) and (.model|id) and (.model_profile_ref|id) and (.prompt_version|id) and
  (.receipt_ref|id) and (.service_cost_cents|cents) and
  (.kind=="initial" or .kind=="planned_turn" or .kind=="corrective_retry" or .kind=="fallback")));
 "invalid task/attempt record; HTTP status cannot substitute for an accepted outcome") |
require(([.tasks[].task_id]|unique|length)==(.tasks|length);"duplicate task") |
require(([.tasks[].attempts[].attempt_id]|unique|length)==([.tasks[].attempts[]]|length);"duplicate attempt") |
require(([.tasks[].attempts[].service_cost_cents]|summed)<=.costs.service_total_cents;"attempt costs exceed service pool; do not double count") |
.sourcing as $s |
require(($s.external.fixed_monthly_cents|cents) and ($s.external.minimum_monthly_cents|cents) and
 ($s.external.variable_microusd_per_task|count) and ($s.migration_cost_cents|cents);"invalid sourcing costs") |
require(($s.comparability.quality|type)=="boolean" and ($s.comparability.slo|type)=="boolean" and
 ($s.comparability.privacy|type)=="boolean" and ($s.comparability.evidence_ref|id);"comparison evidence required") |
require(($s.private_steps|type)=="array" and ($s.private_steps|length)>0 and all($s.private_steps[];
 (.id|id) and (.max_tasks|count) and .max_tasks>0 and (.fixed_monthly_cents|cents) and
 (.variable_microusd_per_task|count) and (.peak_qualified|type)=="boolean" and (.evidence_ref|id));"invalid capacity steps") |
require(([$s.private_steps[].id]|unique|length)==($s.private_steps|length) and
 ([$s.private_steps[].max_tasks]|sort|unique)==[$s.private_steps[].max_tasks];"capacity steps must be unique and increasing") |
require(($s.scenarios|type)=="array" and ($s.scenarios|length)>0 and all($s.scenarios[];
 (.name|id) and (.accepted_tasks|count));"invalid demand scenarios") |
require(([$s.scenarios[].name]|unique|length)==($s.scenarios|length);"duplicate scenario") |
# Bound integer products before using jq doubles. Derived ratios are analytical, not ledger amounts.
require(all($s.scenarios[]; .accepted_tasks * $s.external.variable_microusd_per_task <= 4503599627370495) and
 all($s.private_steps[]; .max_tasks * .variable_microusd_per_task <= 4503599627370495);"projection precision bound exceeded") |
($s.comparability.quality and $s.comparability.slo and $s.comparability.privacy) as $comparable |
([if $s.comparability.quality then empty else "quality_not_equivalent" end,
  if $s.comparability.slo then empty else "slo_not_equivalent" end,
  if $s.comparability.privacy then empty else "privacy_not_eligible" end]) as $reasons |
([.tasks[]|select(.accepted)]|length) as $accepted |
(.costs.service_total_cents+.costs.workflow_extra_cents+.costs.human_rework_cents) as $total |
([$s.scenarios[] | . as $d |
  ([$s.private_steps[]|select(.max_tasks >= $d.accepted_tasks)][0] // null) as $p |
  ([$s.external.minimum_monthly_cents,
    ($s.external.fixed_monthly_cents + $d.accepted_tasks * $s.external.variable_microusd_per_task / 10000)]|max) as $external |
  ($comparable and $p!=null and $p.peak_qualified==true) as $eligible |
  (if $eligible then $p.fixed_monthly_cents + $d.accepted_tasks * $p.variable_microusd_per_task / 10000 else null end) as $private |
  {name:$d.name,accepted_tasks:$d.accepted_tasks,external_cost_cents:$external,private_cost_cents:$private,
   capacity_step:($p.id//null),capacity_eligible:$eligible,
   savings_cents:(if $eligible then $external-$private else null end),
   payback_months:(if $eligible and $external>$private then $s.migration_cost_cents/($external-$private) else null end)}]) as $scenarios |
# Solve each capacity interval for both branches of the provider commitment floor.
([range(0;($s.private_steps|length)) as $i | $s.private_steps[$i] as $p |
  (if $i==0 then 0 else $s.private_steps[$i-1].max_tasks+1 end) as $low |
  ($s.external.variable_microusd_per_task/10000) as $e | ($p.variable_microusd_per_task/10000) as $v |
  [{branch:"usage",n:(if $e!=$v then ($p.fixed_monthly_cents-$s.external.fixed_monthly_cents)/($e-$v) else null end)},
   {branch:"commitment_floor",n:(if $v>0 then ($s.external.minimum_monthly_cents-$p.fixed_monthly_cents)/$v else null end)}][] |
  select(.n!=null and .n>=0) |
  {capacity_step:$p.id,branch:.branch,accepted_tasks:.n,
   valid:($comparable and $p.peak_qualified and .n >= $low and .n <= $p.max_tasks and
    (if .branch=="usage" then $s.external.fixed_monthly_cents+$e*.n >= $s.external.minimum_monthly_cents
     else $s.external.fixed_monthly_cents+$e*.n <= $s.external.minimum_monthly_cents end))}]) as $crossings |
{schema_version:1,report_type:"service_advice",report_id:.report_id,evidence_kind:.evidence_kind,
 currency:.currency,period:.period,input_sha256:$hash,evidence_refs:.evidence_refs,
 acceptance_definition:.acceptance_definition,
 calculation_basis:"Analytical estimates from supplied evidence; ratios and projections are not invoice charges.",
 totals:{tasks:(.tasks|length),accepted_tasks:$accepted,attempts:([.tasks[].attempts[]]|length),
  corrective_retries:([.tasks[].attempts[]|select(.kind=="corrective_retry")]|length),
  planned_turns:([.tasks[].attempts[]|select(.kind=="planned_turn")]|length),
  fallbacks:([.tasks[].attempts[]|select(.kind=="fallback")]|length),total_cost_cents:$total,
  cost_per_accepted_task_cents:ratio($total;$accepted),
  service_cost_outside_attempts_cents:(.costs.service_total_cents-([.tasks[].attempts[].service_cost_cents]|summed))},
 tasks:.tasks,costs:.costs,
 sourcing:{eligible:$comparable,reasons:$reasons,assumptions:$s,scenarios:$scenarios,break_even_candidates:$crossings,
  recommendation:(if $comparable|not then "insufficient_comparison_evidence"
    elif any($scenarios[];.capacity_eligible and .savings_cents>0) then "review_private_for_qualified_scenarios"
    else "no_demonstrated_private_savings" end),
  action:"Review sustained demand and representative peak-load evidence with the consumer; no automatic migration."}}
' "$work_dir/input.json" >"$work_dir/report.json" || fail 'invalid or incomplete analysis evidence'
link "$work_dir/report.json" "$output" || fail 'could not create report without overwrite'
printf 'Created service analysis: %s\n' "$output" >&2
