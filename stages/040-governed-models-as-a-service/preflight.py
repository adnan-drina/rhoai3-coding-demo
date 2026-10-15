#!/usr/bin/env python3
"""Read-only Stage040 ownership and retained database prerequisites."""
import base64,json,os,subprocess,sys
from pathlib import Path
from urllib.parse import quote,urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/shared'))
import stage_apps
def get(kind,name=None,ns=None):
 command=['oc','--request-timeout=10s','get',kind]+([name] if name else [])+(['-n',ns] if ns else [])+(['--ignore-not-found'] if name else [])+['-o','json']
 r=subprocess.run(command,capture_output=True,text=True,timeout=15)
 if r.returncode:raise RuntimeError('Prerequisite API read failed')
 return json.loads(r.stdout) if r.stdout.strip() else None
def reconciled(x):
 s=x.get('status',{});source=x['spec']['source'];op=s.get('operationState',{});result=op.get('syncResult',{})
 return s.get('sync',{}).get('status')=='Synced' and s['sync'].get('revision')==source['targetRevision'] and s.get('health',{}).get('status')=='Healthy' and op.get('phase')=='Succeeded' and result.get('revision')==source['targetRevision'] and result.get('source',{}).get('path')==source['path']
def tracked(x):
 # Exact tracking id of the Stage 040 component Application that renders x.
 return stage_apps.tracked('040',x)
