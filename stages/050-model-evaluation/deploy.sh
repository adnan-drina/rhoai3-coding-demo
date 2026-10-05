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
deadline=$((SECONDS + 900))
until [[ $(oc --request-timeout=10s get evalhub evalhub -n evalhub -o jsonpath='{.status.ready}' 2>/dev/null || true) == True ]]; do
  (( SECONDS < deadline )) || { echo '[FAIL] Native EvalHub readiness timed out'; exit 1; }
  sleep 5
done
"$SCRIPT_DIR/validate.sh"
