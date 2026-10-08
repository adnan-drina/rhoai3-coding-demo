#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT}"
load_env
check_oc_logged_in
python3 "$ROOT/scripts/platform/check-operator-policy.py" "$ROOT/gitops/stages/040-governed-models-as-a-service/mcp-gateway-platform"
[[ "$(oc config view --minify -o jsonpath='{.contexts[0].context.namespace}')" == openshift-gitops ]] || { echo 'Use a dedicated kubeconfig context in openshift-gitops for Argo core.' >&2; exit 1; }
branch="${1:?Usage: deploy-mcp-gateway-platform.sh published-branch}"
sha="$(git -C "$ROOT" rev-parse HEAD)"
[[ "$(git -C "$ROOT" ls-remote origin "refs/heads/$branch" | awk '{print $1}')" == "$sha" ]] || { echo 'Published branch must equal checkout HEAD.' >&2; exit 1; }
[[ -z "$(git -C "$ROOT" status --porcelain -- gitops/stages/040-governed-models-as-a-service/mcp-gateway-platform gitops/argocd/app-of-apps/040-governed-models-as-a-service-mcp-platform.yaml stages/040-governed-models-as-a-service/deploy-mcp-gateway-platform.sh stages/040-governed-models-as-a-service/validate-mcp-gateway-platform.sh scripts/platform/check-operator-policy.py)" ]] || { echo 'MCP Gateway platform source is unpublished.' >&2; exit 1; }
python3 - <<'PY'
import json,subprocess
def get(kind,name,ns=None):
 args=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']+(['-n',ns] if ns else [])
 r=subprocess.run(args,capture_output=True,text=True,timeout=20)
 assert r.returncode==0,'Native ownership read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
app=get('applications.argoproj.io','mcp-gateway-platform','openshift-gitops')
if app:
 s=app['spec'];assert not app['metadata'].get('deletionTimestamp') and not app['metadata'].get('ownerReferences') and not s.get('sources')
 assert s['project']=='rhoai-demo' and s['source']['repoURL']=='https://github.com/adnan-drina/rhoai3-coding-demo.git' and s['source']['path']=='gitops/stages/040-governed-models-as-a-service/mcp-gateway-platform'
 assert s['destination']=={'server':'https://kubernetes.default.svc','namespace':'mcp-gateway-system'}
 assert not app.get('operation') and app.get('status',{}).get('operationState',{}).get('phase')!='Running'
og=get('operatorgroup','global-operators','openshift-operators')
assert og and not og['metadata'].get('deletionTimestamp') and not og['spec'].get('targetNamespaces'),'Existing native global OperatorGroup required'
for kind,name,ns in [('namespace','mcp-gateway-system',None),('resourcequota','mcp-private-boundary','mcp-gateway-system'),('limitrange','mcp-private-defaults','mcp-gateway-system'),('subscription','mcp-gateway','openshift-operators')]:
 obj=get(kind,name,ns)
 if obj:
  assert app is not None and not obj['metadata'].get('deletionTimestamp') and not obj['metadata'].get('ownerReferences'),'Foreign/terminating platform resource'
  group=obj['apiVersion'].split('/')[0] if '/' in obj['apiVersion'] else ''
  expected=f'mcp-gateway-platform:{group}/{obj["kind"]}:{ns or "mcp-gateway-system"}/{name}'
  assert obj['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id')==expected,'Platform resource belongs to another owner'
print('PASS Native platform ownership preflight')
PY
# Own Application is the first write; OLM reconciles Automatic subscriptions.
oc --request-timeout=10s apply -f <(python3 - "$ROOT" "$sha" <<'PY'
import json,subprocess,sys
root,sha=sys.argv[1:]
a=json.loads(subprocess.check_output(['oc','create','--dry-run=client','-f',root+'/gitops/argocd/app-of-apps/040-governed-models-as-a-service-mcp-platform.yaml','-o','json']))
a['spec']['source']['targetRevision']=sha
print(json.dumps(a))
PY
)
ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync mcp-gateway-platform --app-namespace openshift-gitops --revision "$sha" --async --timeout 300
python3 "$ROOT/scripts/platform/check-operator-policy.py" "$ROOT/gitops/stages/040-governed-models-as-a-service/mcp-gateway-platform" --wait 900
echo 'Automatic native operator reconciliation completed; no Gateway Extension is deployed.'
