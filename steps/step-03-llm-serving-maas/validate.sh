#!/usr/bin/env bash
# Compatibility wrapper for the stage-based demo flow.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[DEPRECATED] steps/step-03-llm-serving-maas/validate.sh is a compatibility alias."
echo "             Use stages/030 through stages/060 validation scripts."

set +e
max_rc=0
for stage in \
  030-private-model-serving \
  040-governed-models-as-a-service \
  050-approved-external-model-access \
  060-mcp-context-integrations; do
  "$REPO_ROOT/stages/${stage}/validate.sh"
  rc=$?
  if [[ $rc -eq 1 ]]; then
    max_rc=1
  elif [[ $rc -eq 2 && $max_rc -eq 0 ]]; then
    max_rc=2
  fi
done
exit "$max_rc"
