#!/usr/bin/env bash
# Resume or inspect the GPU-backed Stage 020/030 demo path after GPU nodes
# have been intentionally scaled to zero.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-openshift-gitops}"
MODEL_NAMESPACE="${MODEL_NAMESPACE:-internal-models}"
GPU_MACHINESET_REPLICAS="${GPU_MACHINESET_REPLICAS:-2}"
GPU_RESUME_TIMEOUT_SECONDS="${GPU_RESUME_TIMEOUT_SECONDS:-1800}"
GPU_RESUME_POLL_SECONDS="${GPU_RESUME_POLL_SECONDS:-15}"

usage() {
    cat <<'EOF'
Usage:
  scripts/platform/resume-gpu-demo.sh status
  scripts/platform/resume-gpu-demo.sh up [replicas]
  scripts/platform/resume-gpu-demo.sh down
  scripts/platform/resume-gpu-demo.sh resume [replicas]

Commands:
  status   Show GPU MachineSet, GPU node, Kueue queue, and private model state.
  up       Scale GPU MachineSet up and wait for allocatable GPUs.
  down     Scale GPU MachineSet to zero. Model pods become unavailable.
  resume   First-class recovery path after shutdown:
           sync Stage 020, scale GPU capacity up, validate Stage 020,
           leave existing model resources unchanged; validate model stages separately.

Environment overrides:
  GPU_MACHINESET_NAME            Explicit GPU MachineSet name.
  GPU_MACHINESET_REPLICAS        Desired GPU MachineSet replicas. Default: 2.
  GPU_RESUME_TIMEOUT_SECONDS     Wait timeout for GPU/model recovery. Default: 1800.
  GPU_RESUME_POLL_SECONDS        Poll interval. Default: 15.
  ARGOCD_NAMESPACE               Argo CD namespace. Default: openshift-gitops.
  MODEL_NAMESPACE                Private model namespace. Default: internal-models.
EOF
}

require_tools() {
    command -v oc >/dev/null || { log_error "oc is required"; exit 1; }
    command -v jq >/dev/null || { log_error "jq is required"; exit 1; }
}

discover_gpu_machineset() {
    local matches
    matches="$(oc --request-timeout=10s get machineset -n openshift-machine-api -o json | jq -r '.items[] | select(.metadata.labels["cluster-api/accelerator"] == "nvidia-gpu" and .spec.template.spec.providerSpec.value.instanceType == "g6e.2xlarge") | .metadata.name')"
    [[ $(printf '%s\n' "$matches" | sed '/^$/d' | wc -l | tr -d ' ') == 1 ]] || { log_error "Select one unambiguous reviewed GPU MachineSet"; return 1; }
    [[ -z "${GPU_MACHINESET_NAME:-}" || "$GPU_MACHINESET_NAME" == "$matches" ]] || { log_error "Explicit MachineSet differs from reviewed GPU pool"; return 1; }
    oc --request-timeout=10s get machineset "$matches" -n openshift-machine-api -o json | jq -e '.metadata.ownerReferences == null and (.metadata.annotations["argocd.argoproj.io/tracking-id"] | startswith("020-gpu-infrastructure-private-ai:"))' >/dev/null || { log_error "GPU pool ownership is not Stage 020"; return 1; }
    printf '%s\n' "$matches"
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
    if ! oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get application "$app" -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        log_warn "Argo CD Application '$app' was not found in $ARGOCD_NAMESPACE"
        return 0
    fi

    log_info "Requesting Argo CD sync for $app"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" patch application "$app" -n "$ARGOCD_NAMESPACE" \
        --type=merge -p '{"operation":{"sync":{}}}' >/dev/null 2>&1 || \
        log_warn "Could not request sync for $app; an operation may already be running"
}

