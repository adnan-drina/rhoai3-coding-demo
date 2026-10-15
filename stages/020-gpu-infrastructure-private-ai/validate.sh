#!/usr/bin/env bash
# Read-only Stage 020 checks: operators, NFD, the NVIDIA ClusterPolicy and its workloads, GPU MachineSets and
# nodes, Kueue, flavors, queues and hardware profiles. --functional adds per-GPU CUDA vectorAdd and DCGM metrics
# evidence. Queue admission and dashboard persona visibility are separate acceptance (OPERATIONS).
# Usage: stages/020-gpu-infrastructure-private-ai/validate.sh [--readiness|--functional]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in
STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"

mode="${1:---readiness}"
[[ "$mode" == --readiness || "$mode" == --functional ]] || { echo "Use --readiness or --functional (both read-only)." >&2; exit 1; }
check_operator_policy "$REPO_ROOT/gitops/stages/020-gpu-infrastructure-private-ai" --verify

read_json() { oc --request-timeout=10s get "$@" -o json; }
yes_no() { jq -e "$@" >/dev/null && echo yes || echo no; }
# jq definitions shared by the checks below: condition True, condition True at the current generation, current.
JQ_DEFS='def cond($t): any(.status.conditions[]?; .type == $t and .status == "True");
  def freshcond($t): .metadata.generation as $g | any(.status.conditions[]?; .type == $t and .status == "True" and .observedGeneration == $g);
  def current: (.metadata.generation | type) == "number" and .status.observedGeneration == .metadata.generation;
  def owned_by($uid): any(.metadata.ownerReferences[]?; .uid == $uid);
  def controlled_by($uid): any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true);'
# jq with the definitions above; options first, filter last (as with jq).
jqd() { local n=$# filter="${!#}"; jq "${@:1:n-1}" "$JQ_DEFS $filter"; }

# Reviewed GPU pools: MachineSet label cluster-api/accelerator -> instance type, GFD product, Kueue flavor.
POOLS='{"nvidia-gpu": ["g6e.2xlarge", "NVIDIA-L40S", "gpu-l40s"],
  "nvidia-rtxpro6000": ["g7e.2xlarge", "NVIDIA-RTX-PRO-6000-Blackwell-Server-Edition", "gpu-rtxpro6000"]}'

