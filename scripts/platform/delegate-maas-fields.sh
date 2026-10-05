#!/usr/bin/env bash
# Explicit retained-foundation delegation; never change its source or resources.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - <<'PY'
import copy,json,os,subprocess
name='010-openshift-ai-platform-foundation';ns='openshift-gitops'
def run(args,payload=None):
 r=subprocess.run(['oc','--request-timeout=10s']+args,input=json.dumps(payload) if payload else None,capture_output=True,text=True,timeout=15)
 assert r.returncode==0,'Native delegation API operation failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
a=run(['get','applications.argoproj.io',name,'-n',ns,'-o','json']);spec=a['spec'];source=copy.deepcopy(spec['source']);status=a['status'];op=status.get('operationState',{});result=op.get('syncResult',{})
assert source['targetRevision']=='882f327fb25dd047ca7144058b6cca46e693df3a' and source['path']=='gitops/stages/030-private-model-serving/migration/foundation-omit','Expected reviewed retained-foundation bridge'
assert status['sync']['status']=='Synced' and status['sync']['revision']==source['targetRevision'] and status['health']['status']=='Healthy' and op.get('phase')=='Succeeded' and result.get('revision')==source['targetRevision'] and result.get('source',{}).get('path')==source['path'],'Retained foundation has not reconciled'
assert not a['metadata'].get('ownerReferences') and not a['metadata'].get('deletionTimestamp') and not spec.get('sources') and source['repoURL']==os.environ['GIT_REPO_URL'] and spec['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'} and spec['project']=='rhoai-demo' and 'RespectIgnoreDifferences=true' in spec['syncPolicy']['syncOptions'],'Unexpected foundation ownership'
entries=copy.deepcopy(spec.get('ignoreDifferences',[]))
selected=[('datasciencecluster.opendatahub.io','DataScienceCluster','default-dsc',None,['/spec/components/aigateway','/spec/components/ogx']),('opendatahub.io','OdhDashboardConfig','odh-dashboard-config','redhat-ods-applications',['/spec/dashboardConfig/genAiStudio','/spec/dashboardConfig/modelAsService','/spec/dashboardConfig/vLLMDeploymentOnMaaS'])]
for group,kind,n,namespace,paths in selected:
 matches=[i for i in entries if i.get('group','')==group and i.get('kind')==kind and i.get('name')==n and i.get('namespace')==namespace]
 assert len(matches)<=1,'Ambiguous existing delegation'
 if matches:e=matches[0]
 else:
  e={'group':group,'kind':kind,'name':n,'jsonPointers':[]}
  if namespace:e['namespace']=namespace
  entries.append(e)
 for path in paths:
  if path not in e.setdefault('jsonPointers',[]):e['jsonPointers'].append(path)
if entries!=spec.get('ignoreDifferences',[]):
 patch=[{'op':'test','path':'/metadata/resourceVersion','value':a['metadata']['resourceVersion']},{'op':'test','path':'/spec/source','value':source},{'op':'add','path':'/spec/ignoreDifferences','value':entries}]
 run(['patch','applications.argoproj.io',name,'-n',ns,'--type=json','--patch-file=/dev/stdin','-o','json'],patch)
b=run(['get','applications.argoproj.io',name,'-n',ns,'-o','json']);expected=copy.deepcopy(spec);expected['ignoreDifferences']=entries
assert b['metadata']['uid']==a['metadata']['uid'] and b['spec']==expected,'Delegation changed unrelated foundation configuration'
print('PASS Narrow MaaS/Studio delegation; core source882 and all other Application fields unchanged')
PY
