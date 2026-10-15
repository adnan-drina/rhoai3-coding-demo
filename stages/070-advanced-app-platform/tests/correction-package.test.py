"""Executable regressions for Secret lifecycle, source pinning and scoped authority."""
import base64
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import yaml

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'gitops/stages/070-advanced-app-platform'
sys.path.insert(0,str(BASE/'pipelines/gitlab'))
import secret_writer

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
sys.path.insert(0,str(ROOT/'scripts/shared'))
import stage_apps
scm=load('correction_enrollment',BASE/'pipelines/gitlab/reconcile.py')
bootstrap=load('correction_bootstrap',BASE/'gitlab/bootstrap-scm.py')
identity=load('scoped_identity',BASE/'identity/jobs/configure-scm-identity.py')
sys.path.insert(0,str(ROOT/'stages/070-advanced-app-platform'))
rotation=load('reviewed_rotation',ROOT/'stages/070-advanced-app-platform/rotate-credentials.py')
security=load('live_security',ROOT/'stages/070-advanced-app-platform/security-status.py')
renderer=load('correction_renderer',ROOT/'scripts/platform/render-stage070-charts.py')

class SecretAPI:
 def __init__(self,existing=None):self.value=copy.deepcopy(existing);self.calls=[];self.fail=None
 def __call__(self,*args,document=None):
  self.calls.append((args,copy.deepcopy(document)))
  if self.fail:raise subprocess.CalledProcessError(1,['oc',*args],stderr=self.fail)
  if args[0]=='get':
   if self.value is None:raise subprocess.CalledProcessError(1,['oc',*args],stderr='(NotFound)')
   return copy.deepcopy(self.value)
  if args[0]=='create':
   if self.value is not None:raise subprocess.CalledProcessError(1,['oc',*args],stderr='(AlreadyExists)')
   self.value=copy.deepcopy(document)
  elif args[0]=='patch':
   for k,values in document.get('metadata',{}).items():
    target=self.value.setdefault('metadata',{}).setdefault(k,{})
    for key,value in values.items():
     if value is None:target.pop(key,None)
     else:target[key]=value
   self.value.setdefault('data',{}).update(document.get('data',{}))
   self.value.setdefault('stringData',{}).update(document.get('stringData',{}))
  elif args[0]=='apply':
   # Kubernetes client-side apply is the bug: it retains the complete payload.
   self.value=copy.deepcopy(document);self.value['metadata'].setdefault('annotations',{})[secret_writer.LAST_APPLIED]=json.dumps(document)
  return copy.deepcopy(self.value)