wait_for_app() {
    local app="$1"
    local timeout="${2:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 sync health

    if ! oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get application "$app" -n "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        return 0
    fi

    log_info "Waiting for $app to become Synced/Healthy"
    while (( elapsed < timeout )); do
        sync="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get application "$app" -n "$ARGOCD_NAMESPACE" -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
        health="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get application "$app" -n "$ARGOCD_NAMESPACE" -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
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

wait_for_gpu_capacity() {
    local expected="$1"
    local timeout="${2:-$GPU_RESUME_TIMEOUT_SECONDS}"
    local elapsed=0 ready_nodes alloc_nodes

    log_info "Waiting for $expected GPU node(s) with allocatable nvidia.com/gpu"
    while (( elapsed < timeout )); do
        ready_nodes="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get nodes -l nvidia.com/gpu.present=true --no-headers 2>/dev/null | grep -c ' Ready ' || true)"
        alloc_nodes="$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get nodes -l nvidia.com/gpu.present=true -o json 2>/dev/null \
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
    ms="$(gpu_machineset_or_fail)"

    [[ "$replicas" == 2 ]] || { log_error "Reviewed topology requires two GPU workers"; return 1; }
    log_info "Scaling GPU MachineSet $ms to $replicas"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" scale machineset "$ms" -n openshift-machine-api --replicas="$replicas"
    wait_for_gpu_capacity "$replicas"
    wait_for_gpu_operator_ready
}

scale_gpu_down() {
    local ms
    ms="$(gpu_machineset_or_fail)"

    log_warn "Scaling GPU MachineSet $ms to 0. Private model pods will become unavailable."
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" scale machineset "$ms" -n openshift-machine-api --replicas=0
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

print_status() {
    log_step "GPU MachineSets"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get machineset -n openshift-machine-api \
        -o custom-columns='NAME:.metadata.name,INSTANCE:.spec.template.spec.providerSpec.value.instanceType,DESIRED:.spec.replicas,READY:.status.readyReplicas' \
        | awk 'NR == 1 || $2 ~ /^g[0-9]/'

    log_step "GPU Nodes"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get nodes -l nvidia.com/gpu.present=true -o json 2>/dev/null \
        | jq -r '
            (["NAME", "READY", "GPU", "GPU_ROLE_LABEL", "GPU_TAINT"] | @tsv),
            (.items[] | [
                .metadata.name,
                (.status.conditions[] | select(.type == "Ready") | .status),
                (.status.allocatable["nvidia.com/gpu"] // "0"),
                ((.metadata.labels // {}) | has("node-role.kubernetes.io/gpu")),
                (any(.spec.taints[]?; .key == "nvidia-gpu-only" and .effect == "NoSchedule"))
            ] | @tsv)' \
        | column -t || true

    log_step "Kueue Queues"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get resourceflavor gpu-l40s 2>/dev/null || true
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get clusterqueue cq-gpu-reserved-demo 2>/dev/null || true
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get localqueue lq-gpu-reserved-demo -n demo-sandbox 2>/dev/null || true
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get workloads.kueue.x-k8s.io -n "$MODEL_NAMESPACE" 2>/dev/null || true

    log_step "Private Models"
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get llminferenceservice -n "$MODEL_NAMESPACE" 2>/dev/null || true
    oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get pods -n "$MODEL_NAMESPACE" 2>/dev/null | grep -E 'NAME|qwen|qwen3-6-27b|router-scheduler' || true
}

resume_from_zero() {
    local replicas="${1:-$GPU_MACHINESET_REPLICAS}"

    sync_app "020-gpu-infrastructure-private-ai"
    wait_for_app "020-gpu-infrastructure-private-ai" 600
    scale_gpu_up "$replicas"
    run_validation "Stage 020 readiness only" "$REPO_ROOT/stages/020-gpu-infrastructure-private-ai/validate.sh"

    log_info "GPU infrastructure readiness resumed; CUDA/DCGM, admission, dashboard and model-stage acceptance remain separate. No model workloads were changed."

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
