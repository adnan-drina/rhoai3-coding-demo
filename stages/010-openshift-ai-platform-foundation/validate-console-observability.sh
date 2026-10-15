#!/usr/bin/env bash
# Read-only: 010-console-observability is reconciled, the console plugins Git declares are enabled, and the
# console-owned Perses and its workloads are current and available. Persona and browser checks are separate.
# Usage: stages/010-openshift-ai-platform-foundation/validate-console-observability.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

NS=openshift-cluster-observability-operator
PLUGINS_FILE="$REPO_ROOT/gitops/stages/010-openshift-ai-platform-foundation/010-console-observability/console-plugins.yaml"
read_json() { oc --request-timeout=10s get "$@" -o json; }

app=$(read_json application 010-console-observability -n openshift-gitops)
uiplugin=$(read_json uiplugins.observability.openshift.io monitoring)
declared=$(ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0])["spec"]["plugins"])' "$PLUGINS_FILE")
installed=$(read_json consoleplugins.console.openshift.io | jq -c '[.items[].metadata.name]')
enabled=$(read_json console.operator.openshift.io cluster | jq -c '.spec.plugins // []')
uid=$(jq -r '.metadata.uid' <<<"$uiplugin")
owned_by() { jq -c --arg uid "$1" '[.items[] | select(any(.metadata.ownerReferences[]?; .uid == $uid))]'; }
perses=$(read_json perses -n "$NS" | owned_by "$uid")
deployments=$(read_json deployments -n "$NS" | owned_by "$uid")
statefulsets=$(read_json statefulsets -n "$NS" | owned_by "$(jq -r '.[0].metadata.uid // ""' <<<"$perses")")

reconciled() {
    jq -e '.spec.source as $src | .status as $s
        | ($src.targetRevision | length) == 40
        and $s.sync.status == "Synced" and $s.sync.revision == $src.targetRevision
        and $s.health.status == "Healthy"
        and $s.operationState.phase == "Succeeded"
        and $s.operationState.syncResult.revision == $src.targetRevision
        and $s.operationState.syncResult.source.path == $src.path' <<<"$app" >/dev/null && echo yes || echo no
}
perses_ui() {
    jq -e '.spec.type == "Monitoring" and .spec.monitoring.perses.enabled == true
        and (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("010-console-observability:"))' \
        <<<"$uiplugin" >/dev/null && echo yes || echo no
}
# Git declares the whole plugin list: every declared plugin that is installed is enabled, and nothing else is installed.
declared_enabled() {
    jq -nr --argjson d "$declared" --argjson i "$installed" --argjson e "$enabled" \
        '[$d[] | select(. as $p | ($i | index($p)) and ($e | index($p) | not))] | if length == 0 then "yes" else join(", ") end'
}
nothing_undeclared() {
    jq -nr --argjson d "$declared" --argjson i "$installed" \
        '[$i[] | select(. as $p | $d | index($p) | not)] | if length == 0 then "yes" else join(", ") end'
}
one_perses_available() {
    jq -e 'length == 1 and any(.[0].status.conditions[]?; .type == "Available" and .status == "True")' \
        <<<"$perses" >/dev/null && echo yes || echo no
}
deployments_current() {
    jq -e 'length > 0 and all(.[]; (.spec.replicas // 1) as $n | .status as $s
        | $n > 0 and $s.observedGeneration == .metadata.generation
        and $s.updatedReplicas == $n and $s.readyReplicas == $n and $s.availableReplicas == $n)' \
        <<<"$deployments" >/dev/null && echo yes || echo no
}
statefulset_current() {
    jq -e 'length == 1 and (.[0] | (.spec.replicas // 1) as $n | .status as $s
        | $n > 0 and $s.observedGeneration == .metadata.generation
        and $s.updatedReplicas == $n and $s.readyReplicas == $n
        and ($s.currentRevision // "") != "" and $s.currentRevision == $s.updateRevision)' \
        <<<"$statefulsets" >/dev/null && echo yes || echo no
}

check "010-console-observability Synced, Healthy and last synced at its pinned revision" reconciled yes
check "Monitoring UIPlugin enables Perses and is tracked by 010-console-observability" perses_ui yes
check "Every installed console plugin that Git declares is enabled" declared_enabled yes
check "No installed console plugin is missing from Git" nothing_undeclared yes
check "Exactly one console-owned Perses, Available" one_perses_available yes
check "Console-owned Deployments current and available" deployments_current yes
check "Perses StatefulSet current and ready" statefulset_current yes
echo "Scope: native console/Perses readiness; datasource persona permissions and browser checks are separate."
validation_summary
