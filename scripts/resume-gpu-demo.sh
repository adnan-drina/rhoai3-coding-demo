#!/usr/bin/env bash
# Resume or inspect the GPU-backed Stage 020/030 demo path after GPU nodes
# have been intentionally scaled to zero.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-openshift-gitops}"
MODEL_NAMESPACE="${MODEL_NAMESPACE:-maas}"
GPU_MACHINESET_REPLICAS="${GPU_MACHINESET_REPLICAS:-2}"
GPU_RESUME_TIMEOUT_SECONDS="${GPU_RESUME_TIMEOUT_SECONDS:-1800}"
GPU_RESUME_POLL_SECONDS="${GPU_RESUME_POLL_SECONDS:-15}"

usage() {
    cat <<'EOF'
Usage:
  scripts/resume-gpu-demo.sh status
  scripts/resume-gpu-demo.sh up [replicas]
  scripts/resume-gpu-demo.sh down
  scripts/resume-gpu-demo.sh resume [replicas]

Commands:
  status   Show GPU MachineSet, GPU node, Kueue queue, and private model state.
  up       Scale GPU MachineSet up and wait for allocatable GPUs.
  down     Scale GPU MachineSet to zero. Model pods become unavailable.
  resume   First-class recovery path after shutdown:
           sync Stage 020, scale GPU capacity up, validate Stage 020,
           sync Stage 030, clear stale model ReplicaSets, and validate Stage 030.

Environment overrides:
  GPU_MACHINESET_NAME            Explicit GPU MachineSet name.
  GPU_MACHINESET_REPLICAS        Desired GPU MachineSet replicas. Default: 2.
  GPU_RESUME_TIMEOUT_SECONDS     Wait timeout for GPU/model recovery. Default: 1800.
  GPU_RESUME_POLL_SECONDS        Poll interval. Default: 15.
  ARGOCD_NAMESPACE               Argo CD namespace. Default: openshift-gitops.
  MODEL_NAMESPACE                Private model namespace. Default: maas.
EOF
}

require_tools() {
    command -v oc >/dev/null || { log_error "oc is required"; exit 1; }
    command -v jq >/dev/null || { log_error "jq is required"; exit 1; }
}

