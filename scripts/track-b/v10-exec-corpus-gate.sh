#!/usr/bin/env bash
# O-EXECCORPUS host gate — replay archived execution honesty cases.
# Pair with v10-plan-corpus-gate.sh (planning half). Safe for preflight.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"
SCRIPT="${HARNESS}/exec-corpus-lint.sh"
[ -f "$SCRIPT" ] || { echo "O-EXECCORPUS: missing $SCRIPT" >&2; exit 2; }
chmod +x "$SCRIPT"
echo "O-EXECCORPUS gate: $SCRIPT"
bash "$SCRIPT"
echo "O-EXECCORPUS gate GREEN"
