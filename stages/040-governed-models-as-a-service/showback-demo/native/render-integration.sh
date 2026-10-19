#!/usr/bin/env bash
# Offline only. Render inert ConfigMaps; never render/apply active native resources.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { echo 'Usage: render-integration.sh [--write [DIR] | --check [DIR]] [--schema-dir DIR --artifact-pins FILE]' >&2; exit 2; }
fail() { echo "Native integration: $*" >&2; exit 2; }
mode=preview; schemas=''; pins=''
directory="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo/native-inputs"
while (($#)); do
    case "$1" in
        --write|--check)
            [[ "$mode" == preview ]] || usage
            mode=${1#--}; shift
            if (($#)) && [[ "$1" != --* ]]; then directory=$1; shift; fi
            ;;
        --schema-dir) (($#>=2)) || usage; schemas=$2; shift 2 ;;
        --artifact-pins) (($#>=2)) || usage; pins=$2; shift 2 ;;
        *) usage ;;
    esac
done
command -v jq >/dev/null
command -v ruby >/dev/null
if [[ -z "$schemas" && -z "$pins" ]]; then
    schemas="$SCRIPT_DIR/evidence/schemas"
    pins="$SCRIPT_DIR/evidence/artifacts.json"
fi
[[ -n "$schemas" && -f "$pins" ]] || usage
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$pins" "$work/artifacts.json"
for name in config tenant lokistack; do
    [[ -f "$schemas/$name-crd.json" ]] || fail "missing $name-crd.json"
    cp "$schemas/$name-crd.json" "$work/$name-crd.json"
done
schemas=$work
pins="$work/artifacts.json"
# These are targeted field checks, not Kubernetes CEL/defaulting/server validation.
for name in config tenant lokistack; do
    file="$schemas/$name-crd.json"
    [[ -f "$file" ]] || fail "missing $name-crd.json"
    digest=$(shasum -a 256 "$file" | cut -d ' ' -f 1)
    jq -e --arg key "$name-crd.json" --arg hash "$digest" '.schema_sha256[$key]==$hash' "$pins" >/dev/null || fail "schema hash mismatch: $name"
done
jq -e '
  .kind=="CustomResourceDefinition" and .spec.group=="maas.opendatahub.io" and .spec.names.kind=="Config" and
  any(.spec.versions[];.served==true and .name=="v1alpha1" and
    .schema.openAPIV3Schema.properties.spec.properties.usageLogging.type=="boolean")
' "$schemas/config-crd.json" >/dev/null || fail 'Config usageLogging field not verified'
jq -e '
  .kind=="CustomResourceDefinition" and .spec.group=="maas.opendatahub.io" and .spec.names.kind=="MaasTenantConfig" and
  any(.spec.versions[];.served==true and .name=="v1alpha1" and
    (.schema.openAPIV3Schema.properties.spec.properties.telemetry.properties as $t |
      $t.metrics.properties.captureUser.type=="boolean" and ($t|has("logs")|not)))
' "$schemas/tenant-crd.json" >/dev/null || fail 'expected RHOAI 3.5 metrics-only tenant telemetry schema'
jq -e '
  .kind=="CustomResourceDefinition" and .spec.group=="loki.grafana.com" and .spec.names.kind=="LokiStack" and
  any(.spec.versions[];.served==true and .name=="v1" and
    (.schema.openAPIV3Schema.properties.spec.properties as $s |
     ($s.managementState.enum|index("Managed"))!=null and ($s.size.enum|index("1x.demo"))!=null and
     $s.storage.properties.schemas.type=="array" and $s.storage.properties.secret.type=="object" and
     $s.storageClassName.type=="string" and ($s.tenants.properties.mode.enum|index("openshift-logging"))!=null and
     $s.limits.properties.global.properties.retention.properties.days.type=="integer" and
     $s.limits.properties.global.properties.otlp.properties.streamLabels.properties.resourceAttributes.type=="array"))
' "$schemas/lokistack-crd.json" >/dev/null || fail 'LokiStack candidate fields not verified'
jq -e '
  .schema_version==1 and (.evidence_kind=="verified" or .evidence_kind=="synthetic_fixture") and
  (.source|type)=="string" and (.source|length)>0 and
  .config_usage_logging_behavior=="enable_switch" and .live_qualified==false and
  (.components|keys)==["ai_gateway_operator","loki_operator","maas_controller","payload_processor"] and
  all(.components[];
    (.image|test("^.+@sha256:[0-9a-f]{64}$")) and (.source_commit|test("^[0-9a-f]{40}$")) and
    (.product_identity|type)=="string" and (.product_identity|length)>0) and
  .metering_backend.artifact_verified==false
' "$pins" >/dev/null || fail 'artifact digest/source identity metadata incomplete'
qualification=$(jq -c '{schema_fields_checked:true,artifact_metadata_checked:true,live_qualified:false,evidence_kind,source,
  config_usage_logging_behavior,components,metering_backend,schema_sha256,schema_origins}' "$pins")
resources=$(jq -cn --slurpfile i "$SCRIPT_DIR/integration.json" --slurpfile p "$SCRIPT_DIR/provenance.json" --argjson qualification "$qualification" '
  $i[0] as $i | $p[0] as $p |
  if $i.state!="inert-review-inputs" or $p.live_qualified!=false or
    $i.gateway!={name:"maas-default-gateway",namespace:"openshift-ingress"} or
    $i.metering.plugin_parameters.meteringURL!="https://metering.invalid" or
    ([$i.metering.profile_candidate.plugins[]|select(.type=="external-metering-streaming")|.parameters]
      !=[$i.metering.plugin_parameters]) or
    $i.loki.config_usage_logging_behavior!="enable_switch" or
    ($i.loki|has("tenant_patch_candidate")) or
    $i.loki.stack_candidate.spec.storageClassName!="gp3-csi" or
    $i.loki.stack_candidate.spec.limits.global.retention.days!=30
  then error("native defaults must remain inert and match the verified release candidate") else . end |
  ["loki","metering"] | map(. as $lane |
    {apiVersion:"v1",kind:"ConfigMap",metadata:{name:("showback-native-"+$lane+"-inputs"),
      namespace:(if $lane=="loki" then "redhat-ods-monitoring" else "redhat-ai-gateway-infra" end),
      labels:{"app.kubernetes.io/name":("showback-native-"+$lane+"-inputs"),
        "app.kubernetes.io/component":"native-integration-review",
        "app.kubernetes.io/part-of":(if $lane=="loki" then "observability" else "maas" end),
        "app.kubernetes.io/managed-by":"argocd","demo.rhoai.io/stage":"040"},
      annotations:{"demo.rhoai.io/state":"inert-review-inputs"}},
      data:{"README":"Review data only. No controller consumes this ConfigMap. No activation or deployment path is provided.",
        "candidate.json":($i[$lane]|tojson),"provenance.json":($p|tojson),"qualification.json":($qualification|tojson)}})
')
if [[ "$mode" == preview ]]; then printf '%s\n' "$resources" | jq .; exit 0; fi
if [[ "$mode" == write ]]; then mkdir -p "$directory"; else [[ -d "$directory" ]] || fail 'check directory missing'; fi
while IFS= read -r resource; do
    file=$(printf '%s' "$resource" | jq -r '.metadata.name+".yaml"')
    rendered=$(printf '%s' "$resource" | ruby -rjson -ryaml -e 'puts YAML.dump(JSON.parse(STDIN.read))')
    if [[ "$mode" == write ]]; then printf '%s\n' "$rendered" > "$directory/$file"
    elif ! cmp -s <(printf '%s\n' "$rendered") "$directory/$file"; then fail "generated drift: $file"; fi
done < <(printf '%s' "$resources" | jq -c '.[]')
