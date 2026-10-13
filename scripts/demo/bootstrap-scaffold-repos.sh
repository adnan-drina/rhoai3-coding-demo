#!/usr/bin/env bash
# Golden publication is owned by the Stage 070 GitOps integration hook.
# This helper reports the immutable published URLs; it never force-pushes.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
SCAFFOLD_REPOS="${SCAFFOLD_REPOS:-all}"
case "$SCAFFOLD_REPOS" in all|agentic|migration) ;; *) echo 'SCAFFOLD_REPOS must be all, agentic or migration' >&2; exit 1 ;; esac
oc get configmap gitlab-platform-config -n rhdh -o jsonpath='{.data.platform\.json}' |
  python3 -c 'import json,sys; d=json.load(sys.stdin); choice=sys.argv[1]; names=(["agentic-quarkus-scaffold"] if choice=="agentic" else ["quarkus-migration-scaffold-v2"] if choice=="migration" else ["agentic-quarkus-scaffold","quarkus-migration-scaffold-v2"]); [print(n+": "+d[n]) for n in names]' "$SCAFFOLD_REPOS"
log_info 'To publish changed goldens, review/publish the platform revision and sync Stage 070.'