class SecretLifecycle(unittest.TestCase):
 def setUp(self):
  self.doc={'apiVersion':'v1','kind':'Secret','metadata':{'name':'credential','namespace':'test','labels':{'owned':'yes'}},'stringData':{'token':'synthetic-token'}}
 def test_first_write_does_not_copy_payload(self):
  api=SecretAPI();secret_writer.write_secret(self.doc,api)
  self.assertEqual([a[0] for a,d in api.calls],['get','create'])
  self.assertNotIn(secret_writer.LAST_APPLIED,api.value['metadata'].get('annotations',{}))
 def test_update_removes_copy_and_preserves_foreign_fields(self):
  old=copy.deepcopy(self.doc);old['metadata']['uid']='retained';old['metadata']['annotations']={secret_writer.LAST_APPLIED:'old-token','foreign':'keep'};old['data']={'other':'dW5yZWxhdGVk'}
  api=SecretAPI(old);before=copy.deepcopy(self.doc)
  for _ in range(2):secret_writer.write_secret(self.doc,api)
  self.assertEqual(self.doc,before);self.assertEqual(api.value['metadata']['uid'],'retained');self.assertEqual(api.value['data']['other'],'dW5yZWxhdGVk');self.assertEqual(api.value['metadata']['annotations'],{'foreign':'keep'})
  self.assertTrue(all('--force-conflicts' not in a for a,d in api.calls))
 def test_writer_without_read_creates_then_patches(self):
  for existing,calls in ((None,['get','create']),({'metadata':{'name':'credential','namespace':'test'},'stringData':{'token':'old'}},['get','create','patch'])):
   api=SecretAPI(copy.deepcopy(existing));original=api.__call__
   def no_read(*args,document=None):
    if args[0]=='get':api.calls.append((args,document));raise subprocess.CalledProcessError(1,args,stderr='Error from server (Forbidden): secrets is forbidden')
    return original(*args,document=document)
   secret_writer.write_secret(self.doc,no_read)
   self.assertEqual([a[0] for a,d in api.calls],calls);self.assertEqual(api.value['stringData']['token'],'synthetic-token')
 def test_forbidden_does_not_fall_back_or_expose_payload(self):
  api=SecretAPI();api.fail='(Forbidden) synthetic-token'
  with self.assertRaisesRegex(RuntimeError,'redacted') as caught:secret_writer.write_secret(self.doc,api)
  self.assertNotIn('synthetic-token',str(caught.exception));self.assertEqual([c[0][0] for c in api.calls],['get','create'])  # never patch past a refused create
 def test_create_race_updates_existing(self):
  api=SecretAPI();original=api.__call__;first=True
  def race(*args,document=None):
   if args[0]=='create':api.value=copy.deepcopy(self.doc)
   return original(*args,document=document)
  secret_writer.write_secret(self.doc,race)
  self.assertEqual(api.calls[-1][0][0],'patch')
 def test_wrong_kind_or_implicit_namespace_is_refused(self):
  for field in ('kind','namespace'):
   doc=copy.deepcopy(self.doc)
   if field=='kind':doc['kind']='ConfigMap'
   else:del doc['metadata']['namespace']
   api=SecretAPI()
   with self.assertRaises(ValueError):secret_writer.write_secret(doc,api)
   self.assertEqual(api.calls,[])
 def test_real_reconciler_routes_secrets_but_keeps_normal_apply(self):
  api=SecretAPI()
  with patch.object(scm,'oc',api):scm.apply(self.doc)
  self.assertNotIn(secret_writer.LAST_APPLIED,api.value['metadata'].get('annotations',{}))
  with patch.object(scm,'oc',api):scm.apply({'kind':'ConfigMap','metadata':{'name':'x'}})
  self.assertEqual(api.calls[-1][0][0],'apply')
 def test_real_bootstrap_routes_typed_secrets(self):
  api=SecretAPI()
  def call(*args,data=None):return api(*args,document=data)
  with patch.object(bootstrap,'oc',call):bootstrap.apply('Secret','credential','test',{'token':'synthetic-token'})
  self.assertNotIn(secret_writer.LAST_APPLIED,api.value['metadata'].get('annotations',{}))

class Deployment(unittest.TestCase):
 # Deploy behaviour (revision selection, sync, wait) is tested in scripts/shared/stage_apps.test.py.
 sha='1'*40;repo='https://source.example/demo.git'
 def test_components_deploy_in_order_sequentially_with_server_side_diff(self):
  apps=stage_apps.stamped('070',self.sha,self.repo)
  self.assertEqual([a['metadata']['name'] for a in apps][0],'070-namespaces');self.assertEqual([a['metadata']['name'] for a in apps][-2:],['070-gitlab','070-rhdh'])
  self.assertEqual(len(stage_apps.deploy_groups(apps)),len(apps))
  for value in apps:
   self.assertEqual(value['spec']['destination'],{'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'})
   self.assertEqual(value['metadata']['annotations']['argocd.argoproj.io/compare-options'],'ServerSideDiff=true')
   self.assertNotIn('ServerSideDiff=true',value['spec']['syncPolicy']['syncOptions'])
  claims=[x for a in apps for x in a['spec'].get('ignoreDifferences',[]) if x.get('kind')=='PersistentVolumeClaim']
  self.assertTrue(claims);self.assertTrue(all(x.get('name') and x.get('namespace') and x['jsonPointers']==['/spec/volumeName'] for x in claims))

