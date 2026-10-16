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
#   The GPU MachineSet files are generated per cluster beforehand by machinesets/generate.sh SOURCE --write.
# Usage: stages/020-gpu-infrastructure-private-ai/deploy.sh [--revision REF | --gpus N]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/lib.sh"
MODE=deploy ref="${GIT_REPO_BRANCH:-HEAD}" GPUS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) ref="${2:?}"; shift 2 ;;
    --gpus) MODE=gpus GPUS="${2:?}"; shift 2 ;;
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

# ── Deploy ────────────────────────────────────────────────────────────────────
require_env GIT_REPO_URL "reviewed Stage 020 source repository"
assert_required_env
STAGE_APPS="$ROOT_DIR/scripts/stage-apps.sh"
revision=$("$STAGE_APPS" select 020 --ref "$ref" --repo-url "$GIT_REPO_URL" \
)
stage_gitops="$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai"
app_manifest="$ROOT_DIR/gitops/applications/020-gpu-machinesets.yaml"
[[ -f "$stage_gitops/020-gpu-machinesets/machineset-gpu.yaml" ]] || { echo 'ERROR: generate, review and publish the environment MachineSets first (machinesets/generate.sh SOURCE --write).' >&2; exit 1; }
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
    { echo "ERROR: $name: provider differs from the active source (region, reservation or AMI); re-run machinesets/generate.sh SOURCE --write" >&2; exit 1; }
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
  { echo "ERROR: 020-gpu-machinesets lacks a replica exception per GPU MachineSet (re-run machinesets/generate.sh SOURCE --write)" >&2; exit 1; }
echo "PASS $(jq length <<<"$machinesets") GPU MachineSets match their active CPU sources and carry replica exceptions"
require_node_sizing
# First change: the component Applications at the reviewed commit; deploy applies, syncs and waits for each.
"$STAGE_APPS" deploy 020 --revision "$revision" --repo-url "$GIT_REPO_URL"
echo 'Stage 020 components reconciled; native Automatic operator reconciliation is bounded below.'
check_operator_policy "$ROOT_DIR/gitops/stages/020-gpu-infrastructure-private-ai" --wait 900
log_info "GPU pools are declared at zero replicas: start one with deploy.sh --gpus 1, park all with --gpus 0."
