#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo '[FAIL] python3 is required'; exit 1; }
paths=(gitops/stages/050-model-evaluation stages/050-model-evaluation gitops/argocd/app-of-apps/050-model-evaluation scripts/shared)
[[ -z $(git -C "$REPO_ROOT" status --porcelain -- "${paths[@]}") ]] || { echo '[FAIL] Commit the reviewed Stage 050 source first'; exit 1; }
revision=$(git -C "$REPO_ROOT" rev-parse --verify "${GIT_REPO_BRANCH:-HEAD}^{commit}")
[[ "$revision" == "$(git -C "$REPO_ROOT" rev-parse HEAD)" ]] || { echo '[FAIL] Selected revision must equal the current reviewed checkout HEAD'; exit 1; }
repo_url=${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}
remote_head=$(git ls-remote "$repo_url" "${GIT_REPO_BRANCH:-HEAD}" | awk 'NR==1 {print $1}')
[[ "$remote_head" == "$revision" ]] || { echo '[FAIL] Published source differs from the reviewed local revision'; exit 1; }
fresh_databases=$(python3 "$SCRIPT_DIR/preflight.py")
# The first modifying action is this stage's component Applications at one revision. Never repoint Stage 010.
applications="$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" applications 050 --revision "$revision" --repo-url "$repo_url")" || { echo '[FAIL] Cannot prepare the Stage 050 Applications'; exit 1; }
oc --request-timeout=20s apply -f - <<<"$applications" >/dev/null || { echo '[FAIL] Cannot apply the Stage 050 Applications'; exit 1; }
echo "Stage 050 component Applications applied at reviewed immutable revision."
"$SCRIPT_DIR/setup-ai-services.sh" --fresh-databases "$fresh_databases"
export RHOAI_STAGE050_EXPECTED_REVISION="$revision"
deadline=$((SECONDS + 1200))
while :; do
  # Every component Synced and Healthy (the qualification component may be Suspended by a stopped candidate).
  if python3 "$REPO_ROOT/scripts/shared/stage_apps.py" status 050 --revision "$revision" --repo-url "$repo_url" >/dev/null
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
