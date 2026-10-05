#!/usr/bin/env bash
# Free-primitives Boot 2→3 composite (W2 §12).
# Run with cwd = derived legacy tree (DERIVE_UPGRADE_CMD context).
#
# Env:
#   COMPOSITE_ROOT   tree to transform (default: cwd)
#   APPLY_LOG_PATH   where to write free-primitives-apply-log.json
#                    (default: beside COMPOSITE_ROOT only when it is positively
#                     a derived tree; otherwise $TMPDIR — FP-1)
#   SKIP_MTA_JAKARTA=1  force package-map fallback (skip mta-cli)
#
# UPLIFT-2: progress + human OK on stderr; one JSON object on stdout.
set -euo pipefail

# --dry-run as first arg or DRY_RUN=1: list rules that would run; no python.
if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  DRY_RUN=1
fi
DRY_RUN="${DRY_RUN:-0}"

HERE="$(cd "$(dirname "$0")" && pwd)"
export COMPOSITE_ROOT="${COMPOSITE_ROOT:-$(pwd)}"
export PYTHONPATH="${HERE}${PYTHONPATH:+:$PYTHONPATH}"

# FP-1: python owns the default (positive derived-tree test, not "not golden").
# Candidate-source refuse (FP-2) runs before any apply-log write.

emit_ok() {
  local human="$1"
  shift
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]),separators=(",",":")))' "$1"
  printf '%s\n' "${human}" >&2
}

echo "free-primitives-boot3: COMPOSITE_ROOT=${COMPOSITE_ROOT}" >&2
echo "free-primitives-boot3: APPLY_LOG_PATH=${APPLY_LOG_PATH:-<default: derived-tree or TMPDIR>}" >&2

RULES=(
  "${HERE}/rules/r00_javax_to_jakarta.py"
  "${HERE}/rules/r10_bump_boot_parent.py"
  "${HERE}/rules/r20_mysql_connector.py"
  "${HERE}/rules/r30_jaxb_api.py"
  "${HERE}/rules/r40_security6_wsca.py"
  "${HERE}/rules/r45_security6_matchers.py"
  "${HERE}/rules/r50_openapi_jakarta.py"
  "${HERE}/rules/r60_springfox_to_springdoc.py"
  "${HERE}/rules/r70_thymeleaf_spring6.py"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY-RUN: free-primitives-boot3 would run ${#RULES[@]} rules:" >&2
  for script in "${RULES[@]}"; do
    echo "DRY-RUN:   $(basename "$script")" >&2
  done
  emit_ok "DRY-RUN: free-primitives-boot3 would run ${#RULES[@]} rules" \
    "$(python3 -c 'import json,sys; print(json.dumps({"script":"run-composite","ok":True,"dry_run":True,"rule_count":int(sys.argv[1])}))' "${#RULES[@]}")"
  exit 0
fi

# FP-2: no pom.xml and no *.java is not a quiet success — refuse before a receipt.
python3 -c '
from _lib import has_candidate_sources, repo_root
import sys
root = repo_root()
if not has_candidate_sources(root):
    print(
        "free-primitives-boot3: no_candidate_sources: "
        f"COMPOSITE_ROOT={root} (need pom.xml or *.java)",
        file=sys.stderr,
    )
    sys.exit(2)
'
if [[ -z "${APPLY_LOG_PATH:-}" ]]; then
  APPLY_LOG_PATH="$(python3 -c 'from _lib import apply_log_path; print(apply_log_path())')"
  export APPLY_LOG_PATH
fi

# Fresh apply log for this invocation
mkdir -p "$(dirname "${APPLY_LOG_PATH}")"
rm -f "${APPLY_LOG_PATH}"

run_rule() {
  local script="$1"
  echo "=== $(basename "$script") ===" >&2
  python3 "$script"
}

# Order: jakarta → Boot bump → POM → Security (WSCA then matchers) → generator → thymeleaf
for script in "${RULES[@]}"; do
  run_rule "${script}"
done

HUMAN="free-primitives-boot3: OK"
emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"run-composite","ok":True,"composite_root":sys.argv[1],"rule_count":int(sys.argv[2]),"apply_log":sys.argv[3]}))' "${COMPOSITE_ROOT}" "${#RULES[@]}" "${APPLY_LOG_PATH:-}")"
