#!/usr/bin/env bash
# W2 §10 — admission fixtures (ACCEPT/REFUSE/INCONCLUSIVE × G-1..G-4).
# Domain-gates skill mechanism — AD-H §7 deterministic gates.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# SR-2: explicit root arg (fixtures) wins; otherwise walk up to migration.yaml.
if [ -n "${1:-}" ]; then
  ROOT="$(cd "$1" && pwd)"
else
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      ROOT="$d"
      break
    fi
    d="$(dirname "$d")"
  done
  if [ -z "${ROOT:-}" ]; then
    echo "cannot find project root (migration.yaml) walking up from $(dirname "$0") (SR-2)" >&2
    exit 1
  fi
fi
SCRIPTS="${SKILL_DIR}/scripts"
cd "${ROOT}"
rc=0
python3 "${SCRIPTS}/g1-characterization.py" "${ROOT}" || rc=1
python3 "${SCRIPTS}/g2-harvest-fidelity.py" "${ROOT}" || rc=1
python3 "${SCRIPTS}/g3-findings-delta.py" "${ROOT}" || rc=1
python3 "${SCRIPTS}/g4-runtime-parity.py" "${ROOT}" || rc=1
if [ "${rc}" -ne 0 ]; then
  echo "Admission fixtures FAILED" >&2
  exit 1
fi
echo "OK: admission fixtures — G-1..G-4 emit ACCEPT/REFUSE/INCONCLUSIVE as specified"
