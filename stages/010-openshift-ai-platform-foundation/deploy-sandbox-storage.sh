#!/usr/bin/env bash
# Deploys only the additive 010-sandbox-storage component (the two sandbox bucket claims and their dashboard
# connections) at a reviewed revision, then validates it. Existing buckets and consumers stay intact.
# Usage: stages/010-openshift-ai-platform-foundation/deploy-sandbox-storage.sh [--revision REF]
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
# Adoption guard (read-only): existing claims and connections must be unowned and tracked by this component;
# an existing Application must have our identity. Missing objects are fine (first install).
APP=010-sandbox-storage
APP_PATH=gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage
unowned() { jq -e '(.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null' >/dev/null; }
existing_app=$(oc --request-timeout=10s get application "$APP" -n openshift-gitops --ignore-not-found -o json)
if [[ -n "$existing_app" ]]; then
    unowned <<<"$existing_app" && jq -e --arg repo "$GIT_REPO_URL" --arg path "$APP_PATH" '.spec | (.sources == null)
        and .project == "rhoai-demo" and .source.repoURL == $repo and .source.path == $path
        and .destination == {server: "https://kubernetes.default.svc", namespace: "openshift-gitops"}' \
        <<<"$existing_app" >/dev/null || { echo "ERROR: existing Application identity differs" >&2; exit 1; }
fi
for object in obc/rhoai-models obc/rhoai-workbench secret/rhoai-models-connection secret/rhoai-workbench-connection; do
    existing=$(oc --request-timeout=10s get "$object" -n demo-sandbox --ignore-not-found -o json)
    [[ -z "$existing" ]] && continue
    unowned <<<"$existing" && jq -e --arg app "$APP" \
        '.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith($app + ":")' <<<"$existing" >/dev/null ||
        { echo "ERROR: existing $object requires reviewed adoption; no changes made" >&2; exit 1; }
done
# First write targets only this additive component, never the core foundation.
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" apply 010 --app 010-sandbox-storage --revision "$commit" --repo-url "$GIT_REPO_URL"
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" sync 010 --app 010-sandbox-storage  # an unchanged render gets no automatic sync operation
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" wait 010 --app 010-sandbox-storage --revision "$commit" --repo-url "$GIT_REPO_URL" --timeout 720
"$SCRIPT_DIR/validate-sandbox-storage.sh"