class EnrollmentErrors(unittest.TestCase):
 def test_permanent_failures_are_never_pending(self):
  for error in [ValueError('foreign identity'),KeyError('missing'),urllib.error.HTTPError('https://example',403,'denied',None,None),subprocess.CalledProcessError(1,['oc'],stderr='(Forbidden)')]:
   self.assertEqual(scm.enrollment_failure(error,'2026-10-14T00:00:00Z')[0],'refused')
 def test_transient_has_one_fixed_request_deadline(self):
  now=datetime.datetime(2026,10,14,0,30,tzinfo=datetime.timezone.utc)
  for error in [scm.EnrollmentPending(),urllib.error.HTTPError('https://example',429,'limited',None,None)]:
   self.assertEqual(scm.enrollment_failure(error,'2026-10-14T00:00:00Z',now)[0],'pending')
   self.assertEqual(scm.enrollment_failure(error,'2026-10-13T23:00:00Z',now),('refused','ENROLLMENT_DEADLINE'))
   self.assertEqual(scm.enrollment_failure(error,None,now)[0],'refused')
 def test_generated_apps_use_diff_annotation(self):
  doc=scm.project_application('example','example-dev',{}, {'PLATFORM_REPO_URL':'https://example.test/repo.git','PLATFORM_REVISION':'1'*40})
  self.assertEqual(doc['metadata']['annotations']['argocd.argoproj.io/compare-options'],'ServerSideDiff=true')

