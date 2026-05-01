#!/usr/bin/env bash
# Compatibility wrapper for the stage-based demo flow.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[DEPRECATED] steps/step-01-rhoai-platform/validate.sh is a compatibility alias."
echo "             Use stages/010-openshift-ai-platform-foundation/validate.sh."
exec "$REPO_ROOT/stages/010-openshift-ai-platform-foundation/validate.sh"
