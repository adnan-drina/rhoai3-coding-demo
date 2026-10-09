#!/usr/bin/env bash
# Reuse the authorized provider credential; values never enter Git or command arguments.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$ROOT_DIR"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - <<'PY'
import base64,json,os,subprocess,time
NS='external-models';NAME=os.environ.get('RHOAI_STAGE040_PROVIDER_SECRET','openai-provider-api-key');assert NAME in ('openai-provider-api-key','anthropic-provider-api-key'),'Unreviewed provider credential';APP='040-governed-models-as-a-service'
ROTATE=os.environ.get('RHOAI_STAGE040_ROTATE_PROVIDER_SECRET','false').lower()
assert ROTATE in ('true','false'),'Rotation flag must be explicitly true or false'
assert ROTATE!='true' or NAME=='openai-provider-api-key','Explicit rotation is scoped to the OpenAI provider'
def get(ns):
 r=subprocess.run(['oc','--request-timeout=10s','get','secret',NAME,'-n',ns,'--ignore-not-found','-o','json'],capture_output=True,text=True,timeout=15)
 if r.returncode:raise RuntimeError('Provider credential read failed')
 return json.loads(r.stdout) if r.stdout.strip() else None
try:
 for _ in range(60):
  r=subprocess.run(['oc','--request-timeout=10s','get','namespace',NS,'--ignore-not-found','-o','json'],capture_output=True,text=True,timeout=15)
  if r.returncode:raise RuntimeError('Provider namespace read failed')
  if r.stdout.strip():
   n=json.loads(r.stdout);assert n['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id')==APP+':/Namespace:openshift-gitops/'+NS,'Provider namespace ownership differs';break
  time.sleep(5)
 else:raise RuntimeError('Provider namespace did not reconcile')
 target=get(NS)
 if target:
  assert target['metadata'].get('annotations',{}).get('argocd.argoproj.io/tracking-id','') in ('', APP+':/Secret:'+NS+'/'+NAME),'Existing provider credential is tracked by another Application'
  assert not target['metadata'].get('ownerReferences') and not target['metadata'].get('deletionTimestamp'),'Existing provider credential requires reviewed ownership'
  encoded=target.get('data',{}).get('api-key','');assert base64.b64decode(encoded,validate=True),'Existing provider credential is incomplete'
  assert target['metadata'].get('labels',{}).get('inference.llm-d.ai/ipp-managed')=='true','Existing native provider credential metadata differs'
  if ROTATE=='true':
   value=os.environ.get('OPENAI_API_KEY');assert value,'Fresh authorized OpenAI credential is unavailable'
   replacement=base64.b64encode(value.encode()).decode()
   if replacement!=encoded:
    patch=[{'op':'test','path':'/metadata/uid','value':target['metadata']['uid']},{'op':'test','path':'/metadata/resourceVersion','value':target['metadata']['resourceVersion']},{'op':'replace','path':'/data/api-key','value':replacement}]
    r=subprocess.run(['oc','--request-timeout=10s','patch','secret',NAME,'-n',NS,'--type=json','--patch-file=/dev/stdin'],input=json.dumps(patch),capture_output=True,text=True,timeout=15)
    if r.returncode:raise RuntimeError('Scoped provider credential rotation failed; response suppressed')
    after=get(NS)
    assert after['metadata']['uid']==target['metadata']['uid'] and after['metadata'].get('labels')==target['metadata'].get('labels'),'Provider identity or labels changed during rotation'
    assert after.get('type')==target.get('type') and after.get('data')=={**target['data'],'api-key':replacement},'Provider credential readback differs'
   print('PASS Authorized OpenAI credential matches the retained native Secret; identity and labels preserved.')
  else:
   print('PASS Existing native provider credential reused without rotation.')
 else:
  assert ROTATE!='true','Explicit rotation requires the existing owned provider credential'
  prior=get('models-as-a-service')
  if prior:
   assert not prior['metadata'].get('deletionTimestamp'),'Prior credential is terminating'
   encoded=prior.get('data',{}).get('api-key','');assert base64.b64decode(encoded,validate=True),'Prior authorized credential is incomplete'
  else:
   value=(os.environ.get('OPENAI_API_KEY') or os.environ.get('RHOAI_OPENAI_API_KEY')) if NAME=='openai-provider-api-key' else os.environ.get('ANTHROPIC_API_KEY');assert value,'Authorized provider credential is unavailable'
   encoded=base64.b64encode(value.encode()).decode()
  secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':NAME,'namespace':NS,'labels':{'inference.llm-d.ai/ipp-managed':'true','app.kubernetes.io/part-of':'rhoai3-coding-demo'}},'type':'Opaque','data':{'api-key':encoded}}
  r=subprocess.run(['oc','--request-timeout=10s','create','-f','-'],input=json.dumps(secret),capture_output=True,text=True,timeout=15)
  if r.returncode:raise RuntimeError('Native provider credential creation failed; inspect ownership before retry')
  print('PASS Authorized provider credential supplied through private standard input.')
except Exception as e:
 print('ERROR: '+(str(e) if isinstance(e,(AssertionError,RuntimeError)) else type(e).__name__))
 raise SystemExit(1)
PY
