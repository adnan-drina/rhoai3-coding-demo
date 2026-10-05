#!/usr/bin/env bash
# Reconcile only the additive console component, retaining the core source.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
revision="${GIT_REPO_BRANCH:-}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then revision="$2";
elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision <published ref>]" >&2; exit 1; fi
commit=$(git -C "$REPO_ROOT" rev-parse --verify "${revision:?Select published revision}^{commit}")
paths=(gitops/stages/010-openshift-ai-platform-foundation/console-observability stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh stages/010-openshift-ai-platform-foundation/validate-console-observability.sh scripts/shared)
git -C "$REPO_ROOT" diff --quiet "$commit" -- "${paths[@]}" || { echo 'ERROR: Component differs from reviewed revision' >&2; exit 1; }
[[ -z $(git -C "$REPO_ROOT" ls-files --others --exclude-standard -- "${paths[@]}") ]] || { echo 'ERROR: Unpublished component files' >&2; exit 1; }
export GIT_REPO_URL
git ls-remote "${GIT_REPO_URL:?}" | awk '{print $1}' | grep -Fx "$commit" >/dev/null || { echo 'ERROR: Revision is not published' >&2; exit 1; }
python3 - <<'PY_ADOPT'
import json,os,subprocess
app='010-console-observability';path='gitops/stages/010-openshift-ai-platform-foundation/console-observability/base'
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
manifest=$(mktemp);trap 'rm -f "$manifest"' EXIT
ruby -ryaml -e 'a=YAML.load_file(ARGV[0]);a["spec"]["source"]["repoURL"]=ENV.fetch("GIT_REPO_URL");a["spec"]["source"]["targetRevision"]=ARGV[1];puts YAML.dump(a)' "$REPO_ROOT/gitops/stages/010-openshift-ai-platform-foundation/console-observability/application.yaml" "$commit" > "$manifest"
# First write is our Application; COO owns the generated plugin/Perses.
oc --request-timeout=10s apply -f "$manifest"
deadline=$((SECONDS + 600))
while (( SECONDS < deadline )); do
 if "$SCRIPT_DIR/validate-console-observability.sh"; then exit 0; fi
 sleep 10
done
echo 'ERROR: Native console integration readiness timed out' >&2
exit 1