discover_gpu_machineset() {
    if [[ -n "${GPU_MACHINESET_NAME:-}" ]]; then
        echo "$GPU_MACHINESET_NAME"
        return 0
    fi

    oc get machineset -n openshift-machine-api -o json 2>/dev/null \
        | jq -r '.items[]
            | select((.spec.template.spec.providerSpec.value.instanceType // "") | test("^g[0-9]"))
            | .metadata.name' \
        | head -n 1
}

gpu_machineset_or_fail() {
    local ms
    ms="$(discover_gpu_machineset)"
    if [[ -z "$ms" ]]; then
        log_error "No GPU MachineSet found. Deploy or sync Stage 020 first."
        exit 1
    fi
    echo "$ms"
}

sync_app() {
    local app="$1"
    if ! oc get application "$app" -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        log_warn "Argo CD Application '$app' was not found in $ARGOCD_NAMESPACE"
        return 0
    fi

    log_info "Requesting Argo CD sync for $app"
    oc patch application "$app" -n "$ARGOCD_NAMESPACE" \
        --type=merge -p '{"operation":{"sync":{}}}' >/dev/null 2>&1 || \
        log_warn "Could not request sync for $app; an operation may already be running"
}

wait_for_app() {
    local app="$1"
    local timeout="${2:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 sync health

    if ! oc get application "$app" -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        return 0
    fi

    log_info "Waiting for $app to become Synced/Healthy"
    while (( elapsed < timeout )); do
        sync="$(oc get application "$app" -n "$ARGOCD_NAMESPACE" -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
        health="$(oc get application "$app" -n "$ARGOCD_NAMESPACE" -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
        if [[ "$sync" == "Synced" && "$health" == "Healthy" ]]; then
            log_success "$app is Synced/Healthy"
            return 0
        fi
        log_info "$app sync=$sync health=$health"
        sleep "$GPU_RESUME_POLL_SECONDS"
        elapsed=$((elapsed + GPU_RESUME_POLL_SECONDS))
    done

    log_error "Timed out waiting for $app to become Synced/Healthy"
    return 1
}

repair_gpu_node_labels() {
    local nodes
    nodes="$(oc get nodes -l nvidia.com/gpu.present=true -o name 2>/dev/null || true)"
    if [[ -z "$nodes" ]]; then
        return 0
    fi

    while IFS= read -r node; do
        [[ -z "$node" ]] && continue
        oc label "$node" node-role.kubernetes.io/gpu= --overwrite >/dev/null
        oc adm taint "$node" nvidia.com/gpu=true:NoSchedule --overwrite >/dev/null 2>&1 || true
    done <<< "$nodes"
}

wait_for_gpu_capacity() {
    local expected="$1"
    local timeout="${2:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 ready_nodes alloc_nodes

    log_info "Waiting for $expected GPU node(s) with allocatable nvidia.com/gpu"
    while (( elapsed < timeout )); do
        repair_gpu_node_labels
        ready_nodes="$(oc get nodes -l nvidia.com/gpu.present=true --no-headers 2>/dev/null | grep -c ' Ready ' || true)"
        alloc_nodes="$(oc get nodes -l nvidia.com/gpu.present=true -o json 2>/dev/null \
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

    if ! oc get clusterpolicy gpu-cluster-policy >/dev/null 2>&1; then
        log_warn "NVIDIA ClusterPolicy was not found; Stage 020 validation will report details"
        return 0
    fi

    log_info "Waiting for NVIDIA ClusterPolicy to return to ready"
    while (( elapsed < timeout )); do
        state="$(oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.state}' 2>/dev/null || true)"
        ready="$(oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
        if [[ "$state" == "ready" && "$ready" == "True" ]]; then
            log_success "NVIDIA ClusterPolicy is ready"
            return 0
        fi

        log_info "NVIDIA ClusterPolicy not ready yet: state=${state:-Unknown} ready=${ready:-Unknown}"
        sleep "$GPU_RESUME_POLL_SECONDS"
        elapsed=$((elapsed + GPU_RESUME_POLL_SECONDS))
    done

    log_warn "Timed out waiting for NVIDIA ClusterPolicy; Stage 020 validation will report details"
}

gpu_machines_for_machineset() {
    local ms="$1"
    oc get machines -n openshift-machine-api -o json 2>/dev/null \
        | jq -r --arg ms "$ms" '
            .items[]
            | select(any(.metadata.ownerReferences[]?; .kind == "MachineSet" and .name == $ms))
            | .metadata.name'
}

stopped_gpu_machines_for_machineset() {
    local ms="$1"
    oc get machines -n openshift-machine-api -o json 2>/dev/null \
        | jq -r --arg ms "$ms" '
            .items[]
            | select(any(.metadata.ownerReferences[]?; .kind == "MachineSet" and .name == $ms))
            | select((.status.providerStatus.instanceState // "") == "stopped")
            | .metadata.name'
}

wait_for_machineset_machine_count() {
    local ms="$1"
    local expected="$2"
    local timeout="${3:-600}"
    local elapsed=0 count

    while (( elapsed < timeout )); do
        count="$(gpu_machines_for_machineset "$ms" | grep -c . || true)"
        if [[ "$count" -eq "$expected" ]]; then
            return 0
        fi

        log_info "Waiting for MachineSet $ms machine count: current=$count expected=$expected"
        sleep "$GPU_RESUME_POLL_SECONDS"
        elapsed=$((elapsed + GPU_RESUME_POLL_SECONDS))
    done

    log_error "Timed out waiting for MachineSet $ms machine count to become $expected"
    return 1
}

recreate_stopped_gpu_machines() {
    local ms="$1"
    local replicas="$2"
    local stopped total_count stopped_count
    stopped="$(stopped_gpu_machines_for_machineset "$ms")"

    if [[ -z "$stopped" ]]; then
        return 0
    fi

    total_count="$(gpu_machines_for_machineset "$ms" | grep -c . || true)"
    stopped_count="$(printf '%s\n' "$stopped" | grep -c . || true)"

    log_warn "GPU MachineSet $ms has stopped provider instances; recreating Machine objects"
    if [[ "$stopped_count" -eq "$total_count" ]]; then
        oc scale machineset "$ms" -n openshift-machine-api --replicas=0
    fi

    while IFS= read -r machine; do
        [[ -z "$machine" ]] && continue
        log_warn "Deleting stopped Machine openshift-machine-api/$machine so the MachineSet can replace it"
        oc delete machine "$machine" -n openshift-machine-api --wait=false
    done <<< "$stopped"

    if [[ "$stopped_count" -eq "$total_count" ]]; then
        wait_for_machineset_machine_count "$ms" 0 900
    fi

    log_info "Scaling GPU MachineSet $ms back to $replicas after stopped instance cleanup"
    oc scale machineset "$ms" -n openshift-machine-api --replicas="$replicas"
}

scale_gpu_up() {
    local replicas="${1:-$GPU_MACHINESET_REPLICAS}"
    local ms
    ms="$(gpu_machineset_or_fail)"

    log_info "Scaling GPU MachineSet $ms to $replicas"
    oc scale machineset "$ms" -n openshift-machine-api --replicas="$replicas"
    recreate_stopped_gpu_machines "$ms" "$replicas"
    wait_for_gpu_capacity "$replicas"
    wait_for_gpu_operator_ready
}

scale_gpu_down() {
    local ms
    ms="$(gpu_machineset_or_fail)"

    log_warn "Scaling GPU MachineSet $ms to 0. Private model pods will become unavailable."
    oc scale machineset "$ms" -n openshift-machine-api --replicas=0
}

run_validation() {
    local label="$1"
    shift

    log_step "$label"
    set +e
    "$@"
    local rc=$?
    set -e

    case "$rc" in
        0)
            log_success "$label passed"
            ;;
        2)
            log_warn "$label completed with warnings"
            ;;
        *)
            log_error "$label failed with exit code $rc"
            return "$rc"
            ;;
    esac
}

cleanup_stale_model_replicasets() {
    if ! oc get namespace "$MODEL_NAMESPACE" >/dev/null 2>&1; then
        log_warn "Namespace $MODEL_NAMESPACE does not exist; skipping stale ReplicaSet cleanup"
        return 0
    fi

    local deployments
    deployments="$(oc get deployment -n "$MODEL_NAMESPACE" -o json 2>/dev/null \
        | jq -r '.items[]
            | select(.metadata.name | test("^(gpt-oss-20b|nemotron-3-nano-30b-a3b)-kserve$"))
            | .metadata.name')"

    if [[ -z "$deployments" ]]; then
        log_warn "No generated private model Deployments found; skipping stale ReplicaSet cleanup"
        return 0
    fi

    while IFS= read -r deployment; do
        [[ -z "$deployment" ]] && continue
        local stale
        stale="$(oc get replicaset -n "$MODEL_NAMESPACE" -o json \
            | jq -r --arg dep "$deployment" '
                [ .items[]
                  | select(any(.metadata.ownerReferences[]?; .kind == "Deployment" and .name == $dep))
                  | {
                      name: .metadata.name,
                      replicas: (.spec.replicas // 0),
                      revision: ((.metadata.annotations["deployment.kubernetes.io/revision"] // "0") | tonumber)
                    }
                ] as $sets
                | ($sets | map(.revision) | max // 0) as $current
                | $sets[]
                | select(.revision < $current and .replicas > 0)
                | .name')"

        if [[ -z "$stale" ]]; then
            log_info "No stale ReplicaSets with replicas found for $deployment"
            continue
        fi

        while IFS= read -r rs; do
            [[ -z "$rs" ]] && continue
            log_warn "Scaling stale ReplicaSet $MODEL_NAMESPACE/$rs to 0 to release Kueue quota"
            oc scale replicaset "$rs" -n "$MODEL_NAMESPACE" --replicas=0
        done <<< "$stale"
    done <<< "$deployments"
}

wait_for_private_models() {
    local timeout="${1:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 gpt nemotron

    log_info "Waiting for private LLMInferenceService resources to become Ready"
    while (( elapsed < timeout )); do
        cleanup_stale_model_replicasets
        gpt="$(oc get llminferenceservice gpt-oss-20b -n "$MODEL_NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
        nemotron="$(oc get llminferenceservice nemotron-3-nano-30b-a3b -n "$MODEL_NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"

        if [[ "$gpt" == "True" && "$nemotron" == "True" ]]; then
            log_success "Private models are Ready"
            return 0
        fi

        log_info "Model readiness: gpt-oss-20b=${gpt:-Unknown} nemotron-3-nano-30b-a3b=${nemotron:-Unknown}"
        sleep "$GPU_RESUME_POLL_SECONDS"
        elapsed=$((elapsed + GPU_RESUME_POLL_SECONDS))
    done

    log_warn "Timed out waiting for both private models to become Ready; validation will report details"
}

print_status() {
    log_step "GPU MachineSets"
    oc get machineset -n openshift-machine-api \
        -o custom-columns='NAME:.metadata.name,INSTANCE:.spec.template.spec.providerSpec.value.instanceType,DESIRED:.spec.replicas,READY:.status.readyReplicas' \
        | awk 'NR == 1 || $2 ~ /^g[0-9]/'

    log_step "GPU Nodes"
    oc get nodes -l nvidia.com/gpu.present=true -o json 2>/dev/null \
        | jq -r '
            (["NAME", "READY", "GPU", "GPU_ROLE_LABEL", "GPU_TAINT"] | @tsv),
            (.items[] | [
                .metadata.name,
                (.status.conditions[] | select(.type == "Ready") | .status),
                (.status.allocatable["nvidia.com/gpu"] // "0"),
                ((.metadata.labels // {}) | has("node-role.kubernetes.io/gpu")),
                (any(.spec.taints[]?; .key == "nvidia.com/gpu" and .value == "true" and .effect == "NoSchedule"))
            ] | @tsv)' \
        | column -t || true

    log_step "Kueue Queues"
    oc get resourceflavor nvidia-l4-gpu 2>/dev/null || true
    oc get clusterqueue private-model-serving-gpu 2>/dev/null || true
    oc get localqueue private-model-serving -n "$MODEL_NAMESPACE" 2>/dev/null || true
    oc get workloads.kueue.x-k8s.io -n "$MODEL_NAMESPACE" 2>/dev/null || true

    log_step "Private Models"
    oc get llminferenceservice -n "$MODEL_NAMESPACE" 2>/dev/null || true
    oc get pods -n "$MODEL_NAMESPACE" 2>/dev/null | grep -E 'NAME|gpt-oss|nemotron|router-scheduler' || true
}

resume_from_zero() {
    local replicas="${1:-$GPU_MACHINESET_REPLICAS}"

    sync_app "020-gpu-infrastructure-private-ai"
    wait_for_app "020-gpu-infrastructure-private-ai" 600
    scale_gpu_up "$replicas"
    run_validation "Stage 020 validation" "$REPO_ROOT/stages/020-gpu-infrastructure-private-ai/validate.sh"

    sync_app "030-private-model-serving"
    wait_for_app "030-private-model-serving" 600
    cleanup_stale_model_replicasets
    wait_for_private_models "$GPU_RESUME_TIMEOUT_SECONDS"
    run_validation "Stage 030 validation" "$REPO_ROOT/stages/030-private-model-serving/validate.sh"
}

main() {
    local command="${1:-}"
    if [[ "$command" == "-h" || "$command" == "--help" || "$command" == "help" || -z "$command" ]]; then
        usage
        return 0
    fi

    load_env
    require_tools
    check_oc_logged_in

    case "$command" in
        status)
            print_status
            ;;
        up)
            scale_gpu_up "${2:-$GPU_MACHINESET_REPLICAS}"
            ;;
        down)
            scale_gpu_down
            ;;
        resume)
            resume_from_zero "${2:-$GPU_MACHINESET_REPLICAS}"
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
