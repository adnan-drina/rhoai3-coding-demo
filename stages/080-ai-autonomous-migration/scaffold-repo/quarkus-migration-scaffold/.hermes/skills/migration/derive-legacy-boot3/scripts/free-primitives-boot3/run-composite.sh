#!/usr/bin/env bash
# Free-primitives Boot 2→3 composite (W2 §12).
# Run with cwd = derived legacy tree (DERIVE_UPGRADE_CMD context).
#
# Env:
#   COMPOSITE_ROOT   tree to transform (default: cwd)
#   APPLY_LOG_PATH   where to write free-primitives-apply-log.json
#                    (default: TMPDIR when COMPOSITE_ROOT looks like golden tip;
#                     else COMPOSITE_ROOT/.rhoai3-free-primitives-apply-log.json)
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

# Fail-closed default when unset and cwd/COMPOSITE_ROOT is the golden tip.
if [[ -z "${APPLY_LOG_PATH:-}" ]]; then
  if [[ -f "${COMPOSITE_ROOT}/BOOTSTRAP.md" && -d "${COMPOSITE_ROOT}/governance" ]]; then
    export APPLY_LOG_PATH="${TMPDIR:-/tmp}/rhoai3-free-primitives-apply-log.json"
  fi
fi

emit_ok() {
  local human="$1"
  shift
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]),separators=(",",":")))' "$1"
  printf '%s\n' "${human}" >&2
}

echo "free-primitives-boot3: COMPOSITE_ROOT=${COMPOSITE_ROOT}" >&2
echo "free-primitives-boot3: APPLY_LOG_PATH=${APPLY_LOG_PATH:-<default beside COMPOSITE_ROOT>}" >&2

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

# Fresh apply log for this invocation
if [ -n "${APPLY_LOG_PATH:-}" ]; then
  mkdir -p "$(dirname "${APPLY_LOG_PATH}")"
  rm -f "${APPLY_LOG_PATH}"
fi

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
