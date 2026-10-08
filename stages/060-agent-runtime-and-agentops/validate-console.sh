#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
python3 - <<'PY'
import json,os,subprocess
def get(kind,name,ns):
 return json.loads(subprocess.check_output(['oc','--request-timeout=10s','get',kind,name,'-n',ns,'-o','json'],stderr=subprocess.PIPE,timeout=15))
a=get('application','agent-console','openshift-gitops');s=a['spec'];st=a['status']
assert s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/agent-console' and s['project']=='rhoai-demo','Unexpected component source'
assert st['sync']['status']=='Synced' and st['sync']['revision']==s['source']['targetRevision'] and st['health']['status']=='Healthy' and st['operationState']['phase']=='Succeeded' and st['operationState']['syncResult']['revision']==s['source']['targetRevision'],'Console source not reconciled'
assert get('odhdashboardconfig','odh-dashboard-config','redhat-ods-applications')['spec']['dashboardConfig'].get('agentOps') is True,'AgentOps flag not enabled'
for user,ns,foreign in [('ai-admin','openshell-admin','openshell-developer'),('ai-developer','openshell-developer','openshell-admin')]:
 for resource in ['sandboxes.agents.x-k8s.io','services']:
  for verb in ['get','list']:
   r=subprocess.run(['oc','auth','can-i',verb,resource,'-n',ns,'--as='+user],capture_output=True,text=True,timeout=15)
   assert r.returncode==0 and r.stdout.strip()=='yes','Own console discovery permission missing'
 for verb in ['create','delete']:
  r=subprocess.run(['oc','auth','can-i',verb,'sandboxes.agents.x-k8s.io','-n',ns,'--as='+user],capture_output=True,text=True,timeout=15)
  assert r.returncode==1 and r.stdout.strip()=='no','Human Sandbox lifecycle permission unexpectedly granted'
 r=subprocess.run(['oc','auth','can-i','list','sandboxes.agents.x-k8s.io','-n',foreign,'--as='+user],capture_output=True,text=True,timeout=15)
 assert r.returncode==1 and r.stdout.strip()=='no','Foreign Sandbox discovery permission unexpectedly granted'
print('PASS Console configuration and native read-only authorization; no positive agent instance or browser workflow claimed')
PY
