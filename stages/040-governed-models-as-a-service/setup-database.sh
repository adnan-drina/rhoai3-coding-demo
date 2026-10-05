#!/usr/bin/env bash
# Runtime-only MaaS credentials; never rotate an existing database password.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - "$@" <<'PY'
import argparse,base64,json,secrets,subprocess,time
from urllib.parse import quote
p=argparse.ArgumentParser();p.add_argument('--fresh-database',action='store_true');args=p.parse_args()
ns='models-as-a-service-db';app='040-governed-models-as-a-service'
def oc(arguments,payload=None):
 r=subprocess.run(['oc','--request-timeout=10s']+arguments,input=json.dumps(payload) if payload else None,capture_output=True,text=True,timeout=15)
 if r.returncode:raise RuntimeError('Native database API operation failed; no credential details returned')
 return json.loads(r.stdout) if r.stdout.strip() else None
def get(kind,name,namespace=None):
 return oc(['get',kind,name]+(['-n',namespace] if namespace else [])+['--ignore-not-found','-o','json'])
def safe_secret(obj,name,namespace):
 assert not obj['metadata'].get('ownerReferences') and not obj['metadata'].get('deletionTimestamp'),'Runtime database Secret ownership differs'
 assert obj['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','') in ('',app+':/Secret:'+namespace+'/'+name),'Runtime database Secret tracking differs'
def decode(s,key):
 try:return base64.b64decode(s['data'][key],validate=True).decode()
 except Exception:raise RuntimeError('Existing database Secret has missing or invalid keys') from None
def create(name,namespace,values):
 payload={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':namespace,'labels':{'app.kubernetes.io/name':name,'app.kubernetes.io/component':'configuration','app.kubernetes.io/part-of':'rhoai3-coding-demo','app.kubernetes.io/managed-by':'stage040-runtime'}},'type':'Opaque','stringData':values}
 oc(['create','-f','-','-o','json'],payload)
try:
 deadline=time.monotonic()+300
 while True:
  n=get('namespace',ns)
  if n:
   assert n['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith(app+':'),'Database namespace not owned by Stage040'
   break
  if time.monotonic()>=deadline:raise RuntimeError('Database namespace readiness timed out')
  time.sleep(5)
 existing=get('secret','maas-postgres-credentials',ns)
 infra=get('namespace','redhat-ai-gateway-infra')
 config=get('secret','maas-db-config','redhat-ai-gateway-infra') if infra else None
 assert existing or not config,'Partial retained database configuration forbids credential generation'
 if existing:
  safe_secret(existing,'maas-postgres-credentials',ns)
  user=decode(existing,'POSTGRESQL_USER');password=decode(existing,'POSTGRESQL_PASSWORD');database=decode(existing,'POSTGRESQL_DATABASE')
  assert user=='maas' and database=='maas' and password,'Existing database credentials differ from reviewed contract'
  print('Reusing existing MaaS database credentials')
 else:
  storage=oc(['get','pvc','-n',ns,'-o','json'])
  workload=get('statefulset','maas-postgres',ns)
  assert args.fresh_database or not(storage['items'] or workload),'Retained database has no credentials; restore original Secret'
  if args.fresh_database:
   assert not storage['items'],'Storage appeared after clean-install preflight; refusing new credentials'
   if workload:assert workload['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','').startswith(app+':'),'Foreign PostgreSQL workload appeared'
  user=database='maas';password=secrets.token_hex(24)
  create('maas-postgres-credentials',ns,{'POSTGRESQL_USER':user,'POSTGRESQL_PASSWORD':password,'POSTGRESQL_DATABASE':database})
 uri=f'postgresql://{quote(user,safe="")}:{quote(password,safe="")}@maas-postgres.{ns}.svc.cluster.local:5432/{quote(database,safe="")}?sslmode=disable'
 deadline=time.monotonic()+600
 while not get('namespace','redhat-ai-gateway-infra'):
  if time.monotonic()>=deadline:raise RuntimeError('Native AIGateway infrastructure namespace readiness timed out')
  time.sleep(5)
 config=get('secret','maas-db-config','redhat-ai-gateway-infra')
 if config:
  safe_secret(config,'maas-db-config','redhat-ai-gateway-infra')
  assert decode(config,'DB_CONNECTION_URL')==uri,'Existing MaaS DB URI differs; restore matching original configuration'
 else:create('maas-db-config','redhat-ai-gateway-infra',{'DB_CONNECTION_URL':uri})
 print('PASS MaaS runtime database configuration; plaintext transport remains namespace-scoped demo intent')
except (RuntimeError,AssertionError) as e:
 raise SystemExit('ERROR: '+str(e)) from None
PY
