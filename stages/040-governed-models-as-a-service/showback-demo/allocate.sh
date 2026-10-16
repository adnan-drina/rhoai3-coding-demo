#!/usr/bin/env bash
# Offline: allocate evidenced hosting costs and create new private JSON/CSV reports.
# Safe to replay to new paths; existing evidence is never replaced. No network or cluster reads.
# Usage: allocate.sh --input EVIDENCE.json --output REPORT.json [--csv REPORT.csv]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077

usage() {
    echo 'Usage: allocate.sh --input EVIDENCE.json --output REPORT.json [--csv REPORT.csv]' >&2
    exit 2
}
fail() { echo "Allocation failed: $*" >&2; exit 2; }
input=''
output=''
csv=''
while (($#)); do
    case "$1" in
        --input) (($# >= 2)) || usage; input=$2; shift 2 ;;
        --output) (($# >= 2)) || usage; output=$2; shift 2 ;;
        --csv) (($# >= 2)) || usage; csv=$2; shift 2 ;;
        -h|--help) usage ;;
        *) usage ;;
    esac
done
[[ -n "$input" && -n "$output" ]] || usage
command -v jq >/dev/null || fail 'jq is required'
command -v link >/dev/null || fail 'the POSIX link utility is required for atomic evidence creation'
[[ -f "$input" ]] || fail 'input file does not exist'
output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"
[[ ! -e "$output" && ! -L "$output" ]] || fail 'refusing to replace existing evidence'
if [[ -n "$csv" ]]; then
    csv="$(cd "$(dirname "$csv")" && pwd)/$(basename "$csv")"
    [[ "$csv" != "$output" ]] || fail 'JSON and CSV output paths must differ'
    [[ ! -e "$csv" && ! -L "$csv" ]] || fail 'refusing to replace existing CSV evidence'
fi

# jq's normal object parser keeps the last duplicate key. Stream paths also expose
# closed containers, so reject duplicate keys before normal parsing (including
# duplicated objects whose descendants differ), multiple documents and NaN/Inf.
JSON_CHECK=$(cat <<'JQ'
reduce inputs as $event ({closed:{}, leaves:0};
  if ($event|length)==2 then
    $event[0] as $path |
    reduce range(0; ($path|length)+1) as $n (. ;
      if .closed[($path[0:$n]|tojson)] then error("duplicate JSON object key or document") else . end) |
    if ($event[1]|type)=="number" and (($event[1]|isnan) or ($event[1]|isinfinite))
      then error("non-finite JSON number") else . end |
    .closed[($path|tojson)]=true | .leaves += 1
  else .closed[($event[0][0:-1]|tojson)]=true end)
| if .leaves==0 then error("empty JSON evidence") else true end
JQ
)
jq -en --stream "$JSON_CHECK" "$input" >/dev/null || fail 'invalid or duplicate-key JSON evidence'

# Rational numerators and denominators are reduced integers. Every addition and
# multiplication is checked BEFORE it happens. jq uses IEEE doubles; keeping
# components <= 2^52-1 leaves exact-integer headroom for division checks. Raw
# hosting costs remain exact. Consumer shares are rounded to 1e-9 cent before
# carry, using integer long division; the <= 0.5e-9 cent/window error is reported.
# This prevents coprime token totals from growing carry denominators without bound.
# Decimal strings are display-only (18 fractional places); fractions are retained.
ACCOUNTING_JQ=$(cat <<'JQ'
def limit: 4503599627370495;
def require($test;$message): if $test then . else error($message) end;
def text_ok: type=="string" and test("\\S");
def integer: type=="number" and (isfinite) and floor==. and fabs<=limit;
def count: integer and .>=0;
def checked: if integer then . else error("exact integer precision bound exceeded") end;
def iadd($a;$b):
  if ($b>0 and $a>limit-$b) or ($b<0 and $a<(-limit)-$b)
  then error("exact rational precision bound exceeded; no approximate money emitted") else $a+$b end;
def idiv($a;$b):
  ($a/$b|floor) as $q | ($q*$b) as $p |
  if $p>$a then $q-1 elif $p+$b<=$a then $q+1 else $q end;
def imul($a;$b):
  if $a==0 or $b==0 then 0
  elif ($a|fabs)>idiv(limit;($b|fabs)) then error("exact rational precision bound exceeded; no approximate money emitted")
  else $a*$b end;
def gcd($a;$b): if $b==0 then $a else gcd($b;($a%$b)) end;
def rational($n;$d):
  $n|checked|. as $num | $d|checked|. as $den |
  if $den<=0 then error("invalid rational denominator")
  elif $num==0 then [0,1] else gcd(($num|fabs);$den) as $g | [$num/$g,$den/$g] end;
def add($a;$b):
  gcd($a[1];$b[1]) as $g | ($a[1]/$g) as $left | ($b[1]/$g) as $right |
  rational(iadd(imul($a[0];$right);imul($b[0];$left));imul($left;$b[1]));
def neg($a): [-$a[0],$a[1]];
def subtract($a;$b): add($a;neg($b));
def multiply($a;$b):
  gcd(($a[0]|fabs);$b[1]) as $g | gcd(($b[0]|fabs);$a[1]) as $h |
  rational(imul($a[0]/$g;$b[0]/$h);imul($a[1]/$h;$b[1]/$g));
def sum_int: reduce .[] as $n (0;iadd(.;$n));
def sum_rat: reduce .[] as $n ([0,1];add(.;$n));
def money_rate:
  require(type=="string";"rates must be decimal strings") |
  require(test("^[0-9]+(\\.[0-9]{1,12})?$");"invalid rate; use a nonnegative decimal string with at most 12 fractional digits") |
  split(".") as $p | ($p[1]//"") as $fraction |
  (($p[0]+$fraction)|sub("^0+";"")|if .=="" then "0" else . end) as $digits |
  require(($digits|length)<16 or (($digits|length)==16 and $digits<=(limit|tostring));"rate exceeds exact precision") |
  rational(($digits|tonumber);pow(10;($fraction|length)));
def decimal_step($remainder;$denominator):
  if $remainder<=450359962737049 then ($remainder*10) as $scaled |
    idiv($scaled;$denominator) as $digit | {digit:$digit,remainder:($scaled-$digit*$denominator)}
  else reduce range(0;10) as $unused ({digit:0,remainder:0};
    if .remainder >= $denominator-$remainder
    then .remainder -= ($denominator-$remainder) | .digit += 1
    else .remainder += $remainder end) end;
def decimal($r):
  ($r[0]|fabs) as $n | $r[1] as $d | idiv($n;$d) as $whole |
  reduce range(0;18) as $unused ({remainder:($n-$whole*$d),fraction:""};
    if .remainder==0 then . else decimal_step(.remainder;$d) as $step |
      .fraction += ($step.digit|tostring) | .remainder=$step.remainder end) |
  (if $r[0]<0 then "-" else "" end)+($whole|tostring)+
    (if .fraction=="" then "" else "."+.fraction end);
def quantize_share($r):
  # Round an exact, nonnegative cent share to the nearest 1e-9 cent. Long
  # division avoids multiplying a potentially large numerator by 1e9.
  idiv($r[0];$r[1]) as $whole |
  (reduce range(0;9) as $unused ({remainder:($r[0]-$whole*$r[1]),units:0};
    decimal_step(.remainder;$r[1]) as $step |
    .units=iadd(imul(.units;10);$step.digit) | .remainder=$step.remainder)) as $fraction |
  decimal_step($fraction.remainder;$r[1]) as $round |
  rational(iadd(iadd(imul($whole;1000000000);$fraction.units);(if $round.digit>=5 then 1 else 0 end));1000000000);
def utc:
  require(type=="string";"UTC timestamp required") |
  capture("^(?<base>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\\.(?<fraction>[0-9]{1,3}))?(?:Z|\\+00:00)$") as $p |
  if $p==null then error("timestamp must use UTC and at most milliseconds") else . end |
  (($p.base+"Z")|fromdateiso8601) as $seconds |
  require(($seconds|strftime("%Y-%m-%dT%H:%M:%S"))==$p.base;"invalid calendar timestamp") |
  imul($seconds;1000) as $whole | iadd($whole;(($p.fraction//""|. + "000"|.[0:3])|tonumber));
def parse_utc: . as $value | [utc] | if length!=1 then error("invalid UTC timestamp: \($value)") else .[0] end;
def iso($ms):
  idiv($ms;1000) as $sec | ($ms-$sec*1000) as $fraction |
  ($sec|strftime("%Y-%m-%dT%H:%M:%S"))+
    (if $fraction==0 then "" else "."+(("000"+($fraction|tostring))|.[-3:]) end)+"Z";
def counts:
  require(type=="object";"token counts must be subscription-to-integer objects") |
  require(all(to_entries[]; (.key|text_ok) and (.value|count));"token counts must be nonnegative exact integers");
def demo_team($name): if ["engineering","marketing","support"]|index($name) then $name else "other_consumers" end;
def receipt_fields: ["receipt_input_tokens","receipt_output_tokens","request_counts","error_counts","quota_rejections"];
def apportion($raw;$budget;$carry):
  ($raw|keys|map(select($raw[.][0]>0))) as $active |
  if ($active|length)==0 then
    if $budget!=0 then error("zero-cost pool cannot receive rounded cents")
    else {allocated:($raw|map_values(0)),carry:$carry} end
  else
    (reduce $active[] as $key ({};.[$key]=add($raw[$key];($carry[$key]//[0,1])))) as $targets |
    (reduce $active[] as $key ({};.[$key]=([0,idiv($targets[$key][0];$targets[$key][1])]|max))) as $initial |
    {allocated:$initial,difference:($budget-($initial|sum_int))} |
    until(.difference==0;
      . as $state | (if .difference>0 then 1 else -1 end) as $direction |
      (reduce $active[] as $key (null;
        if $direction<0 and $state.allocated[$key]==0 then .
        else subtract([$state.allocated[$key],1];$targets[$key]) as $deficit |
          if .==null then {key:$key,deficit:$deficit}
          elif (subtract($deficit;.deficit)[0]*$direction)<0 then {key:$key,deficit:$deficit} else . end end)) as $best |
      .allocated[$best.key]+=$direction | .difference-=$direction) |
    .allocated as $allocated |
    {allocated:(reduce ($raw|keys[]) as $key ({};.[$key]=($allocated[$key]//0))),
     carry:(reduce $active[] as $key ($carry;.[$key]=subtract($targets[$key];[$allocated[$key],1])))}
  end;
def validate:
  require(type=="object" and .schema_version==1;"schema_version must be 1") |
  require((.report_id|text_ok) and (.scope|text_ok);"report_id and scope are required") |
  require(.policy_version=="model-window-token-share-v1";"unsupported policy_version") |
  require(.evidence_kind=="synthetic_fixture" or .evidence_kind=="observed";"invalid evidence_kind") |
  require(.currency=="USD";"currency must be USD") |
  require((.models|type)=="array" and (.models|length)>0 and all(.models[];text_ok);"models must be nonempty IDs") |
  require((.models|length)==(.models|unique|length);"duplicate model IDs") | .models|=sort |
  require((.subscriptions|type)=="object" and (.subscriptions|length)>0;"known subscriptions required") |
  require(all(.subscriptions|to_entries[]; .value as $team | (.key|text_ok) and ($team|text_ok) and
    (["platform_idle","unresolved_allocation","platform_shared_overhead"]|index($team)|not));"invalid subscription identity") |
  require((.rates|type)=="object";"rates must be an object") |
  . as $data | ._prices=(reduce (.rates|to_entries[]) as $rate ({};
    require(($rate.key|text_ok) and ($rate.value|type)=="object";"invalid rate entry") |
    require(($rate.value|has("currency")|not) or $rate.value.currency=="USD";"rate currency must be USD when supplied") |
    .[$rate.key]=(if $rate.value.usd_per_hour==null then null else
      require($rate.value.source|text_ok;"known rate requires source") | $rate.value.usd_per_hour|money_rate end))) |
  require((.windows|type)=="array" and (.windows|length)>0;"windows must be nonempty") |
  .windows |= map(
    require((.id|text_ok) and (.phase|text_ok);"window id and phase required") |
    ._start=(.start|parse_utc) | ._end=(.end|parse_utc) |
    require(._end>._start;"windows must have positive duration") |
    require((.usage|type)=="object" and (.usage|keys)==$data.models;"window must explicitly cover every model") |
    .usage |= with_entries(.value |= (
      .coverage as $coverage | require(["complete","missing_usage","partial_period"]|index($coverage);"invalid coverage") |
      .tokens |= counts | . as $usage |
      require(.coverage!="complete" or all(.tokens|keys[]; $data.subscriptions[.]!=null);"unknown subscription identity") |
      reduce ["input_tokens","output_tokens"][] as $field (. ;
        if has($field) then .[$field]|=counts |
          require(all(.[$field]|to_entries[]; $usage.tokens[.key]!=null and .value<=$usage.tokens[.key]);"token detail exceeds total")
        else . end) |
      require((has("input_tokens") and has("output_tokens")|not) or
        all((.input_tokens//{})|keys[]; . as $key | $usage.output_tokens[$key]==null or
          iadd($usage.input_tokens[$key];$usage.output_tokens[$key])==$usage.tokens[$key]);"input/output tokens mismatch") |
      reduce receipt_fields[] as $field (. ; if has($field) then .[$field]|=counts |
        require(.coverage!="complete" or all(.[$field]|keys[];$data.subscriptions[.]!=null);"unknown receipt identity") else . end)))) |
  .windows |= sort_by(._start,.id) |
  require((.windows|map(.id)|unique|length)==(.windows|length);"duplicate window IDs") |
  . as $validated |
  require(all(range(1;(.windows|length)); . as $i | $validated.windows[$i-1]._end==$validated.windows[$i]._start);
    "windows must be a contiguous non-overlapping partition") |
  require((.instance_intervals|type)=="array" and (.instance_intervals|length)>0;"explicit instance lifecycle evidence required") |
  .instance_intervals |= map(
    require(all([.instance_id,.model,.rate_id,.source][];text_ok);"instance identity/model/rate/source required") |
    .model as $model | require($data.models|index($model);"unknown interval model") |
    ._start=(.start|parse_utc) | ._end=(.end|parse_utc) | require(._end>._start;"invalid instance duration")) |
  (.instance_intervals|sort_by(.instance_id,._start,._end)) as $by_instance |
  require(all(range(1;($by_instance|length)); . as $i |
    $by_instance[$i-1].instance_id!=$by_instance[$i].instance_id or $by_instance[$i-1]._end<=$by_instance[$i]._start);
    "overlapping assignments for one instance") |
  .instance_intervals |= sort_by(._start,.instance_id,._end) |
  . as $validated | .windows[0]._start as $first | .windows[-1]._end as $last |
  reduce .models[] as $model (. ;
    (reduce $validated.instance_intervals[] as $interval ($first;
      if $interval.model==$model and $interval._start<=. and $interval._end>. then $interval._end else . end)) as $cursor |
    require($cursor>=$last;"instance lifecycle coverage gap; absence is not zero cost"));
def interval_cost($interval;$start;$end;$prices):
  if $prices[$interval.rate_id]==null then null
  else multiply($prices[$interval.rate_id];rational($end-$start;3600000)) end;
def pools($window;$data):
  reduce $data.models[] as $model ({};
    .[$model]=(
      reduce $data.instance_intervals[] as $interval ({raw:[0,1],duration:0,missing:[]};
        if $interval.model!=$model or $interval._start>=$window._end or $interval._end<=$window._start then .
        else ([$interval._start,$window._start]|max) as $start | ([$interval._end,$window._end]|min) as $end |
          .duration=iadd(.duration;$end-$start) | interval_cost($interval;$start;$end;$data._prices) as $cost |
          if $cost==null then .missing += [{instance_id:$interval.instance_id,rate_id:$interval.rate_id,
            start:iso($start),end:iso($end)}] else .raw=add(.raw;$cost) end end)));
def weights($usage;$priced;$data):
  if $usage.coverage!="complete" or ($priced|not) then {unresolved_allocation:1}
  elif ($usage.tokens|sum_int)==0 then {platform_idle:1}
  else reduce ($usage.tokens|to_entries[]) as $token ({};
    demo_team($data.subscriptions[$token.key]) as $team | .[$team]=iadd((.[$team]//0);$token.value)) end;
def render_model($model;$pool;$usage;$cents;$model_carry;$consumer_carry;$carry_counts;$data):
  (($pool.missing|length)==0) as $priced | ($usage.coverage=="complete") as $complete |
  ($usage.tokens|sum_int) as $tokens | weights($usage;$priced;$data) as $weights | ($weights|sum_int) as $weight_total |
  (reduce ($weights|to_entries[]|select(.value>0)) as $weight ({};
    .[$weight.key]=multiply(multiply($pool.raw;[100,1]);rational($weight.value;$weight_total)))) as $raw |
  apportion(($raw|map_values(quantize_share(.)));$cents;$consumer_carry) as $shares |
  (reduce ($raw|to_entries[]|select(.value[0]>0)) as $share ($carry_counts;
    .[$share.key]=iadd((.[$share.key]//0);1))) as $counts |
  {model:$model,cost_cents:(if $priced then $cents else null end),known_cost_cents:$cents,
   raw_cost_usd:(if $priced then decimal($pool.raw) else null end),known_raw_cost_usd:decimal($pool.raw),
   known_raw_cost_usd_fraction:$pool.raw,instance_hours:decimal(rational($pool.duration;3600000)),
   pricing_complete:$priced,allocation_complete:($priced and $complete),coverage:$usage.coverage,tokens:$usage.tokens,
   total_tokens:(if $complete then $tokens else null end),observed_tokens:$tokens,
   usage_state:(if $complete and $tokens==0 and ($usage.tokens|length)>0 then "measured_zero"
     elif $complete and $tokens==0 then "no_activity_with_valid_coverage" elif $complete then "measured_usage" else $usage.coverage end),
   price_state:(if $priced then "priced" else "missing_price" end),allocations:$shares.allocated,
   raw_allocations_usd:($raw|map_values(decimal(multiply(.;[1,100])))),
   rounding_adjustment_usd:decimal(subtract([$cents,100];$pool.raw)),
   consumer_rounding_adjustment_usd:($raw|with_entries(.value=decimal(multiply(subtract([$shares.allocated[.key],1];.value);[1,100])))),
   rounding_residual_cents:decimal($model_carry),consumer_residual_cents:($shares.carry|map_values(decimal(.))),
   consumer_residual_cents_fractions:$shares.carry,
   consumer_share_rounding_error_bound_cents:($counts|map_values(decimal(rational(.;2000000000)))),
   missing_price_intervals:$pool.missing,_carry:$shares.carry,_carry_counts:$counts} |
  reduce (["input_tokens","output_tokens","reasons","source","source_hashes"]+receipt_fields)[] as $field (. ;
    if $usage|has($field) then .[$field]=$usage[$field] else . end) |
  if $usage|has("issues") then .coverage_issues=$usage.issues else . end;
def allocate:
  . as $original | validate as $data |
  (reduce $data.windows[] as $window (
    {raw:[0,1],cents:0,pool_carry:{},consumer_carry:{},carry_counts:{},windows:[],pricing:true,allocation:true,
     totals:{engineering:0,marketing:0,support:0,other_consumers:0,platform_idle:0,unresolved_allocation:0}};
    pools($window;$data) as $pools | .raw=add(.raw;([$pools[].raw]|sum_rat)) |
    add(multiply(.raw;[100,1]);[1,2]) as $round | idiv($round[0];$round[1]) as $next_cents |
    ($next_cents-.cents) as $budget | .cents=$next_cents |
    apportion(($pools|map_values(multiply(.raw;[100,1])));$budget;.pool_carry) as $pool_shares |
    .pool_carry=$pool_shares.carry | .current=[] |
    reduce $data.models[] as $model (. ;
      render_model($model;$pools[$model];$window.usage[$model];$pool_shares.allocated[$model];
        (.pool_carry[$model]//[0,1]);(.consumer_carry[$model]//{});(.carry_counts[$model]//{});$data) as $result |
      .consumer_carry[$model]=$result._carry | .carry_counts[$model]=$result._carry_counts |
      .current += [($result|del(._carry,._carry_counts))] |
      reduce ($result.allocations|to_entries[]) as $allocation (. ;
        .totals[$allocation.key]=iadd(.totals[$allocation.key];$allocation.value))) |
    all(.current[];.pricing_complete) as $priced | .pricing=(.pricing and $priced) |
    .allocation=(.allocation and all(.current[];.allocation_complete)) |
    .windows += [{id:$window.id,start:iso($window._start),end:iso($window._end),phase:$window.phase,
      pricing_complete:$priced,total_cents:(if $priced then $budget else null end),known_total_cents:$budget,models:.current}]
  )) as $result |
  $data.windows[0]._start as $first | $data.windows[-1]._end as $last |
  (reduce ["schema_version","report_id","scope","evidence_kind","policy_version","currency"][] as $field
    ({};.[$field]=$data[$field])) +
  {start:iso($first),end:iso($last),pricing_complete:$result.pricing,allocation_complete:$result.allocation,
   known_total_cents:$result.cents,total_cents:(if $result.pricing then $result.cents else null end),
   raw_total_usd:(if $result.pricing then decimal($result.raw) else null end),
   known_raw_total_usd:decimal($result.raw),known_raw_total_usd_fraction:$result.raw,
   totals_by_consumer:$result.totals,windows:$result.windows,rates:$data.rates,
   instance_intervals:($data.instance_intervals|map(.start=iso(._start)|.end=iso(._end)|del(._start,._end))),
   out_of_scope_intervals:[
     $data.instance_intervals[] as $interval |
     [[$interval._start,([$interval._end,$first]|min),"preparation"],
      [([$interval._start,$last]|max),$interval._end,"after_report"]][] |
     select(.[0]<.[1]) | . as $part | interval_cost($interval;.[0];.[1];$data._prices) as $cost |
     $interval|del(._start,._end)|.start=iso($part[0])|.end=iso($part[1])|
     .classification=$part[2]|.included_in_total=false|.raw_cost_usd=(if $cost==null then null else decimal($cost) end)],
   subscriptions:$data.subscriptions,subscription_teams:($data.subscriptions|map_values(demo_team(.))),source_sha256:$source_sha256,
   source_sha256_encoding:"jq -cS JSON including final newline",
   rounding:{method:"cumulative-half-up-hierarchical-largest-remainders-with-carry",
     replay:"full ordered evidence; corrections require replay of affected and later windows",
     adjustment_usd:decimal(subtract([$result.cents,100];$result.raw)),
     arithmetic:"exact reduced rationals, integer components <= 2^52-1; overflow fails closed",
     consumer_share_quantization:"nearest 1e-9 cent, half-up before carried allocation; costs and cent totals remain exact",
     consumer_share_error_bound:"<=0.5e-9 cent per active model/consumer/window; accumulated bounds are in each model result",
     decimal_display:"at most 18 fractional digits; exact rational fields retain computational values"},
   cost_basis:"GPU-worker compute estimate; other costs are excluded unless explicitly included by a different policy"} |
  reduce ["scenario_hash","scenario_sha256","source_hashes","input_sha256","metadata","excluded_costs",
    "price_basis","source","metering","limitations","supersedes_report_id"][] as $field (. ;
    if $original|has($field) then .[$field]=$original[$field] else . end);
allocate
JQ
)

temporary=$(mktemp "$(dirname "$output")/.showback-allocation.XXXXXX")
csv_temporary=''
cleanup() {
    rm -f "$temporary"
    [[ -z "$csv_temporary" ]] || rm -f "$csv_temporary"
}
trap cleanup EXIT
# The hash covers canonical jq JSON bytes; raw input hashes supplied by collection
# are separately preserved. A final newline is part of this canonical encoding.
source_hash=$(jq -cS . "$input" | shasum -a 256 | awk '{print $1}')
jq -eS --arg source_sha256 "$source_hash" "$ACCOUNTING_JQ" "$input" > "$temporary" || fail 'evidence validation/allocation failed'
if [[ -n "$csv" ]]; then
    csv_temporary=$(mktemp "$(dirname "$csv")/.showback-csv.XXXXXX")
    jq -r '
      ["report_id","scope","evidence_kind","policy_version","currency","window_id","start","end","phase",
       "model","coverage","pricing_complete","consumer","allocated_cents","known_cost_cents","cost_cents"],
      (. as $r | .windows[] as $w | $w.models[] as $m | $m.allocations|to_entries[] |
       [$r.report_id,$r.scope,$r.evidence_kind,$r.policy_version,$r.currency,$w.id,$w.start,$w.end,$w.phase,
        $m.model,$m.coverage,$m.pricing_complete,.key,.value,$m.known_cost_cents,$m.cost_cents]) | @csv
    ' "$temporary" > "$csv_temporary"
fi
link "$temporary" "$output" || fail 'could not publish a new report; nothing was overwritten'
if [[ -n "$csv" ]] && ! link "$csv_temporary" "$csv"; then
    rm -f "$output"
    fail 'could not publish CSV; new report rolled back'
fi
echo "Created $output"
