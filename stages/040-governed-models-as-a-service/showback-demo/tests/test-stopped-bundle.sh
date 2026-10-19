#!/usr/bin/env bash
# Offline manifest and containment checks. Creates temporary Kustomize output only; never queries a cluster.
# Usage: stages/040-governed-models-as-a-service/showback-demo/tests/test-stopped-bundle.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
COMPONENT="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo"
source "$REPO_ROOT/scripts/lib.sh"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT
kustomize build "$COMPONENT" | yaml_json >"$WORK_DIR/bundle.json"
if jq -e '
  ([.[]|select(.kind=="Deployment")][0].spec.replicas) as $replicas |
  [.[]|select(.kind=="ConfigMap" and .metadata.name=="showback-selected-report")][0] as $report |
  all(.[]; .kind!="Job" and .kind!="CronJob" and .kind!="Application"
       and .kind!="Pod" and .kind!="DaemonSet" and .kind!="StatefulSet"
       and .kind!="HorizontalPodAutoscaler" and .kind!="LLMInferenceService"
       and .kind!="InferenceService" and .kind!="MaaSModelRef"
       and .metadata.annotations["argocd.argoproj.io/hook"]==null)
  and ([.[]|select(.kind=="Deployment")]|length)==1
  and ([.[]|select(.kind=="Deployment")][0].spec.replicas|IN(0,1))
  and length==21
  and ([.[]|select(.kind=="MaaSSubscription")]|length)==2
  and ([.[]|select(.kind=="MaaSAuthPolicy")]|length)==2
  and all(.[]|select(.kind=="MaaSSubscription" or .kind=="MaaSAuthPolicy");
      (.metadata.name|IN("team-engineering","team-support"))
      and (.spec.modelRefs|length)==1 and .spec.modelRefs[0].name=="qwen3-8-27b")
  and ([.[]|select(.kind=="PersesDashboard")]|length)==8
  and (if $replicas==0 then $report.data=={}
     else ($report.data|keys)==["metrics.prom"]
       and ($report.metadata.annotations["showback.demo.rhoai.io/report-sha256"]|test("^[a-f0-9]{64}$"))
       and ($report.data["metrics.prom"]|test("(?m)^showback_selected_report_info\\{[^\\n]*evidence_kind=\"observed\""))
       and ($report.data["metrics.prom"]|contains("report_sha256=\""+$report.metadata.annotations["showback.demo.rhoai.io/report-sha256"]+"\""))
     end)
  and ([.[]|select(.kind=="ConfigMap" and .metadata.annotations["demo.rhoai.io/state"]=="inert-review-inputs")]|length)==2
  ' "$WORK_DIR/bundle.json" >/dev/null; then
    record 'Only an observed selected-report publisher may run; no models or scheduled load' pass
else record 'Only an observed selected-report publisher may run; no models or scheduled load' 'Unexpected workload or report'; fi

# The explicit qualification component narrows activation; the original generated scenario stays reusable.
cp -R "$COMPONENT" "$WORK_DIR/full"
yaml_json <"$WORK_DIR/full/kustomization.yaml" | jq '.[0] | del(.components)' >"$WORK_DIR/full/kustomization.yaml.new"
mv "$WORK_DIR/full/kustomization.yaml.new" "$WORK_DIR/full/kustomization.yaml"
kustomize build "$WORK_DIR/full" | yaml_json >"$WORK_DIR/full.json"
if jq -e 'length==23
  and ([.[]|select(.kind=="MaaSSubscription")]|length)==3
  and ([.[]|select(.kind=="MaaSAuthPolicy")]|length)==3
  and ([.[]|select(.kind=="MaaSAuthPolicy")|.spec.modelRefs[].name]|unique)
      ==["mistral-small4-119b","qwen3-8-27b"]
  and any(.[]; .kind=="RoleBinding" and .metadata.namespace=="showback-reporting"
      and .roleRef=={apiGroup:"rbac.authorization.k8s.io",kind:"ClusterRole",name:"edit"}
      and .subjects==[{apiGroup:"rbac.authorization.k8s.io",kind:"Group",name:"rhods-admins"}])' \
    "$WORK_DIR/full.json" >/dev/null; then
    record 'Full generated scenario retained; archive grant is namespaced for rhods-admins' pass
else record 'Full generated scenario retained; archive grant is namespaced for rhods-admins' 'Scenario or grant differs'; fi
kustomize build "$COMPONENT/model-drafts/mistral" | yaml_json >"$WORK_DIR/mistral.json"
if jq -e 'any(.[]; .kind=="LLMInferenceService" and .spec.replicas==0)
  and any(..|objects; .sectionName?=="api")' "$WORK_DIR/mistral.json" >/dev/null; then
    record 'Mistral candidate remains stopped' pass
else record 'Mistral candidate remains stopped' 'Invalid draft'; fi

# Keep the optional bundle ready for review without relaxing repository manifest rules.
manifest_conventions() {
    local file
    while IFS= read -r file; do
        yaml_json <"$file" | jq -e 'length == 1' >/dev/null || return 1
    done < <(find "$COMPONENT" -type f -name '*.yaml')
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
yaml_json <"$REPO_ROOT/gitops/applications/040-showback-demo.yaml" >"$WORK_DIR/app.json"
if jq -e '.[0] | .metadata.annotations["demo.rhoai.io/optional"]=="true"
    and .metadata.annotations["demo.rhoai.io/deploy-order"]==null
    and (.metadata.annotations["demo.rhoai.io/deploy-script"]|endswith("--component 040-showback-demo"))
    and .spec.syncPolicy.automated==null and .operation==null
    and (.metadata.finalizers // []|index("resources-finalizer.argocd.argoproj.io"))==null
    and .spec.source.path=="gitops/stages/040-governed-models-as-a-service/040-showback-demo"' \
    "$WORK_DIR/app.json" >/dev/null; then
    record 'Optional Application requires an explicit manual sync' pass
else record 'Optional Application requires an explicit manual sync' 'Activation contract differs'; fi

# A component may reference shared services, but it must never become their second owner.
if jq -e 'all(.[];
    (.kind!="Namespace" or .metadata.name=="showback-reporting")
    and (.kind|IN("Gateway","HTTPRoute","DataScienceCluster","DSCInitialization","OdhDashboardConfig",
      "MaasTenantConfig","Config","MachineSet","ClusterQueue","ResourceFlavor","LokiStack")|not)
    and (.kind!="ConfigMap" or .metadata.name!="payload-processing-plugins"))' "$WORK_DIR/bundle.json" >/dev/null; then
    record 'Shared platform and model resources keep their existing owners' pass
else record 'Shared platform and model resources keep their existing owners' 'Found shared resource owner'; fi

for component in "$REPO_ROOT"/gitops/stages/040-governed-models-as-a-service/040-*/; do
    [[ "${component%/}" == "$COMPONENT" ]] && continue
    kustomize build "$component" | yaml_json
done | jq -s 'add' >"$WORK_DIR/other-components.json"
if jq -ne --slurpfile bundle "$WORK_DIR/bundle.json" --slurpfile other "$WORK_DIR/other-components.json" '
    def identities: map([(.apiVersion|split("/")|if length>1 then .[0] else "" end),.kind,
      (.metadata.namespace // "openshift-gitops"),.metadata.name]|join(":"));
    ($bundle[0]|identities) as $b | ($other[0]|identities) as $o | ($b - ($b-$o))==[]' >/dev/null; then
    record 'Optional objects are disjoint from every other Stage 040 component' pass
else record 'Optional objects are disjoint from every other Stage 040 component' 'Duplicate object owner'; fi
validation_summary
