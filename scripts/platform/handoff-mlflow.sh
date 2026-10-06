#!/usr/bin/env bash
# One-time immutable core882 MLflow protect/omit bridge; never a generic uninstall path.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
phase="${1:-}";revision="${2:-}";evidence="${3:-}"
[[ "$phase" == protect || "$phase" == omit ]] && [[ -n "$revision" && -n "$evidence" ]] || { echo 'Usage: handoff-mlflow.sh protect|omit PUBLISHED_BRANCH PRIVATE_EVIDENCE_DIR' >&2; exit 1; }
sha=$(git ls-remote "${GIT_REPO_URL:?}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: reviewed checkout must match the published branch.' >&2; exit 1; }
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- gitops/stages/050-model-evaluation stages/050-model-evaluation scripts/platform/handoff-mlflow.sh scripts/shared) ]] || { echo 'ERROR: publish the complete reviewed handoff source first.' >&2; exit 1; }
mkdir -p "$evidence";chmod 700 "$evidence"
export HANDOFF_PHASE="$phase" HANDOFF_SHA="$sha" HANDOFF_EVIDENCE="$evidence" HANDOFF_ROOT="$ROOT_DIR"
python3 - <<'PY'
import hashlib,json,os,ssl,subprocess,time,urllib.request
from pathlib import Path
phase=os.environ['HANDOFF_PHASE'];sha=os.environ['HANDOFF_SHA'];directory=Path(os.environ['HANDOFF_EVIDENCE']);appname='010-openshift-ai-platform-foundation';core='882f327fb25dd047ca7144058b6cca46e693df3a';prefix='gitops/stages/050-model-evaluation/migration/foundation-'
ids=[('mlflows.mlflow.opendatahub.io','mlflow',None),('statefulset','mlflow-postgresql','redhat-ods-applications'),('pvc','mlflow-postgresql','redhat-ods-applications'),('service','mlflow-postgresql','redhat-ods-applications'),('networkpolicy','mlflow-postgresql','redhat-ods-applications'),('objectbucketclaim','rhoai-mlflow-artifacts','redhat-ods-applications'),('configmap','mlflow-service-ca','redhat-ods-applications')]
def oc(args,body=None):
 p=subprocess.run(['oc','--request-timeout=10s',*args],input=body,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,'Native handoff API operation failed'
 return p.stdout

def get(kind,name,ns=None):
 args=['get',kind,name,'-o','json']
 if ns:args+=['-n',ns]
 return json.loads(oc(args))
def tracking(x):return x['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','')
def snapshot():
 result={'resources':{},'operators':{}}
 for kind,name,ns in ids+[('modelregistries.modelregistry.opendatahub.io','demo-registry','rhoai-model-registries'),('pvc','demo-registry-postgres-storage','rhoai-model-registries'),('objectbucketclaim','demo-sandbox-bucket','demo-sandbox')]:
  x=get(kind,name,ns);assert not x['metadata'].get('deletionTimestamp'),'Retained resource terminating'
  if kind=='pvc':assert x['status']['phase']=='Bound','Retained PVC not Bound'
  if kind=='objectbucketclaim':assert x['status']['phase']=='Bound','Existing bucket not Bound'
  result['resources'][kind+'/'+name]={'uid':x['metadata']['uid'],'owners':x['metadata'].get('ownerReferences',[]),'spec':x.get('spec')}
 for name in ['mlflow-db-credentials','rhoai-mlflow-artifacts']:
  meta=json.loads(oc(['get','secret',name,'-n','redhat-ods-applications','-o','jsonpath={.metadata}']));assert not meta.get('deletionTimestamp'),'Retained credential terminating'
  result['resources']['secret/'+name]={'uid':meta['uid'],'owners':meta.get('ownerReferences',[])}
 for ns,name in [('redhat-ods-operator','rhods-operator'),('openshift-storage','odf-operator')]:
  x=get('subscription',name,ns);result['operators'][name]={'uid':x['metadata']['uid'],'csv':x['status'].get('installedCSV'),'installPlan':x['status'].get('installPlanRef',{}).get('name')}
 dsc=get('datasciencecluster','default-dsc');assert dsc['spec']['components']['mlflowoperator']['managementState']=='Managed','Retained MLflow component removed'
 mlflow=get('mlflows.mlflow.opendatahub.io','mlflow');assert any(c.get('type')=='Available' and c.get('status')=='True' for c in mlflow['status']['conditions']),'Retained MLflow unavailable'
 expected=json.loads(subprocess.check_output(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_file(ARGV[0])["spec"])',os.environ['HANDOFF_ROOT']+'/gitops/stages/050-model-evaluation/base/mlflow/mlflow.yaml'],text=True))
 assert mlflow['spec']==expected,'MLflow full native spec differs from reviewed receiving configuration'
 import importlib.util
 path=Path(os.environ['HANDOFF_ROOT'])/'stages/050-model-evaluation/service-api.py';module=importlib.util.spec_from_file_location('service_api',path);api=importlib.util.module_from_spec(module);module.loader.exec_module(api)
 token=oc(['whoami','-t']).strip();ca=get('configmap','mlflow-service-ca','redhat-ods-applications')['data']['service-ca.crt'];records={}
 # Discover real native workspaces; the server namespace is not necessarily a workspace.
 with api.api('mlflow','redhat-ods-applications',mlflow['status']['address']['url'],ca,token,'demo-sandbox') as request:
  discovery=request('api/3.0/mlflow/workspaces')
 workspaces=discovery.get('workspaces');assert isinstance(workspaces,list) and 0<len(workspaces)<=100 and not discovery.get('next_page_token'),'Incomplete native workspace discovery'
 names=sorted(w['name'] for w in workspaces);assert 'demo-sandbox' in names and len(names)==len(set(names)),'Expected unique sandbox workspace missing'
 for workspace in names:
  with api.api('mlflow','redhat-ods-applications',mlflow['status']['address']['url'],ca,token,workspace) as request:
   exp=request('api/2.0/mlflow/experiments/search',{'max_results':1000,'view_type':'ALL'});assert not exp.get('next_page_token'),'Incomplete experiment baseline';experiments=exp.get('experiments',[]);runs={};artifacts={}
   if experiments:
    runs=request('api/2.0/mlflow/runs/search',{'experiment_ids':[e['experiment_id'] for e in experiments],'max_results':1000,'run_view_type':'ALL'});assert not runs.get('next_page_token'),'Incomplete run baseline'
    for run in runs.get('runs',[]):
     runid=run['info']['run_id'];listing=request('api/2.0/mlflow/artifacts/list?run_id='+runid);assert not listing.get('next_page_token'),'Incomplete artifact baseline';artifacts[runid]=listing
   records[workspace]={'experiments':exp,'runs':runs,'artifactMetadata':artifacts}
 result['mlflowRecords']=records
 return result
app=get('application',appname,'openshift-gitops');spec=app['spec'];status=app['status'];source=spec['source']
assert spec['project']=='rhoai-demo' and source['repoURL']==os.environ['GIT_REPO_URL'] and not spec.get('sources') and not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp'),'Unexpected foundation ownership/source'
assert spec['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected foundation destination'
already=source['path']==prefix+phase and source['targetRevision']==sha
if not already:
 assert status['sync']['status']=='Synced' and status['health']['status']=='Healthy' and status.get('operationState',{}).get('phase')=='Succeeded','Foundation must be exactly reconciled before bridge phase'
 assert status['sync']['revision']==source['targetRevision'] and status['operationState'].get('syncResult',{}).get('revision')==source['targetRevision'] and status['operationState'].get('syncResult',{}).get('source',{}).get('path')==source['path'],'Foundation desired and reconciled source/revision differ'
 if phase=='protect':assert source['path']=='gitops/stages/030-private-model-serving/migration/foundation-omit' and source['targetRevision']==core,'Protection only supports the reviewed immutable core882 prestate'
 else:assert source['path']==prefix+'protect' and source['targetRevision']==sha,'Omission requires the exact published protection revision'
if phase=='omit':
 for kind,name,ns in ids:
  x=get(kind,name,ns);assert {'Prune=false','Delete=false'}<=set(x['metadata']['annotations']['argocd.argoproj.io/sync-options'].split(',')),'Protection not applied'
for kind,name,ns in ids:assert tracking(get(kind,name,ns)).startswith(appname+':'),'Unexpected MLflow resource owner'
before=snapshot();baseline=directory/'baseline.json'
if phase=='protect' and not already:
 assert not baseline.exists(),'Preserve the previous evidence directory; choose a new one'
 baseline.write_text(json.dumps(before,indent=2))
else:assert before==json.loads(baseline.read_text()),'UID/data/bucket/operator state changed since protection'
# Preserve the current Application, modifying only source and exact delegation.
source['path']=prefix+phase;source['targetRevision']=sha
ignores=spec.setdefault('ignoreDifferences',[])
for group,kind,name,ns,paths in [('datasciencecluster.opendatahub.io','DataScienceCluster','default-dsc',None,['/spec/components/mlflowoperator','/spec/components/trustyai']),('','Namespace','demo-sandbox',None,['/metadata/labels/evalhub.trustyai.opendatahub.io~1tenant'])]:
 entry=next((i for i in ignores if i.get('group')==group and i.get('kind')==kind and i.get('name')==name and (ns is None or i.get('namespace')==ns)),None)
 if entry is None:
  entry={'group':group,'kind':kind,'name':name,'jsonPointers':[]};ignores.append(entry)
  if ns:entry['namespace']=ns
 entry['jsonPointers']=sorted(set(entry.get('jsonPointers',[])+paths))
assert 'RespectIgnoreDifferences=true' in spec['syncPolicy']['syncOptions'],'Delegation must be respected'
metadata={k:v for k,v in app['metadata'].items() if k in ['name','namespace','labels','annotations','resourceVersion']}
metadata.get('annotations',{}).pop('kubectl.kubernetes.io/last-applied-configuration',None)
body=json.dumps({'apiVersion':app['apiVersion'],'kind':'Application','metadata':metadata,'spec':spec})
if not already:oc(['apply','-f','-'],body) # First modifying action: core Application only.
expected={('MLflow','mlflow',''),('StatefulSet','mlflow-postgresql','redhat-ods-applications'),('PersistentVolumeClaim','mlflow-postgresql','redhat-ods-applications'),('Service','mlflow-postgresql','redhat-ods-applications'),('NetworkPolicy','mlflow-postgresql','redhat-ods-applications'),('ObjectBucketClaim','rhoai-mlflow-artifacts','redhat-ods-applications'),('ConfigMap','mlflow-service-ca','redhat-ods-applications')}
for _ in range(120):
 live=get('application',appname,'openshift-gitops');s=live.get('status',{});operation=s.get('operationState',{})
 if operation.get('phase')=='Failed':raise RuntimeError('Native bridge sync failed; preserve resources and diagnose')
 assert live['spec']['source']['path']==prefix+phase and live['spec']['source']['targetRevision']==sha,'Foundation source changed during handoff'
 if operation.get('phase')=='Succeeded' and operation.get('syncResult',{}).get('revision')==sha and operation.get('syncResult',{}).get('source',{}).get('path')==prefix+phase and s.get('sync',{}).get('revision')==sha and s.get('health',{}).get('status')=='Healthy':
  drift=[r for r in s.get('resources',[]) if r.get('status')!='Synced']
  if phase=='protect':assert not drift,'Unexpected protection drift'
  else:assert {(r['kind'],r['name'],r.get('namespace','')) for r in drift}<=expected and all(r.get('requiresPruning') for r in drift),'Unexpected omitted-resource drift'
  for kind,name,ns in ids:
   resource=get(kind,name,ns);assert {'Prune=false','Delete=false'}<=set(resource['metadata'].get('annotations',{}).get('argocd.argoproj.io/sync-options','').split(',')),'Retention protection was not reconciled'
  after=snapshot();assert after==before,'Retained UID/data/bucket/operator configuration changed'
  (directory/(phase+'-after.json')).write_text(json.dumps(after,indent=2));print('PASS '+phase+' bridge: native state, data and existing buckets preserved');break
 time.sleep(5)
else:raise RuntimeError('Bounded bridge reconciliation timed out')
PY
