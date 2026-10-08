#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT}"
load_env
check_oc_logged_in
export MCP_ROOT="$ROOT"
[[ "${RHOAI_MCP_GATEWAY_EXPECTED_REVISION:-}" =~ ^[0-9a-f]{40}$ ]] || { echo 'Supply RHOAI_MCP_GATEWAY_EXPECTED_REVISION as the reviewed published full SHA.' >&2; exit 1; }
export RHOAI_MCP_GATEWAY_EXPECTED_REVISION
python3 - <<'PY'
import json,os,subprocess
def get(kind,name,ns='mcp-gateway-system'):
 return json.loads(subprocess.check_output(['oc','--request-timeout=10s','get',kind,name,'-n',ns,'-o','json'],stderr=subprocess.PIPE,timeout=20))
pin=json.load(open(os.environ['MCP_ROOT']+'/gitops/stages/040-governed-models-as-a-service/mcp-gateway-platform/source-pins.json'))
a=get('application','mcp-gateway-platform','openshift-gitops');s=a['spec'];st=a['status'];op=st.get('operationState',{});source=op.get('syncResult',{}).get('source',{})
assert not a['metadata'].get('deletionTimestamp') and not a['metadata'].get('ownerReferences') and not s.get('sources')
assert s['project']=='rhoai-demo' and s['source']['repoURL']=='https://github.com/adnan-drina/rhoai3-coding-demo.git' and s['source']['path']=='gitops/stages/040-governed-models-as-a-service/mcp-gateway-platform'
assert s['destination']=={'server':'https://kubernetes.default.svc','namespace':'mcp-gateway-system'}
rev=os.environ['RHOAI_MCP_GATEWAY_EXPECTED_REVISION'];assert s['source']['targetRevision']==rev and st['sync']['status']=='Synced' and st['sync']['revision']==rev and op.get('phase')=='Succeeded' and op['syncResult']['revision']==rev and source.get('path')==s['source']['path'] and source.get('repoURL')==s['source']['repoURL'] and source.get('targetRevision')==rev
sub=get('subscription','mcp-gateway','openshift-operators');assert not sub['metadata'].get('deletionTimestamp') and not sub['metadata'].get('ownerReferences') and sub['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id')=='mcp-gateway-platform:operators.coreos.com/Subscription:openshift-operators/mcp-gateway'
assert sub['spec']['name']=='mcp-gateway' and sub['spec']['source']=='redhat-operators' and sub['spec']['sourceNamespace']=='openshift-marketplace' and sub['spec']['startingCSV']==pin['csv'] and sub['spec']['channel']=='preview' and sub['spec']['installPlanApproval']=='Manual' and sub['status']['installedCSV']==pin['csv']
csv=get('csv',pin['csv'],'openshift-operators');assert csv['status']['phase']=='Succeeded' and csv['spec']['version']=='0.7.1' and any(m['type']=='AllNamespaces' and m['supported'] for m in csv['spec']['installModes'])
for deployment in csv['spec']['install']['spec']['deployments']:
 d=get('deployment',deployment['name'],'openshift-operators');m=d['metadata'];x=d['status'];n=d['spec'].get('replicas',1)
 assert any(o.get('uid')==csv['metadata']['uid'] and o.get('kind')=='ClusterServiceVersion' for o in m.get('ownerReferences',[])) and not m.get('deletionTimestamp')
 assert pin['operator'] in [c['image'] for c in d['spec']['template']['spec']['containers']]
 assert n>0 and x.get('observedGeneration')==m['generation'] and all(x.get(k,0)==n for k in ['replicas','updatedReplicas','readyReplicas','availableReplicas'])
q=get('resourcequota','mcp-private-boundary');assert all(q['spec']['hard'].get(k)=='0' and q['status']['hard'].get(k)=='0' for k in ['services.loadbalancers','services.nodeports','count/routes.route.openshift.io'])
print('PASS Exact native MCP Gateway operator primitive and private quota boundary; shared Gateway integration NOT qualified')
PY
