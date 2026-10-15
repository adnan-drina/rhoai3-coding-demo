#!/usr/bin/env bash
# Enable only the native operator prerequisites; never deploy a tool server.
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
export MCP_PLATFORM_ROOT="$ROOT_DIR"
python3 - <<'PY'
import json,os,subprocess
def get(kind,name,ns=None):
 a=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:a+=['-n',ns]
 r=subprocess.run(a,capture_output=True,text=True,timeout=15)
 assert r.returncode==0,'Prerequisite API read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
import sys;sys.path.insert(0,os.environ['MCP_PLATFORM_ROOT']+'/scripts/shared');import stage_apps
assert '/spec/components/mcplifecycleoperator' in stage_apps.delegated('010','DataScienceCluster','default-dsc',group='datasciencecluster.opendatahub.io'),'Foundation has not delegated the native MCP component'
dsc=get('datasciencecluster','default-dsc');assert dsc and not dsc['metadata'].get('deletionTimestamp'),'Existing DSC missing or terminating'
assert get('odhdashboardconfig','odh-dashboard-config','redhat-ods-applications')['spec']['dashboardConfig'].get('mcpCatalog') is True,'MCP Catalog must already be enabled'
app=get('application','060-mcp-platform','openshift-gitops')
if app:
 s=app['spec'];assert not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp') and not app.get('operation') and app.get('status',{}).get('operationState',{}).get('phase') not in ['Running','Terminating'] and not s.get('sources') and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/060-mcp-platform' and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Foreign or active MCP platform Application'
for kind,ns,trackingkind in [('serviceaccount','redhat-ods-applications','/ServiceAccount'),('clusterrole',None,'rbac.authorization.k8s.io/ClusterRole'),('clusterrolebinding',None,'rbac.authorization.k8s.io/ClusterRoleBinding'),('job','redhat-ods-applications','batch/Job')]:
 x=get(kind,'enable-mcp-platform',ns)
 if x:
  m=x['metadata'];assert app and not m.get('ownerReferences') and not m.get('deletionTimestamp') and m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')=='060-mcp-platform:'+trackingkind+':'+(ns or 'openshift-gitops')+'/enable-mcp-platform','Foreign MCP prerequisite resource'
  if kind=='clusterrole':assert x['rules']==[{'apiGroups':['datasciencecluster.opendatahub.io'],'resources':['datascienceclusters'],'resourceNames':['default-dsc'],'verbs':['get','patch']}],'MCP prerequisite permissions differ'
  if kind=='clusterrolebinding':assert x['roleRef']=={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'enable-mcp-platform'} and x['subjects']==[{'kind':'ServiceAccount','name':'enable-mcp-platform','namespace':'redhat-ods-applications'}],'MCP prerequisite binding differs'
print('PASS Narrow native MCP prerequisite source/ownership guards')
PY
python3 "$STAGE_APPS" apply 060 --app 060-mcp-platform --revision "$sha" --repo-url "$GIT_REPO_URL"
python3 "$STAGE_APPS" sync 060 --app 060-mcp-platform
python3 "$STAGE_APPS" wait 060 --app 060-mcp-platform --revision "$sha" --repo-url "$GIT_REPO_URL" --timeout 300
bash "$ROOT_DIR/stages/060-agent-runtime-and-agentops/validate-mcp-platform.sh"
