#!/usr/bin/env bash
# Compatibility wrapper for the stage-based demo flow.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[DEPRECATED] steps/step-03-llm-serving-maas/deploy.sh is a compatibility alias."
echo "             Use stages/030 through stages/060 for the split model-serving, MaaS,"
echo "             external-model, and MCP stages."

"$REPO_ROOT/stages/030-private-model-serving/deploy.sh"
"$REPO_ROOT/stages/040-governed-models-as-a-service/deploy.sh"
"$REPO_ROOT/stages/050-approved-external-model-access/deploy.sh"
"$REPO_ROOT/stages/060-mcp-context-integrations/deploy.sh"
