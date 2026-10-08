#!/usr/bin/env bash
# Install native Automatic prerequisites; runtime functional gates remain separate.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 "$REPO_ROOT/scripts/platform/check-operator-policy.py" "$REPO_ROOT/gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/controller"
# Use the caller-selected Python interpreter for native readiness checks.
PYTHON="${RHOAI_STAGE060_PYTHON:-python3}"
# Core-mode Argo CD reads its settings from the kube-context namespace; refuse before any write.
argocd app sync --help 2>&1 | grep -q -- '--core' || { echo 'An argocd client with --core support is required' >&2; exit 1; }
[[ "$(oc config view --minify -o jsonpath='{.contexts[0].context.namespace}')" == openshift-gitops ]] || { echo 'Set the kube-context namespace to openshift-gitops for argocd --core' >&2; exit 1; }
REVISION="${RHOAI_STAGE060_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$(git -C "$REPO_ROOT" ls-remote origin refs/heads/codex/stage-010-foundation-35 | awk '{print $1}')" == "$REVISION" ]] || { echo 'Published revision mismatch' >&2; exit 1; }
git -C "$REPO_ROOT" diff --exit-code "$REVISION" -- gitops/stages/060-agent-runtime-and-agentops gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-runtime.yaml "$SCRIPT_DIR" scripts/platform/check-operator-policy.py >/dev/null
if [[ "${1:-}" == '--finish' ]]; then
  python3 "$SCRIPT_DIR/setup-runtime.py" --revision "$REVISION"
  ARGOCD_NAMESPACE=openshift-gitops argocd --core app wait openshell-runtime --app-namespace openshift-gitops --sync --operation --timeout 360
  exit
fi
# Fail closed on foreign App or resource ownership before the first component write.
python3 - "$REVISION" <<'PY'
import json,subprocess,sys
app='openshell-runtime'
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
for kind,name,ns in [('Namespace',n,'openshell') for n in ('openshell','openshell-admin','openshell-developer','agent-sandbox-system')]+[('Subscription','agent-sandbox-operator','agent-sandbox-system'),('ConfigMap','openshell-identity','openshell'),('ConfigMap','openshell-runtime-ready','openshell'),('Secret','openshell-credentials','openshell')]:
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
ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync openshell-runtime --app-namespace openshift-gitops --strategy hook --revision "$REVISION" --async --timeout 300
DEADLINE=$((SECONDS+180))
until oc --request-timeout=10s get secret/openshell-credentials configmap/openshell-identity configmap/openshell-runtime-ready -n openshell >/dev/null 2>&1; do
  (( SECONDS < DEADLINE )) || { echo 'Runtime prerequisite creation timed out' >&2; exit 1; }
  sleep 5
done
# Async CLI submission precedes status population; wait only for the exact current operation.
python3 - "$REVISION" <<'PYWAIT'
import json,subprocess,sys,time
end=time.monotonic()+60
while time.monotonic()<end:
 r=subprocess.run(['oc','--request-timeout=10s','get','application','openshell-runtime','-n','openshift-gitops','-o','json'],capture_output=True,text=True)
 assert r.returncode==0,'Operation read failed'
 a=json.loads(r.stdout);o=a.get('status',{}).get('operationState',{});x=o.get('syncResult',{})
 if o.get('phase') in ('Running','Succeeded') and x.get('revision')==sys.argv[1] and x.get('source')==a['spec']['source']:break
 time.sleep(3)
else:raise RuntimeError('Exact async operation did not start within60seconds')
PYWAIT
python3 "$SCRIPT_DIR/setup-runtime.py" --revision "$REVISION" --prepare-only
"$PYTHON" "$REPO_ROOT/scripts/platform/check-operator-policy.py" "$REPO_ROOT/gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/controller" --wait 900
"$PYTHON" "$SCRIPT_DIR/setup-runtime.py" --revision "$REVISION"
ARGOCD_NAMESPACE=openshift-gitops argocd --core app wait openshell-runtime --app-namespace openshift-gitops --sync --health --operation --timeout 600
