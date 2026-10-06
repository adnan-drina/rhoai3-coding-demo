#!/usr/bin/env bash
# Install reviewed prerequisites; explicit controller approval remains a separate gate.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
# Use a caller-selected interpreter with the native bundle YAML parser installed.
PYTHON="${RHOAI_STAGE060_PYTHON:-python3}"
"$PYTHON" -c 'import yaml' || { echo 'PyYAML is required for exact native bundle inventory; set RHOAI_STAGE060_PYTHON' >&2; exit 1; }
REVISION="${RHOAI_STAGE060_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$(git -C "$REPO_ROOT" ls-remote origin refs/heads/codex/stage-010-foundation-35 | awk '{print $1}')" == "$REVISION" ]] || { echo 'Published revision mismatch' >&2; exit 1; }
git -C "$REPO_ROOT" diff --exit-code "$REVISION" -- gitops/stages/060-agent-runtime-and-agentops gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-runtime.yaml "$SCRIPT_DIR" >/dev/null
if [[ "${1:-}" == '--finish' ]]; then
  python3 "$SCRIPT_DIR/setup-runtime.py" --revision "$REVISION"
  ARGOCD_NAMESPACE=openshift-gitops argocd --core app wait 060-agent-runtime-and-agentops-runtime --app-namespace openshift-gitops --sync --operation --timeout 360
  exit
fi
# Fail closed on foreign App or resource ownership before the first component write.
python3 - "$REVISION" <<'PY'
import json,subprocess,sys
app='060-agent-runtime-and-agentops-runtime'
def get(kind,name,ns):
 r=subprocess.run(['oc','--request-timeout=15s','get',kind,name,'-n',ns,'--ignore-not-found','-o','json'],capture_output=True,text=True)
 assert r.returncode==0,'Preflight read failed'
 return json.loads(r.stdout) if r.stdout.strip() else None
a=get('application',app,'openshift-gitops')
if a:
 m=a['metadata'];s=a['spec'];assert not m.get('ownerReferences') and not m.get('deletionTimestamp') and not a.get('operation') and 'sources' not in s
 assert s['project']=='rhoai-demo' and s['source']['repoURL']=='https://github.com/adnan-drina/rhoai3-coding-demo.git' and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/runtime'
 assert s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshell'}
 assert a.get('status',{}).get('operationState',{}).get('phase') not in ('Running','Terminating')
for kind,name,ns in [('Namespace',n,'openshell') for n in ('openshell','openshell-admin','openshell-developer','stage060-agent-sandbox-operator')]+[('Subscription','agent-sandbox-operator','stage060-agent-sandbox-operator'),('ConfigMap','stage060-openshell-identity','openshell'),('ConfigMap','stage060-runtime-ready','openshell'),('Secret','stage060-openshell-credentials','openshell')]:
 o=get(kind,name,ns)
 if o:
  m=o['metadata'];group=o['apiVersion'].split('/')[0] if '/' in o['apiVersion'] else ''
  assert not m.get('ownerReferences') and not m.get('deletionTimestamp')
  assert m.get('annotations',{}).get('argocd.argoproj.io/tracking-id')==app+':'+group+'/'+o['kind']+':'+m.get('namespace','openshell')+'/'+name,'Foreign prerequisite'
PY
python3 - "$REPO_ROOT" "$REVISION" <<'PY' | oc --request-timeout=15s apply -f -
import json,pathlib,sys
p=pathlib.Path(sys.argv[1])/'gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-runtime.yaml'
a=json.loads(p.read_text());a['spec']['source']['targetRevision']=sys.argv[2];print(json.dumps(a))
PY
ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync 060-agent-runtime-and-agentops-runtime --app-namespace openshift-gitops --strategy hook --revision "$REVISION" --async --timeout 300
DEADLINE=$((SECONDS+180))
until oc --request-timeout=10s get secret/stage060-openshell-credentials configmap/stage060-openshell-identity configmap/stage060-runtime-ready -n openshell >/dev/null 2>&1; do
  (( SECONDS < DEADLINE )) || { echo 'Runtime prerequisite creation timed out' >&2; exit 1; }
  sleep 5
done
python3 "$SCRIPT_DIR/setup-runtime.py" --revision "$REVISION" --prepare-only
"$PYTHON" "$SCRIPT_DIR/approve-controller.py" --revision "$REVISION"
echo 'Manual controller plan requires permission review. After explicit reviewed approval, rerun with --finish.'
