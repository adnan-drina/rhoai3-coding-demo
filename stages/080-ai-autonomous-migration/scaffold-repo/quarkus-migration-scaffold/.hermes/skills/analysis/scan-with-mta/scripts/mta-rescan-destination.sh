#!/usr/bin/env bash
# Destination MTA rescan for M3/M4 obligation closure (same targets, same
# custom rules, no --source). Writes verification/mta-rescan/findings.json
# (append-only execution evidence; never touches evidence/ planning files).
set -euo pipefail

ROOT="${1:-/projects/modernized}"
[[ -d "${ROOT}" ]] || { echo "usage: mta-rescan-destination.sh <dest-root>" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ENSURE_CLI_LIB=1
# shellcheck source=mta-analyze-legacy.sh
source "${SCRIPTS}/mta-analyze-legacy.sh"
unset ENSURE_CLI_LIB
CLI="$(ensure_cli)" || { echo "FAIL: MTA CLI unusable" >&2; exit 1; }
OUT="${ROOT}/verification/mta-rescan"
rm -rf "${OUT}"; mkdir -p "${OUT}/report"
TARGETS=()
while IFS= read -r t; do [[ -n "${t}" ]] && TARGETS+=(--target "${t}"); done < <(python3 - "${ROOT}/migration.yaml" <<'PY'
import sys
sys.path.insert(0, sys.argv[1].rsplit("/", 1)[0] + "/.hermes/lib")
from planner.evidence import load_migration
from pathlib import Path
for t in load_migration(Path(sys.argv[1]).parent)["targets"]:
    print(t)
PY
)
RULES="$(python3 - "${ROOT}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/.hermes/lib")
from planner.evidence import load_migration
from pathlib import Path
print(load_migration(Path(sys.argv[1]))["custom_rules"])
PY
)"
RULES_FLAGS=()
[[ -n "${RULES}" && -d "${ROOT}/${RULES#/}" ]] && RULES_FLAGS=(--rules "${ROOT}/${RULES#/}")
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"; export PATH="${JAVA_HOME}/bin:${PATH}"
MTA_RUN_CWD="${MTA_RUN_CWD:-/projects/.tools/mta-run}"; mkdir -p "${MTA_RUN_CWD}"
set +e
( cd "${MTA_RUN_CWD}" && "${CLI}" analyze --input "${ROOT}" --output "${OUT}/report" "${TARGETS[@]}" "${RULES_FLAGS[@]}" --json-output "${OUT}/findings.json" --overwrite )
rc=$?
set -e
if [[ ! -s "${OUT}/findings.json" && -s "${OUT}/report/output.json" ]]; then cp -f "${OUT}/report/output.json" "${OUT}/findings.json"; fi
[[ -s "${OUT}/findings.json" ]] || { echo "FAIL: destination rescan produced no findings (rc=${rc})" >&2; exit 1; }
DEST_DIGEST="$(git -C "${ROOT}" rev-parse HEAD 2>/dev/null || echo worktree)"
python3 "${SCRIPTS}/normalize-findings.py" "${OUT}/findings.json" "${CLI}" "$(printf '%s,' "${TARGETS[@]}" | tr -d '-' | sed 's/target,//g; s/,$//')" "destination:${DEST_DIGEST}" "${OUT}/rules-coverage.json" "${OUT}/report/static-report/index.html"
echo "OK: destination rescan → ${OUT}/findings.json (rc=${rc})"
