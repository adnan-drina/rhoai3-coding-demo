#!/usr/bin/env python3
"""Initialize only retained customer runtime keys and verify native controller readiness."""
import argparse,base64,json,os,pathlib,secrets,subprocess,urllib.request
p=argparse.ArgumentParser();p.add_argument('--revision',required=True);p.add_argument('--prepare-only',action='store_true');args=p.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[2];APP='060-agent-runtime-and-agentops-runtime';NS='openshell';OPNS='stage060-agent-sandbox-operator';CSV='agent-sandbox-operator.v0.9.0'
g=subprocess.run(['bash','-c','REPO_ROOT="$1";source "$1/scripts/shared/lib.sh";load_env;check_oc_logged_in','guard',str(ROOT)],capture_output=True,text=True);assert g.returncode==0,'Shared guard failed'
assert subprocess.check_output(['git','-C',str(ROOT),'show',args.revision+':'+str(pathlib.Path(__file__).resolve().relative_to(ROOT))])==pathlib.Path(__file__).read_bytes(),'Published helper content differs'
def oc(*a,payload=None):
    r=subprocess.run(['oc','--request-timeout=15s',*a],input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True)
    assert r.returncode==0,'Bounded Kubernetes request failed'
    return json.loads(r.stdout) if r.stdout.strip() else None
def get(kind,name,namespace=NS):return oc('get',kind,name,'-n',namespace,'-o','json')
app=get('application',APP,'openshift-gitops');m=app['metadata'];s=app['spec'];assert not m.get('ownerReferences') and not m.get('deletionTimestamp') and 'sources' not in s
source={'repoURL':'https://github.com/adnan-drina/rhoai3-coding-demo.git','targetRevision':args.revision,'path':'gitops/stages/060-agent-runtime-and-agentops/runtime'}
assert s['source']==source and s['project']=='rhoai-demo' and s['destination']=={'server':'https://kubernetes.default.svc','namespace':NS}
operation=app['status']['operationState'];assert operation['phase'] in ('Running','Succeeded') and operation['syncResult']['revision']==args.revision and operation['syncResult']['source']==source
assert 'RespectIgnoreDifferences=true' in s['syncPolicy']['syncOptions']
for kind,name,pointers in [('Secret','stage060-openshell-credentials',['/data/key-encryption-key']),('ConfigMap','stage060-openshell-identity',['/data/issuer']),('ConfigMap','stage060-runtime-ready',['/data/controller-ready','/data/source-revision','/data/controller-csv-uid'])]:
    assert any(i.get('group','')=='' and i.get('kind')==kind and i.get('name')==name and i.get('namespace')==NS and i.get('jsonPointers')==pointers for i in s.get('ignoreDifferences',[])),'Missing narrow runtime field delegation'
def tracked(obj):
    m=obj['metadata'];group=obj['apiVersion'].split('/')[0] if '/' in obj['apiVersion'] else ''
    expected=APP+':'+group+'/'+obj['kind']+':'+m.get('namespace',NS)+'/'+m['name']
    assert m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')==expected and not m.get('ownerReferences') and not m.get('deletionTimestamp'),'Foreign runtime object'
    return obj
tracked(get('namespace',NS))
identity=tracked(get('configmap','stage060-openshell-identity'));ready=tracked(get('configmap','stage060-runtime-ready'));credential=tracked(get('secret','stage060-openshell-credentials'))
pvcs=oc('get','pvc','-n',NS,'-o','json');assert isinstance(pvcs.get('items'),list)
value=credential.get('data',{}).get('key-encryption-key')
if value:
    decoded=base64.b64decode(value,validate=True);assert len(base64.b64decode(decoded,validate=True))==32,'Invalid retained encryption key'
else:
    assert not pvcs['items'],'Missing key with retained storage; rotation refused'
    value=base64.b64encode(base64.b64encode(secrets.token_bytes(32))).decode()
route=get('route','keycloak','keycloak');assert route['spec']['tls']['termination']=='reencrypt'
issuer='https://'+route['spec']['host']+'/realms/openshell'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None
with urllib.request.build_opener(NoRedirect()).open(issuer+'/.well-known/openid-configuration',timeout=15) as response:discovery=json.load(response)
assert discovery['issuer']==issuer and discovery['jwks_uri'].startswith(issuer+'/'),'Issuer discovery mismatch'
def patch_data(obj,fields):
    # Preserve all unrelated fields and refuse concurrency rather than overwrite.
    m=obj['metadata'];data=dict(obj.get('data',{}));data.update(fields)
    if data==obj.get('data',{}):return
    changes=[{'op':'test','path':'/metadata/uid','value':m['uid']},{'op':'test','path':'/metadata/resourceVersion','value':m['resourceVersion']},{'op':'add','path':'/data','value':data}]
    oc('patch',obj['kind'],m['name'],'-n',m['namespace'],'--type=json','--patch-file=/dev/stdin','-o','json',payload=changes)
patch_data(credential,{'key-encryption-key':value});patch_data(identity,{'issuer':issuer})
if args.prepare_only:
    print('Runtime issuer/retained key initialized; controller gate remains closed');raise SystemExit(0)
sub=tracked(get('subscription','agent-sandbox-operator',OPNS));assert sub['spec']['installPlanApproval']=='Manual' and sub['spec']['startingCSV']==CSV and sub['spec']['source']=='redhat-operators' and sub['spec']['channel']=='preview-0.9'
assert sub['status']['installedCSV']==CSV
csv=get('csv',CSV,OPNS);assert csv['status']['phase']=='Succeeded'
deployments=csv['spec']['install']['spec']['deployments'];assert deployments
for declared in deployments:
    d=get('deployment',declared['name'],OPNS);assert any(o.get('uid')==csv['metadata']['uid'] and o.get('kind')=='ClusterServiceVersion' and o.get('apiVersion','').startswith('operators.coreos.com/') for o in d['metadata'].get('ownerReferences',[]))
    status=d['status'];desired=d['spec'].get('replicas',1)
    assert desired>=1 and status.get('observedGeneration')==d['metadata']['generation'] and all(status.get(k)==desired for k in ('replicas','updatedReplicas','availableReplicas','readyReplicas')),'Native controller rollout incomplete'
    for c in declared['spec']['template']['spec']['containers']:
        assert '@sha256:' in c['image'] and any(x['name']==c['name'] and x['image']==c['image'] for x in d['spec']['template']['spec']['containers']),'Controller image mismatch'
crd=oc('get','crd','sandboxes.agents.x-k8s.io','-o','json');assert any(c['type']=='Established' and c['status']=='True' for c in crd['status']['conditions']) and any(v['served'] and v['name'] in ('v1alpha1','v1beta1') for v in crd['spec']['versions'])
patch_data(ready,{'controller-ready':'true','source-revision':args.revision,'controller-csv-uid':csv['metadata']['uid']})
print('Exact native Manual CSV/controller/served Sandbox API qualified; startup barrier released')
