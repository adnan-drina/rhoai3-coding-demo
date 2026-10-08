#!/usr/bin/env bash
# Enable only the native operator prerequisites; never deploy a tool server.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
argocd app sync --help 2>&1 | grep -q -- '--core' || { echo 'ERROR: argocd --core is required'; exit 1; }
[[ "$(oc config view --minify -o jsonpath='{.contexts[0].context.namespace}')" == openshift-gitops ]] || { echo 'ERROR: use a private kubeconfig context namespace openshift-gitops'; exit 1; }
revision="${1:?Pass the reviewed published branch}"
sha=$(git ls-remote "${GIT_REPO_URL:?}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: published source differs'; exit 1; }
paths=(gitops/stages/060-agent-runtime-and-agentops/mcp-platform gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-platform.yaml stages/060-agent-runtime-and-agentops/deploy-mcp-platform.sh stages/060-agent-runtime-and-agentops/validate-mcp-platform.sh)
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- "${paths[@]}") ]] || { echo 'ERROR: publish reviewed MCP platform source first'; exit 1; }
export MCP_PLATFORM_SHA="$sha" MCP_PLATFORM_ROOT="$ROOT_DIR"
python3 - <<'PY'
import json,os,subprocess
def get(kind,name,ns=None):
 a=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:a+=['-n',ns]
 r=subprocess.run(a,capture_output=True,text=True,timeout=15)
 assert r.returncode==0,'Prerequisite API read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
core=get('application','010-openshift-ai-platform-foundation','openshift-gitops')
assert core and not core['metadata'].get('deletionTimestamp') and 'RespectIgnoreDifferences=true' in core['spec'].get('syncPolicy',{}).get('syncOptions',[]) and any(i.get('group')=='datasciencecluster.opendatahub.io' and i.get('kind')=='DataScienceCluster' and i.get('name')=='default-dsc' and not i.get('namespace') and '/spec/components/mcplifecycleoperator' in i.get('jsonPointers',[]) for i in core['spec'].get('ignoreDifferences',[])),'Foundation has not delegated the native MCP component'
dsc=get('datasciencecluster','default-dsc');assert dsc and not dsc['metadata'].get('deletionTimestamp'),'Existing DSC missing or terminating'
assert get('odhdashboardconfig','odh-dashboard-config','redhat-ods-applications')['spec']['dashboardConfig'].get('mcpCatalog') is True,'MCP Catalog must already be enabled'
app=get('application','mcp-platform','openshift-gitops')
if app:
 s=app['spec'];assert not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp') and not app.get('operation') and app.get('status',{}).get('operationState',{}).get('phase') not in ['Running','Terminating'] and not s.get('sources') and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/mcp-platform' and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'redhat-ods-applications'},'Foreign or active MCP platform Application'
for kind,ns,trackingkind in [('serviceaccount','redhat-ods-applications','/ServiceAccount'),('clusterrole',None,'rbac.authorization.k8s.io/ClusterRole'),('clusterrolebinding',None,'rbac.authorization.k8s.io/ClusterRoleBinding'),('job','redhat-ods-applications','batch/Job')]:
 x=get(kind,'enable-mcp-platform',ns)
 if x:
  m=x['metadata'];assert app and not m.get('ownerReferences') and not m.get('deletionTimestamp') and m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')=='mcp-platform:'+trackingkind+':'+(ns or 'redhat-ods-applications')+'/enable-mcp-platform','Foreign MCP prerequisite resource'
  if kind=='clusterrole':assert x['rules']==[{'apiGroups':['datasciencecluster.opendatahub.io'],'resources':['datascienceclusters'],'resourceNames':['default-dsc'],'verbs':['get','patch']}],'MCP prerequisite permissions differ'
  if kind=='clusterrolebinding':assert x['roleRef']=={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'enable-mcp-platform'} and x['subjects']==[{'kind':'ServiceAccount','name':'enable-mcp-platform','namespace':'redhat-ods-applications'}],'MCP prerequisite binding differs'
p=json.loads(subprocess.check_output(['oc','create','--dry-run=client','-f',os.environ['MCP_PLATFORM_ROOT']+'/gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-platform.yaml','-o','json']))
p['spec']['source']['targetRevision']=os.environ['MCP_PLATFORM_SHA']
r=subprocess.run(['oc','apply','-f','-'],input=json.dumps(p),capture_output=True,text=True,timeout=20);assert r.returncode==0,'MCP platform Application apply failed'
print('PASS Narrow native MCP prerequisite source/ownership guards')
PY
ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync mcp-platform --app-namespace openshift-gitops --strategy hook --revision "$sha" --timeout 180
ARGOCD_NAMESPACE=openshift-gitops argocd --core app wait mcp-platform --app-namespace openshift-gitops --health --sync --timeout 180
bash "$ROOT_DIR/stages/060-agent-runtime-and-agentops/validate-mcp-platform.sh"
