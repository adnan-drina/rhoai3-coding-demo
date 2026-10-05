#!/usr/bin/env bash
# Read-only native readiness; persona proxy and browser checks are separate.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - <<'PY'
import json,subprocess

def get(kind,name=None,ns=None):
 args=['oc','--request-timeout=10s','get',kind]+([name] if name else [])+(['-n',ns] if ns else [])+['-o','json']
 p=subprocess.run(args,capture_output=True,text=True,timeout=15);assert p.returncode==0,'Native component read failed';return json.loads(p.stdout)
app=get('application','010-console-observability','openshift-gitops');s=app['status'];source=app['spec']['source'];o=s.get('operationState',{});result=o.get('syncResult',{})
assert len(source['targetRevision'])==40 and s['sync']['status']=='Synced' and s['sync']['revision']==source['targetRevision'] and s['health']['status']=='Healthy' and o.get('phase')=='Succeeded' and result.get('revision')==source['targetRevision'] and result.get('source',{}).get('path')==source['path'],'Console revision is not reconciled'
x=get('uiplugins.observability.openshift.io','monitoring');assert x['spec']['type']=='Monitoring' and x['spec']['monitoring']['perses']['enabled'] is True,'Native Perses UI disabled'
assert x['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith('010-console-observability:'),'UIPlugin tracking differs'
assert 'monitoring-plugin' in get('console.operator.openshift.io','cluster')['spec'].get('plugins',[]),'Monitoring plugin unregistered'
ns='openshift-cluster-observability-operator'
servers=[p for p in get('perses',ns=ns)['items'] if any(o.get('uid')==x['metadata']['uid'] for o in p['metadata'].get('ownerReferences',[]))]
assert len(servers)==1,'Expected one console-owned Perses'
p=servers[0];assert any(c['type']=='Available' and c['status']=='True' for c in p.get('status',{}).get('conditions',[])),'Console Perses unavailable'
deployments=get('deployments',ns=ns)['items']
owned=[d for d in deployments if any(o.get('uid')==x['metadata']['uid'] for o in d['metadata'].get('ownerReferences',[]))]
assert owned,'Native console deployment absent'
for d in owned:
 n=d['spec'].get('replicas',1);status=d.get('status',{});assert n>0 and status.get('observedGeneration')==d['metadata']['generation'] and status.get('updatedReplicas')==n and status.get('readyReplicas')==n and status.get('availableReplicas')==n,'Native console deployment stale or unavailable'
owned=[d for d in get('statefulsets',ns=ns)['items'] if any(o.get('uid')==p['metadata']['uid'] for o in d['metadata'].get('ownerReferences',[]))]
assert len(owned)==1,'Expected one native Perses StatefulSet'
d=owned[0];n=d['spec'].get('replicas',1);status=d.get('status',{})
assert n>0 and status.get('observedGeneration')==d['metadata']['generation'] and status.get('updatedReplicas')==n and status.get('readyReplicas')==n and status.get('currentRevision')==status.get('updateRevision') and status.get('currentRevision'),'Native Perses StatefulSet stale or unavailable'
print('PASS Native console/Perses readiness; datasource persona permissions and user browser checks are separate')
PY
