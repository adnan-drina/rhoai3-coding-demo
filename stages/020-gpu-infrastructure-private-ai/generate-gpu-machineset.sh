#!/usr/bin/env bash
# generate-gpu-machineset.sh - derive every Stage 020 AWS GPU MachineSet pool from
# the live CPU worker MachineSets in the currently guarded OpenShift environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

WRITE=false
SOURCE_MACHINESET="${RHOAI_SOURCE_WORKER_MACHINESET:-}"
OUTPUT_DIR="gitops/stages/020-gpu-infrastructure-private-ai/gpu-machinesets"
APP_MANIFEST="gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai/gpu-machinesets.yaml"

# Reviewed GPU pools: pool|file|name infix|instance type|cluster-api/accelerator|demo.rhoai.io/gpu-pool label|zones|GPU:memoryMb:vCPU|file comment
# zones "source" = the --source worker's zone only; "all" = every zone with one active CPU worker pool (a Machine API
# MachineSet launches in exactly one subnet and zone and never retries another, so "any zone with capacity" needs one
# MachineSet per zone). Capacity annotations ("-" for none) are what the cluster autoscaler reads to scale from zero.
# The file comment ("~" separates lines) is written at the top of the pool file.
POOLS='l40s|machineset-gpu.yaml|gpu|g6e.2xlarge|nvidia-gpu|-|source|1:65536:8|L40S pool: g6e.2xlarge (1x 48GB GPU), Kueue flavor gpu-l40s; one MachineSet in the source worker zone.~Scale with scripts/platform/resume-gpu-demo.sh (GPU_POOL=l40s).
rtxpro6000|machineset-rtxpro6000.yaml|gpu-rtxpro6000|g7e.2xlarge|nvidia-rtxpro6000|rtxpro6000|all|-|RTX PRO 6000 Blackwell pool: g7e.2xlarge (1x 96GB GPU, FP8 and NVFP4), Kueue flavor gpu-rtxpro6000.~One MachineSet per zone; the Machine API fills in the GPU/CPU/memory annotations from DescribeInstanceTypes.~Scale with scripts/platform/resume-gpu-demo.sh (default pool).'

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write)
      WRITE=true
      shift
      ;;
    --source)
      if [[ -z "${2:-}" ]]; then
        echo "ERROR: --source requires a MachineSet name." >&2
        exit 1
      fi
      SOURCE_MACHINESET="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  ./stages/020-gpu-infrastructure-private-ai/generate-gpu-machineset.sh --source <worker-machineset> [--write]

Generates every reviewed GPU pool (L40S, RTX PRO 6000) from the active AWS CPU
worker MachineSets: the L40S pool in the --source worker's zone, the other pools in
every zone that has exactly one active CPU worker pool. Each MachineSet is declared
with replicas 0; scripts/platform/resume-gpu-demo.sh scales the pool in use, and the
Application ignores /spec/replicas so Argo CD keeps the live count.

By default, prints the MachineSets to stdout. With --write, replaces the pool files in
gitops/stages/020-gpu-infrastructure-private-ai/gpu-machinesets/ and writes the replica
exception for every generated MachineSet to the 020-gpu-machinesets Application manifest.

Environment overrides:
  RHOAI_SOURCE_WORKER_MACHINESET  source CPU worker MachineSet (same as --source)
EOF
      exit 0
      ;;
    *)
      if [[ -z "$SOURCE_MACHINESET" ]]; then
        SOURCE_MACHINESET="$1"
        shift
      else
        echo "ERROR: unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env >&2
check_oc_logged_in >&2
[[ -n "$SOURCE_MACHINESET" ]] || { echo "ERROR: select an active CPU worker MachineSet with --source." >&2; exit 1; }
for cmd in oc jq ruby python3; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done

# Root volume sized for large modelcar images: a 100GB worker default hits
# kubelet DiskPressure mid-pull (~36GB qwen modelcar + base images) and image
# GC thrashes the pull.
GPU_VOLUME_SIZE=200
GPU_VOLUME_TYPE=gp3

MACHINESETS_JSON=$(oc get machinesets -n openshift-machine-api -o json --request-timeout=10s)

