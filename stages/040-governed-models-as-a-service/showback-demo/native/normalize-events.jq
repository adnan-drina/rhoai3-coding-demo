# Source contract: pinned IPP plugin.go reportUsageEvent; this is not a billing server.
def require($ok;$why): if $ok then . else error($why) end;
def nonempty: type=="string" and length>0;
def count: type=="number" and isfinite and floor==. and .>=0 and .<=4503599627370495;
def stamp:
  require(type=="string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$");"UTC seconds required") |
  . as $s | fromdateiso8601 | require(strftime("%Y-%m-%dT%H:%M:%SZ")==$s;"invalid date");
def key: [.source,.id]|tojson;
def safe_id: "native-"+([.source,.id]|tojson|@base64|gsub("[+]";"-")|gsub("/";"_")|gsub("=";""));
# This binds the selected parser contract, not a claim that fixture events came from this image.
def source_contract: {
  repository:"https://github.com/red-hat-data-services/ai-gateway-payload-processing",
  commit:"a98a2650e74f8b832ff75206f795cbb62b9cd688",
  image:"registry.redhat.io/rhoai/odh-ai-gateway-payload-processing-rhel9@sha256:83091d245d7ae9275ba27db0aed50bfc0b80b78b6ef28b77db7f62c175b14fe2"
};
$capture[0] as $c | $base[0] as $b |
require(($capture|length)==1 and ($base|length)==1;"one capture/base document required") |
require($c.schema_version==1 and $c.source_format=="ipp-cloudevents-v1" and
  $c.source_sha256==$events_hash and $c.source_contract==source_contract;
  "capture must bind event bytes and the implemented source contract") |
require(($c.evidence_kind=="observed" or $c.evidence_kind=="synthetic_fixture") and $c.evidence_kind==$b.evidence_kind;
  "capture/base evidence kind mismatch") |
require($b.schema_version==1 and $b.policy_version=="service-offers-v1" and $b.events==[] and
  ($b.consumers|type)=="object" and ($b.agreements|type)=="array";"empty service-offer event input required") |
require(($c.model_mappings|type)=="array" and ($c.requests|type)=="array" and
  ($c.coverage.complete|type)=="boolean" and ($c.coverage.delivery_reconciled|type)=="boolean";
  "explicit mapping, completion and coverage evidence required") |
($c.coverage.start|stamp) as $start | ($c.coverage.end|stamp) as $end |
require($start<$end;"invalid capture interval") |
require($start>=($b.period.start|stamp) and $end<=($b.period.end|stamp);"capture interval outside offer period") |
require(($c.model_mappings|map([.provider,.model])|unique|length)==($c.model_mappings|length);"ambiguous model mapping") |
require(($c.requests|map(key)|unique|length)==($c.requests|length);"duplicate request evidence") |
require(all($c.model_mappings[];. as $m |
  (.provider|nonempty) and (.model|nonempty) and
  any($b.agreements[];.id==$m.agreement_id) and
  (.token_semantics=="openai-chat" or .token_semantics=="anthropic-messages" or .token_semantics=="unqualified"));
  "invalid model mapping") |
($events|sort_by(.source,.id)|group_by([.source,.id])|map(
  require((unique|length)==1;"conflicting duplicate source/id")|.[0])) as $unique |
require(all($unique[];
  .specversion=="1.0" and .datacontenttype=="application/json" and (.id|nonempty) and (.source|nonempty) and (.type|nonempty) and
  (.data|type)=="object" and (.time|stamp)>= $start and (.time|stamp)<$end);"invalid event envelope or capture window") |
