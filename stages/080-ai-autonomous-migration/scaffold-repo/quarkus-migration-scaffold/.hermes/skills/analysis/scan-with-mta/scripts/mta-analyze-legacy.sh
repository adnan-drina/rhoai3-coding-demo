#!/usr/bin/env bash
# AD-003 amendment A — harness M1/M5 analysis invocation.
#
#   mta-cli analyze --input <frozen analysis copy> --output … --target … \
#     --rules <custom ruleset with canary> [--json-output]
#
# NEVER pass --source (dated Track B evidence 2026-07-27: excludes
# source-labelless rules and narrows the set). Targets come from
# migration.yaml analysis.targets. Input is the FROZEN ORIGINAL SOURCE
# (freeze-migration-input analysis_copy), never a derived Boot 3 tree and
# never the RO mount working copy. The run is recorded in
# evidence/producers/mta.json (emit-mta-receipt.py) with binary,
# provider, ruleset, argument, input, and canary provenance.
set -euo pipefail

# Hermes worker HOME is the profile home (implementer), not the human
# account. kantra-ensure lives under the UDI user home (/home/user).
# Operator 141853Z-op: never use ${HOME} for that binary.
human_home() {
  local h
  # getent on Linux seats; the pwd database everywhere else (same contract as lib/human_home.py)
  if command -v getent >/dev/null 2>&1; then
    h="$(getent passwd "$(id -u)" | cut -d: -f6 || true)"
  else
    h="$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)' 2>/dev/null || true)"
  fi
  if [ -n "${h}" ] && [ -d "${h}" ]; then
    printf '%s\n' "${h}"
    return 0
  fi
  printf '%s\n' "/home/user"
}

HUMAN_HOME="${HUMAN_HOME:-$(human_home)}"

# Capability probe (Architect E-20260825T072032ZA / rule ensure-cli-capability.md):
# `[ -x kantra ]` is not usability. After each resolved path, dest-init
# `kantra-assert-exec` runs on the realpath install prefix. Failure falls
# through (overlay `/opt/kantra` is not chmod-able by the dest uid). Do not
# add a version or provider-RPC handshake (Research E-20260825T073015ZS).
_kantra_install_prefix() {
  local bin="$1"
  python3 -c 'import os, sys
p = sys.argv[1]
if not os.path.exists(p):
    raise SystemExit(1)
print(os.path.dirname(os.path.realpath(p)))' "${bin}"
}

_kantra_assert_prefix() {
  local bin="$1"
  local prefix checker
  checker="${HUMAN_HOME}/.local/bin/kantra-assert-exec"
  if [ ! -x "${checker}" ]; then
    echo "mta-analyze-legacy: missing ${checker}; cannot prove kantra usability" >&2
    return 1
  fi
  prefix="$(_kantra_install_prefix "${bin}")" || return 1
  echo "mta-analyze-legacy: kantra-assert-exec ${prefix}" >&2
  "${checker}" "${prefix}"
}

_accept_cli() {
  local bin="$1"
  [ -n "${bin}" ] || return 1
  [ -x "${bin}" ] || return 1
  _kantra_assert_prefix "${bin}" || return 1
  printf '%s\n' "${bin}"
  return 0
}

_probe_kantra_bin() {
  local bin="$1"
  if [ -x "${bin}" ]; then
    if _accept_cli "${bin}"; then
      return 0
    fi
    echo "mta-analyze-legacy: ${bin} present but unusable; falling through" >&2
  fi
  return 1
}

_probe_path_cmd() {
  local name="$1"
  local candidate
  candidate="$(command -v "${name}" 2>/dev/null || true)"
  if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
    if _accept_cli "${candidate}"; then
      return 0
    fi
    echo "mta-analyze-legacy: ${name} at ${candidate} present but unusable; falling through" >&2
  fi
  return 1
}

