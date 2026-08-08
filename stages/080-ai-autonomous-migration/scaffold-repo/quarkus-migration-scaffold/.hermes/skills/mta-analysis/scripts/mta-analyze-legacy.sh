#!/usr/bin/env bash
# AD-003 amendment A — harness M1/M5 analysis invocation.
#
#   mta-cli analyze --input <legacy@3.x> --output … --target … [--json-output]
#
# NEVER pass --source (dated Track B evidence 2026-07-27: excludes
# source-labelless rules and narrows the set). Targets come from
# migration.yaml analysis.targets. Input is harvest_referent (legacy@3.x),
# not the RO 2.x mount working copy.
set -euo pipefail

# Skill layout: .hermes/skills/mta-analysis/scripts/ → project root is ../../../..
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
MANIFEST="${ROOT}/migration/derived/legacy-at-3.json"
MIGRATION_YAML="${ROOT}/migration.yaml"
OUT_DIR="${MTA_OUT_DIR:-${ROOT}/migration/mta-analyze-out}"
JSON_OUT="${MTA_JSON_OUT:-${ROOT}/migration/mta-findings.json}"

die() { echo "mta-analyze-legacy: $*" >&2; exit 1; }

ensure_cli() {
  export PATH="${HOME}/.local/bin:/projects/.tools/kantra:${PATH}"
  if command -v mta-cli >/dev/null 2>&1; then
    command -v mta-cli
    return 0
  fi
  if command -v kantra >/dev/null 2>&1; then
    command -v kantra
    return 0
  fi
  if [ -x "${HOME}/.local/bin/kantra-ensure" ]; then
    echo "mta-analyze-legacy: running kantra-ensure (lazy ~690MB install)…"
    "${HOME}/.local/bin/kantra-ensure"
    export PATH="/projects/.tools/kantra:${HOME}/.local/bin:${PATH}"
    if [ -x /projects/.tools/kantra/kantra ] && [ ! -e /projects/.tools/kantra/mta-cli ]; then
      ln -sf kantra /projects/.tools/kantra/mta-cli
    fi
  fi
  if command -v mta-cli >/dev/null 2>&1; then
    command -v mta-cli
    return 0
  fi
  if command -v kantra >/dev/null 2>&1; then
    command -v kantra
    return 0
  fi
  return 1
}

CLI="$(ensure_cli)" || die "mta-cli (or kantra) not on PATH — run kantra-ensure / platform tooling"

[ -f "${MANIFEST}" ] || die "missing ${MANIFEST} — run derive-legacy-boot3 skill: bash \"\${HERMES_SKILL_DIR}/scripts/derive-legacy-boot3.sh\""
[ -f "${MIGRATION_YAML}" ] || die "missing ${MIGRATION_YAML}"

# Java 21 required (kantra analyzer bundles osgi.ee=JavaSE-21; Java 17 wedges).
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
export PATH="${JAVA_HOME}/bin:${PATH}"
java -version 2>&1 | head -1 || true
[ -n "${JVM_MAX_MEM:-}" ] || die "JVM_MAX_MEM unset (AD-003) — set in the Dev Spaces container env"

INPUT="$(python3 - "${MANIFEST}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["harvest_referent"])
PY
)"
[ -d "${INPUT}" ] || die "harvest_referent not a directory: ${INPUT}"

# Expand analysis.targets → repeated --target flags (no --source).
TARGET_FLAGS=()
TARGET_LIST=""
while IFS= read -r t; do
  [ -n "${t}" ] || continue
  TARGET_FLAGS+=(--target "${t}")
  TARGET_LIST="${TARGET_LIST} ${t}"
done < <(python3 - "${MIGRATION_YAML}" <<'PY'
import sys
try:
    import yaml
except ImportError:
    text = open(sys.argv[1], encoding="utf-8").read().splitlines()
    in_targets = False
    for ln in text:
        if ln.strip().startswith("targets:"):
            in_targets = True
            continue
        if in_targets:
            s = ln.strip()
            if s.startswith("- "):
                print(s[2:].strip().strip("\"'"))
            elif s and not s.startswith("#") and not s.startswith("-"):
                break
    raise SystemExit
doc = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
for t in (doc.get("analysis") or {}).get("targets") or []:
    print(t)
PY
)
[ "${#TARGET_FLAGS[@]}" -gt 0 ] || die "no analysis.targets in ${MIGRATION_YAML}"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}" "$(dirname "${JSON_OUT}")"

echo "Analyzing INPUT=${INPUT} (legacy@3.x referent)"
echo "Targets:${TARGET_LIST}"
echo "NOTE: --source is intentionally omitted (AD-003 amendment A)."

"${CLI}" analyze \
  --input "${INPUT}" \
  --output "${OUT_DIR}" \
  "${TARGET_FLAGS[@]}" \
  --json-output "${JSON_OUT}" \
  --overwrite

INPUT_DIGEST="$(python3 - "${MANIFEST}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("sha256", ""))
PY
)"
# Preserve model: envelope + codeSnip required (provisional schema lock).
python3 "$(cd "$(dirname "$0")" && pwd)/normalize-findings.py" \
  "${JSON_OUT}" "${CLI}" "$(echo "${TARGET_LIST}" | xargs | tr ' ' ',')" "${INPUT_DIGEST}"
python3 "$(cd "$(dirname "$0")" && pwd)/validate-findings-schema.py" "${JSON_OUT}" \
  || die "findings failed provisional schema validation (migration/schemas/mta-findings.md; skill mta-analysis)"

echo "OK: findings → ${JSON_OUT}  report → ${OUT_DIR}"
