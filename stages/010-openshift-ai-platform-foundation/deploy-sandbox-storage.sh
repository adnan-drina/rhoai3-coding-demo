#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
# The approved additive component leaves existing buckets and consumers intact.
require_env GIT_REPO_URL "reviewed Stage 010 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
commit=$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" select 010 --ref "$ref" --repo-url "$GIT_REPO_URL")
export GIT_REPO_URL
python3 - <<'PY_ADOPT'
import json,subprocess,os
app="010-sandbox-storage"
for kind,name,ns in [("application",app,"openshift-gitops"),("obc","rhoai-models","demo-sandbox"),("obc","rhoai-workbench","demo-sandbox"),("secret","rhoai-models-connection","demo-sandbox"),("secret","rhoai-workbench-connection","demo-sandbox")]:
    projection='{.metadata.uid}{"\\n"}{.metadata.deletionTimestamp}{"\\n"}{range .metadata.ownerReferences[*]}{.uid}{" "}{end}{"\\n"}{.metadata.annotations.argocd\\.argoproj\\.io/tracking-id}'
    p=subprocess.run(["oc","--request-timeout=10s","get",kind,name,"-n",ns,"--ignore-not-found","-o",'jsonpath='+projection],capture_output=True,text=True,timeout=15)
    if p.returncode: raise SystemExit("ERROR: Adoption API unavailable")
    if not p.stdout.strip(): continue
    fields=p.stdout.split('\n');fields+=['']*(4-len(fields));uid,deleting,owners,t=fields[:4]
    if not uid or deleting or owners or (kind!="application" and not t.startswith(app+":")):
        raise SystemExit("ERROR: Existing resource requires reviewed adoption; no changes made")
    if kind=="application":
        p=subprocess.run(["oc","--request-timeout=10s","get",kind,name,"-n",ns,"-o","jsonpath={.spec}"],capture_output=True,text=True)
        if p.returncode: raise SystemExit("ERROR: Application API unavailable")
        s=json.loads(p.stdout)
        if s.get('sources') or s.get("source",{}).get("repoURL")!=os.environ["GIT_REPO_URL"] or s.get("destination")!={"server":"https://kubernetes.default.svc","namespace":"openshift-gitops"} or s.get("project")!="rhoai-demo" or s.get("source",{}).get("path")!="gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage": raise SystemExit("ERROR: Existing Application identity differs")
PY_ADOPT
# First write targets only this additive component, never the core foundation.
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" apply 010 --app 010-sandbox-storage --revision "$commit" --repo-url "$GIT_REPO_URL"
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" sync 010 --app 010-sandbox-storage  # an unchanged render gets no automatic sync operation
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" wait 010 --app 010-sandbox-storage --revision "$commit" --repo-url "$GIT_REPO_URL" --timeout 720
"$SCRIPT_DIR/validate-sandbox-storage.sh"