applications() {
    local out
    out=$("$STAGE_APPS" status 020 2>&1) && echo yes || grep -v "^OK" <<<"$out" | tr "\n" ";"
}
metrics_access() {
    local binding role
    binding=$(read_json rolebinding rhoai-gpu-metrics-admins -n openshift-monitoring)
    role=$(read_json role cluster-monitoring-metrics-api -n openshift-monitoring)
    jq -n -e --argjson b "$binding" --argjson r "$role" \
        '$b.roleRef == {apiGroup: "rbac.authorization.k8s.io", kind: "Role", name: "cluster-monitoring-metrics-api"}
        and $b.subjects == [{apiGroup: "rbac.authorization.k8s.io", kind: "Group", name: "rhods-admins"}]
        and any($r.rules[]?; (.apiGroups | index("monitoring.coreos.com")) and (.resources | index("prometheuses/api"))
            and (.resourceNames | index("k8s")) and (["get", "create", "update"] - .verbs | length == 0))' \
        >/dev/null && echo yes || echo no
}
console_dashboard() {
    local cm owner
    cm=$(read_json configmap nvidia-dcgm-exporter-dashboard -n openshift-config-managed)
    owner=$("$STAGE_APPS" owner 020 ConfigMap nvidia-dcgm-exporter-dashboard openshift-config-managed)
    # Hash the exact bytes (jq -j; a $(...) capture would drop the trailing newline).
    local digest
    digest=$(jq -j '.data["dcgm-exporter-dashboard.json"]' <<<"$cm" | shasum -a 256 | cut -d' ' -f1)
    [[ "$digest" == 7c2172e582524efb70d9f585502366f7fec22b2464c3b89f75418ca648353e71 ]] ||
        { echo "dashboard content differs from the pinned digest"; return; }
    jq -e --arg t "$owner:/ConfigMap:openshift-config-managed/nvidia-dcgm-exporter-dashboard" \
        '.metadata.labels["console.openshift.io/dashboard"] == "true"
        and .metadata.annotations["argocd.argoproj.io/tracking-id"] == $t
        and (.data["dcgm-exporter-dashboard.json"] | fromjson | .title) == "NVIDIA DCGM Exporter Dashboard"' \
        <<<"$cm" >/dev/null && echo yes || echo no
}
# Automatic approval rolls within the reviewed channel; check-operator-policy.py above guards the release family.
operator_current() {
    local sub csv
    sub=$(read_json subscription "$2" -n "$1")
    csv=$(read_json csv "$(jq -r '.status.installedCSV' <<<"$sub")" -n "$1")
    jq -n -e --argjson s "$sub" --argjson c "$csv" '$s.spec.installPlanApproval == "Automatic"
        and $s.status.installedCSV == $s.status.currentCSV and $c.status.phase == "Succeeded"' >/dev/null && echo yes || echo no
}
nfd=$(read_json nodefeaturediscovery nfd-instance -n openshift-nfd)
NFD_UID=$(jq -r '.metadata.uid' <<<"$nfd")
# The operand image is pinned in Git (the NFD CLI guide sets operand.image); it must be the installed operator's own.
nfd_operand_matches_operator() {
    local csv
    csv=$(read_json csv "$(read_json subscription nfd -n openshift-nfd | jq -r '.status.installedCSV')" -n openshift-nfd)
    jq -n -e --argjson c "$csv" --argjson n "$nfd" \
        '[$c.spec.install.spec.deployments[].spec.template.spec.containers[].env[]?
          | select(.name == "NODE_FEATURE_DISCOVERY_IMAGE").value] as $want
        | ($want | length) > 0 and $n.spec.operand.image == $want[0]' >/dev/null && echo yes || echo no
}
# A DaemonSet or Deployment owned by uid, at its current generation, with every replica ready and updated.
native_workload() {
    read_json "$1" "$2" -n "$3" | jqd --arg uid "$4" -e 'owned_by($uid) and current
        and (if .kind == "DaemonSet"
             then .status.desiredNumberScheduled > 0 and .status.numberReady == .status.desiredNumberScheduled
                  and .status.updatedNumberScheduled == .status.desiredNumberScheduled
             else (.spec.replicas // 1) as $n | $n > 0 and .status.readyReplicas == $n
                  and .status.updatedReplicas == $n and .status.availableReplicas == $n end)' >/dev/null
}
nfd_ready() {
    jqd -e 'cond("Available")' <<<"$nfd" >/dev/null && native_workload daemonset nfd-worker openshift-nfd "$NFD_UID" &&
        native_workload deployment nfd-master openshift-nfd "$NFD_UID" && echo yes || echo no
}

cp=$(read_json clusterpolicy gpu-cluster-policy)
CP_UID=$(jq -r '.metadata.uid' <<<"$cp")
gpu_nodes=$(read_json nodes | jq -c '[.items[] | select(.metadata.labels["nvidia.com/gpu.present"] == "true"
    and (.spec.unschedulable | not))]')
GPU_COUNT=$(jq 'length' <<<"$gpu_nodes")
clusterpolicy_ready() { yes_no '.status.state == "ready"' <<<"$cp"; }
# A ClusterPolicy-controlled DaemonSet, current, scheduled and ready on every schedulable GPU node.
owned_daemonset() {
    read_json daemonset "$1" -n nvidia-gpu-operator | jqd --arg uid "$CP_UID" --argjson n "$GPU_COUNT" -e \
        'controlled_by($uid) and current and $n > 0 and .status.desiredNumberScheduled == $n
        and .status.numberReady == $n and .status.updatedNumberScheduled == $n' >/dev/null && echo yes || echo no
}
machinesets=$(read_json machinesets -n openshift-machine-api | jq -c --argjson pools "$POOLS" \
    '[.items[] | select(.metadata.labels["cluster-api/accelerator"] as $l | $pools | has($l // ""))]')
