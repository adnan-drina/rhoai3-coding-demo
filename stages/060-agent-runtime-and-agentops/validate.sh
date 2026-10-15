#!/usr/bin/env bash
# Stage 060: checks the five component Applications; full AgentOps acceptance remains pending by design.
#   validate.sh [--static|--readiness]   exit 0 never (pending), 2 components reconciled, 1 a component is not
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
case "${1:-}" in
  --help|-h) echo "Usage: validate.sh [--static|--readiness]"; exit 0 ;;
  --static) python3 "$REPO_ROOT/scripts/shared/stage_apps.py" check-static 060; exit 0 ;;
  ""|--readiness) ;;
  *) echo "Unsupported argument: $1" >&2; exit 1 ;;
esac
source "$REPO_ROOT/scripts/shared/validate-lib.sh"
log_step "Stage 060 component Applications"
check_stage_applications 060
validation_summary || exit 1
echo "[PENDING] Stage 060 Agent Runtime and AgentOps: components reconciled; full-stage acceptance (persona handshake, agent lifecycle) remains pending."
exit 2
