#!/usr/bin/env python3
"""Read-only Stage040 ownership and retained database prerequisites."""
import base64,json,os,subprocess,sys
from urllib.parse import quote,urlparse
APP='040-governed-models-as-a-service'
def get(kind,name=None,ns=None):
 command=['oc','--request-timeout=10s','get',kind]+([name] if name else [])+(['-n',ns] if ns else [])+(['--ignore-not-found'] if name else [])+['-o','json']
 r=subprocess.run(command,capture_output=True,text=True,timeout=15)
 if r.returncode:raise RuntimeError('Prerequisite API read failed')
 return json.loads(r.stdout) if r.stdout.strip() else None
def reconciled(x):
 s=x.get('status',{});source=x['spec']['source'];op=s.get('operationState',{});result=op.get('syncResult',{})
 return s.get('sync',{}).get('status')=='Synced' and s['sync'].get('revision')==source['targetRevision'] and s.get('health',{}).get('status')=='Healthy' and op.get('phase')=='Succeeded' and result.get('revision')==source['targetRevision'] and result.get('source',{}).get('path')==source['path']
def tracked(x):
 group=x['apiVersion'].split('/')[0] if '/' in x['apiVersion'] else ''
 m=x['metadata'];namespace=m.get('namespace') or 'openshift-gitops'
 expected=APP+':'+group+'/'+x['kind']+':'+namespace+'/'+m['name']
 return m.get('annotations',{}).get('argocd.argoproj.io/tracking-id','')==expected
