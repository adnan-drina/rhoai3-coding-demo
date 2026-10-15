#!/usr/bin/env bash
# Stage 060: OpenShell identity, then the runtime (deploy-runtime.sh). The agent console, MCP platform and agent tools
# have their own component scripts. 060 components sync manually by design (.agents/rules/gitops.md).
#   deploy.sh [--revision REF]     REF defaults to GIT_REPO_BRANCH, then HEAD; it must be published and match the checkout.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 060 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
STAGE_APPS="$REPO_ROOT/scripts/shared/stage_apps.py"
REVISION=$(python3 "$STAGE_APPS" select 060 --ref "$ref" --repo-url "$GIT_REPO_URL" --extra scripts/platform/check-operator-policy.py)
export RHOAI_STAGE060_EXPECTED_REVISION="$REVISION"

# Read-only: the identity component's prerequisites; the Application is the first write.
python3 "$SCRIPT_DIR/setup-identity.py" --revision "$REVISION" --preflight
python3 "$STAGE_APPS" apply 060 --app 060-openshell-identity --revision "$REVISION" --repo-url "$GIT_REPO_URL"
python3 "$STAGE_APPS" sync 060 --app 060-openshell-identity
python3 "$STAGE_APPS" wait 060 --app 060-openshell-identity --revision "$REVISION" --repo-url "$GIT_REPO_URL" --timeout 300
oc --request-timeout=15s wait keycloakrealmimport/openshell-realm -n keycloak --for=condition=Done --timeout=300s
python3 "$SCRIPT_DIR/setup-identity.py" --revision "$REVISION"
"$SCRIPT_DIR/deploy-runtime.sh"
echo 'Identity configured; runtime controller permission approval and persona handshake remain explicit gates.'
