#!/usr/bin/env bash
# Stage 020: GPU infrastructure (Node Feature Discovery, NVIDIA GPU Operator, Kueue, GPU MachineSets, quotas).
#   deploy.sh [--revision REF]
#       Deploys the component Applications at the reviewed published commit (REF defaults to GIT_REPO_BRANCH, then
#       HEAD) after the read-only prerequisites: Stage 010 reconciled, every generated GPU MachineSet still matching
#       the active CPU worker it was derived from. The GPU MachineSets are declared with zero replicas.
#   deploy.sh --gpus N
#       Scales GPU capacity: 1 or 2 starts that many workers in the selected pool (GPU_POOL=rtxpro6000, the default,
#       or l40s; GPU_ZONE for rtxpro6000, default us-east-2a) and waits for allocatable GPUs and the NVIDIA
#       ClusterPolicy; 0 parks every GPU pool (model pods become unavailable). Argo CD ignores the live count.
#   deploy.sh --generate-machinesets SOURCE [--write]
#       Derives every reviewed GPU pool from the active AWS CPU worker MachineSet SOURCE (L40S in SOURCE's zone,
#       RTX PRO 6000 in every zone with one active CPU worker pool). Prints them, or with --write replaces the pool
#       files under gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets/ and the replica exceptions
#       in the 020-gpu-machinesets Application, for review and publication before the next deploy.
# Usage: stages/020-gpu-infrastructure-private-ai/deploy.sh [--revision REF | --gpus N | --generate-machinesets SOURCE [--write]]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/lib.sh"
MODE=deploy ref="${GIT_REPO_BRANCH:-HEAD}" GPUS="" SOURCE_MACHINESET="${RHOAI_SOURCE_WORKER_MACHINESET:-}" WRITE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) ref="${2:?}"; shift 2 ;;
    --gpus) MODE=gpus GPUS="${2:?}"; shift 2 ;;
    --generate-machinesets) MODE=generate SOURCE_MACHINESET="${2:?}"; shift 2 ;;
    --write) WRITE=true; shift ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
load_env >&2
check_oc_logged_in >&2

# ── GPU capacity ──────────────────────────────────────────────────────────────
GPU_POOL="${GPU_POOL:-rtxpro6000}"
GPU_ZONE="${GPU_ZONE:-us-east-2a}"
case "$GPU_POOL" in
  rtxpro6000) GPU_POOL_LABEL=nvidia-rtxpro6000; GPU_POOL_INSTANCE=g7e.2xlarge ;;
  l40s)       GPU_POOL_LABEL=nvidia-gpu;        GPU_POOL_INSTANCE=g6e.2xlarge ;;
  *) echo "Unknown GPU_POOL '$GPU_POOL' (rtxpro6000 or l40s)" >&2; exit 1 ;;
