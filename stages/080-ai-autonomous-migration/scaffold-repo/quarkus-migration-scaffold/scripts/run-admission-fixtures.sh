#!/usr/bin/env bash
# W2 §10 — run the admission fixture set (ACCEPT/REFUSE/INCONCLUSIVE × G-1..G-4).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
rc=0
python3 scripts/gates/g1_mutation.py "${ROOT}" || rc=1
python3 scripts/gates/g2_obligation.py "${ROOT}" || rc=1
python3 scripts/gates/g3_findings.py "${ROOT}" || rc=1
python3 scripts/gates/g4_parity.py "${ROOT}" || rc=1
if [ "${rc}" -ne 0 ]; then
  echo "Admission fixtures FAILED" >&2
  exit 1
fi
echo "OK: admission fixtures — all gates emit ACCEPT/REFUSE/INCONCLUSIVE as specified"