[$unique[] | . as $e | ($e|key) as $key |
  [$c.requests[]|select(key==$key)] as $receipts |
  [$c.model_mappings[]|select(.provider==$e.data.provider and .model==$e.data.model)] as $maps |
  ($maps[0]//null) as $m | ($receipts[0]//null) as $r |
  [$b.consumers|to_entries[]|select(.value.user==$e.data.user and .value.subscription==$e.data.subscription and
    (.value.start//$b.period.start|stamp)<=($e.time|stamp) and (.value.end//$b.period.end|stamp)>($e.time|stamp))] as $who |
  [$b.agreements[]|select(.id==$m.agreement_id)] as $agreements |
  (if $m==null then "unknown_model_mapping"
   elif $e.type!="inference.tokens.used" then "unsupported_event_type"
   elif ($who|length)!=1 or $e.subject!=$e.data.user then "unknown_or_ambiguous_identity"
   elif ($agreements[0].members|index($who[0].key))==null then "identity_not_in_agreement"
   elif $r==null then "missing_request_completion_evidence"
   elif (["completed","aborted","failed"]|index($r.status))==null or
        (["consumer","platform"]|index($r.retry_owner))==null then "unresolved_request_status_or_retry_owner"
   else null end) as $quarantine |
  {source:$e.source,id:$e.id,time:$e.time,agreement_id:$m.agreement_id,
   user:$e.data.user,subscription:$e.data.subscription,model:$e.data.model,provider:$e.data.provider,
   native_type:$e.type,gateway_request_id:null,
   unknown_fields:($e.data|keys-["user","group","subscription","provider","model","prompt_tokens","completion_tokens","total_tokens","cached_input_tokens","cache_creation_tokens","reasoning_tokens","duration_ms","user_agent"])} as $identity |
  if $quarantine!=null then {quarantine:($identity+{reason:$quarantine})}
  else
    $e.data as $u |
    ([$u.prompt_tokens,$u.completion_tokens,$u.total_tokens,$u.cached_input_tokens,$u.cache_creation_tokens,$u.reasoning_tokens] | all(.[];count)) as $counts |
    (if $counts then
       $u.total_tokens==$u.prompt_tokens+$u.completion_tokens and $u.reasoning_tokens<=$u.completion_tokens and
       (if $m.token_semantics=="openai-chat" then $u.cached_input_tokens<=$u.prompt_tokens and $u.cache_creation_tokens==0
        elif $m.token_semantics=="anthropic-messages" then $u.reasoning_tokens==0 and
          ($u.cache_creation_tokens==0 or $m.cache_write_pricing=="single-confirmed-rate") else false end)
     else false end) as $categories |
    ($r.usage_complete==true and $r.final_usage_observed==true and $r.billing_categories_verified==true and
      ($r.streaming==false or ($r.streaming==true and $r.stream_done_observed==true)) and
      ($r.evidence|nonempty)) as $completion |
    ($categories and $completion and ($identity.unknown_fields|length)==0) as $complete |
    {event:{id:($e|safe_id),agreement_id:$m.agreement_id,consumer_id:$who[0].key,at:$e.time,
      status:$r.status,retry_owner:$r.retry_owner,usage_complete:$complete,
      quantities:(if $complete then
        {input_uncached:(if $m.token_semantics=="openai-chat" then $u.prompt_tokens-$u.cached_input_tokens else $u.prompt_tokens end),
         output:$u.completion_tokens} +
        (if $u.cached_input_tokens>0 then {cache_read:$u.cached_input_tokens} else {} end) +
        (if $u.cache_creation_tokens>0 then {cache_write:$u.cache_creation_tokens} else {} end)
        else {} end),
      native_source:$e.source,native_event_id:$e.id},
     evidence:($identity+{usage_complete:$complete,reason:(if $complete then null
       elif ($identity.unknown_fields|length)>0 then "unknown_billing_fields"
       elif $categories|not then "unqualified_or_inconsistent_token_categories" else "incomplete_final_usage_or_stream" end)})}
  end] as $records |
([$c.requests[]|key] - [$unique[]|key]) as $missing_event_keys |
($c.coverage.complete==true and $c.coverage.delivery_reconciled==true and ($c.coverage.evidence|nonempty) and
  ($missing_event_keys|length)==0 and
  $c.coverage.start==$b.period.start and $c.coverage.end==$b.period.end) as $whole_period |
$b | .events=[$records[]|select(.event!=null)|.event] |
.agreements |= map(. as $a |
  .usage_coverage=(if $whole_period and any($c.model_mappings[];.agreement_id==$a.id) and
    all($records[];
      if .quarantine then .quarantine.agreement_id!=null and .quarantine.agreement_id!=$a.id
      elif .event.agreement_id==$a.id then .event.usage_complete else true end)
    then "complete" else "missing" end)) |
.native_import={schema_version:1,source_format:$c.source_format,evidence_kind:$c.evidence_kind,
  events_sha256:$events_hash,capture_sha256:$capture_hash,base_offers_sha256:$offers_hash,
  source_contract:$c.source_contract,raw_event_count:($events|length),unique_event_count:($unique|length),
  identical_replays:(($events|length)-($unique|length)),coverage:$c.coverage,
  missing_event_keys:$missing_event_keys,
  event_evidence:[$records[]|select(.evidence!=null)|.evidence],
  quarantined:[$records[]|select(.quarantine!=null)|.quarantine],
  request_join:"unavailable: native CloudEvent UUID is not the gateway request ID"}
