#!/usr/bin/env bash
# Read-only native readiness checks; functional admission/UI evidence is separate.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
mode="${1:---readiness}"
[[ "$mode" == --readiness || "$mode" == --functional ]] || { echo "Use --readiness or --functional (both read-only)." >&2; exit 1; }
python3 - "$mode" <<'PY'
import json,pathlib,subprocess,sys,time,urllib.request,socket,datetime
failed=0
def get(kind,name='',ns=''):
 cmd=['oc','--request-timeout=10s','get',kind]
 if name:cmd.append(name)
 if ns:cmd+=['-n',ns]
 p=subprocess.run(cmd+['-o','json'],capture_output=True,text=True,timeout=15)
 if p.returncode:raise RuntimeError('API read failed: '+kind)
 return json.loads(p.stdout)
def check(label,fn):
 global failed
 try:assert fn();print('PASS '+label)
 except Exception:failed+=1;print('FAIL '+label)
def instant(value):return datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
def cond(x,t):
 return any(c.get('type')==t and c.get('status')=='True' for c in x.get('status',{}).get('conditions',[]))
def freshcond(x,t):
 return any(c.get('type')==t and c.get('status')=='True' and c.get('observedGeneration')==x['metadata'].get('generation') for c in x.get('status',{}).get('conditions',[]))
def current(x):return isinstance(x['metadata'].get('generation'),int) and x.get('status',{}).get('observedGeneration')==x['metadata']['generation']
app=get('applications.argoproj.io','020-gpu-infrastructure-private-ai','openshift-gitops')
check('Application exact desired revision Synced/Healthy',lambda:app['status']['sync']['status']=='Synced' and app['status']['health']['status']=='Healthy' and app['status']['sync']['revision']==app['spec']['source']['targetRevision'] and len(app['spec']['source']['targetRevision'])==40)
for ns,name,csv in [('openshift-nfd','nfd','nfd.4.22.0-202609212027'),('nvidia-gpu-operator','gpu-operator-certified','gpu-operator-certified.v26.7.1'),('openshift-kueue-operator','kueue-operator','kueue-operator.v1.4.2')]:
 def operator(ns=ns,name=name,csv=csv):
  s=get('subscription',name,ns);c=get('csv',csv,ns)
  return s['spec']['installPlanApproval']=='Manual' and s['status'].get('installedCSV')==csv and c['status']['phase']=='Succeeded'
 check(name+' exact reviewed CSV Succeeded',operator)
nfd=get('nodefeaturediscovery','nfd-instance','openshift-nfd')
def native_workload(kind,name,ns,owner):
 x=get(kind,name,ns);assert any(o.get('uid')==owner for o in x['metadata'].get('ownerReferences',[]));assert current(x)
 if kind=='daemonset':assert x['status'].get('desiredNumberScheduled',0)>0 and x['status'].get('numberReady')==x['status']['desiredNumberScheduled'] and x['status'].get('updatedNumberScheduled')==x['status']['desiredNumberScheduled']
 else:assert x['spec'].get('replicas',1)>0 and x['status'].get('readyReplicas')==x['spec'].get('replicas',1) and x['status'].get('updatedReplicas')==x['spec'].get('replicas',1) and x['status'].get('availableReplicas')==x['spec'].get('replicas',1)
 return True
check('NFD Available with fresh native worker/master',lambda:cond(nfd,'Available') and native_workload('daemonset','nfd-worker','openshift-nfd',nfd['metadata']['uid']) and native_workload('deployment','nfd-master','openshift-nfd',nfd['metadata']['uid']))
cp=get('clusterpolicy','gpu-cluster-policy')
check('ClusterPolicy native ready',lambda:cp['status'].get('state')=='ready')
def owned_ds(name):
 x=get('daemonset',name,'nvidia-gpu-operator');assert any(o.get('uid')==cp['metadata']['uid'] and o.get('controller') for o in x['metadata'].get('ownerReferences',[]));assert current(x) and x['status'].get('desiredNumberScheduled')==2 and x['status'].get('numberReady')==2 and x['status'].get('updatedNumberScheduled')==2;return x