pools_reviewed() {
    jqd --argjson pools "$POOLS" -e 'length > 0 and all(.[];
        .spec.template.spec.providerSpec.value.instanceType == $pools[.metadata.labels["cluster-api/accelerator"]][0]
        and current and (.status.readyReplicas // 0) == .spec.replicas)' <<<"$machinesets" >/dev/null && echo yes || echo no
}
gpu_nodes_ready() {
    jqd --argjson pools "$POOLS" -e 'length > 0 and all(.[]; $pools[.metadata.labels["cluster-api/accelerator"] // ""] as $p
        | $p != null and cond("Ready") and .status.allocatable["nvidia.com/gpu"] == "1"
        and .metadata.labels["nvidia.com/gpu.product"] == $p[1]
        and any(.spec.taints[]?; .key == "nvidia-gpu-only" and .effect == "NoSchedule"))' \
        <<<"$gpu_nodes" >/dev/null && echo yes || echo no
}
# The node's driver DaemonSet (selected by its RHCOS build) is current, and a Ready driver pod runs on the node.
driver_ready() {
    local node=$1 version daemonsets ds_uid
    version=$(jq -r --arg n "$node" '.[] | select(.metadata.name == $n)
        | .metadata.labels["feature.node.kubernetes.io/system-os_release.OSTREE_VERSION"] // ""' <<<"$gpu_nodes")
    [[ -n "$version" ]] || { echo "node has no OSTREE_VERSION label"; return; }
    daemonsets=$(read_json daemonsets -n nvidia-gpu-operator | jqd -c --arg v "$version" --arg uid "$CP_UID" \
        '[.items[] | select(.metadata.labels["openshift.driver-toolkit.rhcos"] == $v and controlled_by($uid)
          and any(.spec.template.spec.containers[]; .name == "nvidia-driver-ctr"))]')
    jqd -e 'length == 1 and (.[0] | current and .status.numberReady == .status.desiredNumberScheduled
        and .status.updatedNumberScheduled == .status.desiredNumberScheduled)' <<<"$daemonsets" >/dev/null ||
        { echo "driver DaemonSet missing or not current"; return; }
    ds_uid=$(jq -r '.[0].metadata.uid' <<<"$daemonsets")
    read_json pods -n nvidia-gpu-operator | jqd -e --arg n "$node" --arg uid "$ds_uid" \
        'any(.items[]; .spec.nodeName == $n and cond("Ready") and controlled_by($uid))' >/dev/null && echo yes || echo no
}
dsc=$(read_json datasciencecluster default-dsc)
kueue_delegated() {
    jqd -e '.spec.components.kueue.managementState == "Unmanaged" and .spec.components.kueue.autoCreateQueues == false
        and cond("Ready") and current' <<<"$dsc" >/dev/null && echo yes || echo no
}
kueue_ready() {
    local kueues uid
    kueues=$(read_json kueues.kueue.openshift.io)
    jqd -e '(.items | length) == 1 and (.items[0] | cond("Available") and cond("CertManagerAvailable")
        and (cond("Degraded") | not) and (cond("Progressing") | not))' <<<"$kueues" >/dev/null || { echo no; return; }
    uid=$(jq -r '.items[0].metadata.uid' <<<"$kueues")
    native_workload deployment kueue-controller-manager openshift-kueue-operator "$uid" && echo yes || echo no
}
flavors() {
    local label flavor
    for label in $(jq -r 'keys[]' <<<"$POOLS"); do
        flavor=$(jq -r --arg l "$label" '.[$l][2]' <<<"$POOLS")
        read_json resourceflavor "$flavor" | jq -e --arg l "$label" '.spec.nodeLabels == {"cluster-api/accelerator": $l}
            and any(.spec.tolerations[]?; .key == "nvidia-gpu-only")' >/dev/null || { echo "$flavor"; return; }
    done
    echo yes
}
queue_active() { read_json "$@" | jqd -e 'freshcond("Active")' >/dev/null && echo yes || echo no; }
profile_queue() {
    read_json hardwareprofile "$1" -n redhat-ods-applications |
        jq -r --arg q "lq-$1" 'if .spec.scheduling.kueue.localQueueName == $q then "yes" else "no" end'
}

