#!/usr/bin/env bash
# Retire one registered GitLab project; no GitHub/Quay deletion or PVC wipe.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
exec python3 "$REPO_ROOT/scripts/demo/gitlab-project-lifecycle.py" retire "$@"
