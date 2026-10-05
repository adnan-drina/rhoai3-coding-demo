#!/usr/bin/env bash
# Native serving/discovery infrastructure; no model deployment or metadata seed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - <<'PY'
import json,subprocess

def get(kind,name,ns=None):
 args=['oc','--request-timeout=10s','get',kind,name,'-o','json']
 if ns:args+=['-n',ns]
 p=subprocess.run(args,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,'Native prerequisite read failed'
 return json.loads(p.stdout)
app=get('application','030-private-model-serving','openshift-gitops');s=app['status'];revision=app['spec']['source']['targetRevision']
assert len(revision)==40 and s['sync']['revision']==revision and s['sync']['status']=='Synced' and s['health']['status']=='Healthy','Stage 030 exact revision is not Synced/Healthy'
operation=s.get('operationState',{});result=operation.get('syncResult',{})
assert operation.get('phase')=='Succeeded' and result.get('revision')==revision and result.get('source',{}).get('path')==app['spec']['source']['path'],'Stage 030 operation source/path is stale'
dsc=get('datasciencecluster','default-dsc');g=dsc['metadata']['generation'];status=dsc['status'];conditions={c['type']:c for c in status.get('conditions',[])}
assert status.get('observedGeneration')==g,'DSC generation is stale'
for t in ['Ready','KserveReady']:
 assert conditions.get(t,{}).get('status')=='True','Native DSC condition not ready: '+t
assert dsc['spec']['components']['kserve']['managementState']=='Managed','KServe is not Managed'
assert dsc['spec']['components']['modelregistry']['managementState']=='Managed','Model Registry is not Managed'
component=get('kserves.components.platform.opendatahub.io','default-kserve');cs=component['status'];cc={c['type']:c for c in cs.get('conditions',[])}
assert cs.get('observedGeneration')==component['metadata']['generation'],'Native KServe generation is stale'
for t in ['Ready','KServeReady','ModelControllerReady']:assert cc.get(t,{}).get('status')=='True','Native KServe condition not ready: '+t
p=subprocess.run(['oc','--request-timeout=10s','get','deployments','-n','redhat-ods-applications','-o','json'],capture_output=True,text=True,timeout=15);assert p.returncode==0,'Native serving workload read failed'
owned=[d for d in json.loads(p.stdout)['items'] if any(o.get('uid')==component['metadata']['uid'] and o.get('controller') for o in d['metadata'].get('ownerReferences',[]))]
assert owned,'Native KServe-owned deployments missing'
for d in owned:
 st=d['status'];n=d['spec'].get('replicas',1);assert st.get('observedGeneration')==d['metadata']['generation'] and st.get('readyReplicas',0)>=n and st.get('updatedReplicas',0)>=n,'Native serving workload is not current'
print('PASS Native DSC/KServe conditions and current owned serving workloads')
for ns,name,size in [('openshift-monitoring','k8s','40Gi'),('openshift-user-workload-monitoring','user-workload','20Gi')]:
 p=get('prometheus.monitoring.coreos.com',name,ns);spec=p['spec'];claim=spec['storage']['volumeClaimTemplate']['spec']
 assert claim['storageClassName']=='gp3-csi' and claim['resources']['requests']['storage']==size,'Native monitoring persistence differs from reviewed intent'
 sts=get('statefulset','prometheus-'+name,ns);n=sts['spec'].get('replicas',1);st=sts['status']
 assert st.get('observedGeneration')==sts['metadata']['generation'] and st.get('readyReplicas',0)==n and st.get('updatedReplicas',0)==n and st.get('currentRevision')==st.get('updateRevision'),'Native Prometheus rollout is not current'
 for i in range(n):assert get('pvc','prometheus-'+name+'-db-prometheus-'+name+'-'+str(i),ns)['status']['phase']=='Bound','Monitoring PVC not Bound'
print('PASS Native persistent platform and user-workload monitoring')
PY
"$SCRIPT_DIR/validate-model-discovery.sh"
echo 'Infrastructure/API acceptance only. No models are deployed; actual persona/browser UI acceptance remains separate.'
