#!/usr/bin/env bash
# Live E2E demo flow validation.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

"$REPO_ROOT/scripts/validate-stage-flow.sh"

load_env
check_oc_logged_in

log_step "E2E Demo Flow Validation"

mapfile -t stages < <(
    python3 - "$REPO_ROOT/flows/default.yaml" <<'PY'
from pathlib import Path
import sys
import yaml

flow = yaml.safe_load(Path(sys.argv[1]).read_text())
for stage in flow["stages"]:
    print(Path(stage["validateScript"]).parent.name)
PY
)

set +e
max_rc=0
for stage in "${stages[@]}"; do
    log_step "Validating ${stage}"
    "$REPO_ROOT/stages/${stage}/validate.sh"
    rc=$?
    if [[ $rc -eq 1 ]]; then
        max_rc=1
    elif [[ $rc -eq 2 && $max_rc -eq 0 ]]; then
        max_rc=2
    fi
done

exit "$max_rc"
