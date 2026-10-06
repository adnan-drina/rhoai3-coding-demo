#!/usr/bin/env python3
"""Guarded, idempotent native Keycloak broker setup; credentials never leave memory/API stdin."""
import argparse, base64, json, os, pathlib, secrets, subprocess, urllib.error, urllib.parse, urllib.request
P=argparse.ArgumentParser();P.add_argument('--revision',required=True);P.add_argument('--preflight',action='store_true');args=P.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[2]
# Standalone entry uses the same canonical guard as deployment, before every API read.
guard=subprocess.run(['bash','-c','REPO_ROOT="$1"; source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in','stage060-guard',str(ROOT)],capture_output=True,text=True)
assert guard.returncode==0,'Shared environment/login guard failed'
assert subprocess.check_output(['git','-C',str(ROOT),'show',args.revision+':'+str(pathlib.Path(__file__).resolve().relative_to(ROOT))])==pathlib.Path(__file__).read_bytes(),'Helper differs from selected published source'
APP='060-agent-runtime-and-agentops';REALM='openshell';NS='keycloak';MARKER='rhoai3-coding-demo';BROKER='stage060-openshell-broker'
class IdentityFailure(RuntimeError):
    def __init__(self,status):self.status=status;super().__init__('Identity API status '+str(status))
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw): return None
http=urllib.request.build_opener(NoRedirect())
def oc(*a,payload=None,optional=False):
    cmd=['oc','--request-timeout=15s',*a]
    if optional: cmd+=['--ignore-not-found']
    r=subprocess.run(cmd,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True)
    if r.returncode: raise RuntimeError('Bounded Kubernetes request failed: '+a[0])
    return json.loads(r.stdout) if r.stdout.strip() else None
server=subprocess.check_output(['oc','--request-timeout=15s','whoami','--show-server'],text=True).strip()
expected=os.environ.get('RHOAI_EXPECTED_API_SERVER','');assert expected and expected in server,'Target guard failed'
app=oc('get','application',APP,'-n','openshift-gitops','-o','json',optional=args.preflight)
if app:
    s=app['spec'];m=app['metadata']
    assert not m.get('ownerReferences') and not m.get('deletionTimestamp') and 'sources' not in s
    assert s['project']=='rhoai-demo' and s['source']['repoURL']=='https://github.com/adnan-drina/rhoai3-coding-demo.git' and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/base'
    assert s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'}
    if not args.preflight:
        assert s['source']['targetRevision']==args.revision
        st=app['status'];op=st.get('operationState',{});assert st['sync']['revision']==args.revision and st['sync']['status']=='Synced' and op.get('phase')=='Succeeded' and op['syncResult']['revision']==args.revision
route=oc('get','route','keycloak','-n',NS,'-o','json');assert route['spec']['tls']['termination']=='reencrypt'
base='https://'+route['spec']['host'];issuer=base+'/realms/'+REALM
kc=oc('get','keycloak','keycloak','-n',NS,'-o','json');admin=oc('get','secret','keycloak-initial-admin','-n',NS,'-o','json')
assert any(o.get('uid')==kc['metadata']['uid'] and o.get('kind')=='Keycloak' for o in admin['metadata'].get('ownerReferences',[]))
def request(path,method='GET',data=None,token=None,optional=False):
    headers={};body=None
    if token: headers['Authorization']='Bearer '+token
    if data is not None: body=json.dumps(data).encode();headers['Content-Type']='application/json'
    try:
        with http.open(urllib.request.Request(base+path,data=body,headers=headers,method=method),timeout=15) as r:
            raw=r.read(2*1024*1024);return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if optional and e.code==404:return None
        raise IdentityFailure(e.code) from None
