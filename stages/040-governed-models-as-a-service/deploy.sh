#!/usr/bin/env bash
# Reconcile native Stage040 desired state; runtime credentials remain outside Git.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
revision="${1:-${GIT_REPO_BRANCH:-}}"
[[ -n "$revision" ]] || { echo 'ERROR: select the reviewed published branch.' >&2; exit 1; }
export GIT_REPO_URL
remote_sha=$(git ls-remote "${GIT_REPO_URL:?Set GIT_REPO_URL}" "refs/heads/$revision" | awk '{print $1}')
[[ "$remote_sha" =~ ^[0-9a-f]{40}$ && "$remote_sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published revision differs from reviewed checkout.' >&2; exit 1; }
paths=(gitops/stages/040-governed-models-as-a-service gitops/argocd/app-of-apps/040-governed-models-as-a-service.yaml stages/040-governed-models-as-a-service scripts/shared scripts/platform/validate-serving-update.py)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish all reviewed Stage040 source before deployment.' >&2; exit 1; }
state=$(python3 "$SCRIPT_DIR/preflight.py")
if [[ -n "$(oc --request-timeout=10s get application 040-governed-models-as-a-service -n openshift-gitops --ignore-not-found -o jsonpath='{.metadata.uid}')" ]]; then
  python3 "$ROOT_DIR/scripts/platform/validate-serving-update.py" 040
else
  "$ROOT_DIR/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
fi
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
work=$(mktemp -d);trap 'rm -rf "$work"' EXIT
oc --request-timeout=10s get ingresscontroller default -n openshift-ingress-operator -o json > "$work/ingress.json"
ruby -ryaml -rjson -ruri -e '
a=YAML.load_file(ARGV[0]);a["spec"]["source"]["repoURL"]=ENV.fetch("GIT_REPO_URL");a["spec"]["source"]["targetRevision"]=ARGV[1]
domain=JSON.parse(File.read(ARGV[2])).dig("status","domain");abort "ERROR: native ingress domain is unavailable." unless domain && domain.match?(/\A[a-z0-9.-]+\z/)
patches=[]
["maas","qwen3-6-maas","qwen3-8-maas"].each_with_index{|host,i|patches << {"op"=>"replace","path"=>"/spec/listeners/#{i}/hostname","value"=>"#{host}.#{domain}"}}
a["spec"]["source"]["kustomize"]={"patches"=>[
 {"target"=>{"group"=>"gateway.networking.k8s.io","version"=>"v1","kind"=>"Gateway","name"=>"maas-default-gateway","namespace"=>"openshift-ingress"},"patch"=>JSON.generate(patches)},
 {"target"=>{"group"=>"maas.opendatahub.io","version"=>"v1alpha1","kind"=>"MaaSModelRef","name"=>"gpt-6-luna","namespace"=>"external-models"},"patch"=>JSON.generate([{ "op"=>"replace","path"=>"/spec/endpointOverride","value"=>"https://maas.#{domain}"}])}
]};provider=URI.parse(ENV.fetch("REDHAT_MODELS_BASE_URL"));abort "ERROR: approved Red Hat provider endpoint must be HTTPS." unless provider.scheme=="https" && provider.port==443 && ["","/","/v1","/v1/"].include?(provider.path) && provider.host && !provider.userinfo && !provider.query && !provider.fragment
 a["spec"]["source"]["kustomize"]["patches"] << {"target"=>{"group"=>"inference.opendatahub.io","version"=>"v1alpha1","kind"=>"ExternalProvider","name"=>"redhat-models","namespace"=>"external-models"},"patch"=>JSON.generate([{"op"=>"replace","path"=>"/spec/endpoint","value"=>provider.host}])}
 a["spec"]["source"]["kustomize"]["patches"] << {"target"=>{"group"=>"maas.opendatahub.io","version"=>"v1alpha1","kind"=>"MaaSModelRef","name"=>"minimax-m2","namespace"=>"external-models"},"patch"=>JSON.generate([{"op"=>"replace","path"=>"/spec/endpointOverride","value"=>"https://maas.#{domain}"}])};puts YAML.dump(a)' "$ROOT_DIR/gitops/argocd/app-of-apps/040-governed-models-as-a-service.yaml" "$remote_sha" "$work/ingress.json" > "$work/application.yaml"
# The first modifying action is this stage's own immutable Application.
oc --request-timeout=10s apply -f "$work/application.yaml"
"$SCRIPT_DIR/setup-provider-secret.sh"
RHOAI_STAGE040_PROVIDER_SECRET=redhat-models-provider-api-key "$SCRIPT_DIR/setup-provider-secret.sh"
"$SCRIPT_DIR/approve-operators.sh"
if [[ "$state" == fresh ]]; then
 "$SCRIPT_DIR/setup-database.sh" --fresh-database
else
 "$SCRIPT_DIR/setup-database.sh"
fi
hook_sync_requested=false
for _ in $(seq 1 240); do
 # Selective autosync can skip Sync hooks. Use the supported native full-hook path once.
 native_operation="$(oc --request-timeout=10s get applications.argoproj.io 040-governed-models-as-a-service -n openshift-gitops -o go-template='{{.status.operationState.phase}}|{{.status.operationState.syncResult.revision}}|{{.status.operationState.syncResult.source.path}}')"
 if [[ "$hook_sync_requested" == false && ( "$native_operation" != "Succeeded|$remote_sha|gitops/stages/040-governed-models-as-a-service/base" || "$(oc --request-timeout=10s get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiTracing}')" != true ) && -z "$(oc --request-timeout=10s get applications.argoproj.io 040-governed-models-as-a-service -n openshift-gitops -o go-template='{{if .operation}}pending{{end}}')" ]]; then
  command -v argocd >/dev/null || { echo 'ERROR: current Argo CLI required to execute native Sync hooks.' >&2;exit 1; }
  RHOAI_STAGE040_SYNC_REVISION="$remote_sha" python3 - <<'PY_GUARD'
import json,os,subprocess
x=json.loads(subprocess.check_output(['oc','--request-timeout=10s','get','applications.argoproj.io','040-governed-models-as-a-service','-n','openshift-gitops','-o','json'],text=True));s=x['spec']
assert 'RespectIgnoreDifferences=true' in s['syncPolicy']['syncOptions']
for name in ['qwen3-6-27b','qwen3-8-27b-int4']:assert any(i.get('kind')=='LLMInferenceService' and i.get('name')==name and i.get('namespace')=='models-as-a-service' and '/spec/replicas' in i.get('jsonPointers',[]) for i in s['ignoreDifferences']),'Model lifecycle delegation missing'
assert s['source']['targetRevision']==os.environ['RHOAI_STAGE040_SYNC_REVISION'] and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/040-governed-models-as-a-service/base' and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'} and not s.get('sources') and not x['metadata'].get('ownerReferences') and not x['metadata'].get('deletionTimestamp') and not x.get('operation'),'Unexpected own Application identity or active operation'
PY_GUARD
  ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync 040-governed-models-as-a-service --app-namespace openshift-gitops --strategy hook --revision "$remote_sha" --async --timeout 300
  hook_sync_requested=true
 fi
 if "$SCRIPT_DIR/validate.sh" --readiness; then
  echo 'PASS Native Stage040 readiness. Bounded real inference/stream/auth/metrics and user Studio visual acceptance are separate.'
  exit 0
 fi
 sleep 10
done
echo 'ERROR: Stage040 native readiness timed out; inspect exact operator/component conditions. No generated operands were patched.' >&2
exit 1