try:
 core=get('applications.argoproj.io','010-openshift-ai-platform-foundation','openshift-gitops')
 serving=get('applications.argoproj.io','030-private-model-serving','openshift-gitops')
 assert core and serving and reconciled(core) and reconciled(serving),'Foundation and serving exact source/path must be reconciled'
 for app in (core,serving):
  a=app['spec'];assert not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp') and not a.get('sources'),'Prerequisite Application ownership differs'
  assert a['project']=='rhoai-demo' and a['source']['repoURL']==os.environ['GIT_REPO_URL'] and a['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Prerequisite Application repository/destination differs'
 assert core['spec']['source']['path'] in ('gitops/stages/010-openshift-ai-platform-foundation/aggregate/overlays/demo','gitops/stages/030-private-model-serving/migration/foundation-omit') and serving['spec']['source']['path']=='gitops/stages/030-private-model-serving/base','Prerequisite source path differs'
 spec=core['spec'];assert 'RespectIgnoreDifferences=true' in spec['syncPolicy']['syncOptions'],'Foundation must respect delegated ownership'
 entries=spec.get('ignoreDifferences',[])
 paths={p for i in entries if i.get('group')=='datasciencecluster.opendatahub.io' and i.get('kind')=='DataScienceCluster' and i.get('name')=='default-dsc' for p in i.get('jsonPointers',[])}
 assert {'/spec/components/aigateway','/spec/components/ogx'}<=paths,'Complete the reviewed retention-safe AIGateway/Studio delegation before Stage040'
 dashboard_paths={p for i in entries if i.get('group')=='opendatahub.io' and i.get('kind')=='OdhDashboardConfig' and i.get('name')=='odh-dashboard-config' and i.get('namespace')=='redhat-ods-applications' for p in i.get('jsonPointers',[])}
 assert {'/spec/dashboardConfig/'+field for field in ['genAiStudio','genAiTracing','modelAsService','vLLMDeploymentOnMaaS','externalModels','llmdTemplates','guardrails','agentConfigManagement','promptManagement']}<=dashboard_paths,'Complete reviewed dashboard delegation before Stage040'
 existing=get('applications.argoproj.io',APP,'openshift-gitops')
 if existing:
  e=existing['spec'];assert not existing['metadata'].get('ownerReferences') and not existing['metadata'].get('deletionTimestamp') and not e.get('sources'),'Foreign or terminating Application'
  assert e['project']=='rhoai-demo' and e['source']['repoURL']==os.environ['GIT_REPO_URL'] and e['source']['path']=='gitops/stages/040-governed-models-as-a-service/base','Unexpected Application source'
  assert e['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected Application destination'
 for ns in ['models-as-a-service','models-as-a-service-db','kuadrant-system','external-models','rhoai-mcp','openshift-lws-operator']:
  n=get('namespace',ns)
  if n:assert not n['metadata'].get('ownerReferences') and not n['metadata'].get('deletionTimestamp') and tracked(n),'Existing namespace requires reviewed adoption'
 # Existing same-name customer resources must already belong to this stage.
 for resource,name,namespace in [
  ('gateways.gateway.networking.k8s.io','maas-default-gateway','openshift-ingress'),
  ('deployment','openshift-mcp','rhoai-mcp'),
  ('configmap','authorino-service-ca','kuadrant-system')]:
  obj=get(resource,name,namespace)
  if obj:assert tracked(obj) and not obj['metadata'].get('deletionTimestamp') and not obj['metadata'].get('ownerReferences'),'Existing customer resource requires reviewed adoption'
 for name,namespace in [('rhcl-operator','openshift-operators'),('authorino-operator','openshift-operators'),('dns-operator','openshift-operators'),('limitador-operator','openshift-operators'),('servicemeshoperator3','openshift-operators'),('leader-worker-set','openshift-lws-operator')]:
  subscription=get('subscriptions.operators.coreos.com',name,namespace)
  if subscription:assert tracked(subscription) and not subscription['metadata'].get('deletionTimestamp'),'Existing operator Subscription requires reviewed native adoption'
 result=subprocess.run(['oc','--request-timeout=10s','get','secret','maas-gateway-tls','-n','openshift-ingress','--ignore-not-found','-o','jsonpath={.metadata}'],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,'Gateway certificate metadata read failed'
 tls={'apiVersion':'v1','kind':'Secret','metadata':json.loads(result.stdout)} if result.stdout.strip() else None
 if tls:assert tracked(tls) and not tls['metadata'].get('ownerReferences') and not tls['metadata'].get('deletionTimestamp'),'Existing gateway certificate requires reviewed adoption'
 database=get('statefulset','maas-postgres','models-as-a-service-db')
 db_namespace=get('namespace','models-as-a-service-db');storage=get('pvc',ns='models-as-a-service-db') if db_namespace else {'items':[]}
 assert storage is not None or db_namespace is None,'Unexpected empty storage API response in existing namespace'
 pvcs=storage['items'] if storage is not None else []
 # Secret existence checks retrieve metadata only, never credential data.
 def secret_present(name,ns):
  r=subprocess.run(['oc','--request-timeout=10s','get','secret',name,'-n',ns,'--ignore-not-found','-o','jsonpath={.metadata.uid}'],capture_output=True,text=True,timeout=15)
  assert r.returncode==0,'Secret metadata read failed';return bool(r.stdout)
 assert (secret_present('openai-provider-api-key','external-models') or secret_present('openai-provider-api-key','models-as-a-service') or os.environ.get('OPENAI_API_KEY') or os.environ.get('RHOAI_OPENAI_API_KEY')), 'Authorized external provider credential must be available before deployment'
 provider_url=urlparse(os.environ.get('REDHAT_MODELS_BASE_URL',''));assert provider_url.scheme=='https' and provider_url.port in (None,443) and provider_url.path in ('','/','/v1','/v1/') and provider_url.hostname and not provider_url.username and not provider_url.password and not provider_url.query and not provider_url.fragment,'Approved Red Hat provider requires a private HTTPS input'
 assert secret_present('redhat-models-provider-api-key','external-models') or secret_present('redhat-models-provider-api-key','models-as-a-service') or os.environ.get('REDHAT_MODELS_API_KEY'),'Authorized Red Hat provider credential must be available'
 credential=secret_present('maas-postgres-credentials','models-as-a-service-db');config=secret_present('maas-db-config','redhat-ai-gateway-infra')
 legacy_config=secret_present('maas-db-config','redhat-ods-applications')
 assert credential or not(database or pvcs or config or legacy_config),'Partial retained database forbids credential generation'
 if credential:
  secret=get('secret','maas-postgres-credentials','models-as-a-service-db')
  assert not secret['metadata'].get('ownerReferences') and not secret['metadata'].get('deletionTimestamp'),'Database credential ownership differs'
  assert secret['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','') in ('',APP+':/Secret:models-as-a-service-db/maas-postgres-credentials'),'Database credential tracking differs'
  def decode(x,key):
   try:return base64.b64decode(x['data'][key],validate=True).decode()
   except Exception:raise RuntimeError('Existing database credential/configuration is incomplete') from None
  user=decode(secret,'POSTGRESQL_USER');password=decode(secret,'POSTGRESQL_PASSWORD');db=decode(secret,'POSTGRESQL_DATABASE')
  assert user==db=='maas' and password,'Existing database credential contract differs'
  uri=f'postgresql://{quote(user,safe="")}:{quote(password,safe="")}@maas-postgres.models-as-a-service-db.svc.cluster.local:5432/{quote(db,safe="")}?sslmode=disable'
  for namespace,present in [('redhat-ai-gateway-infra',config),('redhat-ods-applications',legacy_config)]:
   if present:
    connection=get('secret','maas-db-config',namespace)
    assert not connection['metadata'].get('ownerReferences') and not connection['metadata'].get('deletionTimestamp'),'MaaS database configuration ownership differs'
    assert connection['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','') in ('',APP+':/Secret:'+namespace+'/maas-db-config'),'MaaS database configuration tracking differs'
    assert decode(connection,'DB_CONNECTION_URL')==uri,'Existing MaaS database configuration differs; restore original matching credentials'
 if database:assert tracked(database) and not database['metadata'].get('deletionTimestamp'),'Unreviewed PostgreSQL ownership'
 for pvc in pvcs:
  assert pvc['metadata']['name']=='data-maas-postgres-0' and pvc.get('status',{}).get('phase')=='Bound' and not pvc['metadata'].get('deletionTimestamp'),'Unexpected or unavailable retained database storage'
  assert database and all(o.get('uid')==database['metadata']['uid'] for o in pvc['metadata'].get('ownerReferences',[])),'Database PVC owner differs'
 sc=get('storageclass','gp3-csi');assert sc and sc['provisioner']=='ebs.csi.aws.com','Reviewed gp3 storage unavailable'
 print('fresh' if not(credential or database or pvcs or config) else 'retained')
except (RuntimeError,AssertionError,KeyError,ValueError,TypeError) as e:
 print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