ensure_cli() {
  # Product order (SAD §2): the pinned MTA CLI 8.2 artifact first
  # (MTA_CLI_HOME / .hermes/pins.json mta_cli.install_prefix), then kantra.
  # A kantra hit is a PROVISIONAL, NON-ADMISSIBLE fallback: the receipt
  # records provenance=kantra-fallback and admission blocks (MTA_PROVENANCE).
  local mta_home="${MTA_CLI_HOME:-/opt/mta-cli}"
  local home_kantra="${KANTRA_HOME:-/projects/.tools/kantra}"
  local kantra_bin="${home_kantra}/kantra"
  local mta_alias="${home_kantra}/mta-cli"
  export PATH="${HUMAN_HOME}/.local/bin:${mta_home}:${home_kantra}:${PATH}"

  _link_mta_alias() {
    if [ -x "${kantra_bin}" ]; then
      ln -sfn kantra "${mta_alias}"
      [ -x "${mta_alias}" ] || [ -x "${kantra_bin}" ] || return 1
    fi
    return 0
  }

  _try_resolved_clis() {
    _probe_kantra_bin "${mta_home}/mta-cli" && return 0
    _link_mta_alias || true
    _probe_kantra_bin "${kantra_bin}" && return 0
    _probe_path_cmd kantra && return 0
    _probe_path_cmd mta-cli && return 0
    return 1
  }

  if _try_resolved_clis; then
    return 0
  fi
  if [ -x "${HUMAN_HOME}/.local/bin/kantra-ensure" ]; then
    echo "mta-analyze-legacy: running kantra-ensure (lazy ~690MB install; provisional fallback)…" >&2
    # Helper status must not join CLI="$(ensure_cli)" (v30: stdout "Downloading
    # kantra…" became the analyze argv0). Discard helper stdout; path comes
    # from the probes below.
    "${HUMAN_HOME}/.local/bin/kantra-ensure" >/dev/null
    export PATH="${home_kantra}:${HUMAN_HOME}/.local/bin:${PATH}"
    _link_mta_alias || true
  fi
  _try_resolved_clis
}

# assert-ensure-cli-path.sh sources this file as a library (no analyze).
if [ "${ENSURE_CLI_LIB:-0}" = 1 ]; then
  return 0 2>/dev/null || exit 0
fi

# Resolve project root by walking up to migration.yaml (depth-safe after
# categorized skill tree: .hermes/skills/<cat>/<skill>/scripts/).
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
# Isolated rehearsal (and any caller) must name the destination. Walking up
# from this script otherwise lands on the dest clone that ships the skill
# (PetClinic v2 2026-09-09: /tmp/rehearsal wrote MTA artefacts onto
# /projects/modernized and skipped /tmp/rehearsal/evidence/producers/mta.json).
ROOT=""
if [ "${1:-}" = "--root" ]; then
  ROOT="${2:-}"
  shift 2
elif [ -n "${1:-}" ] && [ -f "${1}/migration.yaml" ]; then
  ROOT="${1}"
  shift
fi
if [ -z "${ROOT}" ]; then
  ROOT="$(resolve_project_root)" || { echo "mta-analyze-legacy: cannot find migration.yaml walking up from $(dirname "$0")" >&2; exit 1; }
fi
[ -f "${ROOT}/migration.yaml" ] || { echo "mta-analyze-legacy: no migration.yaml under ${ROOT}" >&2; exit 1; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
FREEZE="${ROOT}/evidence/producers/freeze.json"
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

CLI="$(ensure_cli)" || die "mta-cli/kantra missing or unusable after kantra-ensure — re-run once; prefer the pinned MTA CLI 8.2 (MTA_CLI_HOME)"
# Measured product version (provenance; the receipt compares it with pins.mta_cli.version).
# MTA CLI 8.2 answers the `version` subcommand ("version: 8.2.1"); its `--version`
# prints usage (measured on the ws-080 image 2026-09-09). Keep the first line that
# carries a dotted number; an unmeasurable version is non-admissible by design.
CLI_VERSION="$("${CLI}" version 2>/dev/null | grep -m1 -E '[0-9]+\.[0-9]+' || true)"
[ -n "${CLI_VERSION}" ] || CLI_VERSION="$("${CLI}" --version 2>/dev/null | grep -m1 -E '[0-9]+\.[0-9]+' || true)"
case "${CLI}" in
  *$'\n'*)
    die "ensure_cli captured a newline (kantra-ensure status leaked onto stdout): $(printf %q "${CLI}")"
    ;;
esac
[ -x "${CLI}" ] || die "ensure_cli path is not executable: $(printf %q "${CLI}")"

[ -f "${FREEZE}" ] || die "missing ${FREEZE} — run freeze-migration-input first (the frozen original source is the only admitted MTA input)"
[ -f "${MIGRATION_YAML}" ] || die "missing ${MIGRATION_YAML}"

# Java 21 required (kantra analyzer bundles osgi.ee=JavaSE-21; Java 17 wedges).
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
export PATH="${JAVA_HOME}/bin:${PATH}"
java -version 2>&1 | head -1 || true
[ -n "${JVM_MAX_MEM:-}" ] || die "JVM_MAX_MEM unset (AD-003) — set in the Dev Spaces container env"

INPUT="$(python3 - "${FREEZE}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("analysis_copy") or "")
PY
)"
[ -n "${INPUT}" ] || die "freeze receipt names no analysis_copy (pass --copy-to to freeze-migration-input; MTA needs a writable byte-identical copy)"
[ -d "${INPUT}" ] || die "analysis_copy not a directory: ${INPUT}"
INPUT_DIGEST="$(python3 - "${FREEZE}" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8")).get("source_digest", ""))
PY
)"
[ -n "${INPUT_DIGEST}" ] || die "freeze receipt has no source_digest"