check "Component Applications at one exact revision, Synced/Healthy" applications yes
check "AI administrators use the scoped native monitoring metrics Role" metrics_access yes
check "Pinned native NVIDIA console dashboard configuration" console_dashboard yes
check "nfd current CSV Succeeded" "operator_current openshift-nfd nfd" yes
check "gpu-operator-certified current CSV Succeeded" "operator_current nvidia-gpu-operator gpu-operator-certified" yes
check "kueue-operator current CSV Succeeded" "operator_current openshift-kueue-operator kueue-operator" yes
check "NFD operand image is the installed operator's own (update the Git pin after an operator update)" \
    nfd_operand_matches_operator yes
check "NFD Available with fresh native worker/master" nfd_ready yes
check "ClusterPolicy native ready" clusterpolicy_ready yes
check "nvidia-operator-validator native owner/current readiness" "owned_daemonset nvidia-operator-validator" yes
check "nvidia-dcgm-exporter native owner/current readiness" "owned_daemonset nvidia-dcgm-exporter" yes
check "Reviewed GPU MachineSets (L40S g6e.2xlarge, RTX PRO 6000 g7e.2xlarge) at their desired replicas" pools_reviewed yes
jq -r 'group_by(.metadata.labels["cluster-api/accelerator"])[]
    | "  pool \(.[0].metadata.labels["cluster-api/accelerator"]): \(map("\(.metadata.name)=\(.spec.replicas)") | join(", "))"' \
    <<<"$machinesets"
check "Ready GPU workers each advertise one full GPU matching their pool, with the intended taint" gpu_nodes_ready yes
index=0
for node in $(jq -r '.[].metadata.name' <<<"$gpu_nodes"); do
    index=$((index + 1))
    check "GPU $index native Driver Toolkit/current driver" "driver_ready $node" yes
done
check "Kueue delegated Unmanaged with autoCreateQueues=false" kueue_delegated yes
check "Native Kueue Available with fresh owned controller" kueue_ready yes
check "Each GPU ResourceFlavor selects exactly its own pool" flavors yes
for suffix in cpu-default gpu-reserved-demo gpu-rtxpro6000; do
    check "ClusterQueue $suffix Active" "queue_active clusterqueue cq-$suffix" yes
    check "Sandbox LocalQueue $suffix Active" "queue_active localqueue lq-$suffix -n demo-sandbox" yes
    check "HardwareProfile $suffix queue identity" "profile_queue $suffix" yes
done
# Consumer LocalQueues belong to their stages: internal-models to Stage 040, evaluated-models to Stage 050.
echo "One hardware profile per GPU type: gpu-reserved-demo (L40S) and gpu-rtxpro6000, each with its own ClusterQueue."
echo "Global profiles require matching LocalQueues in every consuming project."

