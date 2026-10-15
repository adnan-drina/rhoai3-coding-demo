#!/usr/bin/env bash
# Reconcile only the additive console component, retaining the core source.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 010 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
commit=$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" select 010 --ref "$ref" --repo-url "$GIT_REPO_URL")
# Adoption guard (read-only): existing objects must be ours or unowned, and the Application must have our identity.
APP=010-console-observability
APP_PATH=gitops/stages/010-openshift-ai-platform-foundation/010-console-observability
not_foreign() {
    jq -e --arg app "$APP" '.metadata as $m | ($m.ownerReferences // [] | length) == 0 and ($m.deletionTimestamp == null)
        and (($m.annotations["argocd.argoproj.io/tracking-id"] // "") as $t | $t == "" or ($t | startswith($app + ":")))' >/dev/null
}
existing_app=$(oc --request-timeout=10s get application "$APP" -n openshift-gitops --ignore-not-found -o json)
if [[ -n "$existing_app" ]]; then
    not_foreign <<<"$existing_app" || { echo "ERROR: $APP has unexpected ownership" >&2; exit 1; }
    jq -e --arg repo "$GIT_REPO_URL" --arg path "$APP_PATH" '.spec | (.sources == null) and .project == "rhoai-demo"
        and .source.repoURL == $repo and .source.path == $path
        and .destination == {server: "https://kubernetes.default.svc", namespace: "openshift-gitops"}' \
        <<<"$existing_app" >/dev/null || { echo "ERROR: existing $APP identity differs" >&2; exit 1; }
fi
existing_plugin=$(oc --request-timeout=10s get uiplugins.observability.openshift.io monitoring --ignore-not-found -o json)
if [[ -n "$existing_plugin" ]]; then
    not_foreign <<<"$existing_plugin" || { echo "ERROR: UIPlugin monitoring has unexpected ownership" >&2; exit 1; }
    jq -e '.spec == {type: "Monitoring", monitoring: {perses: {enabled: true}}}' <<<"$existing_plugin" >/dev/null ||
        { echo "ERROR: existing UIPlugin monitoring requires a reviewed merge" >&2; exit 1; }
fi
# First write is our Application; COO owns the generated plugin/Perses.
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" apply 010 --app 010-console-observability --revision "$commit" --repo-url "$GIT_REPO_URL"
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" sync 010 --app 010-console-observability  # an unchanged render gets no automatic sync operation
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" wait 010 --app 010-console-observability --revision "$commit" --repo-url "$GIT_REPO_URL" --timeout 600
deadline=$((SECONDS + 600))
while (( SECONDS < deadline )); do
 if "$SCRIPT_DIR/validate-console-observability.sh"; then exit 0; fi
 sleep 10
done
echo 'ERROR: Native console integration readiness timed out' >&2
exit 1