# Byte-identity of the analysis copy vs the frozen manifest, BEFORE analysis.
python3 "${SCRIPTS}/assert-frozen-input-intact.py" "${ROOT}" || die "analysis copy diverged from the frozen manifest; refreeze (nothing may transform the input before baseline analysis)"

# Expand analysis.targets → repeated --target flags (no --source).
read_yaml_list() {
  "${PYTHON_YAML}" - "${MIGRATION_YAML}" "$1" <<'PY'
import sys
key = sys.argv[2]
try:
    import yaml
except ImportError:
    text = open(sys.argv[1], encoding="utf-8").read().splitlines()
    inside = False
    for ln in text:
        if ln.strip().startswith(key + ":"):
            inside = True
            continue
        if inside:
            s = ln.strip()
            if s.startswith("- "):
                print(s[2:].strip().strip("\"'"))
            elif s and not s.startswith("#") and not s.startswith("-"):
                break
    raise SystemExit
doc = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
for t in (doc.get("analysis") or {}).get(key) or []:
    print(t)
PY
}
read_yaml_scalar() {
  "${PYTHON_YAML}" - "${MIGRATION_YAML}" "$1" <<'PY'
import sys
key = sys.argv[2]
try:
    import yaml
    doc = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
    print((doc.get("analysis") or {}).get(key) or "")
    raise SystemExit
except ImportError:
    pass
for ln in open(sys.argv[1], encoding="utf-8"):
    s = ln.strip()
    if s.startswith(key + ":"):
        print(s.split(":", 1)[1].strip().strip("\"'"))
        break
PY
}
TARGET_FLAGS=()
TARGET_LIST=""
while IFS= read -r t; do
  [ -n "${t}" ] || continue
  TARGET_FLAGS+=(--target "${t}")
  TARGET_LIST="${TARGET_LIST} ${t}"
done < <(read_yaml_list targets)
[ "${#TARGET_FLAGS[@]}" -gt 0 ] || die "no analysis.targets in ${MIGRATION_YAML}"

# Custom ruleset with the canary (SAD §5.1). No --source: custom rules
# carry target labels for each configured target (see ruleset.yaml).
RULES_REL="$(read_yaml_scalar custom_rules)"
CANARY_ID="$(read_yaml_scalar canary_rule_id)"
RULES_FLAGS=()
RULES_DIR=""
if [ -n "${RULES_REL}" ]; then
  RULES_DIR="${ROOT}/${RULES_REL#/}"
  [ -d "${RULES_DIR}" ] || die "analysis.custom_rules ${RULES_DIR} is not a directory"
  RULES_FLAGS=(--rules "${RULES_DIR}")
fi

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}" "$(dirname "${JSON_OUT}")"

# Clean-room finding 2026-08-09 (v8): analyzer-lsp hard-codes
# `-configuration ./` and often empty `-data`, so Equinox dirs land in cwd.
# Never run analyze with cwd inside the destination git root.
MTA_RUN_CWD="${MTA_RUN_CWD:-/projects/.tools/mta-run}"
mkdir -p "${MTA_RUN_CWD}"

echo "Analyzing INPUT=${INPUT} (frozen original source; digest=${INPUT_DIGEST})" >&2
echo "MTA_RUN_CWD=${MTA_RUN_CWD} (Equinox -configuration ./ containment)" >&2
echo "Targets:${TARGET_LIST}" >&2
[ -n "${RULES_DIR}" ] && echo "Custom rules: ${RULES_DIR} (canary ${CANARY_ID:-<none>})" >&2
echo "NOTE: --source is intentionally omitted (AD-003 amendment A)." >&2

ARGV=("${CLI}" analyze --input "${INPUT}" --output "${OUT_DIR}" "${TARGET_FLAGS[@]}" "${RULES_FLAGS[@]}" --json-output "${JSON_OUT}" --overwrite)
printf '%s\n' "${ARGV[@]}" > "${OUT_DIR}/argv.txt"

# --json-output can fail after a successful analysis (kantra marshal of
# dependencies.yaml: map[interface{}]interface{}). Treat tool exit as soft if
# OUT_DIR still has output.json / output.yaml (AD-003 / live P10 retry path).
set +e
( cd "${MTA_RUN_CWD}" && "${ARGV[@]}" )
analyze_rc=$?
set -e
echo "${analyze_rc}" > "${OUT_DIR}/analyze.rc"

