#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
export MCP_PLATFORM_ROOT="$ROOT_DIR"
python3 - <<'PY'
import json,subprocess,time,os
def get(kind,name,ns=None):
 a=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:a+=['-n',ns]
 r=subprocess.run(a,capture_output=True,text=True,timeout=15);assert r.returncode==0,'Native MCP readiness API read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
a=get('application','mcp-platform','openshift-gitops');assert a,'MCP platform Application missing'
s=a['spec'];st=a['status'];op=st.get('operationState',{});result=op.get('syncResult',{})
assert not a['metadata'].get('ownerReferences') and not a['metadata'].get('deletionTimestamp') and not s.get('sources') and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'redhat-ods-applications'} and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/mcp-platform','Unexpected MCP platform Application identity'
assert st['sync']['status']=='Synced' and st['sync']['revision']==s['source']['targetRevision'] and st['health']['status']=='Healthy' and op.get('phase')=='Succeeded' and result.get('revision')==s['source']['targetRevision'] and result.get('source',{}).get('path')==s['source']['path'],'MCP platform source not reconciled'
pin=json.load(open(os.environ['MCP_PLATFORM_ROOT']+'/gitops/stages/060-agent-runtime-and-agentops/mcp-platform/operator-source.json'))
end=time.monotonic()+180
while True:
 d=get('datasciencecluster','default-dsc');c=get('crd','mcpservers.mcp.x-k8s.io')
 component=get('mcplifecycleoperators.components.platform.opendatahub.io','default')
 assert d['spec']['components']['mcplifecycleoperator']['managementState']=='Managed','Native MCP component is not Managed'
 deployments=json.loads(subprocess.check_output(['oc','--request-timeout=10s','get','deployments','-n','redhat-ods-applications','-l','app.kubernetes.io/name=mcp-lifecycle-operator','-o','json'],stderr=subprocess.PIPE,timeout=15))['items']
 native_ready=any(x['type']=='MCPLifecycleOperatorReady' and x['status']=='True' for x in d.get('status',{}).get('conditions',[]))
 workload_ready=False;component_ready=False
 if len(deployments)==1:
  dep=deployments[0];m=dep['metadata'];status=dep.get('status',{});replicas=dep['spec'].get('replicas',1)
  assert component and not component['metadata'].get('deletionTimestamp') and component['spec'].get('managementState')=='Managed' and any(o.get('uid')==d['metadata']['uid'] and o.get('kind')=='DataScienceCluster' and o.get('controller') is True for o in component['metadata'].get('ownerReferences',[])),'Native component owner is not the current DSC'
  component_ready=component.get('status',{}).get('observedGeneration')==component['metadata']['generation'] and any(x['type']=='Ready' and x['status']=='True' and x.get('observedGeneration')==component['metadata']['generation'] for x in component.get('status',{}).get('conditions',[]))
  assert not m.get('deletionTimestamp') and any(o.get('uid')==component['metadata']['uid'] and o.get('kind')=='MCPLifecycleOperator' and o.get('controller') is True for o in m.get('ownerReferences',[])),'Native operator Deployment owner is not the current component'
  images=[x['image'] for x in dep['spec']['template']['spec']['containers']]
  assert pin['image'] in images,'Installed native operator image differs from the reviewed RHOAI tuple'
  workload_ready=replicas>0 and status.get('observedGeneration')==m['generation'] and status.get('replicas',0)==replicas and status.get('updatedReplicas',0)==replicas and status.get('readyReplicas',0)==replicas and status.get('availableReplicas',0)==replicas
 if native_ready and component_ready and workload_ready and c and any(x['type']=='Established' and x['status']=='True' for x in c.get('status',{}).get('conditions',[])):
  assert c['spec']['group']=='mcp.x-k8s.io' and any(v['name']=='v1alpha1' and v['served'] for v in c['spec']['versions']),'Unexpected native MCP API schema'
  break
 assert time.monotonic()<end,'Native MCP component/API/current owned workload not ready within bounded wait'
 time.sleep(5)
print('PASS Native MCP operator/API prerequisites; no secure MCPServer or endpoint qualification claimed')
PY