esac
GPU_POOL_LABELS='["nvidia-gpu","nvidia-rtxpro6000"]'
GPU_RESUME_TIMEOUT_SECONDS="${GPU_RESUME_TIMEOUT_SECONDS:-1800}"
GPU_RESUME_POLL_SECONDS="${GPU_RESUME_POLL_SECONDS:-15}"
discover_gpu_machineset() {
    local matches
    matches="$(oc --request-timeout=10s get machineset -n openshift-machine-api -o json | jq -r '.items[] | select(.metadata.labels["cluster-api/accelerator"] == $label and .spec.template.spec.providerSpec.value.instanceType == $itype and ($zone == "" or .spec.template.spec.providerSpec.value.placement.availabilityZone == $zone)) | .metadata.name' --arg label "$GPU_POOL_LABEL" --arg itype "$GPU_POOL_INSTANCE" --arg zone "$([[ $GPU_POOL == rtxpro6000 ]] && echo "$GPU_ZONE")")"
    [[ $(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ') == 1 ]] || { log_error "Select one unambiguous reviewed GPU MachineSet"; return 1; }
    [[ -z "${GPU_MACHINESET_NAME:-}" || "$GPU_MACHINESET_NAME" == "$matches" ]] || { log_error "Explicit MachineSet differs from reviewed GPU pool"; return 1; }
    oc --request-timeout=10s get machineset "$matches" -n openshift-machine-api -o json | jq -e '.metadata.ownerReferences == null and (.metadata.annotations["argocd.argoproj.io/tracking-id"] | startswith("020-gpu-machinesets:"))' >/dev/null || { log_error "GPU pool ownership is not Stage 020"; return 1; }
    printf '%s\n' "$matches"
}

wait_for_gpu_capacity() {
    local expected="$1"
    local timeout="${2:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 ready_nodes alloc_nodes

    log_info "Waiting for $expected GPU node(s) with allocatable nvidia.com/gpu"
    while (( elapsed < timeout )); do
        ready_nodes="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get nodes -l "cluster-api/accelerator=$GPU_POOL_LABEL" --no-headers 2>/dev/null | grep -c ' Ready ' || true)"
        alloc_nodes="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get nodes -l "cluster-api/accelerator=$GPU_POOL_LABEL" -o json 2>/dev/null \
            | jq '[.items[] | select(((.status.allocatable["nvidia.com/gpu"] // "0") | tonumber) >= 1)] | length' 2>/dev/null || echo 0)"

        if [[ "$ready_nodes" -ge "$expected" && "$alloc_nodes" -ge "$expected" ]]; then
            log_success "GPU capacity is ready: ready_nodes=$ready_nodes allocatable_gpu_nodes=$alloc_nodes"
            return 0
        fi

        log_info "GPU capacity not ready yet: ready_nodes=$ready_nodes allocatable_gpu_nodes=$alloc_nodes expected=$expected"
        sleep "$GPU_RESUME_POLL_SECONDS"
        elapsed=$((elapsed + GPU_RESUME_POLL_SECONDS))
    done

    log_error "Timed out waiting for GPU capacity"
    return 1
}

wait_for_gpu_operator_ready() {
    local timeout="${1:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 state ready

    if ! oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get clusterpolicy gpu-cluster-policy >/dev/null 2>&1; then
        log_warn "NVIDIA ClusterPolicy was not found; Stage 020 validation will report details"
        return 0
    fi

    log_info "Waiting for NVIDIA ClusterPolicy to return to ready"
    while (( elapsed < timeout )); do
        state="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.state}' 2>/dev/null || true)"
        if [[ "$state" == "ready" ]]; then
            log_success "NVIDIA ClusterPolicy is ready"
            return 0
        fi

        log_info "NVIDIA ClusterPolicy not ready yet: state=${state:-Unknown}"
        sleep "$GPU_RESUME_POLL_SECONDS"
        elapsed=$((elapsed + GPU_RESUME_POLL_SECONDS))
    done

    log_error "Timed out waiting for native NVIDIA ClusterPolicy ready state"
    return 1
}

scale_gpu_up() {
    local replicas="${1:-$GPU_MACHINESET_REPLICAS}"
    local ms
    ms="$(discover_gpu_machineset)" || exit 1

    [[ "$replicas" =~ ^[12]$ ]] || { log_error "Reviewed topology is one or two GPU workers per pool"; return 1; }
    log_info "Scaling GPU MachineSet $ms to $replicas"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" scale machineset "$ms" -n openshift-machine-api --replicas="$replicas"
    wait_for_gpu_capacity "$replicas"
    wait_for_gpu_operator_ready
}

scale_gpu_down() {
    local ms
    # Every reviewed GPU pool, so no forgotten pool keeps billing.
    for ms in $(oc --request-timeout=10s get machineset -n openshift-machine-api -o json \
        | jq -r --argjson labels "$GPU_POOL_LABELS" '.items[] | select((.metadata.labels["cluster-api/accelerator"] // "") as $l | $labels | index($l)) | select(.spec.replicas > 0) | .metadata.name'); do
        log_warn "Scaling GPU MachineSet $ms to 0. Private model pods will become unavailable."
        oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" scale machineset "$ms" -n openshift-machine-api --replicas=0
    done
}

if [[ "$MODE" == gpus ]]; then
  case "$GPUS" in
    0) scale_gpu_down ;;
    1|2) scale_gpu_up "$GPUS" ;;
    *) echo "ERROR: --gpus takes 0, 1 or 2" >&2; exit 1 ;;
  esac
  exit 0
fi

# ── GPU MachineSet generation ─────────────────────────────────────────────────
OUTPUT_DIR="gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets"
APP_MANIFEST="gitops/applications/020-gpu-machinesets.yaml"
# Reviewed GPU pools: pool|file|name infix|instance type|cluster-api/accelerator|demo.rhoai.io/gpu-pool label|zones|GPU:memoryMb:vCPU|file comment
# zones "source" = the --source worker's zone only; "all" = every zone with one active CPU worker pool (a Machine API
# MachineSet launches in exactly one subnet and zone and never retries another, so "any zone with capacity" needs one
# MachineSet per zone). Capacity annotations ("-" for none) are what the cluster autoscaler reads to scale from zero.
# The file comment ("~" separates lines) is written at the top of the pool file.
POOLS='l40s|machineset-gpu.yaml|gpu|g6e.2xlarge|nvidia-gpu|-|source|1:65536:8|L40S pool: g6e.2xlarge (1x 48GB GPU), Kueue flavor gpu-l40s; one MachineSet in the source worker zone.~Scale with stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus N (GPU_POOL=l40s).
rtxpro6000|machineset-rtxpro6000.yaml|gpu-rtxpro6000|g7e.2xlarge|nvidia-rtxpro6000|rtxpro6000|all|-|RTX PRO 6000 Blackwell pool: g7e.2xlarge (1x 96GB GPU, FP8 and NVFP4), Kueue flavor gpu-rtxpro6000.~One MachineSet per zone; the Machine API fills in the GPU/CPU/memory annotations from DescribeInstanceTypes.~Scale with stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus N (default pool).'

