#!/usr/bin/env bash
# Stage 060 agent tools: the native OpenShift MCP servers (060-agent-tools). Protocol qualification is separate.
#   deploy-native-mcp.sh [--revision REF] [--publish-studio]
#     --publish-studio  only publish the servers to the Gen AI Studio catalog (Stage 040 publish-catalog-mcp.py)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT}"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 060 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"; publish=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) ref="${2:?}"; shift 2 ;;
    --publish-studio) publish=true; shift ;;
    *) echo "Usage: $0 [--revision REF] [--publish-studio]" >&2; exit 1 ;;
  esac
done
STAGE_APPS="$ROOT/scripts/shared/stage_apps.py"
sha=$(python3 "$STAGE_APPS" select 060 --ref "$ref" --repo-url "$GIT_REPO_URL" \
  --extra stages/040-governed-models-as-a-service/publish-catalog-mcp.py --extra stages/040-governed-models-as-a-service/qualify-catalog-mcp.py)
export RHOAI_STAGE060_EXPECTED_REVISION="$sha"
if [[ "$publish" == true ]]; then
  python3 "$ROOT/stages/040-governed-models-as-a-service/publish-catalog-mcp.py"
  exit 0
fi
python3 "$ROOT/stages/060-agent-runtime-and-agentops/validate-native-mcp.py" --preflight
# Own Application is the first write. Native operators own all generated objects.
python3 "$STAGE_APPS" apply 060 --app 060-agent-tools --revision "$sha" --repo-url "$GIT_REPO_URL"
python3 "$STAGE_APPS" sync 060 --app 060-agent-tools
python3 "$STAGE_APPS" wait 060 --app 060-agent-tools --revision "$sha" --repo-url "$GIT_REPO_URL" --timeout 600
echo 'Native MCP servers reconciled; protocol qualification (validate-native-mcp.py) remains a separate step.'
