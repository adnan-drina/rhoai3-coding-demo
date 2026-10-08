#!/usr/bin/env bash
# Reconcile only console visibility/discovery; never touch the OpenShell runtime.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
argocd app sync --help 2>&1 | grep -q -- '--core' || { echo 'ERROR: argocd --core is required'; exit 1; }
[[ "$(oc config view --minify -o jsonpath='{.contexts[0].context.namespace}')" == openshift-gitops ]] || { echo 'ERROR: use a private kubeconfig context namespace openshift-gitops'; exit 1; }
revision="${1:?Pass a published branch pointing to the reviewed checkout}"
sha=$(git ls-remote "${GIT_REPO_URL:?}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published revision differs'; exit 1; }
paths=(gitops/stages/060-agent-runtime-and-agentops/agent-console gitops/stages/060-agent-runtime-and-agentops/runtime/console-discovery gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-console.yaml stages/060-agent-runtime-and-agentops/deploy-console.sh)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish reviewed console source first'; exit 1; }
export CONSOLE_SHA="$sha" CONSOLE_ROOT="$ROOT_DIR"
python3 - <<'PY'
import json,os,subprocess
def get(kind,name,ns=None):
 a=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:a+=['-n',ns]
 r=subprocess.run(a,capture_output=True,text=True,timeout=15)
 assert r.returncode==0,'Prerequisite API read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
runtime=get('application','openshell-runtime','openshift-gitops')
assert runtime and not runtime['metadata'].get('deletionTimestamp') and runtime['status']['health']['status']=='Healthy' and runtime['status']['sync']['status']=='Synced','Existing OpenShell runtime must be healthy'
assert runtime['spec']['source']['repoURL']==os.environ['GIT_REPO_URL'] and runtime['spec']['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/runtime','Unexpected runtime source'
crd=get('crd','sandboxes.agents.x-k8s.io')
assert crd and any(c['type']=='Established' and c['status']=='True' for c in crd['status']['conditions']),'Native Sandbox CRD is not established'
core=get('application','010-openshift-ai-platform-foundation','openshift-gitops')
assert core and 'RespectIgnoreDifferences=true' in core['spec'].get('syncPolicy',{}).get('syncOptions',[]) and any(i.get('group')=='opendatahub.io' and i.get('kind')=='OdhDashboardConfig' and i.get('name')=='odh-dashboard-config' and i.get('namespace')=='redhat-ods-applications' and '/spec/dashboardConfig/agentOps' in i.get('jsonPointers',[]) for i in core['spec'].get('ignoreDifferences',[])),'Foundation has not delegated agentOps'
app=get('application','agent-console','openshift-gitops')
if app:
 s=app['spec'];assert not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp') and not s.get('sources') and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/agent-console' and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'redhat-ods-applications'},'Foreign console Application'
objects=[('serviceaccount','enable-agent-console','redhat-ods-applications','/ServiceAccount'),('role','enable-agent-console','redhat-ods-applications','rbac.authorization.k8s.io/Role'),('rolebinding','enable-agent-console','redhat-ods-applications','rbac.authorization.k8s.io/RoleBinding'),('job','enable-agent-console','redhat-ods-applications','batch/Job')]
for ns in ['openshell-admin','openshell-developer']:
 assert get('namespace',ns),'Existing workspace namespace is missing'
 for kind in ['role','rolebinding']:objects.append((kind,'agent-discovery-readers',ns,'rbac.authorization.k8s.io/'+('Role' if kind=='role' else 'RoleBinding')))
for kind,name,ns,tracking in objects:
 x=get(kind,name,ns)
 if x:
  m=x['metadata'];assert app and not m.get('ownerReferences') and not m.get('deletionTimestamp') and m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')=='agent-console:'+tracking+':'+ns+'/'+name,'Foreign console resource'
payload=json.loads(subprocess.check_output(['oc','create','--dry-run=client','-f',os.environ['CONSOLE_ROOT']+'/gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-console.yaml','-o','json']))
payload['spec']['source']['targetRevision']=os.environ['CONSOLE_SHA']
r=subprocess.run(['oc','apply','-f','-'],input=json.dumps(payload),text=True,capture_output=True,timeout=20)
assert r.returncode==0,'Console Application apply failed'
print('PASS Console prerequisites and exact source ownership')
PY
ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync agent-console --app-namespace openshift-gitops --strategy hook --revision "$sha" --timeout 180
ARGOCD_NAMESPACE=openshift-gitops argocd --core app wait agent-console --app-namespace openshift-gitops --health --sync --timeout 180