if [[ ! -s "${JSON_OUT}" ]]; then
  if [[ -s "${OUT_DIR}/output.json" ]]; then
    echo "mta-analyze-legacy: --json-output missing/empty (analyze_rc=${analyze_rc}); falling back to ${OUT_DIR}/output.json" >&2
    cp -f "${OUT_DIR}/output.json" "${JSON_OUT}"
  elif [[ -s "${OUT_DIR}/output.yaml" ]]; then
    echo "mta-analyze-legacy: --json-output missing/empty (analyze_rc=${analyze_rc}); converting ${OUT_DIR}/output.yaml" >&2
    convert_yaml_json "${OUT_DIR}/output.yaml" "${JSON_OUT}" \
      || die "analyze wrote output.yaml but YAML→JSON conversion failed (need python3.11+PyYAML or yq; analyze_rc=${analyze_rc})"
  else
    python3 "${SCRIPTS}/emit-mta-receipt.py" "${ROOT}" --cli "${CLI}" --cli-version "${CLI_VERSION}" --status failed --exit-status "${analyze_rc}" --targets "$(echo "${TARGET_LIST}" | xargs | tr ' ' ',')" --rules-dir "${RULES_DIR}" --canary-id "${CANARY_ID}" --input "${INPUT}" || true
    die "mta-cli analyze failed (rc=${analyze_rc}) with no ${OUT_DIR}/output.json|output.yaml"
  fi
fi

# Preserve model: envelope + codeSnip required (provisional schema lock).
# Digest form: frozen:<source sha256>
python3 "${SCRIPTS}/normalize-findings.py" \
  "${JSON_OUT}" "${CLI}" "$(echo "${TARGET_LIST}" | xargs | tr ' ' ',')" "frozen:${INPUT_DIGEST}" \
  "${OUT_DIR}/rules-coverage.json" \
  "${OUT_DIR}/static-report/index.html"
python3 "${SCRIPTS}/assert-mta-rescan.py" "${ROOT}" \
  --snapshot-m1 --findings "${JSON_OUT}" \
  || die "M1 findings digest snapshot failed (WC-5)"
python3 "${SCRIPTS}/validate-findings-schema.py" "${JSON_OUT}" \
  || die "findings failed provisional schema validation (skill scan-with-mta)"

# Producer receipt with full provenance (binary, providers, rulesets, args,
# input, exit, output digest, canary). Admissibility is a recorded fact.
python3 "${SCRIPTS}/emit-mta-receipt.py" "${ROOT}" --cli "${CLI}" --cli-version "${CLI_VERSION}" --status ok --exit-status "${analyze_rc}" \
  --targets "$(echo "${TARGET_LIST}" | xargs | tr ' ' ',')" --rules-dir "${RULES_DIR}" --canary-id "${CANARY_ID}" \
  --input "${INPUT}" --findings "${JSON_OUT}" --argv-file "${OUT_DIR}/argv.txt" \
  || die "emit-mta-receipt failed"
python3 "${SCRIPTS}/assert-mta-canary.py" "${ROOT}" || echo "mta-analyze-legacy: WARN canary did not fire — admission will block CANARY_MISSING" >&2

# M1→M2 seam: bounded handoff index (no codeSnip). Evidence store stays at JSON_OUT.
python3 "${SCRIPTS}/emit-findings-handoff.py" "${ROOT}" "${JSON_OUT}" \
  "${ROOT}/evidence/findings-handoff.json" \
  || die "emit findings-handoff failed"
python3 "${SCRIPTS}/check-findings-handoff.py" "${ROOT}" \
  || die "findings-handoff gate failed after emit"
python3 "${SCRIPTS}/emit-required-extensions.py" "${ROOT}" \
  || die "emit required-extensions failed (V35-EXTENSIONS; M1 must emit the set)"

HANDOFF="${ROOT}/evidence/findings-handoff.json"
REQUIRED_EXT="${ROOT}/evidence/required-extensions.json"
STATIC_REPORT="${OUT_DIR}/static-report/index.html"
COVERAGE="${OUT_DIR}/rules-coverage.json"
RECEIPT="${ROOT}/evidence/producers/mta.json"
HUMAN="OK: findings → ${JSON_OUT}  receipt → ${RECEIPT}  handoff → ${HANDOFF}  required-extensions → ${REQUIRED_EXT}  coverage → ${COVERAGE}  report → ${OUT_DIR}"
emit_ok "${HUMAN}" "$(python3 - "${JSON_OUT}" "${HANDOFF}" "${OUT_DIR}" "${INPUT}" "${COVERAGE}" "${STATIC_REPORT}" "${REQUIRED_EXT}" "${RECEIPT}" <<'PY'
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
    "receipt": sys.argv[8],
}))
PY
)"
