#!/usr/bin/env bash
# Reconcile native Stage040 desired state; runtime credentials remain outside Git.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/040-governed-models-as-a-service"
revision="${1:-${GIT_REPO_BRANCH:-}}"
[[ -n "$revision" ]] || { echo 'ERROR: select the reviewed published branch.' >&2; exit 1; }
export GIT_REPO_URL
remote_sha=$(git ls-remote "${GIT_REPO_URL:?Set GIT_REPO_URL}" "refs/heads/$revision" | awk '{print $1}')
[[ "$remote_sha" =~ ^[0-9a-f]{40}$ && "$remote_sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published revision differs from reviewed checkout.' >&2; exit 1; }
export RHOAI_STAGE040_EXPECTED_REVISION="$remote_sha"
paths=(gitops/stages/040-governed-models-as-a-service gitops/argocd/app-of-apps/040-governed-models-as-a-service stages/040-governed-models-as-a-service scripts/shared scripts/platform/validate-serving-update.py scripts/platform/check-operator-policy.py)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish all reviewed Stage040 source before deployment.' >&2; exit 1; }
STAGE_APPS="$ROOT_DIR/scripts/shared/stage_apps.py"
components=()
while IFS= read -r name; do components+=("$name"); done < <(python3 "$STAGE_APPS" names 040)
state=$(python3 "$SCRIPT_DIR/preflight.py")
if [[ -n "$(oc --request-timeout=10s get applications.argoproj.io "${components[@]}" -n openshift-gitops --ignore-not-found -o name)" ]]; then
  python3 "$ROOT_DIR/scripts/platform/validate-serving-update.py" 040
else
  "$ROOT_DIR/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
fi
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
work=$(mktemp -d);trap 'rm -rf "$work"' EXIT
oc --request-timeout=10s get ingresscontroller default -n openshift-ingress-operator -o json > "$work/ingress.json"
python3 "$STAGE_APPS" applications 040 --revision "$remote_sha" --repo-url "$GIT_REPO_URL" > "$work/components.json"
# The Gateway component gets this cluster's listener hostnames as a source patch.
ruby -rjson -e '
apps=JSON.parse(File.read(ARGV[0]))
domain=JSON.parse(File.read(ARGV[1])).dig("status","domain");abort "ERROR: native ingress domain is unavailable." unless domain && domain.match?(/\A[a-z0-9.-]+\z/)
patches=[]
["maas","qwen3-8-maas"].each_with_index{|host,i|patches << {"op"=>"replace","path"=>"/spec/listeners/#{i}/hostname","value"=>"#{host}.#{domain}"}}
gateway=apps["items"].find{|a| a["metadata"]["name"]=="040-gateway-governance"} or abort "ERROR: Gateway component is missing."
gateway["spec"]["source"]["kustomize"]={"patches"=>[
 {"target"=>{"group"=>"gateway.networking.k8s.io","version"=>"v1","kind"=>"Gateway","name"=>"maas-default-gateway","namespace"=>"openshift-ingress"},"patch"=>JSON.generate(patches)}
]}
puts JSON.generate(apps)' "$work/components.json" "$work/ingress.json" > "$work/applications.json"
# The first modifying action is this stage's own immutable component Applications.
oc --request-timeout=10s apply -f "$work/applications.json"
"$SCRIPT_DIR/setup-provider-secret.sh"
RHOAI_STAGE040_PROVIDER_SECRET=anthropic-provider-api-key "$SCRIPT_DIR/setup-provider-secret.sh"
RHOAI_STAGE040_PROVIDER_SECRET=nvidia-provider-api-key "$SCRIPT_DIR/setup-provider-secret.sh"
"$SCRIPT_DIR/approve-operators.sh"
if [[ "$state" == fresh ]]; then
 "$SCRIPT_DIR/setup-database.sh" --fresh-database
else
 "$SCRIPT_DIR/setup-database.sh"
fi
# Selective autosync can skip Sync hooks. Use the supported native full-hook path once per component
# whose last operation is not a successful sync of this revision (and for MaaS enablement until tracing is on).
hook_synced=" "
for _ in $(seq 1 240); do
 for name in "${components[@]}"; do
  [[ "$hook_synced" == *" $name "* ]] && continue
  operation="$(oc --request-timeout=10s get applications.argoproj.io "$name" -n openshift-gitops -o go-template='{{.status.operationState.phase}}|{{.status.operationState.syncResult.revision}}|{{if .operation}}pending{{end}}')"
  needs_hooks=false
  [[ "$operation" == "Succeeded|$remote_sha|" ]] || needs_hooks=true
  if [[ "$name" == 040-maas-platform && "$(oc --request-timeout=10s get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiTracing}')" != true ]]; then needs_hooks=true; fi
  [[ "$needs_hooks" == true && "$operation" != *pending ]] || continue
  command -v argocd >/dev/null || { echo 'ERROR: current Argo CLI required to execute native Sync hooks.' >&2;exit 1; }
  RHOAI_STAGE040_SYNC_REVISION="$remote_sha" RHOAI_STAGE040_COMPONENT="$name" python3 - "$work/applications.json" <<'PY_GUARD'
import json,os,subprocess,sys
x=json.loads(subprocess.check_output(['oc','--request-timeout=10s','get','applications.argoproj.io',os.environ['RHOAI_STAGE040_COMPONENT'],'-n','openshift-gitops','-o','json'],text=True));s=x['spec']
desired=next(a for a in json.load(open(sys.argv[1]))['items'] if a['metadata']['name']==x['metadata']['name'])
assert 'RespectIgnoreDifferences=true' in s['syncPolicy']['syncOptions'] and s.get('ignoreDifferences',[])==desired['spec'].get('ignoreDifferences',[]),'Field delegation differs from the reviewed component'
assert s['source']==desired['spec']['source'] and s['source']['targetRevision']==os.environ['RHOAI_STAGE040_SYNC_REVISION'] and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'} and not s.get('sources') and not x['metadata'].get('ownerReferences') and not x['metadata'].get('deletionTimestamp') and not x.get('operation'),'Unexpected component Application identity or active operation'
PY_GUARD
  ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync "$name" --app-namespace openshift-gitops --strategy hook --revision "$remote_sha" --async --timeout 300
  hook_synced+="$name "
 done
 if [[ "$(oc --request-timeout=10s get applications.argoproj.io 040-genai-studio -n openshift-gitops -o go-template='{{.status.operationState.phase}}|{{.status.operationState.syncResult.revision}}')" == "Succeeded|$remote_sha" ]]; then
  RHOAI_STAGE040_EXPECTED_REVISION="$remote_sha" python3 "$SCRIPT_DIR/publish-catalog-mcp.py" --defer-if-absent
  RHOAI_STAGE040_EXPECTED_REVISION="$remote_sha" python3 "$SCRIPT_DIR/publish-catalog-mcp.py" --key OpenShift-MCP-ReadWrite --defer-if-absent
 fi
 if "$SCRIPT_DIR/validate.sh" --readiness; then
  echo 'PASS Native Stage040 readiness. Bounded real inference/stream/auth/metrics and user Studio visual acceptance are separate.'
  exit 0
 fi
 sleep 10
done
echo 'ERROR: Stage040 native readiness timed out; inspect exact operator/component conditions. No generated operands were patched.' >&2
exit 1
