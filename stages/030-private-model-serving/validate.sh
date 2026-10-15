#!/usr/bin/env bash
# Read-only Stage 030 checks: the Application is reconciled at its pinned revision, the native DSC and KServe
# component are ready with current owned serving workloads, platform and user-workload monitoring are persistent,
# and model discovery works: the demo model registry, its database and authenticated list API, the native model catalog,
# dashboard discovery flags, and authenticated model and agent catalog listings through the dashboard's registry UI
# service (local port-forward only). No models are deployed or records created; persona and browser UI acceptance
# are separate.
# Usage: stages/030-private-model-serving/validate.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in

read_json() { oc --request-timeout=20s get "$@" -o json; }
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

# ── Model discovery ───────────────────────────────────────────────────────────

REG_NS=rhoai-model-registries
UI_NS=redhat-ods-applications
UI_HOST=odh-dashboard-model-registry-ui.redhat-ods-applications.svc
TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin, never an argument or a log line
WORK=$(mktemp -d)
cleanup() {
    while read -r pid; do kill "$pid" 2>/dev/null || true; done < <(cat "$WORK/pids" 2>/dev/null)
    rm -rf "$WORK"
}
trap cleanup EXIT
# A Deployment at its current generation with every replica ready and updated.
FRESH='.status.observedGeneration == .metadata.generation and (.spec.replicas // 1) > 0
    and (.status.readyReplicas // 0) >= (.spec.replicas // 1) and (.status.updatedReplicas // 0) >= (.spec.replicas // 1)'

registry=$(read_json modelregistries.modelregistry.opendatahub.io demo-registry -n "$REG_NS")
REGISTRY_UID=$(jq -r '.metadata.uid' <<<"$registry")
registry_deployments=$(read_json deployments -n "$REG_NS" | jq -c --arg uid "$REGISTRY_UID" \
    '[.items[] | select(any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true))]')
databases=$(jq -c '[.[] | select(any(.spec.template.spec.containers[]; .image | contains("postgresql")))]' <<<"$registry_deployments")
apis=$(jq -c '[.[] | select(all(.spec.template.spec.containers[]; .image | contains("postgresql") | not))]' <<<"$registry_deployments")

registry_available() {
    jq -n -e --argjson r "$registry" 'all("Available", "KubeRBACProxyAvailable"; . as $t
        | any($r.status.conditions[]?; .type == $t and .status == "True"))' >/dev/null && echo yes || echo no
}
registry_workloads() {
    jq -e "length == 1 and (.[0] | $FRESH)" <<<"$apis" >/dev/null || { echo "API deployment not unique or not current"; return; }
    jq -e "length == 1 and (.[0] | $FRESH)" <<<"$databases" >/dev/null || { echo "database deployment not unique or not current"; return; }
    local claims claim
    claims=$(jq -r '.[0].spec.template.spec.volumes[]? | .persistentVolumeClaim.claimName // empty' <<<"$databases")
    [[ -n "$claims" ]] || { echo "database has no persistent claim"; return; }
    for claim in $claims; do
        [[ $(oc --request-timeout=20s get pvc "$claim" -n "$REG_NS" -o jsonpath='{.status.phase}') == Bound ]] ||
            { echo "PVC $claim not Bound"; return; }
    done
    echo yes
}
# Authenticated list through the registry's own Route; ingress certificates verified, redirects refused.
registry_list_api() {
    local host
    host=$(read_json routes -n "$REG_NS" | jq -r --arg uid "$REGISTRY_UID" '[.items[]
        | select(any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true))]
        | if length == 1 then .[0].spec.host else "" end')
    [[ -n "$host" ]] || { echo "registry Route not uniquely discoverable"; return; }
    printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" |
        curl --config - -sf --max-time 20 -H 'Accept: application/json' \
        "https://$host/api/model_registry/v1alpha3/registered_models" |
        jq -e '.items | type == "array"' >/dev/null && echo yes || echo no
}
catalog_component() {
    local component uid
    component=$(read_json modelregistries.components.platform.opendatahub.io default-modelregistry)
    jq -e '.status.phase == "Ready" and (.metadata.generation | type) == "number"
        and .status.observedGeneration == .metadata.generation' <<<"$component" >/dev/null || { echo "component not Ready/current"; return; }
    uid=$(jq -r '.metadata.uid' <<<"$component")
    read_json deployments -n "$REG_NS" | jq -e --arg uid "$uid" "[.items[] | select(any(.metadata.ownerReferences[]?; .uid == \$uid))]
        | (map(.metadata.name) | index(\"model-catalog\") and index(\"model-catalog-postgres\")) and all(.[]; $FRESH)" \
        >/dev/null && echo yes || echo no
}
dashboard_flags() {
    read_json odhdashboardconfig odh-dashboard-config -n "$UI_NS" | jq -e '.spec.dashboardConfig
        | .disableModelRegistry != true and .disableModelCatalog != true and .agentsCatalog == true
        and .toolCalling == true and .mcpCatalog == true and .mcpRegistry == true' >/dev/null && echo yes || echo no
}

# Dashboard registry UI service over a port-forward, TLS verified against the service CA for its service name.
read_json configmap service-ca -n openshift-config-managed | jq -r '.data["ca-bundle.crt"]' >"$WORK/service-ca.crt"
oc -n "$UI_NS" port-forward service/odh-dashboard-model-registry-ui :8043 --address=127.0.0.1 >"$WORK/forward.log" 2>&1 &
echo "$!" >>"$WORK/pids"; disown "$!" 2>/dev/null || true  # the EXIT trap kills it; no job-termination notice
UI_PORT=""
for _ in $(seq 1 50); do
    UI_PORT=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$WORK/forward.log" | head -1)
    [[ -n "$UI_PORT" ]] && break
    sleep 0.1
done
catalog_page() {
    printf 'header = "X-Forwarded-Access-Token: %s"\n' "$TOKEN" |
        curl --config - -sf --max-time 20 --cacert "$WORK/service-ca.crt" --resolve "$UI_HOST:$UI_PORT:127.0.0.1" \
        -H 'Accept: application/json' -G "https://$UI_HOST:$UI_PORT/api/v1/$1" \
        --data-urlencode "namespace=$REG_NS" --data-urlencode "pageSize=100" ${2:+--data-urlencode "nextPageToken=$2"}
}
# All pages (at most 20, no repeated token) of a dashboard catalog listing, as one JSON array of items. Pages go to
# files: an accumulated listing can exceed the command-line size limit as a jq argument.
catalog_items() {
    local catalog=$1 dir next="" seen=" " count=0
    dir=$(mktemp -d "$WORK/pages.XXXX")
    for _ in $(seq 1 20); do
        count=$((count + 1))
        catalog_page "$catalog" "$next" >"$dir/$count.json" || return 1
        jq -e '.data.items | type == "array"' "$dir/$count.json" >/dev/null || return 1
        next=$(jq -r '.data.nextPageToken // ""' "$dir/$count.json")
        if [[ -z "$next" ]]; then
            jq -s -c '[.[].data.items[]]' "$dir"/*.json
            return 0
        fi
        [[ "$seen" == *" $next "* ]] && return 1
        seen+="$next "
    done
    return 1
}
model_catalog() {
    [[ -n "$UI_PORT" ]] || { echo "no port-forward"; return; }
    catalog_items model_catalog/models | jq -e 'length > 0' >/dev/null && echo yes || echo no
}
agent_catalog() {
    [[ -n "$UI_PORT" ]] || { echo "no port-forward"; return; }
    catalog_items agent_catalog/agents >"$WORK/agents.json" || { echo "listing failed"; return; }
    jq -e 'length > 0 and (. as $items | all({opencode: "OpenCode", hermes: "Hermes"} | to_entries[]; . as $want
        | [$items[] | select(.name == $want.key and .source_id == "governed-coding-agents")]
        | length == 1 and .[0].displayName == $want.value))' "$WORK/agents.json" >/dev/null && echo yes || echo no
}

check "ModelRegistry Available with its RBAC proxy" registry_available yes
check "Registry API and PostgreSQL deployments current, database storage Bound" registry_workloads yes
check "Registry authenticated list API returns a collection" registry_list_api yes
check "Native model catalog component Ready with current API and database" catalog_component yes
check "Dashboard registry, catalogs, agents, tool calling and MCP discovery enabled" dashboard_flags yes
check "Authenticated dashboard model_catalog/models discovery returns items" model_catalog yes
check "Authenticated dashboard agent_catalog/agents lists the reviewed OpenCode and Hermes entries" agent_catalog yes
echo "Scope: installation administrator API probes; persona sessions and browser UI acceptance are separate."
echo "Infrastructure/API acceptance only. No models are deployed; persona and browser UI acceptance are separate."
validation_summary
