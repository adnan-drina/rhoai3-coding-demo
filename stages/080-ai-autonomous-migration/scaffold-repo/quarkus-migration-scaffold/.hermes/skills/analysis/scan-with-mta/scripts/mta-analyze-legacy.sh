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

# Resolve project root by walking up to migration.yaml (depth-safe after
# categorized skill tree: .hermes/skills/<cat>/<skill>/scripts/).
# Fixed-depth ../../../.. incorrectly landed on .hermes/ after analysis/ was inserted.
resolve_project_root() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf "%s\n" "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}
ROOT="$(resolve_project_root)" || { echo "mta-analyze-legacy: cannot find migration.yaml walking up from $(dirname "$0")" >&2; exit 1; }
MANIFEST="${ROOT}/evidence/derived/legacy-at-3.json"
MIGRATION_YAML="${ROOT}/migration.yaml"
OUT_DIR="${MTA_OUT_DIR:-${ROOT}/evidence/mta}"
JSON_OUT="${MTA_JSON_OUT:-${ROOT}/evidence/mta-findings.json}"

die() { echo "mta-analyze-legacy: $*" >&2; exit 1; }

# B-19: PyYAML lives on python3.11 (UDI python3 → 3.9). Prefer 3.11 for
# upstream YAML; lite-parser fallback stays in the targets reader below.
python_for_yaml() {
  if command -v python3.11 >/dev/null 2>&1 && python3.11 -c "import yaml" >/dev/null 2>&1; then
    printf '%s\n' "python3.11"
    return 0
  fi
  printf '%s\n' "python3"
}

convert_yaml_json() {
  local src="$1" dest="$2"
  if command -v python3.11 >/dev/null 2>&1 && python3.11 -c "import yaml" >/dev/null 2>&1; then
    python3.11 - "${src}" "${dest}" <<'PY'
import json, sys, yaml
src, dest = sys.argv[1], sys.argv[2]
json.dump(yaml.safe_load(open(src, encoding="utf-8")), open(dest, "w", encoding="utf-8"), indent=2)
print(f"converted {src} -> {dest}", file=sys.stderr)
PY
    return 0
  fi
  if command -v yq >/dev/null 2>&1; then
    yq -o=json "${src}" > "${dest}"
    echo "converted ${src} -> ${dest} (yq)" >&2
    return 0
  fi
  return 1
}

PYTHON_YAML="$(python_for_yaml)"

# UPLIFT-2: progress + human OK on stderr; one JSON object on stdout.
emit_ok() {
  local human="$1"
  shift
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]),separators=(",",":")))' "$1"
  printf '%s\n' "${human}" >&2
}

ensure_cli() {
  # Prefer absolute kantra path; keep mta-cli as atomic symlink alias (F-M1.3).
  local kantra_bin="/projects/.tools/kantra/kantra"
  local mta_alias="/projects/.tools/kantra/mta-cli"
  export PATH="${HOME}/.local/bin:/projects/.tools/kantra:${PATH}"

  _link_mta_alias() {
    if [ -x "${kantra_bin}" ]; then
      ln -sfn kantra "${mta_alias}"
      [ -x "${mta_alias}" ] || [ -x "${kantra_bin}" ] || return 1
    fi
    return 0
  }

  if [ -x "${kantra_bin}" ]; then
    _link_mta_alias || true
    printf '%s\n' "${kantra_bin}"
    return 0
  fi
  if command -v kantra >/dev/null 2>&1; then
    command -v kantra
    return 0
  fi
  if command -v mta-cli >/dev/null 2>&1 && [ -x "$(command -v mta-cli)" ]; then
    command -v mta-cli
    return 0
  fi
  if [ -x "${HOME}/.local/bin/kantra-ensure" ]; then
    echo "mta-analyze-legacy: running kantra-ensure (lazy ~690MB install)…" >&2
    # Helper status must not join CLI="$(ensure_cli)" (v30: stdout "Downloading
    # kantra…" became the analyze argv0). Discard helper stdout; path comes
    # from the probes below.
    "${HOME}/.local/bin/kantra-ensure" >/dev/null
    export PATH="/projects/.tools/kantra:${HOME}/.local/bin:${PATH}"
    _link_mta_alias || true
  fi
  if [ -x "${kantra_bin}" ]; then
    printf '%s\n' "${kantra_bin}"
    return 0
  fi
  if command -v kantra >/dev/null 2>&1; then
    command -v kantra
    return 0
  fi
  if command -v mta-cli >/dev/null 2>&1 && [ -x "$(command -v mta-cli)" ]; then
    command -v mta-cli
    return 0
  fi
  return 1
}