# Active native AWS CPU worker pools with a consistent identity; GPU pools are derived only from these.
ACTIVE_CPU_WORKERS='
 .spec.replicas > 0 and .status.readyReplicas > 0
 and .spec.template.metadata.labels["machine.openshift.io/cluster-api-machine-role"] == "worker"
 and (.metadata.labels["cluster-api/accelerator"] // "") == ""
 and .spec.template.spec.providerSpec.value.kind == "AWSMachineProviderConfig"
 and (.spec.template.spec.providerSpec.value.instanceType | test("^[mc][0-9]+[a-z]*\\."))
 and (.spec.template.spec.providerSpec.value.capacityReservationId // "") == ""
 and (.spec.template.spec.providerSpec.value.ami.id | type == "string")
 and (.spec.template.spec.providerSpec.value.placement.region | length > 0)
 and (.spec.template.spec.providerSpec.value.placement.availabilityZone | length > 0)'

SOURCE_JSON=$(jq --arg name "$SOURCE_MACHINESET" -c '.items[] | select(.metadata.name == $name)' <<<"$MACHINESETS_JSON")
[[ -n "$SOURCE_JSON" && "$SOURCE_JSON" != "null" ]] || { echo "ERROR: source MachineSet not found: $SOURCE_MACHINESET" >&2; exit 1; }
jq -e "$ACTIVE_CPU_WORKERS" <<<"$SOURCE_JSON" >/dev/null || { echo "ERROR: source is not an active native AWS CPU worker pool." >&2; exit 1; }

INFRA_JSON=$(oc --request-timeout=10s get infrastructure cluster -o json)
NODES_JSON=$(oc --request-timeout=10s get nodes -o json)
jq -e '.status.platformStatus.type == "AWS"' <<<"$INFRA_JSON" >/dev/null || { echo "ERROR: AWS environment required." >&2; exit 1; }
jq -e '.items | length > 0 and all(.[]; .status.nodeInfo.architecture == "amd64")' <<<"$NODES_JSON" >/dev/null || { echo "ERROR: reviewed source requires an amd64 cluster." >&2; exit 1; }
CLUSTER_ID=$(jq -r '.metadata.labels["machine.openshift.io/cluster-api-cluster"] // .spec.selector.matchLabels["machine.openshift.io/cluster-api-cluster"] // empty' <<<"$SOURCE_JSON")
[[ -n "$CLUSTER_ID" && "$CLUSTER_ID" == "$(jq -r '.status.infrastructureName' <<<"$INFRA_JSON")" ]] || { echo "ERROR: source provider cluster identity differs from Infrastructure." >&2; exit 1; }
SOURCE_AZ=$(jq -r '.spec.template.spec.providerSpec.value.placement.availabilityZone' <<<"$SOURCE_JSON")

# One source CPU worker per zone: the --source worker for its own zone, otherwise the zone's only active worker pool.
ZONE_SOURCES=$(jq -r --arg source "$SOURCE_MACHINESET" --arg az "$SOURCE_AZ" --arg cluster "$CLUSTER_ID" "
  [.items[] | select($ACTIVE_CPU_WORKERS)
   | select((.metadata.labels[\"machine.openshift.io/cluster-api-cluster\"] // .spec.selector.matchLabels[\"machine.openshift.io/cluster-api-cluster\"]) == \$cluster)
   | {az: .spec.template.spec.providerSpec.value.placement.availabilityZone, name: .metadata.name}]
  | group_by(.az)[]
  | if .[0].az == \$az then {az: .[0].az, names: [\$source]} else {az: .[0].az, names: [.[].name]} end
  | \"\(.az) \(.names | join(\",\"))\"" <<<"$MACHINESETS_JSON")
while read -r az names; do
  [[ "$names" != *,* ]] || { echo "ERROR: zone $az has several active CPU worker pools ($names); scale extras to 0 or extend the generator." >&2; exit 1; }
done <<<"$ZONE_SOURCES"

generate() { # source-json name instance accelerator pool-label capacity
  jq --arg name "$2" --arg source "$(jq -r '.metadata.name' <<<"$1")" --arg cluster "$CLUSTER_ID" \
    --arg instance "$3" --arg accelerator "$4" --arg pool "$5" --arg capacity "$6" \
    --argjson volsize "$GPU_VOLUME_SIZE" --arg voltype "$GPU_VOLUME_TYPE" '
  ($pool | if . == "-" then {} else {"demo.rhoai.io/gpu-pool": .} end) as $poolLabel
  | ($capacity | if . == "-" then {} else split(":") as $c
      | {"machine.openshift.io/GPU": $c[0], "machine.openshift.io/memoryMb": $c[1], "machine.openshift.io/vCPU": $c[2]} end) as $capacityAnnotations
  | del(.metadata.creationTimestamp, .metadata.generation, .metadata.managedFields, .metadata.ownerReferences,
        .metadata.resourceVersion, .metadata.uid, .status)
  | .metadata.name = $name
  | .metadata.namespace = "openshift-machine-api"
  | .metadata.annotations = ({
      "argocd.argoproj.io/sync-options": "Prune=false,Delete=false",
      "demo.rhoai.io/source-machineset": $source
    } + $capacityAnnotations)
  | .metadata.labels = ({
      "app.kubernetes.io/part-of": "gpu-infra",
      "app.kubernetes.io/name": "aws-gpu-machineset",
      "app.kubernetes.io/component": "gpu-worker",
      "app.kubernetes.io/managed-by": "argocd",
      "cluster-api/accelerator": $accelerator,
      "machine.openshift.io/cluster-api-cluster": $cluster
    } + $poolLabel)
  | .spec.template.metadata |= {labels: .labels}
  | .spec.template.spec.metadata |= {labels: .labels}
  | .spec.template.spec.providerSpec.value.blockDevices[0].ebs.encrypted = true
  | .spec.replicas = 0
  | .spec.selector.matchLabels["machine.openshift.io/cluster-api-cluster"] = $cluster
  | .spec.selector.matchLabels["machine.openshift.io/cluster-api-machineset"] = $name
  | .spec.template.metadata.labels = ((.spec.template.metadata.labels // {}) + {
      "cluster-api/accelerator": $accelerator,
      "machine.openshift.io/cluster-api-cluster": $cluster,
      "machine.openshift.io/cluster-api-machine-role": "worker",
      "machine.openshift.io/cluster-api-machine-type": "worker",
      "machine.openshift.io/cluster-api-machineset": $name,
      "node-role.kubernetes.io/gpu": ""
    } + $poolLabel)
  | .spec.template.spec.metadata.labels = ((.spec.template.spec.metadata.labels // {}) + {
      "cluster-api/accelerator": $accelerator,
      "node-role.kubernetes.io/gpu": ""
    } + $poolLabel)
  | .spec.template.spec.providerSpec.value.instanceType = $instance
  | .spec.template.spec.providerSpec.value.blockDevices[0].ebs.volumeSize = $volsize
  | .spec.template.spec.providerSpec.value.blockDevices[0].ebs.volumeType = $voltype
  | .spec.template.spec.taints = [{"effect": "NoSchedule", "key": "nvidia-gpu-only"}]
' <<<"$1"
}

to_yaml() { ruby -rjson -ryaml -e 'puts JSON.parse(STDIN.read).map { |d| YAML.dump(d) }.join'; }

NAMES=()
while IFS='|' read -r pool file infix instance accelerator pool_label zones capacity comment; do
  docs="[]"
  while read -r az source_name; do
    [[ "$zones" == all || "$az" == "$SOURCE_AZ" ]] || continue
    source_json=$(jq --arg name "$source_name" -c '.items[] | select(.metadata.name == $name)' <<<"$MACHINESETS_JSON")
    name="${CLUSTER_ID}-${infix}-${az}"
    docs=$(jq -c --argjson doc "$(generate "$source_json" "$name" "$instance" "$accelerator" "$pool_label" "$capacity")" '. + [$doc]' <<<"$docs")
    NAMES+=("$name")
  done <<<"$ZONE_SOURCES"
  [[ "$(jq length <<<"$docs")" -gt 0 ]] || { echo "ERROR: no zone source for GPU pool $pool." >&2; exit 1; }
  if [[ "$WRITE" == "true" ]]; then
    { tr '~' '\n' <<<"$comment" | sed 's/^/# /'
      echo "# Generated by stages/020-gpu-infrastructure-private-ai/generate-gpu-machineset.sh; replicas are 0 in Git (Argo CD ignores the live count)."
      to_yaml <<<"$docs"; } >"$ROOT_DIR/$OUTPUT_DIR/$file"
    echo "✓ Wrote $OUTPUT_DIR/$file ($(jq length <<<"$docs") MachineSets)"
  else
    to_yaml <<<"$docs"
  fi
done <<<"$POOLS"

if [[ "$WRITE" == "true" ]]; then
  # Every generated MachineSet keeps its live replica count: an exact-name exception per MachineSet goes into the
  # 020-gpu-machinesets Application manifest, which deploy.sh applies as it is.
  python3 - "$ROOT_DIR" "$OUTPUT_DIR" "$APP_MANIFEST" "${NAMES[@]}" <<'PY_PATCH'
import json, pathlib, subprocess, sys
root, out_dir, manifest, names = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]
def to_yaml(data):
    return subprocess.check_output(['ruby', '-rjson', '-ryaml', '-e', 'puts YAML.dump(JSON.parse(STDIN.read))'], input=json.dumps(data), text=True)
ignore = [{'group': 'machine.openshift.io', 'kind': 'MachineSet', 'name': n, 'namespace': 'openshift-machine-api',
           'jsonPointers': ['/spec/replicas']} for n in sorted(names)]
app_path = root / manifest
app = json.loads(subprocess.check_output(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(app_path)], text=True))
app['spec']['ignoreDifferences'] = ignore
app_path.write_text(to_yaml(app))
PY_PATCH
  echo "✓ Replica exceptions for ${#NAMES[@]} MachineSets written to $APP_MANIFEST"
  echo "  Review native provider identifiers, AMI compatibility, disk and retention before publishing."
else
  echo >&2
  echo "Preview of ${#NAMES[@]} MachineSets from source $SOURCE_MACHINESET; re-run with --write to replace the pool files." >&2
fi