generate_machinesets() {
  [[ -n "$SOURCE_MACHINESET" ]] || { echo "ERROR: name an active CPU worker MachineSet: --generate-machinesets SOURCE." >&2; exit 1; }
  for cmd in oc jq ruby; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done

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
        echo "# Generated by stages/020-gpu-infrastructure-private-ai/deploy.sh --generate-machinesets; replicas are 0 in Git (Argo CD ignores the live count)."
        to_yaml <<<"$docs"; } >"$ROOT_DIR/$OUTPUT_DIR/$file"
      echo "✓ Wrote $OUTPUT_DIR/$file ($(jq length <<<"$docs") MachineSets)"
    else
      to_yaml <<<"$docs"
    fi
  done <<<"$POOLS"

  if [[ "$WRITE" == "true" ]]; then
    # Every generated MachineSet keeps its live replica count: an exact-name exception per MachineSet goes into the
    # 020-gpu-machinesets Application manifest, which deploy.sh applies as it is.
    ignore=$(jq -n '[$ARGS.positional | sort[] | {group: "machine.openshift.io", kind: "MachineSet", name: .,
      namespace: "openshift-machine-api", jsonPointers: ["/spec/replicas"]}]' --args "${NAMES[@]}")
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$ROOT_DIR/$APP_MANIFEST" |
      jq --argjson ignore "$ignore" '[.spec.ignoreDifferences = $ignore]' | to_yaml >"$ROOT_DIR/$APP_MANIFEST.tmp"
    mv "$ROOT_DIR/$APP_MANIFEST.tmp" "$ROOT_DIR/$APP_MANIFEST"
    echo "✓ Replica exceptions for ${#NAMES[@]} MachineSets written to $APP_MANIFEST"
    echo "  Review native provider identifiers, AMI compatibility, disk and retention before publishing."
  else
    echo >&2
    echo "Preview of ${#NAMES[@]} MachineSets from source $SOURCE_MACHINESET; add --write to replace the pool files." >&2
  fi
}
if [[ "$MODE" == generate ]]; then
  generate_machinesets
  exit 0
fi

# ── Deploy ────────────────────────────────────────────────────────────────────
require_env GIT_REPO_URL "reviewed Stage 020 source repository"
assert_required_env
STAGE_APPS="$ROOT_DIR/scripts/stage-apps.sh"
revision=$("$STAGE_APPS" select 020 --ref "$ref" --repo-url "$GIT_REPO_URL" \
)
stage_gitops="$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai"
app_manifest="$ROOT_DIR/gitops/applications/020-gpu-machinesets.yaml"
[[ -f "$stage_gitops/020-gpu-machinesets/machineset-gpu.yaml" ]] || { echo 'ERROR: generate, review and publish the environment MachineSets first (deploy.sh --generate-machinesets SOURCE --write).' >&2; exit 1; }
# All prerequisites are read-only and run before the first Application write.
"$STAGE_APPS" status 010 >/dev/null || { echo "ERROR: Stage 010 must be reconciled first" >&2; exit 1; }
"$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io |
  grep -qx /spec/components/kueue || { echo "ERROR: Stage 010 must delegate /spec/components/kueue" >&2; exit 1; }
oc --request-timeout=10s get csv -A -o json | jq -e 'any(.items[]; (.metadata.name | startswith("cert-manager-operator.v1.20."))
  and .status.phase == "Succeeded")' >/dev/null || { echo "ERROR: Provider cert-manager prerequisite unavailable" >&2; exit 1; }
# Existing Applications and objects must already be ours; MachineSets are checked against their sources below.
"$STAGE_APPS" preflight 020 --repo-url "$GIT_REPO_URL" --skip-kind MachineSet

