#!/usr/bin/env bash
# O-PLANCORPUS host gate — re-lint committed plan corpus with live M3 flags.
# Intended for preflight before outer restart (see v9-preflight-outer-start.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS="${ROOT}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/harness"
SCRIPT="${HARNESS}/plan-corpus-lint.sh"
[ -x "$SCRIPT" ] || chmod +x "$SCRIPT"
echo "O-PLANCORPUS gate: $SCRIPT"
bash "$SCRIPT"
# Also refresh/check defaults inventory seed (O-DEFAULTAUDIT)
INV="${HARNESS}/defaults-inventory.sh"
if [ -f "$INV" ]; then
  chmod +x "$INV"
  bash "$INV" --check || {
    echo "O-DEFAULTAUDIT: regenerating artefact" >&2
    bash "$INV"
    bash "$INV" --check
  }
fi
echo "O-PLANCORPUS / O-DEFAULTAUDIT gate GREEN"
