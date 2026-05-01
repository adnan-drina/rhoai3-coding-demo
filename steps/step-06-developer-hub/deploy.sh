#!/usr/bin/env bash
# Compatibility wrapper for the stage-based demo flow.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[DEPRECATED] steps/step-06-developer-hub/deploy.sh is a compatibility alias."
echo "             Use stages/090-developer-portal-self-service/deploy.sh."
exec "$REPO_ROOT/stages/090-developer-portal-self-service/deploy.sh"
