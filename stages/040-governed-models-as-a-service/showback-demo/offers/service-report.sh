#!/usr/bin/env bash
# Offline monthly service-offer accounting. Creates new private statements; never replaces evidence.
# No network, environment loading, cluster calls, credentials, or current-price lookup.
# Usage: service-report.sh --input MONTH.json --output NEW.json [--csv NEW.csv] [--previous PREVIOUS.json]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077
usage() {
    echo 'Usage: service-report.sh --input MONTH.json --output NEW.json [--csv NEW.csv] [--previous PREVIOUS.json]' >&2
    echo '       service-report.sh --check-report REPORT.json' >&2
    exit 2
}
fail() { echo "Service accounting failed: $*" >&2; exit 2; }
input=''
output=''
csv=''
previous=''
check_report=''
while (($#)); do
    case "$1" in
        --input) (($#>=2)) || usage; input=$2; shift 2 ;;
        --output) (($#>=2)) || usage; output=$2; shift 2 ;;
        --csv) (($#>=2)) || usage; csv=$2; shift 2 ;;
        --previous) (($#>=2)) || usage; previous=$2; shift 2 ;;
        --check-report) (($#>=2)) || usage; check_report=$2; shift 2 ;;
        *) usage ;;
    esac
done
if [[ -n "$check_report" ]]; then
    [[ -z "$input$output$csv$previous" ]] || usage
    input=$check_report
else
    [[ -n "$input" && -n "$output" ]] || usage
fi
command -v jq >/dev/null || fail 'jq is required'
command -v link >/dev/null || fail 'POSIX link is required'
[[ -f "$input" ]] || fail 'input is not a file'
if [[ -z "$check_report" ]]; then
    output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"
    [[ ! -e "$output" && ! -L "$output" ]] || fail 'refusing to replace statement'
fi
if [[ -n "$csv" ]]; then
    csv="$(cd "$(dirname "$csv")" && pwd)/$(basename "$csv")"
    [[ "$csv" != "$output" && ! -e "$csv" && ! -L "$csv" ]] || fail 'refusing to replace CSV'
fi
# Freeze caller-owned evidence before validation. Every subsequent read and hash
# uses these private bytes, including a correction's predecessor.
work=$(mktemp -d)
tmp=''
csv_tmp=''
cleanup() {
    rm -rf "$work"
    [[ -z "$tmp" ]] || rm -f "$tmp"
    [[ -z "$csv_tmp" ]] || rm -f "$csv_tmp"
}
trap cleanup EXIT
cat < "$input" > "$work/input.json" || fail 'cannot snapshot input'
input="$work/input.json"
previous_hash=''
previous_source=/dev/null
if [[ -n "$previous" ]]; then
    [[ -f "$previous" ]] || fail 'previous statement missing'
    cat < "$previous" > "$work/previous.json" || fail 'cannot snapshot previous statement'
    previous_source="$work/previous.json"
fi
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
if [[ -n "$previous" ]]; then
    jq -en --stream "$JSON_CHECK" "$previous_source" >/dev/null || fail 'invalid previous statement JSON'
    previous_hash=$(shasum -a 256 "$previous_source" | cut -d ' ' -f 1)
fi
input_hash=$(shasum -a 256 "$input" | cut -d ' ' -f 1)
# Guarded exact rationals copied from the bounded allocator. Costs/charges remain
# exact until one cumulative half-away-from-zero cent rounding per agreement.
# No float money: overflow fails closed before arithmetic, fractions retained.
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
def signed_money:
  if type=="string" and startswith("-") then .[1:]|money_rate|neg(.) else money_rate end;
def maybe_money: if .==null then null else money_rate end;
def exact_div($a;$b): require($b[0]>0;"zero/negative divisor") | multiply($a;[$b[1],$b[0]]);
def cents($r):
  multiply($r;[100,1]) as $c | ($c[0]|fabs) as $n | idiv($n;$c[1]) as $whole |
  ($n-$whole*$c[1]) as $rem |
  iadd($whole;(if $rem >= $c[1]-$rem then 1 else 0 end)) * (if $c[0]<0 then -1 else 1 end);
def nonempty: type=="string" and test("\\S");
def identifier: nonempty and test("^[A-Za-z0-9][A-Za-z0-9_.:/-]*$");
def evidence($kind):
  require(.evidence_kind=="verified" or .evidence_kind=="synthetic_fixture" or .evidence_kind=="unavailable";
    "price/cost evidence_kind must be verified, synthetic_fixture or unavailable") |
  require($kind=="synthetic_fixture" or .evidence_kind!="synthetic_fixture";"synthetic price in observed report") |
  require(.source|nonempty;"source required");
def round_lines($field):
  sort_by(.id) | reduce .[] as $line ({raw:[0,1],rounded:0,lines:[]};
    if $line._raw==null then .lines += [$line+{($field):null,raw_usd:null,raw_fraction:null}]
    else .raw=add(.raw;$line._raw) | cents(.raw) as $rounded |
      .lines += [$line+{($field):($rounded-.rounded),raw_usd:decimal($line._raw),raw_fraction:$line._raw}] |
      .rounded=$rounded end) | .lines | map(del(._raw));
def known($lines;$field): [$lines[]|.[$field]|select(.!=null)]|sum_int;
def total($lines;$field): if all($lines[];.[$field]!=null) then known($lines;$field) else null end;
def base_line($a;$id;$category;$kind;$who):
  {id:$id,agreement_id:$a.id,offer:$a.offer,model:$a.model,category:$category,kind:$kind,
   user:$who.user,team:$who.team,subscription:$who.subscription};
def validate:
  require(.schema_version==1 and .policy_version=="service-offers-v1";"unsupported schema/policy") |
  require((.report_id|identifier) and (.revision|count) and .revision>0;"report identity/revision required") |
  require(.currency=="USD" and .period.timezone=="UTC";"only USD and UTC supported") |
  require(.statement_status=="estimate" or .statement_status=="closed";"invalid statement status") |
  require(.evidence_kind=="synthetic_fixture" or .evidence_kind=="observed";"invalid evidence_kind") |
  require((.cost_scope|nonempty) and (.price_basis|nonempty);"cost scope and price basis required") |
  ._start=(.period.start|parse_utc) | ._end=(.period.end|parse_utc) |
  require(.period.start|test("^[0-9]{4}-[0-9]{2}-01T00:00:00Z$");"period must start at a UTC calendar month") |
  require(.period.end==((._start/1000+2764800)|strftime("%Y-%m-01T00:00:00Z"));"period must be exactly one month") |
  require((.consumers|type)=="object" and (.agreements|type)=="array" and (.agreements|length)>0;
    "consumers and agreements required") |
  . as $d |
  .consumers|=with_entries(.value |= (
    require((.user|nonempty) and all([.team,.subscription][];identifier);"consumer identity required") |
    ._start=((.start//$d.period.start)|parse_utc) | ._end=((.end//$d.period.end)|parse_utc) |
    require(._start<._end;"invalid identity interval"))) |
  (.consumers|to_entries|sort_by(.value.user,.value.subscription,.value._start)) as $identities |
  require(all(range(1;($identities|length));. as $i |
    $identities[$i-1].value as $p | $identities[$i].value as $n |
    $p.user!=$n.user or $p.subscription!=$n.subscription or $p._end<=$n._start);
    "overlapping consumer membership mappings") |
  require((.agreements|map(.id)|unique|length)==(.agreements|length);"duplicate agreements") |
  .agreements |= map(
    require((.id|identifier) and (.model|identifier) and (.price_basis|nonempty) and
      (.contract_version|nonempty) and (.source|nonempty);"agreement identity/version/source/price basis required") |
    require(.offer as $value|["external","dedicated","shared"]|index($value);"unknown service offer") |
    require(.usage_coverage=="complete" or .usage_coverage=="missing";"explicit usage coverage required") |
    require(.cost_coverage=="complete" or .cost_coverage=="missing";"explicit cost coverage required") |
    require((.members|type)=="array" and all(.members[];. as $c|$d.consumers[$c]!=null);"unknown agreement member") |
    require((.members|unique|length)==(.members|length);"duplicate agreement member") |
    if .offer=="dedicated" then require(.owner_team|identifier;"dedicated owner required") |
      require(.billing_method=="cost_reimbursement" or .billing_method=="fixed_quote";"dedicated billing method required")
    else . end) |
  .agreements|=sort_by(.id) |
  . as $d | (.agreements|map({key:.id,value:.})|from_entries) as $agreements |
  require((.events|type)=="array" and (.cost_items|type)=="array" and (.adjustments|type)=="array";
    "events, cost_items and adjustments must be arrays") |
  .deduplicated_events=0 |
  .events=(.events|sort_by(.id)|group_by(.id)|map(
    require((unique|length)==1;"conflicting duplicate event")|.[0])) |
  .deduplicated_events=($d.events|length)-(.events|length) |
  .events |= map(
    require((.id|identifier) and $agreements[.agreement_id]!=null;"unknown event agreement/ID") |
    $agreements[.agreement_id] as $a | .consumer_id as $consumer | $d.consumers[$consumer] as $who |
    require(($a.members|index($consumer))!=null;"event consumer not permitted") |
    ._at=(.at|parse_utc) |
    require(._at>=$d._start and ._at<$d._end;"event outside monthly period") |
    require(._at>=$who._start and ._at<$who._end;"event outside frozen identity membership") |
    require(.status as $value|["completed","aborted","failed"]|index($value);"event status required") |
    require(.retry_owner=="consumer" or .retry_owner=="platform";"explicit retry ownership required") |
    require(.usage_complete==true or .usage_complete==false;"explicit event usage completeness required") |
    require((.quantities|type)=="object";"event quantities required") |
    require(all(.quantities|to_entries[];
      (.key as $k|["input_uncached","cache_read","cache_write","output","tool_calls"]|index($k))!=null and (.value|count));
      "invalid or overlapping provider billing category") |
    require(.usage_complete==false or ((.quantities|has("input_uncached")) and (.quantities|has("output")));
      "complete usage requires explicit input and output, including zero")) |
  require((.cost_items|map(.id)|unique|length)==(.cost_items|length);"duplicate cost pool identity") |
  .cost_items |= map(
    require((.id|identifier) and $agreements[.agreement_id]!=null and (.category|identifier);"invalid cost item") |
    evidence($d.evidence_kind) |
    if has("instance_id") then
      require((.instance_id|identifier) and (has("amount_usd")|not);"invalid/duplicate instance cost basis") |
      ._start=(.start|parse_utc) | ._end=(.end|parse_utc) |
      require(._start>= $d._start and ._end<=$d._end and ._start<._end;"instance cost interval outside month") |
      ._raw=(.usd_per_hour|maybe_money) |
      ._raw=(if ._raw==null then null else multiply(._raw;rational(._end-._start;3600000)) end)
    else ._raw=(.amount_usd|maybe_money) end |
    require(._raw==null or .evidence_kind!="unavailable";"known cost needs available evidence")) |
  (.cost_items|map(select(has("instance_id")))|sort_by(.instance_id,._start)) as $intervals |
  require(all(range(1;($intervals|length));. as $i|
    $intervals[$i-1].instance_id!=$intervals[$i].instance_id or $intervals[$i-1]._end<=$intervals[$i]._start);
    "instance capacity double counted across cost pools") |
  require((.adjustments|map(.id)|unique|length)==(.adjustments|length);"duplicate adjustment") |
  .adjustments |= map(
    require((.id|identifier) and $agreements[.agreement_id]!=null;"invalid adjustment") |
    require(.kind as $value|["platform_fee","credit","contract_adjustment"]|index($value);"invalid adjustment kind") |
    require((.team|identifier) and (.reason|nonempty) and (.source|nonempty);"adjustment owner/reason/source required") |
    . as $adjustment | $agreements[.agreement_id] as $a |
    require(any($a.members[];$d.consumers[.] as $c|$c.team==$adjustment.team and
      ($adjustment.user==null or ($c.user==$adjustment.user and $c.subscription==$adjustment.subscription))) or
      ($a.offer=="dedicated" and .team==$a.owner_team and .user==null and .subscription==null);
      "adjustment identity is outside the agreement") |
    require(.user!=null or .subscription==null;"team adjustment cannot name a user subscription") |
    ._raw=(.amount_usd|signed_money) |
    require(.kind!="credit" or ._raw[0]<=0;"credit must be nonpositive")) |
  ($previous[0]//null) as $prior |
  if $prior==null then require(.revision==1 and .supersedes_report_id==null;"correction requires previous report")
  else require($prior.schema_version==1 and $prior.report_type=="service_offers" and
      $prior.period==.period and $prior.currency==.currency and $prior.policy_version==.policy_version and
      $prior.evidence_kind==.evidence_kind and
      .revision==$prior.revision+1 and .supersedes_report_id==$prior.report_id and .report_id!=$prior.report_id and
      (.correction_reason|nonempty);"correction must link same-period previous revision and explain change") end;
def rate_cards($a;$d):
  require(($a.rate_cards|type)=="array";"external rate cards required") |
  ($a.rate_cards|map(evidence($d.evidence_kind)|
    require((.id|identifier) and (.rate_version|nonempty);"rate identity/version required") |
    ._start=(.start|parse_utc) | ._end=(.end|parse_utc) |
    require(._start<._end;"invalid rate interval") |
    require((.prices|type)=="object";"rate prices required") |
    require(all(.prices|keys[];. as $k|["input_uncached","cache_read","cache_write","output","tool_calls"]|index($k));
      "unsupported rate category") |
    .prices|=with_entries(.value|=maybe_money) |
    require(.evidence_kind!="unavailable" or all(.prices[];.==null);"known rate needs available evidence"))|
    sort_by(._start)) as $cards |
  require(all(range(1;($cards|length));. as $i|$cards[$i-1]._end<=$cards[$i]._start);"overlapping rate windows") |
  $cards;
def event_lines($a;$d;$cards;$tariff):
  [$d.events[]|select(.agreement_id==$a.id)|. as $e | $d.consumers[.consumer_id] as $who |
    (if $a.offer=="external" then [$cards[]|select(._start<=$e._at and ._end>$e._at)]|.[0] else null end) as $card |
    (if $e.usage_complete then $e.quantities|to_entries else [{key:"unknown_usage",value:null}] end)[] |
    .key as $cat | .value as $qty |
    (if $a.offer=="external" then $card.prices[$cat]
     elif $cat=="input_uncached" then $tariff.input_rate
     elif $cat=="output" then $tariff.output_rate else null end) as $rate |
    base_line($a;("usage:"+$e.id+":"+$cat);$cat;"usage";$who)+
    {event_id:$e.id,at:$e.at,event_status:$e.status,retry_owner:$e.retry_owner,quantity:$qty,
     unit:(if $cat=="tool_calls" then "call" else "token" end),
     rate_usd:(if $rate==null then null else decimal($rate) end),rate_fraction:$rate,
     rate_version:($card.rate_version//$tariff.rate_version//"unpriced"),source:($card.source//$tariff.source//"unavailable"),
     coverage:(if $qty==null then "missing_usage" elif $rate==null then "missing_price" else "complete" end),
     _raw:(if $qty==null or $rate==null then null else multiply($rate;[$qty,1]) end)} |
    . as $line | $line,
    (if $e.retry_owner=="platform" then $line+{id:($line.id+":retry-credit"),kind:"platform_retry_credit",
      category:"platform_retry_credit",quantity:null,unit:"adjustment",
      _raw:(if $line._raw==null then null else neg($line._raw) end)}
     else empty end)];
def tariff($a;$d):
  $a.tariff as $t | $t|evidence($d.evidence_kind) |
  require((.rate_version|nonempty) and (.status=="approved" or .status=="unpriced");"shared tariff version/status required") |
  ((.reservation_fees//[])|sort_by(.team)) as $fees |
  require(($fees|type)=="array" and all($fees[];(.team|identifier));"reservation owners required") |
  require(.evidence_kind!="unavailable" or (($fees|length)==0 and .subsidy_usd==null);
    "reservation fees and subsidy need available tariff evidence") |
  require(($fees|map(.team)|unique|length)==($fees|length);"one reservation per team per agreement") |
  require(all($fees[];.team as $team|any($a.members[];$d.consumers[.].team==$team));"reservation owner not an agreement member") |
  ($fees|map(.amount_usd|money_rate)|sum_rat) as $reserved |
  ($fees|map((.included_usage_credit_usd//"0")|money_rate)|sum_rat) as $credits |
  require(all($fees[];subtract((.amount_usd|money_rate);((.included_usage_credit_usd//"0")|money_rate))[0]>=0);
    "included credit exceeds reservation fee") |
  (.subsidy_usd|maybe_money) as $subsidy |
  if .status=="unpriced" then
    {input_rate:null,output_rate:null,rate_version:.rate_version,source:.source,reservation_fees:$fees,subsidy:$subsidy}
  else
    require(.evidence_kind!="unavailable";"approved tariff needs available evidence") |
    require((.approved_at|parse_utc)<=$d._start;"tariff approved after usage period began") |
    require((.start|parse_utc)<=$d._start and (.end|parse_utc)>=$d._end;"tariff does not cover month") |
    (.forecast.service_cost_usd|money_rate) as $forecast |
    require(.forecast.input_tokens|count;"forecast input required") |
    require(.forecast.output_tokens|count;"forecast output required") |
    (.forecast.output_weight|money_rate) as $weight |
    require($weight[0]>0 and $subsidy!=null;"positive weight and explicit subsidy required") |
    subtract(subtract($forecast;$subsidy);$reserved) as $net |
    require($net[0]>=0;"subsidy/reservations exceed forecast cost; review contract") |
    add([.forecast.input_tokens,1];multiply($weight;[.forecast.output_tokens,1])) as $den |
    require($den[0]>0;"zero forecast cannot define tariff") |
    exact_div(add($net;$credits);$den) as $input |
    {input_rate:$input,output_rate:multiply($input;$weight),rate_version:.rate_version,source:.source,
     reservation_fees:$fees,subsidy:$subsidy,forecast_service_cost_usd:decimal($forecast),
     forecast_input_tokens:.forecast.input_tokens,forecast_output_tokens:.forecast.output_tokens,
     output_weight:decimal($weight),forecast_credit_redemption_usd:decimal($credits)} end;
def agreement_report($a;$d):
  require($a.offer=="external" or $a.cost_coverage!="complete" or
    any($d.cost_items[];.agreement_id==$a.id);"complete private cost requires explicit cost items, including zero") |
  (if $a.offer=="shared" then tariff($a;$d) else null end) as $tariff |
  (if $a.offer=="external" then rate_cards($a;$d) else [] end) as $cards |
  [$d.cost_items[]|select(.agreement_id==$a.id)|
    {id:("cost:"+.id),agreement_id:$a.id,offer:$a.offer,model:$a.model,category,source,
     owner_team:($a.owner_team//"platform"),_raw,instance_id,start,end,evidence_kind}] as $provided_costs |
  (if $a.offer=="dedicated" then [] else event_lines($a;$d;$cards;$tariff) end) as $metered |
  ([$metered[]|select(.kind=="usage")|._raw]|map(select(.!=null))|sum_rat) as $metered_known |
  (all($metered[];._raw!=null) and $a.usage_coverage=="complete" and
    all($d.events[]|select(.agreement_id==$a.id);.usage_complete)) as $usage_priced |
  (if $a.offer=="external" then $a.invoice|evidence($d.evidence_kind)|
    require(.usd==null or .evidence_kind!="unavailable";"known invoice needs available evidence")|.usd|maybe_money
   else null end) as $invoice |
  (if $a.offer=="external" then $provided_costs+[
    {id:("invoice:"+$a.id),agreement_id:$a.id,offer:$a.offer,model:$a.model,category:"provider_service",
     source:(if $invoice==null then "metered usage estimate; invoice unavailable" else $a.invoice.source end),
     owner_team:"platform",evidence_kind:(if $invoice==null then $d.evidence_kind else $a.invoice.evidence_kind end),
     _raw:(if $invoice!=null then $invoice elif $usage_priced then $metered_known else null end)}]
   else $provided_costs end) as $costs |
  ($costs|round_lines("cost_cents")) as $cost_lines |
  (if $a.cost_coverage=="complete" then total($cost_lines;"cost_cents") else null end) as $cost_total |
  (if $a.offer=="dedicated" then
    (if $a.billing_method=="fixed_quote" then
      $a.quote|evidence($d.evidence_kind)|
        require((.approved_at|parse_utc)<=$d._start;"fixed quote must be agreed before the month") |
        require(.amount_usd==null or .evidence_kind!="unavailable";"known quote needs available evidence")|.amount_usd|maybe_money
     elif $cost_total==null then null else [$costs[]._raw]|sum_rat end) as $charge |
    [base_line($a;("availability:"+$a.id);"dedicated_availability";"availability";{team:$a.owner_team})+
      {quantity:1,unit:"month",rate_usd:(if $charge==null then null else decimal($charge) end),
       rate_version:$a.contract_version,source:$a.source,coverage:(if $charge==null then "missing_cost" else "complete" end),_raw:$charge}]
   else $metered end) as $base_charges |
  (if $a.offer=="shared" then [$tariff.reservation_fees|to_entries[]|.key as $n|.value as $fee|
    base_line($a;("reservation:"+$a.id+":"+($n|tostring));"reservation";"reservation";{team:$fee.team})+
    {quantity:1,unit:"month",rate_usd:$fee.amount_usd,rate_version:$tariff.rate_version,source:$tariff.source,
     coverage:"complete",_raw:($fee.amount_usd|money_rate)},
    ([$base_charges[]|select(.team==$fee.team)|._raw]) as $team_charges |
    (if all($team_charges[];.!=null) then $team_charges|sum_rat else null end) as $gross |
    (($fee.included_usage_credit_usd//"0")|money_rate) as $cap |
    base_line($a;("reservation-credit:"+$a.id+":"+($n|tostring));"included_usage_credit";"credit";{team:$fee.team})+
    {quantity:null,unit:"adjustment",rate_usd:null,rate_version:$tariff.rate_version,source:$tariff.source,
     coverage:(if $gross==null then "missing_usage" else "complete" end),
     _raw:(if $gross==null then null elif subtract($gross;$cap)[0]<0 then neg($gross) else neg($cap) end)}]
   else [] end) as $reservation_charges |
  [$d.adjustments[]|select(.agreement_id==$a.id)|
    base_line($a;("adjustment:"+.id);.kind;.kind;.)+
    {quantity:null,unit:"adjustment",rate_usd:null,rate_version:$a.contract_version,source,reason,
     coverage:"complete",_raw}] as $adjustments |
  (($base_charges+$reservation_charges+$adjustments)|round_lines("charge_cents")) as $charge_lines |
  (if ($a.usage_coverage=="complete" or $a.offer=="dedicated") and
    ($a.offer!="shared" or ($tariff.input_rate!=null and $tariff.output_rate!=null))
   then total($charge_lines;"charge_cents") else null end) as $charged |
  (if $a.offer=="shared" then $tariff.subsidy else [0,1] end) as $subsidy |
  (if $subsidy==null then null else cents($subsidy) end) as $subsidy_cents |
  {id:$a.id,offer:$a.offer,model:$a.model,owner_team:$a.owner_team,contract_version:$a.contract_version,
   price_basis:$a.price_basis,
   cost_basis:(if $a.offer!="external" then "provided_costs" elif $invoice!=null then "invoice" else "metered_estimate" end),
   pricing_complete:($charged!=null),cost_complete:($cost_total!=null),
   usage_complete:($a.usage_coverage=="complete" and all($d.events[]|select(.agreement_id==$a.id);.usage_complete)),
   cost_cents:$cost_total,known_cost_cents:known($cost_lines;"cost_cents"),charge_cents:$charged,
   known_charge_cents:known($charge_lines;"charge_cents"),subsidy_cents:$subsidy_cents,
   recovery_balance_cents:(if $cost_total==null or $charged==null or $subsidy_cents==null then null
     else iadd(iadd($charged;$subsidy_cents);-$cost_total) end),
   invoice_cents:(if $invoice==null then null else cents($invoice) end),
   invoice_difference_cents:(if $invoice==null or $usage_priced==false then null else cents(subtract($invoice;$metered_known)) end),
   invoice_reconciled:(if $a.offer!="external" then null else $invoice!=null and $usage_priced and
     cents(subtract($invoice;$metered_known))==0 end),
   tariff:(if $tariff==null then null else $tariff|del(.input_rate,.output_rate,.subsidy)+
     {input_usd_per_million:(if .input_rate==null then null else decimal(multiply(.input_rate;[1000000,1])) end),
      output_usd_per_million:(if .output_rate==null then null else decimal(multiply(.output_rate;[1000000,1])) end)} end),
   usage:{requests:([$d.events[]|select(.agreement_id==$a.id)]|length),
     input_tokens:([$d.events[]|select(.agreement_id==$a.id)|.quantities|
       [(.input_uncached//0),(.cache_read//0),(.cache_write//0)]|sum_int]|sum_int),
     output_tokens:([$d.events[]|select(.agreement_id==$a.id)|.quantities.output//0]|sum_int)},
   cost_lines:$cost_lines,charge_lines:$charge_lines};
validate | . as $d |
[.agreements[]|agreement_report(.;$d)] as $reports |
(all($reports[];.pricing_complete and .cost_complete and .usage_complete)) as $complete |
require(.statement_status!="closed" or ($complete and all($reports[];.offer!="external" or .invoice_cents!=null));
  "closed statement requires complete evidence and external invoice") |
{schema_version:1,report_type:"service_offers",scope:"service-offers",start:.period.start,end:.period.end,
 report_id,revision,policy_version,period,currency,evidence_kind,
 statement_status,cost_scope,price_basis,complete:$complete,input_sha256:$input_hash,
 supersedes_report_id,previous_report_sha256:(if $previous_hash=="" then null else $previous_hash end),correction_reason,
 source_snapshot:{consumers:.consumers,agreements:.agreements},deduplicated_events,
 metadata:(.metadata//{}),native_import,
 rounding_policy:"exact-rational; cumulative half-away-from-zero cents per agreement; stable line ID order",
 agreements:($reports|map(del(.cost_lines,.charge_lines))),cost_lines:[$reports[].cost_lines[]],charge_lines:[$reports[].charge_lines[]],
 totals:{cost_cents:(if all($reports[];.cost_cents!=null) then [$reports[].cost_cents]|sum_int else null end),
   known_cost_cents:([$reports[].known_cost_cents]|sum_int),
   charge_cents:(if all($reports[];.charge_cents!=null) then [$reports[].charge_cents]|sum_int else null end),
   known_charge_cents:([$reports[].known_charge_cents]|sum_int),
   subsidy_cents:(if all($reports[];.subsidy_cents!=null) then [$reports[].subsidy_cents]|sum_int else null end),
   recovery_balance_cents:(if all($reports[];.recovery_balance_cents!=null)
     then [$reports[].recovery_balance_cents]|sum_int else null end)}}
JQ
)
REPORT_CHECK_JQ="${ACCOUNTING_JQ%%$'\ndef validate:'*}
$(cat <<'JQ'
def fraction_ok: type=="array" and length==2 and all(.[];integer) and .[1]>0;
def nullable_integer: .==null or integer;
def hash_ok: type=="string" and test("^[0-9a-f]{64}$");
require(.schema_version==1 and .report_type=="service_offers" and .scope=="service-offers" and
  .policy_version=="service-offers-v1" and .currency=="USD";"invalid report schema/scope") |
require((.report_id|identifier) and (.revision|count) and .revision>=1 and (.input_sha256|hash_ok);
  "invalid report identity/revision/hash") |
require(.evidence_kind=="synthetic_fixture" or .evidence_kind=="observed";"invalid report evidence kind") |
require((.cost_scope|nonempty) and (.price_basis|nonempty) and (.complete|type)=="boolean";
  "report cost scope/price basis/completeness required") |
require(.statement_status=="estimate" or .statement_status=="closed";"invalid report status") |
require(.period.timezone=="UTC" and .start==.period.start and .end==.period.end;"report period aliases differ") |
(.start|parse_utc) as $start | (.end|parse_utc) as $end |
require((.start|test("^[0-9]{4}-[0-9]{2}-01T00:00:00Z$")) and
  .end==(($start/1000+2764800)|strftime("%Y-%m-01T00:00:00Z"));"report is not one UTC month") |
require(if .revision==1 then .supersedes_report_id==null and .previous_report_sha256==null
  else (.supersedes_report_id|identifier) and (.previous_report_sha256|hash_ok) and (.correction_reason|nonempty) end;
  "invalid correction linkage") |
require((.agreements|type)=="array" and (.agreements|length)>0 and (.charge_lines|type)=="array" and
  (.cost_lines|type)=="array";"report arrays required") |
require((.agreements|map(.id)|unique|length)==(.agreements|length) and
  (.charge_lines|map(.id)|unique|length)==(.charge_lines|length) and
  (.cost_lines|map(.id)|unique|length)==(.cost_lines|length);"duplicate report identity") |
. as $r | (.agreements|map({key:.id,value:.})|from_entries) as $agreements |
reduce ["charge","cost"][] as $kind (. ;
  ($kind+"_lines") as $lines | ($kind+"_cents") as $amount |
  require(all(.[$lines][];
    . as $line | $agreements[.agreement_id] as $a |
    (.id|identifier) and $a!=null and .offer==$a.offer and .model==$a.model and
    (.category|identifier) and (.source|nonempty) and (.[$amount]|nullable_integer) and
    (if .[$amount]==null then .raw_fraction==null and .raw_usd==null
     else (.raw_fraction|fraction_ok) and .raw_usd==decimal(.raw_fraction) end));"invalid financial line") |
  reduce .agreements[] as $a (. ;
    [$r[$lines][]|select(.agreement_id==$a.id)] as $original |
    ($original|map(._raw=.raw_fraction)|round_lines($amount)) as $rounded |
    require([$original[]|{id,amount:.[$amount]}]==[$rounded[]|{id,amount:.[$amount]}];
      "financial lines differ from exact rounding") |
    require($a[("known_"+$amount)]==known($original;$amount) and
      ($a[$amount]==null or $a[$amount]==total($original;$amount));"agreement does not reconcile"))) |
require(all(.charge_lines[];(.team|identifier) and (.user==null or (.user|nonempty)) and
  (.subscription==null or (.subscription|identifier)) and (.rate_version|nonempty));"charge ownership/version required") |
require(all(.agreements[];
  (.id|identifier) and (.model|identifier) and (.price_basis|nonempty) and (.contract_version|nonempty) and
  (.offer as $o|["external","dedicated","shared"]|index($o))!=null and
  (.pricing_complete==(.charge_cents!=null)) and (.cost_complete==(.cost_cents!=null)) and
  (.usage_complete|type)=="boolean" and (.usage|type)=="object" and
  all([.usage.requests,.usage.input_tokens,.usage.output_tokens][];count) and
  ([.cost_cents,.known_cost_cents,.charge_cents,.known_charge_cents,.subsidy_cents,.recovery_balance_cents,
    .invoice_cents,.invoice_difference_cents]|all(.[];nullable_integer)) and
  .recovery_balance_cents==(if .cost_cents==null or .charge_cents==null or .subsidy_cents==null then null
    else iadd(iadd(.charge_cents;.subsidy_cents);-.cost_cents) end));"invalid agreement recovery/completeness") |
require(.complete==all(.agreements[];.pricing_complete and .cost_complete and .usage_complete);
  "report completeness differs") |
require(.statement_status!="closed" or (.complete and all(.agreements[];.offer!="external" or .invoice_cents!=null));
  "closed report is incomplete") |
reduce ["cost_cents","charge_cents","subsidy_cents","recovery_balance_cents","known_cost_cents","known_charge_cents"][]
  as $field (. ; require(.totals[$field]==(if all(.agreements[];.[$field]!=null)
    then [.agreements[]|.[$field]]|sum_int else null end);"report totals do not reconcile")) | true
JQ
)"
if [[ -n "$check_report" ]]; then
    jq -e "$REPORT_CHECK_JQ" "$input" >/dev/null || fail 'invalid service report'
    printf 'Service report validated: %s\n' "$check_report"
    exit 0
fi
if [[ -n "$previous" ]]; then
    jq -e "$REPORT_CHECK_JQ" "$previous_source" >/dev/null || fail 'previous report invalid'
fi
tmp=$(mktemp "$(dirname "$output")/.service-report.XXXXXX")
jq -e --arg input_hash "$input_hash" --arg previous_hash "$previous_hash" --slurpfile previous "$previous_source" \
    "$ACCOUNTING_JQ" "$input" > "$tmp" || fail 'invalid accounting evidence'
jq -e "$REPORT_CHECK_JQ" "$tmp" >/dev/null || fail 'generated report failed financial validation'
if [[ -n "$csv" ]]; then
    csv_tmp=$(mktemp "$(dirname "$csv")/.service-csv.XXXXXX")
    jq -r '(["report_id","start","end","agreement","offer","model","user","team","subscription","category",
      "quantity","unit","rate_usd","raw_usd","charge_cents","coverage"]|@csv),
      (. as $r|.charge_lines[]|[$r.report_id,$r.period.start,$r.period.end,.agreement_id,.offer,.model,.user,.team,
        .subscription,.category,.quantity,.unit,.rate_usd,.raw_usd,.charge_cents,.coverage]|@csv)' "$tmp" > "$csv_tmp"
fi
link "$tmp" "$output" || fail 'statement exists or cannot be published'
if [[ -n "$csv" ]]; then
    if ! link "$csv_tmp" "$csv"; then rm -f "$output"; fail 'CSV creation failed; new JSON rolled back'; fi
fi
printf 'Created private service statement: %s\n' "$output"