try:
 for kind,namespace in [('serviceaccount','redhat-ods-applications'),('clusterrole',None),('clusterrolebinding',None),('job','redhat-ods-applications')]:
  item=get(kind,'prepare-maas-route-access',namespace)
  if item:
   assert tracked(item) and not item['metadata'].get('deletionTimestamp'),'Namespace-label helper is foreign or terminating'
   assert not item['metadata'].get('ownerReferences'),'Namespace-label helper has foreign ownership'
   if kind=='clusterrolebinding':
    assert item['roleRef']=={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'prepare-maas-route-access'} and item['subjects']==[{'kind':'ServiceAccount','name':'prepare-maas-route-access','namespace':'redhat-ods-applications'}],'Namespace-label binding differs'
   if kind=='clusterrole':
    assert item['rules']==[{'apiGroups':[''],'resources':['namespaces'],'resourceNames':['redhat-ods-applications','redhat-ai-gateway-infra'],'verbs':['get','patch']}],'Namespace-label permission scope differs'
 foundation=stage_apps.stage_problems('010')
 assert not foundation,'Stage 010 must be reconciled: '+'; '.join(foundation)
 serving=get('applications.argoproj.io','030-private-model-serving','openshift-gitops')
 assert serving and reconciled(serving),'Serving exact source/path must be reconciled'
 a=serving['spec'];assert not serving['metadata'].get('ownerReferences') and not serving['metadata'].get('deletionTimestamp') and not a.get('sources'),'Prerequisite Application ownership differs'
 assert a['project']=='rhoai-demo' and a['source']['repoURL']==os.environ['GIT_REPO_URL'] and a['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Prerequisite Application repository/destination differs'
 assert a['source']['path']=='gitops/stages/030-private-model-serving/030-private-model-serving','Prerequisite source path differs'
 paths=stage_apps.delegated('010','DataScienceCluster','default-dsc',group='datasciencecluster.opendatahub.io')
 assert {'/spec/components/aigateway','/spec/components/ogx'}<=paths,'Complete the reviewed retention-safe AIGateway/Studio delegation before Stage040'
 dashboard_paths=stage_apps.delegated('010','OdhDashboardConfig','odh-dashboard-config','redhat-ods-applications','opendatahub.io')
 assert {'/spec/dashboardConfig/'+field for field in ['genAiStudio','genAiTracing','modelAsService','vLLMDeploymentOnMaaS','externalModels','llmdTemplates','guardrails','agentConfigManagement','promptManagement']}<=dashboard_paths,'Complete reviewed dashboard delegation before Stage040'
 assert not get('applications.argoproj.io','040-governed-models-as-a-service','openshift-gitops'),'Retired single Stage040 Application still exists; finish the component move (docs/OPERATIONS.md)'
 for desired in stage_apps.components('040'):
  existing=get('applications.argoproj.io',desired['metadata']['name'],'openshift-gitops')
  if existing:
   e=existing['spec'];assert not existing['metadata'].get('ownerReferences') and not existing['metadata'].get('deletionTimestamp') and not e.get('sources'),'Foreign or terminating Application'
   assert e['project']=='rhoai-demo' and e['source']['repoURL']==os.environ['GIT_REPO_URL'] and e['source']['path']==desired['spec']['source']['path'],'Unexpected Application source'
   assert e['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected Application destination'
 for ns in ['models-as-a-service','internal-models','models-as-a-service-db','kuadrant-system','external-models','openshift-lws-operator']:
  n=get('namespace',ns)
  if n:assert not n['metadata'].get('ownerReferences') and not n['metadata'].get('deletionTimestamp') and tracked(n),'Existing namespace requires reviewed adoption'
 # Existing same-name customer resources must already belong to this stage.
 for resource,name,namespace in [
  ('gateways.gateway.networking.k8s.io','maas-default-gateway','openshift-ingress'),
  ('configmap','authorino-service-ca','kuadrant-system')]:
  obj=get(resource,name,namespace)
  if obj:assert tracked(obj) and not obj['metadata'].get('deletionTimestamp') and not obj['metadata'].get('ownerReferences'),'Existing customer resource requires reviewed adoption'
 for name in ['single-node-queue-router','single-node-exclusive-gpu']:
  obj=get('llminferenceserviceconfigs.serving.kserve.io',name,'redhat-ods-applications')
  if obj:assert tracked(obj) and not obj['metadata'].get('deletionTimestamp') and not obj['metadata'].get('ownerReferences'),'Existing reusable serving template requires reviewed adoption'
 for name,namespace in [('rhcl-operator','openshift-operators'),('authorino-operator','openshift-operators'),('dns-operator','openshift-operators'),('limitador-operator','openshift-operators'),('servicemeshoperator3','openshift-operators'),('leader-worker-set','openshift-lws-operator')]:
  subscription=get('subscriptions.operators.coreos.com',name,namespace)
  if subscription:assert tracked(subscription) and not subscription['metadata'].get('deletionTimestamp'),'Existing operator Subscription requires reviewed native adoption'
 # The Gateway terminates TLS with the cluster's cert-manager ingress certificate; require that source (no copy).
 ingress=get('ingresscontrollers.operator.openshift.io','default','openshift-ingress-operator')
 assert ingress and ingress['spec'].get('defaultCertificate',{}).get('name')=='cert-manager-ingress-cert','Ingress certificate source requires review'
 result=subprocess.run(['oc','--request-timeout=10s','get','secret','cert-manager-ingress-cert','-n','openshift-ingress','-o','go-template={{if index .data "tls.crt"}}crt{{end}}|{{if index .data "tls.key"}}key{{end}}'],capture_output=True,text=True,timeout=15)
 assert result.returncode==0 and result.stdout=='crt|key','Gateway certificate Secret is incomplete'
 database=get('statefulset','maas-postgres','models-as-a-service-db')
 db_namespace=get('namespace','models-as-a-service-db');storage=get('pvc',ns='models-as-a-service-db') if db_namespace else {'items':[]}
 assert storage is not None or db_namespace is None,'Unexpected empty storage API response in existing namespace'
 pvcs=storage['items'] if storage is not None else []
 # Secret existence checks retrieve metadata only, never credential data.
 def secret_present(name,ns):
  r=subprocess.run(['oc','--request-timeout=10s','get','secret',name,'-n',ns,'--ignore-not-found','-o','jsonpath={.metadata.uid}'],capture_output=True,text=True,timeout=15)
  assert r.returncode==0,'Secret metadata read failed';return bool(r.stdout)
 assert (secret_present('openai-provider-api-key','external-models') or secret_present('openai-provider-api-key','models-as-a-service') or os.environ.get('OPENAI_API_KEY') or os.environ.get('RHOAI_OPENAI_API_KEY')), 'Authorized external provider credential must be available before deployment'
 assert secret_present('anthropic-provider-api-key','external-models') or os.environ.get('ANTHROPIC_API_KEY'),'Authorized Anthropic provider credential must be available'
 assert secret_present('nvidia-provider-api-key','external-models') or os.environ.get('NVIDIA_API_KEY'),'Authorized NVIDIA provider credential must be available'
 credential=secret_present('maas-postgres-credentials','models-as-a-service-db');config=secret_present('maas-db-config','redhat-ai-gateway-infra')
 legacy_config=secret_present('maas-db-config','redhat-ods-applications')
 assert credential or not(database or pvcs or config or legacy_config),'Partial retained database forbids credential generation'
 if credential:
  secret=get('secret','maas-postgres-credentials','models-as-a-service-db')
  assert not secret['metadata'].get('ownerReferences') and not secret['metadata'].get('deletionTimestamp'),'Database credential ownership differs'
  assert stage_apps.runtime_tracking_ok('040',secret),'Database credential tracking differs'
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
    assert stage_apps.runtime_tracking_ok('040',connection),'MaaS database configuration tracking differs'
    assert decode(connection,'DB_CONNECTION_URL')==uri,'Existing MaaS database configuration differs; restore original matching credentials'
 if database:assert tracked(database) and not database['metadata'].get('deletionTimestamp'),'Unreviewed PostgreSQL ownership'
 for pvc in pvcs:
  assert pvc['metadata']['name']=='data-maas-postgres-0' and pvc.get('status',{}).get('phase')=='Bound' and not pvc['metadata'].get('deletionTimestamp'),'Unexpected or unavailable retained database storage'
  assert database and all(o.get('uid')==database['metadata']['uid'] for o in pvc['metadata'].get('ownerReferences',[])),'Database PVC owner differs'
 sc=get('storageclass','gp3-csi');assert sc and sc['provisioner']=='ebs.csi.aws.com','Reviewed gp3 storage unavailable'
 print('fresh' if not(credential or database or pvcs or config) else 'retained')
except (RuntimeError,AssertionError,KeyError,ValueError,TypeError) as e:
 print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
