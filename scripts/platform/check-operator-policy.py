#!/usr/bin/env python3
"""Read-only catalog/readiness checks for source-selected Automatic Subscriptions."""
import argparse,json,os,pathlib,re,subprocess,time
p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--wait',type=int,default=0);p.add_argument('--verify',action='store_true');a=p.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[2]
guard=subprocess.run(['bash','-c','set -euo pipefail; REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; source "$1/scripts/shared/lib.sh"; load_env >/dev/null; check_oc_logged_in >/dev/null; python3 -c "$2"','guard',str(ROOT),'import json,os; print(json.dumps({k:os.environ[k] for k in ("PATH","KUBECONFIG","RHOAI_OPERATOR_CREDENTIAL_MODE") if k in os.environ}))'],capture_output=True,text=True,timeout=45)
assert guard.returncode==0,'Canonical environment/cluster guard failed'
os.environ.update(json.loads(guard.stdout))
def command(argv):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=30)
 if r.returncode:raise RuntimeError('Native operator read/render failed: '+argv[0])
 return r.stdout
def get(kind,name='',ns='',missing=False):
 args=['oc','--request-timeout=15s','get',kind]
 if name:args.append(name)
 if ns:args+=['-n',ns]
 if missing:args.append('--ignore-not-found')
 value=command(args+['-o','json']);return json.loads(value) if value.strip() else None
raw=command(['oc','kustomize',a.manifest]) if pathlib.Path(a.manifest).is_dir() else pathlib.Path(a.manifest).read_text()
r=subprocess.run(['ruby','-ryaml','-rjson','-e','puts JSON.generate(YAML.load_stream(STDIN.read).compact.select{|o|o["kind"]=="Subscription"})'],input=raw,text=True,capture_output=True,timeout=30)
assert r.returncode==0,'Subscription render failed';selected=json.loads(r.stdout);assert selected,'No selected Subscriptions'
def version(value):
 m=re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-(\d+)|-rhodf)?',value);assert m,'Unsupported operator prerelease/version shape';return tuple(map(int,m.groups()[:3]))+(int(m.group(4) or 0),)
# Qualified release families/minima. Rolling channels are checked at deployment, not frozen.
minimum={'rhods-operator':'3.5.1','openshift-gitops-operator':'1.21.5','odf-operator':'4.22.5','cluster-observability-operator':'1.5.3','opentelemetry-product':'0.158.0-2','tempo-product':'0.22.0-2','nfd':'4.22.0','gpu-operator-certified':'26.7.1','kueue-operator':'1.4.2','leader-worker-set':'1.0.1','rhcl-operator':'1.4.3','authorino-operator':'1.4.3','dns-operator':'1.4.2','limitador-operator':'1.4.2','servicemeshoperator3':'3.4.3','agent-sandbox-operator':'0.9.0'}
channels={'rhods-operator':'stable-3.5','openshift-gitops-operator':'gitops-1.21','odf-operator':'stable-4.22','cluster-observability-operator':'stable','opentelemetry-product':'stable','tempo-product':'stable','nfd':'stable','gpu-operator-certified':'v26.7','kueue-operator':'stable-v1.4','leader-worker-set':'stable-v1.0','rhcl-operator':'stable','authorino-operator':'stable','dns-operator':'stable','limitador-operator':'stable','servicemeshoperator3':'stable-3.4','agent-sandbox-operator':'preview-0.9'}
def compatible(package,value):
 assert package in minimum,'Operator baseline is deferred/unqualified: '+package
 actual,base=version(value),version(minimum[package]);assert actual[:2]==base[:2] and actual>=base,'Unavailable/incompatible operator release: '+package+' '+value
if not (a.wait or a.verify):
 cco=get('cloudcredential','cluster');issuer=get('authentication','cluster').get('spec',{}).get('serviceAccountIssuer','')
 assert cco.get('spec',{}).get('credentialsMode')!='Manual' and not issuer,'Automatic demo install excludes cloud workload-token/Manual credential mode; use the documented cloud-specific lifecycle'
 # Unreported effective credential mode is not inferred from Secrets. The standard
 # fresh demo contract must be supplied by the provisioner; token modes are unsupported.
 assert os.environ.get('RHOAI_OPERATOR_CREDENTIAL_MODE')=='standard','Unknown/nonstandard cloud identity contract; Automatic installation refused'
 catalogs=get('packagemanifest',ns='openshift-marketplace')['items']
 for s in selected:
  x=s['spec'];assert x['installPlanApproval']=='Automatic','Selected subscription is not Automatic'
  assert x.get('channel')==channels.get(x['name']),'Unreviewed release channel'
  matches=[m for m in catalogs if m['metadata']['name']==x['name'] and m.get('status',{}).get('catalogSource')==x['source'] and m['status'].get('catalogSourceNamespace')==x['sourceNamespace']];assert len(matches)==1,'Catalog package/source is missing or ambiguous'
  offered=[c for c in matches[0]['status']['channels'] if c['name']==x['channel']];assert len(offered)==1,'Selected channel unavailable'
  compatible(x['name'],offered[0]['currentCSVDesc']['version'])
  existing=get('subscription',ns=s['metadata']['namespace'])['items']
  for live in existing:
   if live['metadata']['name']==s['metadata']['name']:
    assert all(live['spec'].get(k)==x.get(k) for k in ('name','channel','source','sourceNamespace')),'Existing selected operator has incompatible source/channel scope'
  owned={(o['metadata']['namespace'],o['metadata']['name']) for o in selected}
  assert not any(o['spec'].get('installPlanApproval')=='Manual' and (o['metadata']['namespace'],o['metadata']['name']) not in owned for o in existing),'Foreign Manual subscription blocks namespace Automatic resolution'
 print('PASS Offered catalog/source/channel compatibility; future rolling updates are not frozen')
else:
 deadline=time.monotonic()+a.wait
 for expected in selected:
  while True:
   s=get('subscription',expected['metadata']['name'],expected['metadata']['namespace'],missing=True);e=expected['spec'];ready=False
   assert e['installPlanApproval']=='Automatic' and e['channel']==channels.get(e['name']),'Unreviewed source policy/channel'
   if s:
    x=s['spec'];assert all(x.get(k)==e.get(k) for k in ('name','channel','source','sourceNamespace','installPlanApproval')),'Native Subscription policy differs from source'
    installed=s.get('status',{}).get('installedCSV')
    if installed:
     csv=get('csv',installed,expected['metadata']['namespace'],missing=True)
     if csv:
      compatible(x['name'],csv['spec']['version']);ready=csv.get('status',{}).get('phase')=='Succeeded' and s['status'].get('currentCSV')==installed
   if ready:break
   assert a.wait and time.monotonic()<deadline,'Automatic operator readiness pending; inspect native OLM conditions (no plan is approved by this checker)'
   time.sleep(5)
  print('PASS Automatic current CSV Succeeded: '+x['name'])
