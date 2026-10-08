#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT}"
load_env
check_oc_logged_in
branch="${1:?Usage: deploy-native-mcp.sh published-branch}"
sha="$(git -C "$ROOT" rev-parse HEAD)"
remote="$(git -C "$ROOT" ls-remote origin "refs/heads/$branch" | awk '{print $1}')"
[[ "$remote" == "$sha" ]] || { echo 'Selected published branch must equal checkout HEAD' >&2; exit 1; }
[[ -z "$(git -C "$ROOT" status --porcelain -- gitops/stages/060-agent-runtime-and-agentops/native-mcp stages/060-agent-runtime-and-agentops/deploy-native-mcp.sh stages/060-agent-runtime-and-agentops/validate-native-mcp.py gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-mcp.yaml)" ]] || { echo 'MCP component source is unpublished' >&2; exit 1; }
export RHOAI_STAGE060_EXPECTED_REVISION="$sha"
python3 "$ROOT/stages/060-agent-runtime-and-agentops/validate-native-mcp.py" --preflight
# Own Application is the first write. Native operators own all generated objects.
oc --request-timeout=10s apply -f <(python3 - "$ROOT" "$sha" <<'PY'
import json,subprocess,sys
root,sha=sys.argv[1:]
app=json.loads(subprocess.check_output(['oc','create','--dry-run=client','-f',root+'/gitops/argocd/app-of-apps/060-agent-runtime-and-agentops-mcp.yaml','-o','json'],text=True))
app['spec']['source']['targetRevision']=sha
print(json.dumps(app))
PY
)
echo 'Native MCP desired state submitted; manual exact-revision Argo sync and protocol qualification remain required.'