CLI="$(ensure_cli)" || die "mta-cli/kantra missing after kantra-ensure — re-run once; prefer /projects/.tools/kantra/kantra"
case "${CLI}" in
  *$'\n'*)
    die "ensure_cli captured a newline (kantra-ensure status leaked onto stdout): $(printf %q "${CLI}")"
    ;;
esac
[ -x "${CLI}" ] || die "ensure_cli path is not executable: $(printf %q "${CLI}")"

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
done < <("${PYTHON_YAML}" - "${MIGRATION_YAML}" <<'PY'
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

# Clean-room finding 2026-08-09 (v8): analyzer-lsp hard-codes
# `-configuration ./` and often empty `-data`, so Equinox dirs land in cwd.
# Never run analyze with cwd inside the destination git root.
MTA_RUN_CWD="${MTA_RUN_CWD:-/projects/.tools/mta-run}"
mkdir -p "${MTA_RUN_CWD}"
# JDT/m2e must write `.project` into the analyzed tree. Frozen harvest_referent
# (derive freeze_tree a-w) causes AccessDeniedException and a silent hang.
ANALYZE_INPUT="${INPUT}"
if ! ( touch "${INPUT}/.mta-write-probe" 2>/dev/null && rm -f "${INPUT}/.mta-write-probe" ); then
  ANALYZE_INPUT="${MTA_ANALYZE_INPUT:-/projects/.derived/legacy-at-3-mta-input}"
  echo "mta-analyze-legacy: harvest_referent is not writable — cloning to ${ANALYZE_INPUT}" >&2
  rm -rf "${ANALYZE_INPUT}"
  mkdir -p "${ANALYZE_INPUT}"
  tar -C "${INPUT}" -cf - . | tar -C "${ANALYZE_INPUT}" -xf -
  chmod -R u+w "${ANALYZE_INPUT}" 2>/dev/null || true
fi

echo "Analyzing INPUT=${ANALYZE_INPUT} (legacy@3.x referent; frozen source=${INPUT})" >&2
echo "MTA_RUN_CWD=${MTA_RUN_CWD} (Equinox -configuration ./ containment)" >&2
echo "Targets:${TARGET_LIST}" >&2
echo "NOTE: --source is intentionally omitted (AD-003 amendment A)." >&2

# --json-output can fail after a successful analysis (kantra marshal of
# dependencies.yaml: map[interface{}]interface{}). Treat tool exit as soft if
# OUT_DIR still has output.json / output.yaml (AD-003 / live P10 retry path).
set +e
(
  cd "${MTA_RUN_CWD}"
  "${CLI}" analyze \
    --input "${ANALYZE_INPUT}" \
    --output "${OUT_DIR}" \
    "${TARGET_FLAGS[@]}" \
    --json-output "${JSON_OUT}" \
    --overwrite
)
analyze_rc=$?
set -e

if [[ ! -s "${JSON_OUT}" ]]; then
  if [[ -s "${OUT_DIR}/output.json" ]]; then
    echo "mta-analyze-legacy: --json-output missing/empty (analyze_rc=${analyze_rc}); falling back to ${OUT_DIR}/output.json" >&2
    cp -f "${OUT_DIR}/output.json" "${JSON_OUT}"
  elif [[ -s "${OUT_DIR}/output.yaml" ]]; then
    echo "mta-analyze-legacy: --json-output missing/empty (analyze_rc=${analyze_rc}); converting ${OUT_DIR}/output.yaml" >&2
    convert_yaml_json "${OUT_DIR}/output.yaml" "${JSON_OUT}" \
      || die "analyze wrote output.yaml but YAML→JSON conversion failed (need python3.11+PyYAML or yq; analyze_rc=${analyze_rc})"
  else
    die "mta-cli analyze failed (rc=${analyze_rc}) with no ${OUT_DIR}/output.json|output.yaml"
  fi
fi

INPUT_DIGEST="$(python3 - "${MANIFEST}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("sha256", ""))
PY
)"
# Preserve model: envelope + codeSnip required (provisional schema lock).
# Digest form matches live P10: legacy-at-3:<sha256>
python3 "$(cd "$(dirname "$0")" && pwd)/normalize-findings.py" \
  "${JSON_OUT}" "${CLI}" "$(echo "${TARGET_LIST}" | xargs | tr ' ' ',')" "legacy-at-3:${INPUT_DIGEST}" \
  "${OUT_DIR}/rules-coverage.json" \
  "${OUT_DIR}/static-report/index.html"