body=urllib.parse.urlencode({'grant_type':'password','client_id':'admin-cli','username':base64.b64decode(admin['data']['username']).decode(),'password':base64.b64decode(admin['data']['password']).decode()}).encode()
with http.open(urllib.request.Request(base+'/realms/master/protocol/openid-connect/token',data=body),timeout=15) as r: token=json.load(r)['access_token']
def api(path,method='GET',data=None,optional=False):return request('/admin/realms/'+REALM+path,method,data,token,optional)
def identity_preflight():
    realm=api('',optional=True)
    broker=None;bootstrap_clients=[]
    if realm:
        assert realm.get('attributes',{}).get('stage060-managed')==MARKER,'Foreign realm'
        defaults=api('/roles/default-roles-openshell/composites')
        assert not any(x['name']=='openshell-platform-admin' for x in defaults),'Administrative default role'
        for client_name in ('openshell-cli','openshell-bootstrap'):
            found=api('/clients?clientId='+client_name);assert len(found)<=1
            if client_name=='openshell-bootstrap':bootstrap_clients=found
            if found:assert found[0].get('attributes',{}).get('stage060-managed')==MARKER,'Foreign client'
        broker=api('/identity-provider/instances/openshift-v4',optional=True)
        if broker:
            assert broker['providerId']=='openshift-v4' and broker['config'].get('clientId')==BROKER and broker['config'].get('stage060-managed')==MARKER,'Foreign broker'
        for name in ('ai-admin','ai-developer'):
            external=oc('get','user',name,'-o','json')['metadata']['uid']
            found=api('/users?username='+name+'&exact=true');assert len(found)<=1
            if found:
                u=found[0];assert u.get('attributes',{}).get('stage060-managed')==[MARKER] and u['attributes'].get('openshift-uid')==[external],'Foreign user'
                assert not api('/users/'+u['id']+'/groups'),'Unexpected group role grants'
                effective=api('/users/'+u['id']+'/role-mappings/realm/composite')
                assert not any(x['name']=='openshell-platform-admin' for x in effective),'Composite admin grant'
                assert not api('/users/'+u['id']+'/credentials'),'Unexpected local credentials'
                links=api('/users/'+u['id']+'/federated-identity')
                assert not links or links==[{'identityProvider':'openshift-v4','userId':external,'userName':name}],'Foreign broker identity'
    objects={}
    for kind,name,namespace in [('keycloakrealmimport','stage060-openshell',NS),('secret','stage060-openshell-auth',NS),('oauthclient',BROKER,None)]:
        call=['get',kind,name]
        if namespace:call+=['-n',namespace]
        obj=oc(*call,'-o','json',optional=True);objects[kind]=obj
        if obj:
            m=obj['metadata'];assert not m.get('deletionTimestamp') and not m.get('ownerReferences'),'Foreign/terminating identity object'
            if kind=='keycloakrealmimport':assert obj['spec']['keycloakCRName']=='keycloak' and obj['spec']['realm'].get('attributes',{}).get('stage060-managed')==MARKER
            else:assert m.get('labels',{}).get('app.kubernetes.io/managed-by')=='stage060-identity'
    runtime=objects['secret'];oauth=objects['oauthclient'];seed=objects['keycloakrealmimport']
    if runtime:
        assert seed and runtime['metadata']['annotations']['demo.rhoai.io/realm-import-uid']==seed['metadata']['uid'],'Foreign credential owner'
        data={k:base64.b64decode(v).decode() for k,v in runtime['data'].items()}
        assert set(data)=={'broker-client-secret','bootstrap-client-secret'} and all(len(v)>=32 for v in data.values())
        if oauth:assert oauth['secret']==data['broker-client-secret'] and oauth['metadata']['annotations']['demo.rhoai.io/realm-import-uid']==seed['metadata']['uid'],'Partial/mismatched OAuth credentials'
        if realm:
            found=api('/clients?clientId=openshell-bootstrap')
            if found:assert api('/clients/'+found[0]['id']+'/client-secret')['value']==data['bootstrap-client-secret'],'Bootstrap credential rotation refused'
    else:assert oauth is None and broker is None and not bootstrap_clients,'Partial credential-bearing identity state; rotation refused'
# Native offline RealmImport can leave master admin composite caches stale (upstream #45966).
# One supported cache refresh is allowed only after our exact managed import completed.
if not args.preflight:
    candidate=api('')
    if not candidate.get('attributes') and not candidate.get('id'):
        try:api('/roles')
        except IdentityFailure as failure:
            if failure.status!=403:raise
            seed=oc('get','keycloakrealmimport','stage060-openshell','-n',NS,'-o','json')
            assert seed['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id')==APP+':k8s.keycloak.org/KeycloakRealmImport:keycloak/stage060-openshell'
            assert seed['spec']['keycloakCRName']=='keycloak' and seed['spec']['realm']['attributes']['stage060-managed']==MARKER
            assert any(c['type']=='Done' and c['status']=='True' for c in seed['status']['conditions'])
            username=base64.b64decode(admin['data']['username']).decode()
            users=request('/admin/realms/master/users?username='+urllib.parse.quote(username)+'&exact=true',token=token);assert len(users)==1
            effective=request('/admin/realms/master/users/'+users[0]['id']+'/role-mappings/realm/composite',token=token)
            assert any(r['name']=='admin' for r in effective),'Effective master admin required for cache recovery'
            request('/admin/realms/master/clear-realm-cache','POST',token=token)
            with http.open(urllib.request.Request(base+'/realms/master/protocol/openid-connect/token',data=body),timeout=15) as response:token=json.load(response)['access_token']
            print('Native master cache refreshed once; original identity guards retained')
