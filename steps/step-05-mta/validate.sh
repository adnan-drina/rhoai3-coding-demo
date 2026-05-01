#!/usr/bin/env bash
# Compatibility wrapper for the stage-based demo flow.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[DEPRECATED] steps/step-05-mta/validate.sh is a compatibility alias."
echo "             Use stages/080-ai-assisted-application-modernization/validate.sh."
exec "$REPO_ROOT/stages/080-ai-assisted-application-modernization/validate.sh"