if [[ "$mode" == --functional ]]; then
    pods=$(read_json pods -n nvidia-gpu-operator)
    validator=$(read_json daemonset nvidia-operator-validator -n nvidia-gpu-operator)
    VALIDATOR_UID=$(jq -r '.metadata.uid' <<<"$validator")
    # The newest cuda-validator pod on the node ran inside the current validator pod's cuda-validation init
    # container window and succeeded, and workload validation is not disabled.
    cuda_vectoradd() {
        local node=$1 revision
        revision=$(read_json controllerrevisions -n nvidia-gpu-operator | jqd -r --arg uid "$VALIDATOR_UID" \
            '[.items[] | select(owned_by($uid))] | max_by(.revision) | .metadata.name | split("-") | last')
        jqd -n -e --argjson pods "$pods" --argjson ds "$validator" --arg n "$node" --arg rev "$revision" \
            --arg cp "$CP_UID" --arg uid "$VALIDATOR_UID" '
            def t: fromdateiso8601;
            ([$pods.items[] | select(.metadata.labels.app == "nvidia-cuda-validator" and .spec.nodeName == $n
                and owned_by($cp))] | max_by(.metadata.creationTimestamp)) as $p
            | [$pods.items[] | select(.spec.nodeName == $n and .metadata.labels["controller-revision-hash"] == $rev
                and controlled_by($uid))] as $current
            | $p != null and ($current | length) == 1 and ($current[0] | (.metadata.deletionTimestamp == null) and cond("Ready"))
            and ([$current[0].status.initContainerStatuses[]? | select(.name == "cuda-validation") | .state.terminated]
                 | length == 1 and .[0].exitCode == 0
                 and (.[0].startedAt | t) <= ($p.metadata.creationTimestamp | t)
                 and ($p.metadata.creationTimestamp | t) <= (.[0].finishedAt | t))
            and $p.status.phase == "Succeeded"
            and (any($p.status.initContainerStatuses[]?; .name == "cuda-validation" and .state.terminated.exitCode == 0))
            and ($ds.spec.template.spec.initContainers[] | select(.name == "cuda-validation")
                 | any(.env[]?; .name == "WITH_WORKLOAD" and ((.value // "") | ascii_downcase) == "false") | not)' \
            >/dev/null && echo yes || echo no
    }
    # The node's DCGM exporter pod serves GPU utilization for an NVIDIA GPU (local port-forward, up to 30 s).
    dcgm_metrics() {
        local node=$1 exporter pod log pid port body=""
        exporter=$(read_json daemonset nvidia-dcgm-exporter -n nvidia-gpu-operator | jq -r '.metadata.uid')
        pod=$(jqd -r --arg n "$node" --arg uid "$exporter" '[.items[] | select(controlled_by($uid)
            and .metadata.deletionTimestamp == null and .metadata.labels.app == "nvidia-dcgm-exporter"
            and .spec.nodeName == $n and cond("Ready"))] | if length == 1 then .[0].metadata.name else "" end' <<<"$pods")
        [[ -n "$pod" ]] || { echo "no single Ready exporter pod"; return; }
        log=$(mktemp)
        oc --request-timeout=10s port-forward -n nvidia-gpu-operator "pod/$pod" :9400 --address=127.0.0.1 >"$log" 2>&1 &
        pid=$!
        for _ in $(seq 1 30); do
            port=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$log" | head -1)
            [[ -n "$port" ]] && body=$(curl -s --max-time 3 "http://127.0.0.1:$port/metrics" || true)
            [[ "$body" == *'DCGM_FI_DEV_GPU_UTIL{'* && "$body" == *'modelName="NVIDIA '* ]] && break
            sleep 1
        done
        kill "$pid" 2>/dev/null || true
        rm -f "$log"
        [[ "$body" == *'DCGM_FI_DEV_GPU_UTIL{'* && "$body" == *'modelName="NVIDIA '* ]] && echo yes || echo no
    }
    index=0
    for node in $(jq -r '.[].metadata.name' <<<"$gpu_nodes"); do
        index=$((index + 1))
        check "GPU $index native CUDA vectorAdd success" "cuda_vectoradd $node" yes
        check "GPU $index native DCGM metrics" "dcgm_metrics $node" yes
    done
    echo "Read-only CUDA/DCGM checks do not prove queue admission or dashboard persona visibility." \
        "Follow the bounded admission procedure in OPERATIONS."
else
    echo "READINESS ONLY: CUDA/DCGM, queue admission and dashboard persona visibility remain separate acceptance."
fi
validation_summary