for name in ['nvidia-operator-validator','nvidia-dcgm-exporter']:
 check(name+' native owner/current readiness',lambda n=name:bool(owned_ds(n)))
ms=get('machinesets','','openshift-machine-api')['items'];gpu=[x for x in ms if x['metadata'].get('labels',{}).get('cluster-api/accelerator')=='nvidia-gpu']
check('One reviewed MachineSet with two Ready exclusive L40S workers',lambda:len(gpu)==1 and gpu[0]['spec']['replicas']==2 and gpu[0]['status'].get('readyReplicas')==2 and gpu[0]['spec']['template']['spec']['providerSpec']['value']['instanceType']=='g6e.2xlarge' and current(gpu[0]))
nodes=get('nodes')['items'];gn=[x for x in nodes if x['metadata'].get('labels',{}).get('nvidia.com/gpu.present')=='true']
check('Two Ready nodes each advertise one full L40S GPU and intended taint',lambda:len(gn)==2 and all(cond(x,'Ready') and x['status']['allocatable'].get('nvidia.com/gpu')=='1' and 'L40S' in x['metadata']['labels'].get('nvidia.com/gpu.product','') and any(t['key']=='nvidia-gpu-only' and t['effect']=='NoSchedule' for t in x['spec'].get('taints',[])) for x in gn))
def driver_ready(node):
 version=node['metadata']['labels'].get('feature.node.kubernetes.io/system-os_release.OSTREE_VERSION')
 assert version
 candidates=[d for d in get('daemonsets','','nvidia-gpu-operator')['items'] if d['metadata'].get('labels',{}).get('openshift.driver-toolkit.rhcos')==version and any(c['name']=='nvidia-driver-ctr' for c in d['spec']['template']['spec']['containers']) and any(o.get('uid')==cp['metadata']['uid'] and o.get('controller') for o in d['metadata'].get('ownerReferences',[]))]
 assert len(candidates)==1
 d=candidates[0];assert current(d) and d['status'].get('numberReady')==d['status'].get('desiredNumberScheduled') and d['status'].get('updatedNumberScheduled')==d['status'].get('desiredNumberScheduled')
 return any(p['spec'].get('nodeName')==node['metadata']['name'] and cond(p,'Ready') and any(o.get('uid')==d['metadata']['uid'] and o.get('controller') for o in p['metadata'].get('ownerReferences',[])) for p in get('pods','','nvidia-gpu-operator')['items'])
for index,node in enumerate(gn):check('GPU '+str(index+1)+' native Driver Toolkit/current driver',lambda n=node:driver_ready(n))
dsc=get('datasciencecluster','default-dsc')
check('Kueue delegated Unmanaged with autoCreateQueues=false',lambda:dsc['spec']['components']['kueue']['managementState']=='Unmanaged' and dsc['spec']['components']['kueue'].get('autoCreateQueues') is False and cond(dsc,'Ready') and current(dsc))
def kueue_ready():
 xs=get('kueues.kueue.openshift.io')['items'];assert len(xs)==1;k=xs[0]
 assert cond(k,'Available') and cond(k,'CertManagerAvailable') and not cond(k,'Degraded') and not cond(k,'Progressing')
 return native_workload('deployment','kueue-controller-manager','openshift-kueue-operator',k['metadata']['uid'])
check('Native Kueue Available with fresh owned controller',kueue_ready)
for suffix in ['cpu-default','gpu-shared','gpu-priority','gpu-reserved-demo']:
 check('ClusterQueue '+suffix+' Active',lambda s=suffix:freshcond(get('clusterqueue','cq-'+s),'Active'))
 check('Sandbox LocalQueue '+suffix+' Active',lambda s=suffix:freshcond(get('localqueue','lq-'+s,'demo-sandbox'),'Active'))
 check('HardwareProfile '+suffix+' queue identity',lambda s=suffix:get('hardwareprofile',s,'redhat-ods-applications')['spec']['scheduling']['kueue']['localQueueName']=='lq-'+s)
