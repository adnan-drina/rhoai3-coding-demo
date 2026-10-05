#!/usr/bin/env bash
# Register only the two pinned local models; never archive unrelated records.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - "$REPO_ROOT" <<'PY'
import json,os,re,ssl,subprocess,sys,urllib.error,urllib.parse,urllib.request
from pathlib import Path
root=Path(sys.argv[1]);ns='models-as-a-service';registry='demo-registry'
def oc(args,payload=None):
 r=subprocess.run(['oc','--request-timeout=10s']+args,input=json.dumps(payload) if payload else None,capture_output=True,text=True,timeout=15)
 if r.returncode:raise RuntimeError('Native registry/model API operation failed')
 return json.loads(r.stdout) if r.stdout.strip() else None
def get(kind,name,namespace):return oc(['get',kind,name,'-n',namespace,'-o','json'])
try:
 app=get('applications.argoproj.io','040-governed-models-as-a-service','openshift-gitops');s=app['status'];spec=app['spec'];result=s.get('operationState',{}).get('syncResult',{})
 source=spec['source'];revision=os.environ.get('RHOAI_STAGE040_EXPECTED_REVISION') or subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
 assert re.fullmatch(r'[0-9a-f]{40}',revision) and source['targetRevision']==revision and source['repoURL']==os.environ['GIT_REPO_URL'] and source['path']=='gitops/stages/040-governed-models-as-a-service/base','Reviewed immutable source differs'
 assert spec['project']=='rhoai-demo' and spec['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'} and not spec.get('sources') and not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp'),'Application ownership differs'
 assert s['sync']['status']=='Synced' and s['sync']['revision']==spec['source']['targetRevision'] and s['health']['status']=='Healthy' and s.get('operationState',{}).get('phase')=='Succeeded' and result.get('revision')==spec['source']['targetRevision'] and result.get('source',{}).get('path')==spec['source']['path'],'Stage040 must reconcile before model registration'
 mr=get('modelregistries.modelregistry.opendatahub.io',registry,'rhoai-model-registries');base='https://'+mr['status']['hosts'][0]+'/api/model_registry/v1alpha3'
 token=subprocess.run(['oc','whoami','-t'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):return None
 opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
 def api(path,body=None):
  request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  try:
   with opener.open(request,timeout=20) as response:return json.load(response)
  except Exception:raise RuntimeError('Authenticated CA-verified registry request failed') from None
 def items(path):
  values=[];cursor=None
  for _ in range(100):
   response=api(path+('?' + urllib.parse.urlencode({'nextPageToken':cursor}) if cursor else ''));values+=response.get('items',[]);cursor=response.get('nextPageToken')
   if not cursor:return values
  raise RuntimeError('Registry pagination exceeded bounded limit')
 for file,title in [('qwen27b-llminferenceservice.yaml','Qwen3.6-27B-FP8'),('qwen38-27b-int4-llminferenceservice.yaml','Qwen3.8-27B-INT4')]:
  path=root/'gitops/stages/040-governed-models-as-a-service/base/local-models/base'/file
  expected=json.loads(subprocess.run(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(path)],capture_output=True,text=True,check=True).stdout)
  name=expected['metadata']['name'];uri=expected['spec']['model']['uri'];revision=uri.rsplit(':',1)[1];assert len(revision)==40,'Model source must be immutable'
  llmi=get('llminferenceservices.serving.kserve.io',name,ns)
  assert llmi['spec']['model']['uri']==uri and llmi['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith('040-governed-models-as-a-service:'),'Model source/ownership differs'
  assert isinstance(llmi['metadata'].get('generation'),int) and llmi.get('status',{}).get('observedGeneration')==llmi['metadata']['generation'],'Model readiness is stale'
  assert any(c.get('type')=='Ready' and c.get('status')=='True' for c in llmi.get('status',{}).get('conditions',[])),'Model must be ready before registry publication'
  matches=[x for x in items('/registered_models') if x['name']==title];assert len(matches)<=1,'Ambiguous registered model name'
  model=matches[0] if matches else api('/registered_models',{'name':title,'owner':'rhoai3-coding-demo','description':'Pinned RedHatAI model artifact used by the project. Runtime and GPU compatibility are qualified separately; this is not a Red Hat validated-model claim.'})
  model_id=model['id'];version_name='source-'+revision
  versions=[x for x in items('/registered_models/'+model_id+'/versions') if x['name']==version_name];assert len(versions)<=1,'Ambiguous registered model version'
  version=versions[0] if versions else api('/model_versions',{'name':version_name,'registeredModelId':model_id,'description':'Immutable source '+revision})
  version_id=version['id'];artifacts=items('/model_versions/'+version_id+'/artifacts')
  assert not artifacts or (len(artifacts)==1 and artifacts[0].get('uri')==uri),'Existing version artifact differs; no overwrite'
  if not artifacts:api('/model_versions/'+version_id+'/artifacts',{'name':'model-source','uri':uri,'artifactType':'model-artifact','modelFormatName':'vLLM','modelFormatVersion':'1'})
  labels=dict(llmi['metadata'].get('labels',{}));labels.update({'modelregistry.opendatahub.io/name':registry,'modelregistry.opendatahub.io/registered-model-id':model_id,'modelregistry.opendatahub.io/model-version-id':version_id})
  patch=[{'op':'test','path':'/metadata/resourceVersion','value':llmi['metadata']['resourceVersion']},{'op':'add','path':'/metadata/labels','value':labels}]
  oc(['patch','llminferenceservices.serving.kserve.io',name,'-n',ns,'--type=json','--patch-file=/dev/stdin','-o','json'],patch)
  print('PASS Registered pinned source and native deployment linkage: '+name)
except (RuntimeError,AssertionError,KeyError,ValueError,subprocess.SubprocessError) as error:
 raise SystemExit('ERROR: registry publication stopped ('+type(error).__name__+'); inspect native readiness/source ownership') from None
PY
