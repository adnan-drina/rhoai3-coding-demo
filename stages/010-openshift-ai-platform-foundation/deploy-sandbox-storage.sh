#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
# The approved additive component leaves existing buckets and consumers intact.
[[ "${1:-}" == --revision && $# -eq 2 ]] || { echo "Usage: $0 --revision <published-ref>" >&2; exit 1; }
commit=$(git -C "$REPO_ROOT" rev-parse --verify "${2}^{commit}")
paths=(gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage stages/010-openshift-ai-platform-foundation/deploy-sandbox-storage.sh stages/010-openshift-ai-platform-foundation/validate-sandbox-storage.sh scripts/shared)
git -C "$REPO_ROOT" diff --quiet "$commit" -- "${paths[@]}" || { echo "ERROR: Component differs from selected revision" >&2; exit 1; }
[[ -z "$(git -C "$REPO_ROOT" ls-files --others --exclude-standard -- "${paths[@]}")" ]] || { echo "ERROR: Component has unpublished files" >&2; exit 1; }
repo="${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}"
git ls-remote "$repo" | awk '{print $1}' | grep -Fx "$commit" >/dev/null || { echo "ERROR: Revision is not published" >&2; exit 1; }
GIT_REPO_URL="$repo" python3 - <<'PY_ADOPT'
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
        if s.get('sources') or s.get("source",{}).get("repoURL")!=os.environ["GIT_REPO_URL"] or s.get("destination")!={"server":"https://kubernetes.default.svc","namespace":"demo-sandbox"} or s.get("project")!="rhoai-demo" or s.get("source",{}).get("path")!="gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/base": raise SystemExit("ERROR: Existing Application identity differs")
PY_ADOPT
manifest=$(mktemp)
trap 'rm -f "$manifest"' EXIT
sed -e "s|repoURL: .*|repoURL: $repo|" -e "s|targetRevision: .*|targetRevision: $commit|" "$REPO_ROOT/gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/application.yaml" > "$manifest"
# First write targets only this additive component, never the core foundation.
oc --request-timeout=10s apply -f "$manifest"
deadline=$((SECONDS+720))
while (( SECONDS < deadline )); do
  state=$(oc --request-timeout=10s get application 010-sandbox-storage -n openshift-gitops -o jsonpath='{.status.sync.revision} {.status.sync.status} {.status.health.status}')
  if [[ "$state" == "$commit Synced Healthy" ]]; then
    "$SCRIPT_DIR/validate-sandbox-storage.sh"
    exit
  fi
  sleep 10
done
echo "ERROR: Sandbox storage reconciliation timed out" >&2
exit 1
