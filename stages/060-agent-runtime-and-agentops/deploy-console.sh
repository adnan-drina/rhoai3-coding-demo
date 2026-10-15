#!/usr/bin/env bash
# Reconcile only console visibility/discovery; never touch the OpenShell runtime.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 060 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
STAGE_APPS="$ROOT_DIR/scripts/shared/stage_apps.py"
sha=$(python3 "$STAGE_APPS" select 060 --ref "$ref" --repo-url "$GIT_REPO_URL")
export CONSOLE_ROOT="$ROOT_DIR"
python3 - <<'PY'
import json,os,subprocess
def get(kind,name,ns=None):
 a=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:a+=['-n',ns]
 r=subprocess.run(a,capture_output=True,text=True,timeout=15)
 assert r.returncode==0,'Prerequisite API read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
runtime=get('application','060-openshell-runtime','openshift-gitops')
assert runtime and not runtime['metadata'].get('deletionTimestamp') and runtime['status']['health']['status']=='Healthy' and runtime['status']['sync']['status']=='Synced','Existing OpenShell runtime must be healthy'
assert runtime['spec']['source']['repoURL']==os.environ['GIT_REPO_URL'] and runtime['spec']['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/openshell-runtime','Unexpected runtime source'
crd=get('crd','sandboxes.agents.x-k8s.io')
assert crd and any(c['type']=='Established' and c['status']=='True' for c in crd['status']['conditions']),'Native Sandbox CRD is not established'
import sys;sys.path.insert(0,os.environ['CONSOLE_ROOT']+'/scripts/shared');import stage_apps
assert '/spec/dashboardConfig/agentOps' in stage_apps.delegated('010','OdhDashboardConfig','odh-dashboard-config','redhat-ods-applications','opendatahub.io'),'Foundation has not delegated agentOps'
app=get('application','060-agent-console','openshift-gitops')
if app:
 s=app['spec'];assert not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp') and not s.get('sources') and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/agent-console' and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Foreign console Application'
objects=[('serviceaccount','enable-agent-console','redhat-ods-applications','/ServiceAccount'),('role','enable-agent-console','redhat-ods-applications','rbac.authorization.k8s.io/Role'),('rolebinding','enable-agent-console','redhat-ods-applications','rbac.authorization.k8s.io/RoleBinding'),('job','enable-agent-console','redhat-ods-applications','batch/Job')]
for ns in ['openshell-admin','openshell-developer']:
 assert get('namespace',ns),'Existing workspace namespace is missing'
 for kind in ['role','rolebinding']:objects.append((kind,'agent-discovery-readers',ns,'rbac.authorization.k8s.io/'+('Role' if kind=='role' else 'RoleBinding')))
for kind,name,ns,tracking in objects:
 x=get(kind,name,ns)
 if x:
  m=x['metadata'];assert app and not m.get('ownerReferences') and not m.get('deletionTimestamp') and m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')=='060-agent-console:'+tracking+':'+ns+'/'+name,'Foreign console resource'
print('PASS Console prerequisites and exact source ownership')
PY
python3 "$STAGE_APPS" apply 060 --app 060-agent-console --revision "$sha" --repo-url "$GIT_REPO_URL"
python3 "$STAGE_APPS" sync 060 --app 060-agent-console
python3 "$STAGE_APPS" wait 060 --app 060-agent-console --revision "$sha" --repo-url "$GIT_REPO_URL" --timeout 300
