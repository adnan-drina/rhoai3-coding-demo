#!/usr/bin/env bash
# Read-only Stage 030 checks: the Application is reconciled at its pinned revision, the native DSC and KServe
# component are ready with current owned serving workloads, platform and user-workload monitoring are persistent,
# and model discovery works (validate-model-discovery.sh). No models are deployed; persona and browser UI
# acceptance are separate.
# Usage: stages/030-private-model-serving/validate.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

read_json() { oc --request-timeout=10s get "$@" -o json; }
# Condition $t is True on the object.
COND='def cond($t): any(.status.conditions[]?; .type == $t and .status == "True");'

reconciled() {
    read_json application 030-private-model-serving -n openshift-gitops | jq -e '.spec.source as $src | .status as $s
        | ($src.targetRevision | length) == 40 and $s.sync.revision == $src.targetRevision
        and $s.sync.status == "Synced" and $s.health.status == "Healthy"
        and $s.operationState.phase == "Succeeded" and $s.operationState.syncResult.revision == $src.targetRevision
        and $s.operationState.syncResult.source.path == $src.path' >/dev/null && echo yes || echo no
}
dsc_ready() {
    read_json datasciencecluster default-dsc | jq -e "$COND"' .status.observedGeneration == .metadata.generation
        and cond("Ready") and cond("KserveReady")
        and .spec.components.kserve.managementState == "Managed"
        and .spec.components.modelregistry.managementState == "Managed"' >/dev/null && echo yes || echo no
}
# The KServe component is current and Ready, and every Deployment it controls is current and ready.
kserve_ready() {
    local component uid
    component=$(read_json kserves.components.platform.opendatahub.io default-kserve)
    jq -e "$COND"' .status.observedGeneration == .metadata.generation
        and cond("Ready") and cond("KServeReady") and cond("ModelControllerReady")' <<<"$component" >/dev/null ||
        { echo "component not current/ready"; return; }
    uid=$(jq -r '.metadata.uid' <<<"$component")
    read_json deployments -n redhat-ods-applications | jq -e --arg uid "$uid" '[.items[]
        | select(any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true))]
        | length > 0 and all(.[]; (.spec.replicas // 1) as $n | .status.observedGeneration == .metadata.generation
            and (.status.readyReplicas // 0) >= $n and (.status.updatedReplicas // 0) >= $n)' >/dev/null && echo yes || echo no
}
# Prometheus keeps its reviewed gp3-csi claim size, its StatefulSet is fully rolled out, and every claim is Bound.
monitoring_persistent() {
    local ns=$1 name=$2 size=$3 replicas i
    read_json prometheus.monitoring.coreos.com "$name" -n "$ns" | jq -e --arg size "$size" \
        '.spec.storage.volumeClaimTemplate.spec | .storageClassName == "gp3-csi" and .resources.requests.storage == $size' \
        >/dev/null || { echo "storage intent differs"; return; }
    replicas=$(read_json statefulset "prometheus-$name" -n "$ns" | jq -r '(.spec.replicas // 1) as $n | .status as $s
        | if $s.observedGeneration == .metadata.generation and ($s.readyReplicas // 0) == $n
            and ($s.updatedReplicas // 0) == $n and $s.currentRevision == $s.updateRevision then $n else -1 end')
    [[ "$replicas" -ge 0 ]] || { echo "rollout not current"; return; }
    for ((i = 0; i < replicas; i++)); do
        [[ $(oc --request-timeout=10s get pvc "prometheus-$name-db-prometheus-$name-$i" -n "$ns" -o jsonpath='{.status.phase}') == Bound ]] ||
            { echo "PVC $i not Bound"; return; }
    done
    echo yes
}

check "030-private-model-serving Synced, Healthy and last synced at its pinned revision" reconciled yes
check "DataScienceCluster current, Ready and KServe Ready; KServe and Model Registry Managed" dsc_ready yes
check "Native KServe component current and ready with current owned serving workloads" kserve_ready yes
check "Platform monitoring persistent (gp3-csi 40Gi) and rolled out" \
    "monitoring_persistent openshift-monitoring k8s 40Gi" yes
check "User-workload monitoring persistent (gp3-csi 20Gi) and rolled out" \
    "monitoring_persistent openshift-user-workload-monitoring user-workload 20Gi" yes
summary_status=0
validation_summary || summary_status=$?
discovery_status=0
"$SCRIPT_DIR/validate-model-discovery.sh" || discovery_status=$?
echo "Infrastructure/API acceptance only. No models are deployed; persona and browser UI acceptance are separate."
(( summary_status == 0 && discovery_status == 0 )) || exit 1