# Every generated GPU MachineSet must still match the active CPU worker it was derived from.
machinesets=$(oc kustomize "$stage_gitops/020-gpu-machinesets" |
  ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' | jq -c '[.[] | select(.kind == "MachineSet")]')
[[ $(jq length <<<"$machinesets") -gt 0 ]] || { echo "ERROR: No generated GPU MachineSets" >&2; exit 1; }
infra=$(oc --request-timeout=10s get infrastructure cluster -o json)
cluster=$(jq -r '.status.infrastructureName' <<<"$infra")
region=$(jq -r '.status.platformStatus.aws.region // ""' <<<"$infra")
[[ $(jq -r '.status.platformStatus.type' <<<"$infra") == AWS ]] || { echo "ERROR: AWS environment required" >&2; exit 1; }
oc --request-timeout=10s get nodes -o json | jq -e '(.items | length) > 0 and all(.items[]; .status.nodeInfo.architecture == "amd64")' \
  >/dev/null || { echo "ERROR: Reviewed native source requires amd64 nodes" >&2; exit 1; }
for name in $(jq -r '.[].metadata.name' <<<"$machinesets"); do
  expected=$(jq -c --arg n "$name" '.[] | select(.metadata.name == $n)' <<<"$machinesets")
  jq -e --arg c "$cluster" '[.metadata.labels, .spec.selector.matchLabels, .spec.template.metadata.labels]
    | all(.[]; .["machine.openshift.io/cluster-api-cluster"] == $c)' <<<"$expected" >/dev/null ||
    { echo "ERROR: $name: generated intent belongs to another cluster" >&2; exit 1; }
  jq -e '.spec.replicas == 0' <<<"$expected" >/dev/null ||
    { echo "ERROR: $name: declare replicas 0; deploy.sh --gpus scales the pool" >&2; exit 1; }
  source_name=$(jq -r '.metadata.annotations["demo.rhoai.io/source-machineset"]' <<<"$expected")
  source=$(oc --request-timeout=10s get machineset "$source_name" -n openshift-machine-api -o json)
  jq -e '.spec.replicas > 0 and (.status.readyReplicas // 0) > 0' <<<"$source" >/dev/null ||
    { echo "ERROR: $name: CPU source pool $source_name is no longer active" >&2; exit 1; }
  # The generated provider is the source's, with the GPU instance type and a 200 GiB encrypted gp3 root volume.
  jq -n -e --argjson s "$source" --argjson e "$expected" --arg region "$region" '
    ($s.spec.template.spec.providerSpec.value) as $p
    | $p.placement.region == $region and ($p.capacityReservationId // "") == ""
    and ($p | .instanceType = $e.spec.template.spec.providerSpec.value.instanceType
            | .blockDevices[0].ebs += {volumeSize: 200, volumeType: "gp3", encrypted: true})
        == $e.spec.template.spec.providerSpec.value' >/dev/null ||
    { echo "ERROR: $name: provider differs from the active source (region, reservation or AMI); re-run deploy.sh --generate-machinesets" >&2; exit 1; }
  live=$(oc --request-timeout=10s get machineset "$name" -n openshift-machine-api --ignore-not-found -o json)
  if [[ -n "$live" ]]; then
    jq -n -e --argjson l "$live" --argjson e "$expected" '($l.metadata.ownerReferences // [] | length) == 0
      and ($l.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("020-gpu-machinesets:"))
      and $l.spec.selector == $e.spec.selector and $l.spec.template == $e.spec.template' >/dev/null ||
      { echo "ERROR: $name: existing MachineSet is foreign, unadopted or differs from the reviewed source" >&2; exit 1; }
  fi
done
# 020-gpu-machinesets must hold a replica exception (ignoreDifferences) for every GPU MachineSet.
ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0]))' "$app_manifest" |
  jq -e --argjson ms "$machinesets" '([.spec.ignoreDifferences[]? | select(.kind == "MachineSet") | .name] | sort)
    == ([$ms[].metadata.name] | sort)' >/dev/null ||
  { echo "ERROR: 020-gpu-machinesets lacks a replica exception per GPU MachineSet (re-run deploy.sh --generate-machinesets --write)" >&2; exit 1; }
echo "PASS $(jq length <<<"$machinesets") GPU MachineSets match their active CPU sources and carry replica exceptions"
require_node_sizing
# First change: the component Applications at the reviewed commit; deploy applies, syncs and waits for each.
"$STAGE_APPS" deploy 020 --revision "$revision" --repo-url "$GIT_REPO_URL"
echo 'Stage 020 components reconciled; native Automatic operator reconciliation is bounded below.'
check_operator_policy "$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai" --wait 900
log_info "GPU pools are declared at zero replicas: start one with deploy.sh --gpus 1, park all with --gpus 0."