identity_preflight()
if args.preflight:
    print('Identity preflight PASS; no mutation')
    raise SystemExit(0)
realm=api('');assert realm.get('attributes',{}).get('stage060-managed')==MARKER,'Foreign realm'
assert realm['registrationAllowed'] is False and realm['editUsernameAllowed'] is False
flow=next(x for x in api('/authentication/flows') if x['alias']=='openshell-prelinked-only')
executions=api('/authentication/flows/openshell-prelinked-only/executions');assert len(executions)==1 and executions[0]['providerId']=='deny-access-authenticator' and executions[0]['requirement']=='REQUIRED'
import_cr=oc('get','keycloakrealmimport','stage060-openshell','-n',NS,'-o','json');import_uid=import_cr['metadata']['uid']
# Fail before credential/OAuth writes if an existing curated account is foreign.
for name in ('ai-admin','ai-developer'):
    user=oc('get','user',name,'-o','json');external_id=user['metadata']['uid']
    found=api('/users?username='+name+'&exact=true');assert len(found)<=1
    if found:
        u=found[0];assert u.get('attributes',{}).get('stage060-managed')==[MARKER] and u['attributes'].get('openshift-uid')==[external_id],'Foreign curated identity'
        links=api('/users/'+u['id']+'/federated-identity')
        assert not links or links==[{'identityProvider':'openshift-v4','userId':external_id,'userName':name}],'Foreign broker link'
owned=oc('get','secret','stage060-openshell-auth','-n',NS,'-o','json',optional=True)
def metadata_owned(x):
    m=x['metadata'];assert not m.get('ownerReferences') and not m.get('deletionTimestamp')
    assert m.get('labels',{}).get('app.kubernetes.io/managed-by')=='stage060-identity'
    assert m.get('annotations',{}).get('demo.rhoai.io/realm-import-uid')==import_uid
if owned:
    metadata_owned(owned);values={k:base64.b64decode(v).decode() for k,v in owned['data'].items()}
    assert set(values)=={'broker-client-secret','bootstrap-client-secret'} and all(len(v)>=32 for v in values.values())
else:
    assert oc('get','oauthclient',BROKER,'-o','json',optional=True) is None,'Partial foreign credential state'
    values={k:secrets.token_urlsafe(48) for k in ('broker-client-secret','bootstrap-client-secret')}
    owned={'apiVersion':'v1','kind':'Secret','metadata':{'name':'stage060-openshell-auth','namespace':NS,'labels':{'app.kubernetes.io/managed-by':'stage060-identity','demo.rhoai.io/stage':'060'},'annotations':{'demo.rhoai.io/realm-import-uid':import_uid}},'type':'Opaque','stringData':values}
    oc('create','-f','-','-o','json',payload=owned)
