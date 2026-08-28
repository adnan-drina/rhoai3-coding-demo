#!/usr/bin/env bash
# O-M2CORPUS host gate — re-lint committed M2 roadmap corpus with live argv.
# Intended for preflight / LRR before outer restart.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
qg_refuse_retired_wave5_harness
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"
SCRIPT="${HARNESS}/m2-corpus-lint.sh"
[ -x "$SCRIPT" ] || chmod +x "$SCRIPT"
echo "O-M2CORPUS gate: $SCRIPT"
bash "$SCRIPT"
echo "O-M2CORPUS gate GREEN"
