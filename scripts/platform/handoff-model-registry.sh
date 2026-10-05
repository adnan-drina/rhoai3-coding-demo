#!/usr/bin/env bash
# One-time immutable f38 protect/omit bridge; never a generic uninstall path.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
phase="${1:-}";revision="${2:-}";evidence="${3:-}"
[[ "$phase" == protect || "$phase" == omit ]] && [[ -n "$revision" && -n "$evidence" ]] || { echo 'Usage: handoff-model-registry.sh protect|omit PUBLISHED_BRANCH PRIVATE_EVIDENCE_DIR' >&2; exit 1; }
sha=$(git ls-remote "${GIT_REPO_URL:?}" "$revision" "refs/heads/$revision" | awk '{print $1}' | sort -u)
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$sha" == "$(git -C "$ROOT_DIR" rev-parse HEAD)" ]] || { echo 'ERROR: reviewed checkout must match the published branch.' >&2; exit 1; }
[[ -z $(git -C "$ROOT_DIR" status --porcelain -- gitops/stages/030-private-model-serving scripts/platform/handoff-model-registry.sh scripts/shared) ]] || { echo 'ERROR: publish the complete reviewed handoff source first.' >&2; exit 1; }
mkdir -p "$evidence";chmod 700 "$evidence"
export HANDOFF_PHASE="$phase" HANDOFF_SHA="$sha" HANDOFF_EVIDENCE="$evidence" HANDOFF_ROOT="$ROOT_DIR"
python3 - <<'PY'
import hashlib,json,os,ssl,subprocess,time,urllib.request
from pathlib import Path
phase=os.environ['HANDOFF_PHASE'];sha=os.environ['HANDOFF_SHA'];directory=Path(os.environ['HANDOFF_EVIDENCE']);appname='010-openshift-ai-platform-foundation';f38='f38d84c072ee18c38fb21072a6442a1b07d468eb';prefix='gitops/stages/030-private-model-serving/migration/foundation-'
ids=[('namespace','rhoai-model-registries',None),('modelregistries.modelregistry.opendatahub.io','demo-registry','rhoai-model-registries'),('rolebinding','demo-registry-rhods-admins','rhoai-model-registries'),('rolebinding','demo-registry-rhoai-developers','rhoai-model-registries')]
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
 result={'resources':{},'buckets':{},'operators':{}}
 for kind,name,ns in ids+[('pvc','demo-registry-postgres-storage','rhoai-model-registries'),('mlflows.mlflow.opendatahub.io','mlflow',None),('statefulset','mlflow-postgresql','redhat-ods-applications'),('pvc','mlflow-postgresql','redhat-ods-applications'),('secret','mlflow-db-credentials','redhat-ods-applications'),('secret','demo-registry-postgres-credentials','rhoai-model-registries')]:
  # Secret existence/identity only; credential payload never requested.
  if kind=='secret':
   text=oc(['get',kind,name,'-n',ns,'-o','jsonpath={.metadata.uid}']);assert text,'Retained database credentials missing';result['resources'][kind+'/'+name]={'uid':text}
   if name=='demo-registry-postgres-credentials':
    owner=oc(['get',kind,name,'-n',ns,'-o','jsonpath={.metadata.ownerReferences[?(@.controller==true)].uid}']);assert owner==get('modelregistries.modelregistry.opendatahub.io','demo-registry',ns)['metadata']['uid'],'Registry credential has a foreign owner';result['resources'][kind+'/'+name]['controllerUID']=owner
   continue
  x=get(kind,name,ns);assert not x['metadata'].get('deletionTimestamp'),'Retained data resource terminating'
  if kind=='pvc':assert x.get('status',{}).get('phase')=='Bound','Retained PVC not Bound'
  result['resources'][kind+'/'+name]={'uid':x['metadata']['uid'],'owners':x['metadata'].get('ownerReferences',[])}
  if kind.startswith('modelregistries'):result['registrySpec']=x['spec']
 for ns,name in [('demo-sandbox','demo-sandbox-bucket'),('redhat-ods-applications','rhoai-mlflow-artifacts')]:
  x=get('objectbucketclaim',name,ns);assert x['status']['phase']=='Bound','Existing bucket absent/unbound: naming review forbids recreation'
  cm=get('configmap',name,ns);result['buckets'][ns+'/'+name]={'uid':x['metadata']['uid'],'objectBucket':x['spec']['objectBucketName'],'intent':{k:x['spec'].get(k) for k in ['bucketName','generateBucketName','storageClassName']},'actualBucket':cm['data']['BUCKET_NAME']}
 for ns,name in [('redhat-ods-operator','rhods-operator'),('openshift-storage','odf-operator'),('openshift-cluster-observability-operator','cluster-observability-operator'),('openshift-opentelemetry-operator','opentelemetry-product'),('openshift-tempo-operator','tempo-product')]:
  x=get('subscription',name,ns);result['operators'][name]={'uid':x['metadata']['uid'],'csv':x['status'].get('installedCSV'),'installPlan':x['status'].get('installPlanRef',{}).get('name')}
 result['plugins']=get('console.operator.openshift.io','cluster')['spec'].get('plugins',[])
 dsc=get('datasciencecluster','default-dsc');assert dsc['status'].get('observedGeneration')==dsc['metadata']['generation'] and any(c.get('type')=='Ready' and c.get('status')=='True' for c in dsc['status'].get('conditions',[])),'Core DSC is not current/Ready'
 result['retainedComponents']={k:dsc['spec']['components'][k]['managementState'] for k in ['modelregistry','mlflowoperator']};assert all(v=='Managed' for v in result['retainedComponents'].values()),'Retained core component removed'
 mr=get('modelregistries.modelregistry.opendatahub.io','demo-registry','rhoai-model-registries')
 expected=json.loads(subprocess.check_output(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_file(ARGV[0])["spec"])',os.environ['HANDOFF_ROOT']+'/gitops/stages/030-private-model-serving/base/model-discovery/registry/modelregistry-demo.yaml'],text=True))
 assert mr['spec']==expected,'Registry differs from the complete reviewed original native spec'
 claim=get('pvc','demo-registry-postgres-storage','rhoai-model-registries')
 assert any(o.get('uid')==mr['metadata']['uid'] and o.get('controller') for o in claim['metadata'].get('ownerReferences',[])),'Registry database has a foreign owner'
 assert mr['spec'].get('postgres',{}).get('generateDeployment') is True and mr['spec']['postgres'].get('sslMode')=='disable' and mr['spec']['kubeRBACProxy'].get('serviceRoute')=='enabled','Registry differs from reviewed native demo configuration'
 for namespace,name in [('demo-sandbox','demo-sandbox-bucket'),('redhat-ods-applications','rhoai-mlflow-artifacts')]:
  bucket=get('objectbucketclaim',name,namespace)
  assert bucket['spec'].get('storageClassName')=='openshift-storage.noobaa.io','Unreviewed existing bucket storage intent'
  assert bucket['spec'].get('generateBucketName')=='demo-sandbox' if name=='demo-sandbox-bucket' else bucket['spec'].get('bucketName')=='rhoai-mlflow-artifacts','Unreviewed existing bucket naming intent'
 mlflow=get('mlflows.mlflow.opendatahub.io','mlflow');assert any(c.get('type')=='Available' and c.get('status')=='True' for c in mlflow['status'].get('conditions',[])),'Retained MLflow unavailable'
 registry=get('modelregistries.modelregistry.opendatahub.io','demo-registry','rhoai-model-registries');host=registry['status']['hosts'][0];token=oc(['whoami','-t']).strip();collections={}
 for collection in ['registered_models','model_versions','model_artifacts']:
  request=urllib.request.Request('https://'+host+'/api/model_registry/v1alpha3/'+collection,headers={'Authorization':'Bearer '+token,'Accept':'application/json'})
  try:
   with urllib.request.urlopen(request,context=ssl.create_default_context(),timeout=15) as response:data=json.load(response)
  except Exception:raise RuntimeError('Registry HTTPS preservation read failed') from None
  assert isinstance(data.get('items'),list) and not data.get('nextPageToken'),'Incomplete registry preservation baseline'
  collections[collection]=data
 result['registryContentSHA256']=hashlib.sha256(json.dumps(collections,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return result
app=get('application',appname,'openshift-gitops');spec=app['spec'];status=app['status'];source=spec['source']
assert spec['project']=='rhoai-demo' and source['repoURL']==os.environ['GIT_REPO_URL'] and not spec.get('sources') and not app['metadata'].get('ownerReferences'),'Unexpected foundation ownership/source'
assert spec['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected foundation destination'
already=source['path']==prefix+phase and source['targetRevision']==sha
if not already:
 assert status['sync']['status']=='Synced' and status['health']['status']=='Healthy' and status.get('operationState',{}).get('phase')=='Succeeded','Foundation must be exactly reconciled before bridge phase'
 assert status['sync']['revision']==source['targetRevision'] and status['operationState'].get('syncResult',{}).get('revision')==source['targetRevision'] and status['operationState'].get('syncResult',{}).get('source',{}).get('path')==source['path'],'Foundation desired and reconciled source/revision differ'
 if phase=='protect':assert source['path']=='gitops/stages/010-openshift-ai-platform-foundation/base' and source['targetRevision']==f38,'Protection only supports the reviewed immutable f38 prestate'
 else:assert source['path']==prefix+'protect' and source['targetRevision']==sha,'Omission requires the exact published protection revision'
if phase=='omit':
 for kind,name,ns in ids:
  x=get(kind,name,ns);assert {'Prune=false','Delete=false'}<=set(x['metadata']['annotations']['argocd.argoproj.io/sync-options'].split(',')),'Protection not applied'
for kind,name,ns in ids:assert tracking(get(kind,name,ns)).startswith(appname+':'),'Unexpected registry resource owner'
before=snapshot();baseline=directory/'baseline.json'
if phase=='protect' and not already:
 assert not baseline.exists(),'Preserve the previous evidence directory; choose a new one'
 baseline.write_text(json.dumps(before,indent=2))
else:assert before==json.loads(baseline.read_text()),'UID/data/bucket/operator state changed since protection'
# Preserve the current Application, modifying only source and exact delegation.
source['path']=prefix+phase;source['targetRevision']=sha
ignores=spec.setdefault('ignoreDifferences',[])
for group,kind,name,ns,paths in [('datasciencecluster.opendatahub.io','DataScienceCluster','default-dsc',None,['/spec/components/modelregistry']),('opendatahub.io','OdhDashboardConfig','odh-dashboard-config','redhat-ods-applications',['/spec/dashboardConfig/agentsCatalog','/spec/dashboardConfig/disableModelCatalog','/spec/dashboardConfig/disableModelRegistry'])]:
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
expected={('Namespace','rhoai-model-registries',''),('ModelRegistry','demo-registry','rhoai-model-registries'),('RoleBinding','demo-registry-rhods-admins','rhoai-model-registries'),('RoleBinding','demo-registry-rhoai-developers','rhoai-model-registries')}
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
