#!/usr/bin/env bash
# Reconcile only the additive console component, retaining the core source.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 010 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
commit=$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" select 010 --ref "$ref" --repo-url "$GIT_REPO_URL")
export GIT_REPO_URL
python3 - <<'PY_ADOPT'
import json,os,subprocess
app='010-console-observability';path='gitops/stages/010-openshift-ai-platform-foundation/010-console-observability'
for kind,name,ns in [('application',app,'openshift-gitops'),('uiplugins.observability.openshift.io','monitoring',None)]:
 args=['oc','--request-timeout=10s','get',kind,name,'--ignore-not-found','-o','json']
 if ns:args+=['-n',ns]
 p=subprocess.run(args,capture_output=True,text=True,timeout=15);assert p.returncode==0,'Component ownership read failed'
 if not p.stdout.strip():continue
 x=json.loads(p.stdout);m=x['metadata'];assert not m.get('ownerReferences') and not m.get('deletionTimestamp'),'Unexpected component ownership'
 tracking=m.get('annotations',{}).get('argocd.argoproj.io/tracking-id','');assert not tracking or tracking.startswith(app+':'),'Foreign component tracking'
 if kind=='application':
  s=x['spec'];assert not s.get('sources') and s['project']=='rhoai-demo' and s['source']['repoURL']==os.environ['GIT_REPO_URL'] and s['source']['path']==path and s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'},'Unexpected Application identity'
 else:assert x['spec']=={'type':'Monitoring','monitoring':{'perses':{'enabled':True}}},'Existing UIPlugin requires a reviewed merge'
PY_ADOPT
# First write is our Application; COO owns the generated plugin/Perses.
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" apply 010 --app 010-console-observability --revision "$commit" --repo-url "$GIT_REPO_URL"
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" sync 010 --app 010-console-observability  # an unchanged render gets no automatic sync operation
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" wait 010 --app 010-console-observability --revision "$commit" --repo-url "$GIT_REPO_URL" --timeout 600
deadline=$((SECONDS + 600))
while (( SECONDS < deadline )); do
 if "$SCRIPT_DIR/validate-console-observability.sh"; then exit 0; fi
 sleep 10
done
echo 'ERROR: Native console integration readiness timed out' >&2
exit 1
