#!/usr/bin/env bash
# Register the deployed local model and every prepared format alternate; never archive unrelated records.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - "$REPO_ROOT" <<'PY'
import json,os,re,ssl,subprocess,sys,urllib.error,urllib.parse,urllib.request
from pathlib import Path
root=Path(sys.argv[1]);ns='internal-models';registry='demo-registry'
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
 # Read the rendered models so an enabled format component (e.g. qwen38-fp8) registers its own artifact;
 # the registry title is the checkpoint repository name (Qwen3.8-27B-NVFP4 or Qwen3.8-27B-FP8).
 rendered=subprocess.run(['oc','kustomize',str(root/'gitops/stages/040-governed-models-as-a-service/base/local-models/base')],capture_output=True,text=True,check=True).stdout
 models={o['metadata']['name']:o for o in json.loads(subprocess.run(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_stream(STDIN.read).compact)'],input=rendered,capture_output=True,text=True,check=True).stdout) if o.get('kind')=='LLMInferenceService'}
 QUANT={'NVFP4':'NVFP4 (FP4 weights, FP8 attention)','FP8':'FP8 block-128','INT4':'INT4 W4A16'}
 def register(uri):
  """Registered model per checkpoint (title = repository name), version per immutable revision, one artifact."""
  title=uri.split('/')[-1].split(':')[0];revision=uri.rsplit(':',1)[1];assert len(revision)==40,'Model source must be immutable'
  quant=next((v for k,v in QUANT.items() if title.upper().endswith('-'+k)),'unquantized')
  matches=[x for x in items('/registered_models') if x['name']==title];assert len(matches)<=1,'Ambiguous registered model name'
  model=matches[0] if matches else api('/registered_models',{'name':title,'owner':'rhoai3-coding-demo','description':'Quantization: '+quant+'. Pinned model artifact used by the project ('+uri.split('://')[1].split(':')[0]+'). Runtime and GPU compatibility are qualified separately; this is not a Red Hat validated-model claim.'})
  version_name='source-'+revision
  versions=[x for x in items('/registered_models/'+model['id']+'/versions') if x['name']==version_name];assert len(versions)<=1,'Ambiguous registered model version'
  version=versions[0] if versions else api('/model_versions',{'name':version_name,'registeredModelId':model['id'],'description':'Quantization: '+quant+'. Immutable source '+revision})
  artifacts=items('/model_versions/'+version['id']+'/artifacts')
  assert not artifacts or (len(artifacts)==1 and artifacts[0].get('uri')==uri),'Existing version artifact differs; no overwrite'
  if not artifacts:api('/model_versions/'+version['id']+'/artifacts',{'name':'model-source','uri':uri,'artifactType':'model-artifact','modelFormatName':'vLLM','modelFormatVersion':'1'})
  return title,model['id'],version['id']
 active={}
 for name in ['qwen3-8-27b']:
  expected=models[name];uri=expected['spec']['model']['uri']
  llmi=get('llminferenceservices.serving.kserve.io',name,ns)
  assert llmi['spec']['model']['uri']==uri and llmi['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith('040-governed-models-as-a-service:'),'Model source/ownership differs'
  assert isinstance(llmi['metadata'].get('generation'),int) and llmi.get('status',{}).get('observedGeneration')==llmi['metadata']['generation'],'Model readiness is stale'
  parked=llmi['spec'].get('replicas')==0
  if not parked:assert any(c.get('type')=='Ready' and c.get('status')=='True' for c in llmi.get('status',{}).get('conditions',[])),'Active model must be ready before registry publication'
  title,model_id,version_id=register(uri);active[name]=uri
  existing=llmi['metadata'].get('labels',{}).get('modelregistry.opendatahub.io/registered-model-id')
  if existing and existing!=model_id:
   # Relink only for a format switch: the linked entry must be another checkpoint, never a same-name duplicate.
   linked=api('/registered_models/'+existing);assert linked.get('name')!=title,'Existing model registry identity differs; no reassignment'
   print('NOTE Format switch: deployment relinked from '+linked.get('name','?')+' to '+title)
  labels=dict(llmi['metadata'].get('labels',{}));labels.update({'modelregistry.opendatahub.io/name':registry,'modelregistry.opendatahub.io/registered-model-id':model_id,'modelregistry.opendatahub.io/model-version-id':version_id})
  patch=[{'op':'test','path':'/metadata/resourceVersion','value':llmi['metadata']['resourceVersion']},{'op':'add','path':'/metadata/labels','value':labels}]
  oc(['patch','llminferenceservices.serving.kserve.io',name,'-n',ns,'--type=json','--patch-file=/dev/stdin','-o','json'],patch)
  print(('PASS Registered pinned metadata; parked runtime not qualified: ' if parked else 'PASS Registered pinned source and native deployment linkage: ')+name+' -> '+title)
 # Prepared alternates: every format component under local-models/components registers its artifact
 # (no deployment linkage), so the registry lists each build that can be switched on.
 import shutil,tempfile
 lm=root/'gitops/stages/040-governed-models-as-a-service/base/local-models'
 for comp in sorted(x.name for x in (lm/'components').iterdir() if x.is_dir()):
  with tempfile.TemporaryDirectory() as tmp:
   shutil.copytree(lm,Path(tmp)/'local-models');k=Path(tmp)/'local-models/base/kustomization.yaml'
   k.write_text(k.read_text()+'\ncomponents:\n  - ../components/'+comp+'\n')
   alt=subprocess.run(['oc','kustomize',str(Path(tmp)/'local-models/base')],capture_output=True,text=True,check=True).stdout
  for o in json.loads(subprocess.run(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_stream(STDIN.read).compact)'],input=alt,capture_output=True,text=True,check=True).stdout):
   if o.get('kind')=='LLMInferenceService' and o['spec']['model']['uri']!=active.get(o['metadata']['name']):
    title,_,_=register(o['spec']['model']['uri']);print('PASS Registered prepared alternate (component '+comp+', not deployed): '+title)
except (RuntimeError,AssertionError,KeyError,ValueError,subprocess.SubprocessError) as error:
 raise SystemExit('ERROR: registry publication stopped ('+type(error).__name__+'); inspect native readiness/source ownership') from None
PY
