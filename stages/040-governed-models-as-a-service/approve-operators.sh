#!/usr/bin/env bash
# Approve only source-selected native CSVs; leave later upgrades for review.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/base" | ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact.select{|x|x["kind"]=="Subscription"})' > /private/tmp/stage040-selected-subscriptions.json
python3 - <<'PY'
import json,subprocess,time
selected=json.load(open('/private/tmp/stage040-selected-subscriptions.json'))
assert selected,'No reviewed native operator Subscriptions'
allowed={s['spec']['startingCSV'] for s in selected}
def run(args,payload=None):
 r=subprocess.run(['oc','--request-timeout=10s']+args,input=json.dumps(payload) if payload else None,capture_output=True,text=True,timeout=15)
 if r.returncode:raise RuntimeError('Native OLM API operation failed')
 return json.loads(r.stdout) if r.stdout.strip() else None
for expected in selected:
 name=expected['metadata']['name'];ns=expected['metadata']['namespace'];csv=expected['spec']['startingCSV'];deadline=time.monotonic()+900
 assert expected['spec']['installPlanApproval']=='Manual','Source must retain reviewed Manual lifecycle'
 while time.monotonic()<deadline:
  sub=run(['get','subscription',name,'-n',ns,'--ignore-not-found','-o','json'])
  if sub:
   assert sub['spec']['installPlanApproval']=='Manual' and sub['spec'].get('startingCSV')==csv,'Selected Subscription intent differs'
   if sub.get('status',{}).get('installedCSV')==csv:
    installed=run(['get','csv',csv,'-n',ns,'-o','json'])
    if installed.get('status',{}).get('phase')=='Succeeded':break
   ipname=sub.get('status',{}).get('installPlanRef',{}).get('name')
   if ipname:
    ip=run(['get','installplan',ipname,'-n',ns,'-o','json'])
    assert any(o.get('uid')==sub['metadata']['uid'] for o in ip['metadata'].get('ownerReferences',[])),'Foreign InstallPlan owner'
    versions=set(ip['spec'].get('clusterServiceVersionNames',[]));assert csv in versions and versions<=allowed,'InstallPlan includes unreviewed operator versions'
    if not ip['spec'].get('approved'):
     patch=[{'op':'test','path':'/metadata/resourceVersion','value':ip['metadata']['resourceVersion']},{'op':'replace','path':'/spec/approved','value':True}]
     run(['patch','installplan',ipname,'-n',ns,'--type=json','--patch-file=/dev/stdin','-o','json'],patch)
  time.sleep(5)
 else:raise RuntimeError('Selected operator readiness timed out: '+name)
 print('PASS Selected native operator: '+name)
PY