redirect=issuer+'/broker/openshift-v4/endpoint'
oauth={'apiVersion':'oauth.openshift.io/v1','kind':'OAuthClient','metadata':{'name':BROKER,'labels':{'app.kubernetes.io/managed-by':'stage060-identity','demo.rhoai.io/stage':'060'},'annotations':{'demo.rhoai.io/realm-import-uid':import_uid}},'secret':values['broker-client-secret'],'redirectURIs':[redirect],'grantMethod':'prompt','scopeRestrictions':[{'literals':['user:info']}]}
old=oc('get','oauthclient',BROKER,'-o','json',optional=True)
if old:
    metadata_owned(old);assert old['secret']==oauth['secret'],'Credential rotation refused'
    changes=[{'op':'test','path':'/metadata/uid','value':old['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':old['metadata']['resourceVersion']}]
    for k in ('redirectURIs','grantMethod','scopeRestrictions'):changes.append({'op':'add','path':'/'+k,'value':oauth[k]})
    # JSONPatch is supplied through a private temporary stdin file descriptor, not shell arguments.
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w',prefix='stage060-patch-',delete=True) as f:
        json.dump(changes,f);f.flush();oc('patch','oauthclient',BROKER,'--type=json','--patch-file='+f.name,'-o','json')
else:oc('create','-f','-','-o','json',payload=oauth)
idp={'alias':'openshift-v4','displayName':'OpenShift','providerId':'openshift-v4','enabled':True,'trustEmail':False,'storeToken':False,'addReadTokenRoleOnCreate':False,'firstBrokerLoginFlowAlias':'openshell-prelinked-only','config':{'baseUrl':server,'clientId':BROKER,'clientSecret':values['broker-client-secret'],'defaultScope':'user:info','syncMode':'IMPORT','stage060-managed':MARKER}}
existing=api('/identity-provider/instances/openshift-v4',optional=True)
if existing:assert existing['providerId']=='openshift-v4' and existing['config']['clientId']==BROKER
api('/identity-provider/instances'+('/openshift-v4' if existing else ''),'PUT' if existing else 'POST',idp)
roles={name:api('/roles/'+name) for name in ('openshell-user','openshell-platform-admin')}
mapper={'name':'openshell-resource-audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper','consentRequired':False,'config':{'included.client.audience':'openshell-gateway','id.token.claim':'false','access.token.claim':'true','introspection.token.claim':'true'}}
clients=[{'clientId':'openshell-cli','publicClient':True,'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'redirectUris':['http://127.0.0.1/*'],'attributes':{'pkce.code.challenge.method':'S256','oauth2.device.authorization.grant.enabled':'true','stage060-managed':MARKER}}, {'clientId':'openshell-bootstrap','publicClient':False,'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'serviceAccountsEnabled':True,'secret':values['bootstrap-client-secret'],'attributes':{'stage060-managed':MARKER}}]
client_ids={}
for c in clients:
    c.update({'enabled':True,'protocol':'openid-connect','fullScopeAllowed':False,'protocolMappers':[mapper]})
    found=api('/clients?clientId='+c['clientId']);assert len(found)<=1
    if found:assert found[0].get('attributes',{}).get('stage060-managed')==MARKER
    api('/clients'+('/'+found[0]['id'] if found else ''),'PUT' if found else 'POST',c)
    cid=api('/clients?clientId='+c['clientId'])[0]['id'];client_ids[c['clientId']]=cid
    names=['openshell-user'] if c['clientId']=='openshell-cli' else ['openshell-platform-admin']
    api('/clients/'+cid+'/scope-mappings/realm','POST',[roles[n] for n in names])
bootstrap=api('/clients/'+client_ids['openshell-bootstrap']+'/service-account-user')
api('/users/'+bootstrap['id']+'/role-mappings/realm','POST',[roles['openshell-platform-admin']])
subjects={}
for name in ('ai-admin','ai-developer'):
    user=oc('get','user',name,'-o','json');external_id=user['metadata']['uid'];assert external_id
    users=api('/users?username='+name+'&exact=true');assert len(users)<=1
    if not users:
        api('/users','POST',{'username':name,'enabled':True,'emailVerified':False,'attributes':{'stage060-managed':[MARKER],'openshift-uid':[external_id]}})
        users=api('/users?username='+name+'&exact=true')
    u=users[0];assert u.get('attributes',{}).get('stage060-managed')==[MARKER] and u['attributes'].get('openshift-uid')==[external_id],'Foreign user'
    links=api('/users/'+u['id']+'/federated-identity');expected_link={'identityProvider':'openshift-v4','userId':external_id,'userName':name}
    if links:assert links==[expected_link],'Foreign federation link'
    else:api('/users/'+u['id']+'/federated-identity/openshift-v4','POST',expected_link)
    credentials=api('/users/'+u['id']+'/credentials');assert not credentials,'Password/credential enrollment is not permitted'
    assert not api('/users/'+u['id']+'/groups'),'Unexpected group role grants'
    current=api('/users/'+u['id']+'/role-mappings/realm/composite');assert not any(r['name']=='openshell-platform-admin' for r in current)
    api('/users/'+u['id']+'/role-mappings/realm','POST',[roles['openshell-user']]);subjects[name]=u['id']
print(json.dumps({'realm':REALM,'broker_scope':'user:info','curated_personas':list(subjects),'unknown_broker_enrollment':'denied','role':'openshell-user','credentials':'retained/runtime-only'}))