print('Shared/priority profiles retain zero GPU quota; they are not usable GPU self-service.')
print('Global profiles require matching LocalQueues in every consuming project.')
if sys.argv[1]=='--functional':
 pods=get('pods','','nvidia-gpu-operator')['items']
 def cuda(node):
  candidates=[p for p in pods if p['metadata'].get('labels',{}).get('app')=='nvidia-cuda-validator' and p['spec'].get('nodeName')==node and any(o.get('uid')==cp['metadata']['uid'] for o in p['metadata'].get('ownerReferences',[]))]
  assert candidates
  p=max(candidates,key=lambda x:x['metadata']['creationTimestamp'])
  ds=owned_ds('nvidia-operator-validator')
  revisions=[r for r in get('controllerrevisions','','nvidia-gpu-operator')['items'] if any(o.get('uid')==ds['metadata']['uid'] for o in r['metadata'].get('ownerReferences',[]))]
  assert revisions
  revision=max(revisions,key=lambda r:r['revision'])['metadata']['name'].rsplit('-',1)[1]
  currentpods=[v for v in pods if v['spec'].get('nodeName')==node and v['metadata'].get('labels',{}).get('controller-revision-hash')==revision and any(o.get('uid')==ds['metadata']['uid'] and o.get('controller') for o in v['metadata'].get('ownerReferences',[]))]
  assert len(currentpods)==1 and not currentpods[0]['metadata'].get('deletionTimestamp') and cond(currentpods[0],'Ready')
  runs=[i.get('state',{}).get('terminated',{}) for i in currentpods[0]['status'].get('initContainerStatuses',[]) if i['name']=='cuda-validation']
  assert len(runs)==1 and runs[0].get('exitCode')==0
  assert instant(runs[0]['startedAt']) <= instant(p['metadata']['creationTimestamp']) <= instant(runs[0]['finishedAt']) and p['status']['phase']=='Succeeded'
  init=[i for i in ds['spec']['template']['spec']['initContainers'] if i['name']=='cuda-validation'][0]
  assert not any(e.get('name')=='WITH_WORKLOAD' and str(e.get('value','')).lower()=='false' for e in init.get('env',[]))
  assert any(x['name']=='cuda-validation' and x.get('state',{}).get('terminated',{}).get('exitCode')==0 for x in p['status'].get('initContainerStatuses',[]))
  return True
 def metrics(node):
  ds=owned_ds('nvidia-dcgm-exporter')
  candidates=[p for p in pods if any(o.get('uid')==ds['metadata']['uid'] and o.get('controller') for o in p['metadata'].get('ownerReferences',[])) and not p['metadata'].get('deletionTimestamp') and p['metadata'].get('labels',{}).get('app')=='nvidia-dcgm-exporter' and p['spec'].get('nodeName')==node and cond(p,'Ready')]
  assert len(candidates)==1
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  proc=subprocess.Popen(['oc','--request-timeout=10s','port-forward','-n','nvidia-gpu-operator','pod/'+candidates[0]['metadata']['name'],str(port)+':9400','--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   for attempt in range(30):
    try:
     with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/metrics',timeout=3) as response:body=response.read(4*1024*1024).decode()
     assert 'DCGM_FI_DEV_GPU_UTIL{' in body and 'L40S' in body
     return True
    except OSError:time.sleep(1)
   return False
  finally:proc.terminate();proc.wait(timeout=10)
 for index,node in enumerate(gn):
  check('GPU '+str(index+1)+' native CUDA vectorAdd success',lambda n=node['metadata']['name']:cuda(n))
  check('GPU '+str(index+1)+' native DCGM metrics',lambda n=node['metadata']['name']:metrics(n))
 print('Read-only CUDA/DCGM checks do not prove queue admission or dashboard persona visibility. Follow the bounded admission procedure in OPERATIONS.')
else:print('READINESS ONLY: CUDA/DCGM, queue admission and dashboard persona visibility remain separate acceptance.')
sys.exit(1 if failed else 0)
PY
