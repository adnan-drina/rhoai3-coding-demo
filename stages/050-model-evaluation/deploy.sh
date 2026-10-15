#!/usr/bin/env bash
# Stage 050: MLflow, EvalHub, evaluation content and the model qualification pipeline.
#   deploy.sh [--revision REF]     REF defaults to GIT_REPO_BRANCH, then HEAD; it must be published and match the checkout.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 050 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
STAGE_APPS="$REPO_ROOT/scripts/shared/stage_apps.py"

revision=$(python3 "$STAGE_APPS" select 050 --ref "$ref" --repo-url "$GIT_REPO_URL")
# Read-only: prerequisites, ownership of existing objects, and which service databases are new.
fresh_databases=$(python3 "$SCRIPT_DIR/preflight.py")

# First change: the component Applications at the reviewed commit (Stage 010 is never re-pointed). The AI services
# need their database credentials before the components can become healthy, so set them up before waiting.
python3 "$STAGE_APPS" deploy 050 --revision "$revision" --repo-url "$GIT_REPO_URL" --no-wait
"$SCRIPT_DIR/setup-ai-services.sh" --fresh-databases "$fresh_databases"
python3 "$STAGE_APPS" wait 050 --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 1200

deadline=$((SECONDS + 900))
until [[ $(oc --request-timeout=10s get evalhub evalhub -n evalhub -o jsonpath='{.status.ready}' 2>/dev/null || true) == True ]]; do
  (( SECONDS < deadline )) || { log_error "EvalHub did not become ready"; exit 1; }
  sleep 5
done
deadline=$((SECONDS + 900))
until "$SCRIPT_DIR/validate-ai-services.sh"; do
  (( SECONDS < deadline )) || { log_error "AI services did not reconcile"; exit 1; }
  sleep 10
done

# Stage 040's Studio hook registers the Ops Assistant prompt in MLflow, which this stage installs; on a fresh install
# that hook deferred. Re-run 040-genai-studio's hooks at Stage 040's deployed revision now that MLflow is ready.
studio_revision=$(oc --request-timeout=10s get applications.argoproj.io 040-genai-studio -n openshift-gitops -o jsonpath='{.spec.source.targetRevision}')
python3 "$STAGE_APPS" sync 040 --app 040-genai-studio --resync
python3 "$STAGE_APPS" wait 040 --app 040-genai-studio --revision "$studio_revision" --repo-url "$GIT_REPO_URL" --timeout 600

# Service foundation is complete; running an evaluation is a separate, authorized step.
export RHOAI_STAGE050_EXPECTED_REVISION="$revision"
set +e
"$SCRIPT_DIR/validate.sh"
result=$?
set -e
[[ "$result" == 0 || "$result" == 2 ]] || exit "$result"
log_success "Stage 050 reconciled at ${revision:0:12}; evaluation execution remains a separate step."
