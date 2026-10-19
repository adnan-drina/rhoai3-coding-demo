#!/usr/bin/env bash
# Offline: render sanitized bounded external receipts as immutable gauges; never infer monthly costs or missing usage.
# Usage: render-external-probe.sh --probe SANITIZED_PROBE_JSON [--publisher EXISTING_CONFIGMAP] --output NEW_FILE
set -euo pipefail
probe='' output='' publisher=''
while (($#)); do
    case "$1" in
        --probe) probe=${2:?}; shift 2 ;;
        --publisher) publisher=${2:?}; shift 2 ;;
        --output) output=${2:?}; shift 2 ;;
        -h|--help) sed -n 's/^# Usage: //p' "$0"; exit 0 ;;
        *) printf 'ERROR: Unknown argument\n' >&2; exit 1 ;;
    esac
done
[[ -f "$probe" && -n "$output" && ! -e "$output" && ! -L "$output" ]] || {
    printf 'ERROR: Require existing probe and a new metrics file\n' >&2; exit 1;
}
sha=$(shasum -a 256 "$probe" | cut -d ' ' -f 1)
temporary=$(mktemp "${output}.XXXXXX")
composed=''
trap 'rm -f "$temporary"; [[ -z "$composed" ]] || rm -f "$composed"' EXIT
jq -er --arg sha "$sha" '
  def require($v;$m): if $v then . else error($m) end;
  def name: type=="string" and test("^[A-Za-z0-9_.:/-]+$");
  def count: type=="number" and .>=0 and floor==.;
  def utc: type=="string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$") and
    (try (fromdateiso8601|type=="number") catch false);
  def metric($n;$v;$l): $n+"{"+($l|to_entries|sort_by(.key)|map(.key+"="+(.value|tostring|tojson))|join(","))+"} "+($v|tostring);
  require(.schema_version==1 and .evidence_kind=="observed" and .scope=="bounded_api_probe";
    "Expected observed bounded probe") |
  require((.probe_id|name) and (.period_start|utc) and (.period_end|utc) and .period_start<=.period_end and
    (.inventory|type)=="array" and (.inventory|length)>0 and (.receipts|type)=="array" and (.receipts|length)==2;
    "Invalid probe metadata") |
  require(all(.inventory[];(.model|name) and (.provider|name) and (.upstream_model|name) and (.inventory_at|utc) and
    .evidence_kind=="observed");"Invalid external inventory") |
  require(([.inventory[]|[.model,.provider]]|unique|length)==(.inventory|length) and
    ([.receipts[].sequence]|sort)==[1,2] and
    ([.receipts[].client_request_id]|unique|length)==2;"Duplicate inventory or receipts") |
  require(([.receipts[]|select(.provider_request_id!=null)|[.provider,.provider_request_id]]|unique|length)==
    ([.receipts[]|select(.provider_request_id!=null)]|length);"Duplicate provider receipt IDs") |
  . as $source |
  require(all(.receipts[];(.model|name) and (.provider|name) and (.user|name) and (.subscription|name) and
    (.client_request_id|name) and (.started_at|utc) and (.ended_at|utc) and
    .started_at>= $source.period_start and .ended_at<= $source.period_end and .started_at<=.ended_at and
    (. as $row|any($source.inventory[];.model==$row.model and .provider==$row.provider)) and
    (.transport_status|count) and (.http_status|type=="string" and test("^[0-9]{3}$")) and
    (.usage==null or ((.usage.input_tokens|count) and (.usage.output_tokens|count) and
      (.provider_request_id|name) and .usage.total_tokens==(.usage.input_tokens+.usage.output_tokens) and
      .http_status=="200" and .transport_status==0)));
    "Invalid receipt or fabricated failed-request usage") |
  . as $r |
  {probe_id:.probe_id,probe_sha256:$sha,period_start:.period_start,period_end:.period_end,
    scope:.scope,evidence_kind:.evidence_kind} as $p |
  "# showback_external_: Immutable bounded API receipts; absent usage is unknown. No monthly cost metrics.",
  ($r.inventory[]|metric("showback_external_model_info";1;{model,provider,upstream_model,inventory_at,evidence_kind})),
  metric("showback_external_probe_info";1;$p),
  ($r.receipts|group_by([.model,.provider,.user,.subscription])[]|
    . as $rows|($p+($rows[0]|{model,provider,user,subscription})) as $l|
    metric("showback_external_probe_requests";length;$l),
    metric("showback_external_probe_usage_complete";(if all($rows[];.usage!=null) then 1 else 0 end);$l),
    (if all($rows[];.usage!=null) then
      metric("showback_external_probe_input_tokens";([$rows[].usage.input_tokens]|add);$l),
      metric("showback_external_probe_output_tokens";([$rows[].usage.output_tokens]|add);$l)
      else empty end),
    ($rows|group_by([.http_status,.transport_status])[]|
      metric("showback_external_probe_request_status";length;
        $l+{http_status:.[0].http_status,transport_status:(.[0].transport_status|tostring)})))
' "$probe" > "$temporary"
if [[ -n "$publisher" ]]; then
    [[ -f "$publisher" ]] || { printf 'ERROR: Publisher ConfigMap missing\n' >&2; exit 1; }
    composed=$(mktemp "${output}.XXXXXX")
    source_metadata=$(ruby -ryaml -rjson -e 'puts JSON.generate(YAML.safe_load(STDIN.read))' < "$publisher" |
      jq -ceS 'select(.kind=="ConfigMap" and .metadata.name=="showback-selected-report" and
        (.data["metrics.prom"]|type)=="string")|.metadata')
    awk '
      NR==FNR { metrics=metrics "    " $0 ORS; next }
      $0=="  metrics.prom: |" { found++; print; inblock=1; next }
      inblock && $0 !~ /^    / && $0 !~ /^[[:space:]]*$/ { printf "%s",metrics; inblock=0 }
      inblock && /^    (showback_external_|# (HELP |TYPE )?showback_external_)/ { next }
      { print }
      END { if (found!=1) exit 1; if (inblock) printf "%s",metrics }
    ' "$temporary" "$publisher" > "$composed"
    replacement_metadata=$(ruby -ryaml -rjson -e 'puts JSON.generate(YAML.safe_load(STDIN.read))' < "$composed" |
      jq -ceS '.metadata')
    [[ "$source_metadata" == "$replacement_metadata" ]] || {
      printf 'ERROR: Unexpected publisher metadata change\n' >&2; exit 1;
    }
    ln "$composed" "$output"
else
    ln "$temporary" "$output"
fi
