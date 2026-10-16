#!/usr/bin/env bash
# Offline manifest and containment checks. Creates temporary Kustomize output only; never queries a cluster.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-stopped-bundle.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT
kustomize build "$SCRIPT_DIR/manifests" | yaml_json >"$WORK_DIR/bundle.json"
if jq -e '
  all(.[]; .kind!="Job" and .kind!="CronJob" and .kind!="Application"
       and .kind!="HorizontalPodAutoscaler" and .kind!="LLMInferenceService")
  and ([.[]|select(.kind=="Deployment")]|length)==1
  and all(.[]|select(.kind=="Deployment"); .spec.replicas==0)
  and ([.[]|select(.kind=="MaaSSubscription")]|length)==3
  and ([.[]|select(.kind=="MaaSAuthPolicy")]|length)==3
  and ([.[]|select(.kind=="PersesDashboard")]|length)==3' "$WORK_DIR/bundle.json" >/dev/null; then
    record 'Detached bundle cannot start models, publisher or scheduled load' pass
else record 'Detached bundle cannot start models, publisher or scheduled load' 'Unexpected workload'; fi
kustomize build "$SCRIPT_DIR/model-drafts/mistral" | yaml_json >"$WORK_DIR/mistral.json"
if jq -e 'any(.[]; .kind=="LLMInferenceService" and .spec.replicas==0)
  and any(..|objects; .sectionName?=="api")' "$WORK_DIR/mistral.json" >/dev/null; then
    record 'Mistral candidate remains stopped' pass
else record 'Mistral candidate remains stopped' 'Invalid draft'; fi

# Keep the detached bundle ready for review without relaxing repository manifest rules.
manifest_conventions() {
    local file
    for file in "$SCRIPT_DIR"/manifests/*.yaml "$SCRIPT_DIR"/model-drafts/mistral/*.yaml; do
        yaml_json <"$file" | jq -e 'length == 1' >/dev/null || return 1
    done
    jq -es 'add | all(.[];
      .metadata.labels as $labels
      | ($labels["app.kubernetes.io/name"]|type)=="string"
        and ($labels["app.kubernetes.io/component"]|type)=="string"
        and $labels["app.kubernetes.io/managed-by"]=="argocd"
        and (["maas","observability","llm-serving"]|index($labels["app.kubernetes.io/part-of"]))!=null)' \
        "$WORK_DIR/bundle.json" "$WORK_DIR/mistral.json" >/dev/null
}
if manifest_conventions; then record 'One resource per file and functional ownership labels' pass
else record 'One resource per file and functional ownership labels' 'Manifest convention mismatch'; fi

mkdir "$WORK_DIR/qwen"
for name in qwen38-27b-llminferenceservice.yaml qwen38-27b-maas-modelref.yaml; do
    cp "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-local-models/$name" "$WORK_DIR/qwen/"
done
cp -R "$SCRIPT_DIR/model-drafts/qwen-fp8" "$WORK_DIR/qwen/fp8"
cat >"$WORK_DIR/qwen/kustomization.yaml" <<'YAML'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - qwen38-27b-llminferenceservice.yaml
  - qwen38-27b-maas-modelref.yaml
components:
  - fp8
YAML
kustomize build "$WORK_DIR/qwen" | yaml_json >"$WORK_DIR/qwen.json"
if jq -e 'any(.[]; .kind=="LLMInferenceService" and .spec.replicas==0)
  and any(..|strings; startswith("hf://Qwen/Qwen3.8-27B-FP8:"))
  and any(..|objects; .name?=="VLLM_USE_DEEP_GEMM")' "$WORK_DIR/qwen.json" >/dev/null; then
    record 'Qwen FP8 component preserves stopped state' pass
else record 'Qwen FP8 component preserves stopped state' 'Invalid component'; fi
if grep -Rl --include='*.yaml' 'showback-demo' "$REPO_ROOT/gitops" >"$WORK_DIR/references"; then
    record 'Active GitOps does not reference showback-demo' 'Found active reference'
else
    result=$?
    if (( result == 1 )); then record 'Active GitOps does not reference showback-demo' pass
    else record 'Active GitOps does not reference showback-demo' 'Unable to inspect GitOps'; fi
fi
validation_summary
