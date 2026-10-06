#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo '[FAIL] python3 is required'; exit 1; }
paths=(gitops/stages/050-model-evaluation stages/050-model-evaluation gitops/argocd/app-of-apps/050-model-evaluation.yaml)
[[ -z $(git -C "$REPO_ROOT" status --porcelain -- "${paths[@]}") ]] || { echo '[FAIL] Commit the reviewed Stage 050 source first'; exit 1; }
revision=$(git -C "$REPO_ROOT" rev-parse --verify "${GIT_REPO_BRANCH:-HEAD}^{commit}")
[[ "$revision" == "$(git -C "$REPO_ROOT" rev-parse HEAD)" ]] || { echo '[FAIL] Selected revision must equal the current reviewed checkout HEAD'; exit 1; }
repo_url=${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}
remote_head=$(git ls-remote "$repo_url" "${GIT_REPO_BRANCH:-HEAD}" | awk 'NR==1 {print $1}')
[[ "$remote_head" == "$revision" ]] || { echo '[FAIL] Published source differs from the reviewed local revision'; exit 1; }
fresh_databases=$(python3 "$SCRIPT_DIR/preflight.py")
# The first modifying action is this stage's Application. Never repoint Stage 010.
python3 - "$REPO_ROOT/gitops/argocd/app-of-apps/050-model-evaluation.yaml" "$repo_url" "$revision" <<'PY'
import json,subprocess,sys
result = subprocess.run(["oc", "create", "--dry-run=client", "-f", sys.argv[1], "-o", "json"], capture_output=True, text=True)
if result.returncode:
    sys.exit("[FAIL] Cannot prepare the Stage 050 Application")
app = json.loads(result.stdout)
app["spec"]["source"].update(repoURL=sys.argv[2], targetRevision=sys.argv[3])
result = subprocess.run(["oc", "--request-timeout=20s", "apply", "-f", "-"], input=json.dumps(app), capture_output=True, text=True)
if result.returncode:
    sys.exit("[FAIL] Cannot apply the Stage 050 Application")
print("Stage 050 Application created at reviewed immutable revision.")
PY
"$SCRIPT_DIR/setup-ai-services.sh" --fresh-databases "$fresh_databases"
export RHOAI_STAGE050_EXPECTED_REVISION="$revision"
deadline=$((SECONDS + 1200))
while :; do
  if python3 - "$revision" <<'PY_APP'
import json,subprocess,sys
p=subprocess.run(['oc','--request-timeout=10s','get','application','050-model-evaluation','-n','openshift-gitops','-o','json'],capture_output=True,text=True,timeout=15)
if p.returncode:raise SystemExit(1)
a=json.loads(p.stdout);s=a.get('status',{});o=s.get('operationState',{});r=o.get('syncResult',{})
raise SystemExit(0 if s.get('sync',{}).get('status')=='Synced' and s.get('health',{}).get('status')=='Healthy' and o.get('phase')=='Succeeded' and r.get('revision')==sys.argv[1] and r.get('source',{}).get('path')=='gitops/stages/050-model-evaluation/base' else 1)
PY_APP
  then break; fi
  (( SECONDS < deadline )) || { echo '[FAIL] Exact native Stage050 operation did not complete'; exit 1; }
  sleep 5
done
deadline=$((SECONDS + 900))
until [[ $(oc --request-timeout=10s get evalhub evalhub -n evalhub -o jsonpath='{.status.ready}' 2>/dev/null || true) == True ]]; do
  (( SECONDS < deadline )) || { echo '[FAIL] Native EvalHub readiness timed out'; exit 1; }
  sleep 5
done
deadline=$((SECONDS + 900))
until "$SCRIPT_DIR/validate-ai-services.sh"; do
  (( SECONDS < deadline )) || { echo '[FAIL] Native service reconciliation timed out'; exit 1; }
  sleep 10
done
# Service foundation is complete; a benchmark remains separately authorized.
set +e
"$SCRIPT_DIR/validate.sh"
result=$?
set -e
[[ "$result" == 0 || "$result" == 2 ]] || exit "$result"
echo 'Stage050 service foundation reconciled; evaluation execution remains pending.'