python3 "$(cd "$(dirname "$0")" && pwd)/assert-mta-rescan.py" "${ROOT}" \
  --snapshot-m1 --findings "${JSON_OUT}" \
  || die "M1 findings digest snapshot failed (WC-5)"
python3 "$(cd "$(dirname "$0")" && pwd)/validate-findings-schema.py" "${JSON_OUT}" \
  || die "findings failed provisional schema validation (governance/schemas/mta-findings.md; skill scan-with-mta)"

# M1→M2 seam: bounded handoff index (no codeSnip). Evidence store stays at JSON_OUT.
python3 "$(cd "$(dirname "$0")" && pwd)/emit-findings-handoff.py" "${ROOT}" "${JSON_OUT}" \
  "${ROOT}/evidence/findings-handoff.json" \
  || die "emit findings-handoff failed (governance/schemas/findings-handoff.md)"
python3 "$(cd "$(dirname "$0")" && pwd)/check-findings-handoff.py" "${ROOT}" \
  || die "findings-handoff gate failed after emit"
python3 "$(cd "$(dirname "$0")" && pwd)/emit-required-extensions.py" "${ROOT}" \
  || die "emit required-extensions failed (V35-EXTENSIONS; M1 must emit the set)"

HANDOFF="${ROOT}/evidence/findings-handoff.json"
REQUIRED_EXT="${ROOT}/evidence/required-extensions.json"
STATIC_REPORT="${OUT_DIR}/static-report/index.html"
COVERAGE="${OUT_DIR}/rules-coverage.json"
HUMAN="OK: findings → ${JSON_OUT}  handoff → ${HANDOFF}  required-extensions → ${REQUIRED_EXT}  coverage → ${COVERAGE}  report → ${OUT_DIR}"
emit_ok "${HUMAN}" "$(python3 - "${JSON_OUT}" "${HANDOFF}" "${OUT_DIR}" "${ANALYZE_INPUT}" "${COVERAGE}" "${STATIC_REPORT}" "${REQUIRED_EXT}" <<'PY'
import json, os, sys
print(json.dumps({
    "script": "mta-analyze-legacy",
    "ok": True,
    "findings": sys.argv[1],
    "handoff": sys.argv[2],
    "report_dir": sys.argv[3],
    "analyze_input": sys.argv[4],
    "rules_coverage": sys.argv[5],
    "static_report": sys.argv[6],
    "static_report_present": os.path.isfile(sys.argv[6]),
    "required_extensions": sys.argv[7],
    "required_extensions_present": os.path.isfile(sys.argv[7]),
}))
PY
)"