class ScopedAuthority(unittest.TestCase):
 def test_client_roles_stay_in_platform_and_keep_secret(self):
  requests=[];written=[]
  def api(method,path,data=None):
   requests.append((method,path,data))
   if path=='clients?clientId=stage070-rhdh-provisioner':return [{'id':'existing-client','attributes':{'rhoai3.owner':'stage070'}}]
   if path=='clients?clientId=realm-management':return [{'id':'manager'}]
   if path.endswith('/service-account-user'):return {'id':'service-user'}
   if '/roles/' in path:return {'name':path.rsplit('/',1)[-1]}
   if path.endswith('/client-secret'):return {'value':'preserved-synthetic-secret'}
   if method=='GET':return []
  identity.configure(api,'stage070-rhdh-provisioner','rhdh',('manage-clients',),writer=written.append)
  self.assertEqual(written[0]['stringData']['client_secret'],'preserved-synthetic-secret')
  put=next(data for method,path,data in requests if method=='PUT');self.assertFalse(put['fullScopeAllowed']);self.assertFalse(put['directAccessGrantsEnabled'])
  self.assertFalse(any('/master/' in path or '/sso/' in path for method,path,data in requests))
  self.assertTrue(any('/scope-mappings/' in path for method,path,data in requests))
 def test_bootstrap_authority_is_removed_on_success_or_failure(self):
  docs=list(yaml.safe_load_all((BASE/'gitlab/integrations-bootstrap.yaml').read_text()))
  bindings=[d for d in docs if d and d['kind']=='RoleBinding' and any(s.get('name')=='gitlab-integrations-bootstrap' for s in d.get('subjects',[]))]
  self.assertTrue(bindings)
  self.assertTrue(all(d['metadata']['annotations'].get('argocd.argoproj.io/hook')=='Sync' for d in bindings))
  cleanup=list(yaml.safe_load_all((BASE/'gitlab/bootstrap-cleanup.yaml').read_text()));job=next(d for d in cleanup if d['kind']=='Job')
  self.assertEqual(job['metadata']['annotations']['argocd.argoproj.io/hook'],'PostSync,SyncFail')
  script=job['spec']['template']['spec']['containers'][0]['command'][-1]
  for d in bindings:self.assertIn('oc delete rolebinding '+d['metadata']['name']+' -n '+d['metadata']['namespace'],script)
  roles=[d for d in cleanup if d['kind']=='Role'];self.assertTrue(all(r['rules'][0]['resources']==['rolebindings'] and r['rules'][0]['verbs']==['get','delete'] and r['rules'][0].get('resourceNames') for r in roles))
 def test_downstream_jobs_have_no_master_secret_access(self):
  for file in ['rhdh/jobs/configure-rhdh.yaml','mta/jobs/configure-mta-platform-sso.yaml','pipelines/signing/bootstrap.yaml']:
   for d in yaml.safe_load_all((BASE/file).read_text()):
    if d and d.get('kind')=='Role' and d['metadata'].get('namespace')=='keycloak':self.assertFalse(any('secrets' in r.get('resources',[]) for r in d.get('rules',[])))
 def test_all_shell_commands_parse(self):
  for file in ['rhdh/jobs/configure-rhdh.yaml','mta/jobs/configure-mta-platform-sso.yaml','sonarqube/configure-sonarqube.yaml','devspaces/maas-api-key-provisioning.yaml']:
   for d in yaml.safe_load_all((BASE/file).read_text()):
    if d and d.get('kind')=='Job':
     for c in d['spec']['template']['spec']['containers']:
      for s in c.get('command',[])+c.get('args',[]):
       if '\n' in s:subprocess.run(['/bin/bash','-n'],input=s,text=True,check=True,capture_output=True)
 def test_bash32_empty_auth_array_is_safe(self):
  result=subprocess.run(['/bin/bash','-uc','auth=(); set -- ${auth[@]+"${auth[@]}"}; test "$#" = 0'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)

class RotationSafety(unittest.TestCase):
 def test_operator_sonar_uses_route_and_preserves_pipeline_host(self):
  r=rotation.Rotation.__new__(rotation.Rotation);calls=[];revoked=[False]
  def oc(*args):
   if args[1]=='route':return {'spec':{'host':'sonar.example'}}
   return {'metadata':{'annotations':{}}}
  def api(base,method,path,payload=None,headers=None,**kw):
   self.assertEqual(base,'https://sonar.example');calls.append((method,path))
   if path=='/api/user_tokens/generate':self.assertEqual(payload['login'],'platform-provisioner');return {'token':'new'}
   if path=='/api/user_tokens/revoke':self.assertEqual(payload,{'login':'admin','name':'platform-pipeline'})
   if path=='/api/user_tokens/revoke':revoked[0]=True;return
   token=base64.b64decode(headers['Authorization'].split()[1]).decode().split(':')[0]
   return {'valid':token=='new' or not revoked[0]}
  with patch.object(rotation,'data',side_effect=[({}, {'password':'admin'}),({}, {'host':'http://sonarqube.sonarqube.svc:9000','token':'old'})]),patch.object(rotation,'oc',side_effect=oc),patch.object(rotation,'request',side_effect=api),patch.object(rotation,'update') as writer,patch.object(rotation.subprocess,'run'):
   self.assertTrue(all(r.sonar().values()));writer.assert_called_once_with('app-platform-build','sonarqube-credentials',{'token':'new'})
  self.assertIn(('POST','/api/user_tokens/revoke'),calls)
 def test_project_tokens_move_from_admin_to_the_provisioner(self):
  r=rotation.Rotation.__new__(rotation.Rotation);owned={'admin':{'gitlab-project-5'},'platform-provisioner':set()};live={'old5'};writes=[]
  ann={'rhoai3.io/sonar-project-key':'coolstore','rhoai3.io/sonar-token-type':'PROJECT_ANALYSIS_TOKEN','rhoai3.io/sonar-token-name':'gitlab-project-5'}
  def oc(*args):
   if args[1]=='route':return {'spec':{'host':'sonar.example'}}
   if '-A' in args:return {'items':[{'metadata':{'namespace':'coolstore-dev','annotations':ann},'data':{'token':base64.b64encode(b'old5').decode()}}]}
   ns=args[args.index('-n')+1];return {'items':[{'metadata':{'namespace':ns,'name':'coolstore-sonar-credentials','annotations':{'rhoai3.io/sonar-project-key':'coolstore'}}}] if ns=='wksp-ai-developer' else []}
  def api(base,method,path,payload=None,headers=None,**kw):
   if path.startswith('/api/user_tokens/search'):
    login=path.split('login=')[1];return {'userTokens':[{'name':n,'type':'PROJECT_ANALYSIS_TOKEN'} for n in owned[login]]}
   if path=='/api/user_tokens/generate':
    self.assertEqual((payload['login'],payload['projectKey'],payload['type']),('platform-provisioner','coolstore','PROJECT_ANALYSIS_TOKEN'))
    owned['platform-provisioner'].add(payload['name']);live.add('new5');return {'token':'new5','type':'PROJECT_ANALYSIS_TOKEN'}
   if path=='/api/user_tokens/revoke':self.assertEqual(payload['login'],'admin');owned['admin'].discard(payload['name']);live.discard('old5');return
   token=base64.b64decode(headers['Authorization'].split()[1]).decode().split(':')[0];return {'valid':token in live}
  with patch.object(rotation,'data',return_value=({}, {'password':'admin'})),patch.object(rotation,'oc',side_effect=oc),patch.object(rotation,'request',side_effect=api),patch.object(rotation,'update',side_effect=lambda *a:writes.append(a)):
   self.assertTrue(all(r.sonar_projects().values()))
  self.assertEqual(writes,[('coolstore-dev','sonarqube-credentials',{'token':'new5'}),('wksp-ai-developer','coolstore-sonar-credentials',{'SONAR_TOKEN':'new5'})])
 def test_gitlab_renewal_uses_documented_response_and_preserves_authority(self):
  self.oauth_case()
 def test_gitlab_renewal_rejects_changed_scope_before_persistence(self):
  self.oauth_case('scopes')
 def test_gitlab_renewal_rejects_changed_callback_before_persistence(self):
  self.oauth_case('callback_url')
 def test_gitlab_renewal_rejects_changed_id_before_persistence(self):
  self.oauth_case('application_id')
 def oauth_case(self,mutation=None):
  r=rotation.Rotation.__new__(rotation.Rotation);r.gitlab='https://gitlab.example';calls=[]
  old={'id':'client-id','secret':'old'}
  previous={'id':4,'application_id':'client-id','application_name':'Dev Spaces','callback_url':'https://devspaces.example/callback','confidential':True,'scopes':['api','read_user']}
  new=dict(previous,secret='new')
  if mutation:new[mutation]=['api','sudo'] if mutation=='scopes' else 'foreign'
  def api(method,path,payload=None):
   calls.append((method,path));return [previous] if method=='GET' else new
  def auth(base,method,path,payload=None,**kwargs):
   self.assertEqual(payload['redirect_uri'],previous['callback_url'])
   error='invalid_client' if payload['client_secret']=='old' else 'invalid_grant'
   import io
   raise urllib.error.HTTPError(base,401,'OAuth error',None,io.BytesIO(json.dumps({'error':error}).encode()))
  r.root_api=api
  with patch.object(rotation,'data',return_value=({},old)),patch.object(rotation,'update') as writer,patch.object(rotation,'request',side_effect=auth):
   if mutation:
    with self.assertRaisesRegex(ValueError,'authority'):r.devspaces_oauth()
    writer.assert_not_called()
   else:
    self.assertTrue(all(r.devspaces_oauth().values()));writer.assert_called_once_with('openshift-devspaces','gitlab-oauth-config',{'secret':'new'})
  self.assertEqual(calls,[('GET','applications'),('POST','applications/4/renew-secret')])
 def test_argo_rotation_lets_the_operator_reissue_and_copies_to_developer_hub(self):
  self.argo_case()
 def test_argo_foreign_subject_refuses_before_delete(self):
  self.argo_case('old_subject')
 def test_argo_replacement_with_another_subject_is_not_copied(self):
  self.argo_case('subject')
 def argo_case(self,mutation=None):
  def jwt(claims):return 'header.'+base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')+'.signature'
  claims={'sub':'rhdh:apiKey','iss':'argocd','jti':'old-id'}
  if mutation=='old_subject':claims['sub']='other:apiKey'
  replacement=dict(claims,jti='new-id')
  if mutation=='subject':replacement['sub']='other:apiKey'
  old=jwt(claims);new=jwt(replacement);deleted=[];r=rotation.Rotation.__new__(rotation.Rotation)
  def data(ns,name):
   self.assertEqual((ns,name),('openshift-gitops','rhdh-local-user'))
   return ({'metadata':{'uid':'new' if deleted else 'old'}},{'apiToken':new if deleted else old})
  def req(base,method,path,payload=None,headers=None,**kw):
   if headers['Authorization']=='Bearer '+old and deleted:raise urllib.error.HTTPError(base,401,'revoked',None,None)
   return {'items':[]}
  with patch.object(rotation,'oc',return_value={'spec':{'host':'argo.example'}}),patch.object(rotation,'data',side_effect=data),patch.object(rotation,'command',side_effect=lambda *a:deleted.append(a)),patch.object(rotation,'request',side_effect=req),patch.object(rotation,'time'),patch.object(rotation,'update') as writer:
   if mutation:
    with self.assertRaisesRegex(ValueError,'identity|credential'):r.argo()
    writer.assert_not_called()
    if mutation=='old_subject':self.assertFalse(deleted)
   else:
    self.assertTrue(all(r.argo().values()));writer.assert_called_once_with('rhdh','rhdh-secrets',{'RHDH_ARGOCD_TOKEN':new})
 def test_delivery_writer_rotates_itself_and_the_old_token_stops(self):
  r=rotation.Rotation.__new__(rotation.Rotation);r.gitlab='https://gitlab.example';live={'old'};writes=[]
  secret={'metadata':{'namespace':'app-dev'},'data':{'token':base64.b64encode(b'old').decode()}}
  def req(base,method,path,payload=None,headers=None,**kw):
   token=headers['PRIVATE-TOKEN']
   if token not in live:raise urllib.error.HTTPError(base,401,'revoked',None,None)
   if path.startswith('/api/v4/projects?membership'):return [{'id':7}]
   if path=='/api/v4/projects/7/access_tokens/self/rotate':live.discard(token);live.add('new');return {'token':'new','expires_at':payload['expires_at']}
   return {'id':1}
  with patch.object(rotation,'oc',return_value={'items':[secret]}),patch.object(rotation,'request',side_effect=req),patch.object(rotation,'update',side_effect=lambda *a:writes.append(a)):
   self.assertTrue(all(r.delivery_writers().values()))
  self.assertEqual(writes[0][:2],('app-dev','gitlab-delivery-writer'));self.assertEqual(writes[0][2]['token'],'new')
 def test_annotation_cleanup_preserves_values_and_avoids_master_credentials(self):
  before={'metadata':{'uid':'same','annotations':{secret_writer.LAST_APPLIED:'synthetic-copy'}},'data':{'token':'c3ludGhldGlj'},'type':'Opaque'}
  after=copy.deepcopy(before);after['metadata']['annotations']={}
  with patch.object(rotation,'oc',side_effect=[before,after]),patch.object(rotation,'write_secret') as writer,patch.object(rotation,'data') as credential_read:
   self.assertTrue(all(rotation.remove_annotation('test/credential').values()));credential_read.assert_not_called()
   self.assertNotIn('data',writer.call_args.args[0]);self.assertNotIn('stringData',writer.call_args.args[0])
 def test_removed_rotated_key_is_already_invalidated(self):
  r=rotation.Rotation.__new__(rotation.Rotation);r.sso='https://sso.example';r.client=lambda name:'same-id';current=['old']
  def api(method,path,payload=None):
   if method=='POST':current[0]='new'
   if method=='DELETE':raise urllib.error.HTTPError(r.sso,404,'already absent',None,None)
   return {'value':current[0]}
  r.keycloak=api
  def denied(*args,**kwargs):raise urllib.error.HTTPError(r.sso,401,'refused',None,None)
  with patch.object(rotation,'request',side_effect=denied):self.assertTrue(all(r.rotate_client('expected',lambda value:None).values()))
 def test_client_persist_precedes_predecessor_invalidation(self):
  r=rotation.Rotation.__new__(rotation.Rotation);r.sso='https://sso.example';calls=[];current=['old']
  def api(method,path,payload=None):
   calls.append((method,path))
   if path=='clients?clientId=expected':return [{'id':'retained-id','clientId':'expected'}]
   if method=='POST':current[0]='new';return {'value':'new'}
   if method=='GET':return {'value':current[0]}
  r.keycloak=api
  def denied(*a,**kw):raise urllib.error.HTTPError('https://sso.example',401,'refused',None,None)
  with patch.object(rotation,'request',side_effect=denied):
   proof=r.rotate_client('expected',lambda value:calls.append(('persist',value)))
  self.assertTrue(all(proof.values()));self.assertLess(calls.index(('persist','new')),next(i for i,(method,path) in enumerate(calls) if method=='DELETE'))
 def test_publisher_authority_change_is_refused_before_secret_write(self):
  r=rotation.Rotation.__new__(rotation.Rotation);r.gitlab='https://gitlab.example'
  previous={'id':12,'user_id':7,'scopes':['api','read_repository'],'expires_at':'2026-12-01'}
  def api(method,path,payload=None):
   if method=='GET':return {'username':'rhdh-publisher','id':7}
   return {'user_id':7,'scopes':['api','read_repository','sudo'],'expires_at':'2026-12-01','token':'new'}
  r.root_api=api
  with patch.object(rotation,'data',return_value=({}, {'token':'old'})),patch.object(rotation,'request',return_value=previous),patch.object(rotation,'update') as writer:
   with self.assertRaisesRegex(ValueError,'authority'):r.publisher()
   writer.assert_not_called()
 def test_publisher_updates_both_copies_before_revoke(self):
  r=rotation.Rotation.__new__(rotation.Rotation);r.gitlab='https://gitlab.example';calls=[];revoked=[False]
  old={'id':12,'user_id':7,'scopes':['api','read_repository'],'expires_at':'2026-12-01'}
  def api(method,path,payload=None):
   calls.append((method,path))
   if method=='GET':return {'username':'rhdh-publisher','id':7}
   if method=='DELETE':revoked[0]=True;return
   return dict(old,token='new')
  def request(base,method,path,payload=None,headers=None,**kwargs):
   if headers['PRIVATE-TOKEN']=='old' and revoked[0]:raise urllib.error.HTTPError(base,401,'refused',None,None)
   return old
  r.root_api=api
  with patch.object(rotation,'data',return_value=({}, {'token':'old'})),patch.object(rotation,'request',side_effect=request),patch.object(rotation,'update',side_effect=lambda ns,name,value:calls.append(('write',name))):
   self.assertTrue(all(r.publisher().values()))
  self.assertLess(calls.index(('write','gitlab-publisher')),calls.index(('DELETE','personal_access_tokens/12')))
  self.assertLess(calls.index(('write','rhdh-gitlab')),calls.index(('DELETE','personal_access_tokens/12')))
 def test_foreign_maas_key_never_mints_or_revokes(self):
  r=rotation.Rotation.__new__(rotation.Rotation)
  gateway={'spec':{'listeners':[{'hostname':'maas.example'}]}}
  with patch.object(rotation,'oc',return_value=gateway),patch.object(rotation,'command',return_value='synthetic-jwt'),patch.object(rotation,'data',return_value=({}, {'MAAS_KEY_ID':'old'})),patch.object(rotation,'request',return_value={'username':'other','subscription':'foreign'}) as req,patch.object(rotation,'update') as writer:
   with self.assertRaisesRegex(ValueError,'Foreign'):r.mta()
   self.assertEqual(req.call_count,1);writer.assert_not_called()

class NativeSyncAndIngress(unittest.TestCase):
 def test_mta_patch_is_exact_in_subscription_allowlist_and_validator(self):
  selected=yaml.safe_load((BASE/'mta/mta-operator/subscription.yaml').read_text())['spec']
  self.assertEqual(selected['startingCSV'],'mta-operator.v8.3.1');self.assertEqual(selected['installPlanApproval'],'Manual')
  approval=(BASE/'mta/mta-operator/approve-installplan.yaml').read_text()
  self.assertIn('value: mta-operator.v8.3.1',approval)
  self.assertNotIn('mta-operator.v8.3.0',approval)
  self.assertIn('openshift-mta mta-operator mta-operator.v8.3.1',(ROOT/'stages/070-advanced-app-platform/validate.sh').read_text())
 def test_pvc_storage_classes_are_explicit_and_match_the_deploy_contract(self):
  docs=list(yaml.safe_load_all(subprocess.check_output(['kustomize','build',str(BASE)],text=True)))
  claims=[d for d in docs if d and d['kind']=='PersistentVolumeClaim'];self.assertTrue(claims)
  for claim in claims:self.assertEqual(claim['spec'].get('storageClassName'),'gp3-csi',claim['metadata']['name'])
 def test_identity_check_targets_the_client_configured_by_the_mta_job(self):
  jobs=[d for d in yaml.safe_load_all((BASE/'mta/jobs/configure-mta-platform-sso.yaml').read_text()) if d and d['kind']=='Job']
  script=jobs[0]['spec']['template']['spec']['containers'][0]['command'][-1]
  expected=next(line.split('=',1)[1].strip('"') for line in script.splitlines() if line.startswith('CLIENT_ID='))
  actual=next(target for ns,secret,target in security.CLIENTS if secret=='stage070-mta-provisioner')
  self.assertEqual(actual,expected)
 def test_declarative_secrets_have_explicit_ssa_without_stringdata(self):
  docs=list(yaml.safe_load_all(subprocess.check_output(['kustomize','build',str(BASE)],text=True)))
  secrets=[d for d in docs if d and d['kind']=='Secret'];self.assertTrue(secrets)
  for d in secrets:
   self.assertEqual(d['metadata']['annotations']['argocd.argoproj.io/sync-options'],'ServerSideApply=true');self.assertNotIn('stringData',d)
  for path in (ROOT/'gitops/argocd/app-of-apps/070-advanced-app-platform').glob('*.yaml'):
   self.assertIn('ClientSideApplyMigration=false',yaml.safe_load(path.read_text())['spec']['syncPolicy']['syncOptions'])
 def test_chart_writer_refuses_unreviewed_upstream_shape(self):
  old='kubectl --validate=false --namespace=$namespace apply -f rails-secrets.yml'
  script=renderer.rails_secret_writer(old)
  self.assertNotIn(' apply ',script);self.assertIn('--patch-file=rails-secrets.yml',script);self.assertIn('create -f rails-secrets.yml',script)
  subprocess.run(['/bin/bash','-n'],input=script,text=True,check=True)
  for changed in ('changed upstream',old+'\n'+old):
   with self.assertRaises(ValueError):renderer.rails_secret_writer(changed)
 def test_ingress_contract_preserves_only_declared_cross_namespace_path(self):
  policies=[p for path in sorted(BASE.glob('*/network-policy.yaml')) for p in yaml.safe_load_all(path.read_text())]
  self.assertEqual({p['metadata']['namespace'] for p in policies},{'gitlab-system','sonarqube','rhdh','app-platform-build','trusted-artifact-signer'})
  for p in policies:
   self.assertEqual(p['spec']['podSelector'],{});self.assertEqual(p['spec']['policyTypes'],['Ingress']);self.assertNotIn('egress',p['spec'])
   peers=p['spec']['ingress'][0]['from'];self.assertIn({'podSelector':{}},peers)
   self.assertTrue(all(peer.get('podSelector')=={} if 'podSelector' in peer else bool(peer.get('namespaceSelector',{}).get('matchLabels')) for peer in peers))
   if p['metadata']['namespace']!='sonarqube':self.assertEqual(len(p['spec']['ingress']),1)
   else:
    sonar=p['spec']['ingress'][1];self.assertEqual(sonar['ports'],[{'protocol':'TCP','port':9000}])
    self.assertIn({'namespaceSelector':{'matchLabels':{'rhoai3.redhat.com/pipeline-project':'true'}}},sonar['from'])
  k=(BASE/'pipelines/project-enrollment/kustomization.yaml').read_text();self.assertIn('NetworkPolicy',k)
  project=yaml.safe_load((BASE/'pipelines/project-pipeline/network-policy.yaml').read_text());self.assertEqual(project['spec']['policyTypes'],['Ingress'])
 def test_security_authorization_does_not_turn_api_errors_into_denials(self):
  with patch.object(security.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'no\n','')):self.assertTrue(security.denied('get','secret/x','test','principal'))
  with patch.object(security.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','API unavailable')):
   with self.assertRaises(RuntimeError):security.denied('get','secret/x','test','principal')
 def test_service_credentials_are_not_writable_by_downstream_jobs(self):
  for file,ns,name in [('rhdh/jobs/configure-rhdh.yaml','rhdh','stage070-rhdh-provisioner'),('mta/jobs/configure-mta-platform-sso.yaml','openshift-mta','stage070-mta-provisioner')]:
   roles=[d for d in yaml.safe_load_all((BASE/file).read_text()) if d and d['kind']=='Role' and d['metadata']['namespace']==ns]
   for role in roles:
    for rule in role['rules']:
     if 'secrets' in rule.get('resources',[]) and 'patch' in rule.get('verbs',[]):self.assertNotIn(name,rule.get('resourceNames',[]));self.assertTrue(rule.get('resourceNames'))


class ComponentLayout(unittest.TestCase):
 def test_secret_writer_copies_match_the_canonical_writer(self):
  # Kustomize loads files only from inside a component folder, so each bundle carries its own copy.
  canonical=(BASE/'pipelines/gitlab/secret_writer.py').read_bytes()
  copies=sorted(p for p in BASE.glob('*/secret_writer.py'))
  self.assertEqual([p.parent.name for p in copies],['devspaces','gitlab','identity','mta','sonarqube'])
  for path in copies:self.assertEqual(path.read_bytes(),canonical,str(path)+' differs from pipelines/gitlab/secret_writer.py')

if __name__=='__main__':unittest.main()
