#!/usr/bin/env bash
# W2 §3 amendment (AD-005 / Lead implement-derivation): Boot 2→3 is a pure
# derivation — never mutate /projects/legacy (read-only provenance).
#
#   legacy@2.x (RO) ──upgrade──▶ legacy@3.x (derived, hashed, frozen) ──▶ M1
#
# Skip-if-satisfied: when spring-boot.version >= 3, mode=identity and the
# harvest referent is the RO mount itself.
#
# Usage (from /projects/modernized, before M1):
#   bash "${HERMES_SKILL_DIR}/scripts/derive-legacy-boot3.sh"
#
# Optional:
#   DERIVE_UPGRADE_CMD='…'   override upgrade command inside the copy
#                            (default: free-primitives-boot3 composite, W2 §12)
#   MODERNIZED_ROOT=…        workshop selftest / dest override (default: walk
#                            to migration.yaml from this script)
set -euo pipefail

# --dry-run as first arg or DRY_RUN=1: print plan and exit 0 (no mkdir/rm/mutate).
if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  DRY_RUN=1
fi
DRY_RUN="${DRY_RUN:-0}"

LEGACY_SRC="${LEGACY_SRC:-/projects/legacy}"
# SR-2: walk up to migration.yaml — never a parent-count (V18-F1: 4-up landed on .hermes).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
resolve_migration_root() {
  local d="$1"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  echo "cannot find project root (migration.yaml) walking up from $1 (SR-2)" >&2
  return 1
}
MODERNIZED_ROOT="$(
  if [ -n "${MODERNIZED_ROOT:-}" ]; then
    cd "${MODERNIZED_ROOT}" && pwd
  else
    resolve_migration_root "${SCRIPT_DIR}"
  fi
)" || exit 1
# Operator 083840ZO GAP 3 / Architect 084356ZA: default under dest tree
# `/projects/modernized/.derived/…`. Do not add `/projects/.derived` to
# K2_ALLOW_ROOT (Architect 082958ZA).
DERIVED_ROOT="${DERIVED_ROOT:-${MODERNIZED_ROOT}/.derived/legacy-at-3}"
MANIFEST_DIR="${MODERNIZED_ROOT}/evidence/derived"
MANIFEST="${MANIFEST_DIR}/legacy-at-3.json"
COMPOSITE_SCRIPT="${SCRIPT_DIR}/free-primitives-boot3/run-composite.sh"
APPLY_LOG_DEFAULT="${DERIVED_ROOT}/.rhoai3-free-primitives-apply-log.json"

die() { echo "derive-legacy-boot3: $*" >&2; exit 1; }

# UPLIFT-2: progress + human OK on stderr; one JSON object on stdout.
emit_ok() {
  local human="$1"
  shift
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]),separators=(",",":")))' "$1"
  printf '%s\n' "${human}" >&2
}

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY-RUN: derive-legacy-boot3 plan" >&2
  echo "DRY-RUN: LEGACY_SRC=${LEGACY_SRC}" >&2
  echo "DRY-RUN: DERIVED_ROOT=${DERIVED_ROOT}" >&2
  echo "DRY-RUN: MANIFEST=${MANIFEST}" >&2
  echo "DRY-RUN: COMPOSITE_SCRIPT=${COMPOSITE_SCRIPT}" >&2
  echo "DRY-RUN: APPLY_LOG_DEFAULT=${APPLY_LOG_DEFAULT}" >&2
  emit_ok "DRY-RUN: derive-legacy-boot3 plan" "$(python3 -c 'import json; print(json.dumps({"script":"derive-legacy-boot3","ok":True,"dry_run":True}))')"
  exit 0
fi

[ -d "${LEGACY_SRC}" ] || die "missing LEGACY_SRC=${LEGACY_SRC}"
if [ -f "${LEGACY_SRC}/pom.xml" ]; then
  :
elif [ -f "${LEGACY_SRC}/build.gradle" ] || [ -f "${LEGACY_SRC}/build.gradle.kts" ]; then
  :
else
  die "no pom.xml or build.gradle under ${LEGACY_SRC}"
fi

mkdir -p "${MANIFEST_DIR}"

# Extract spring-boot.version from pom.xml or Gradle (gs-rest identity).
detect_boot_version() {
  local tree="$1"
  local ver
  ver=$(python3 - "$tree" <<'PY'
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
pom = root / "pom.xml"
if pom.is_file():
    text = pom.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<spring-boot\.version>\s*([^<]+)\s*</spring-boot\.version>", text)
    if m:
        print(m.group(1).strip()); raise SystemExit
    m = re.search(
        r"<parent>.*?<artifactId>\s*spring-boot-starter-parent\s*</artifactId>.*?"
        r"<version>\s*([^<]+)\s*</version>",
        text,
        re.S,
    )
    if m:
        print(m.group(1).strip()); raise SystemExit
for name in ("build.gradle", "build.gradle.kts"):
    p = root / name
    if not p.is_file():
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for pat in (
        r"id\s*\(\s*['\"]org\.springframework\.boot['\"]\s*\)\s*version\s+['\"]([^'\"]+)['\"]",
        r"id\s+['\"]org\.springframework\.boot['\"]\s+version\s+['\"]([^'\"]+)['\"]",
    ):
        m = re.search(pat, text)
        if m:
            print(m.group(1).strip()); raise SystemExit
print("")
PY
)
  printf '%s' "${ver}"
}

# JDK / language level (W2 §3.1) — property first, then Maven effective value.
detect_jdk_version() {
  local pom_dir="$1"
  local pom="${pom_dir}/pom.xml"
  local ver
  if [ -f "${pom}" ]; then
  ver="$(python3 - "$pom" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for pat in (
    r"<java\.version>\s*([^<]+)\s*</java\.version>",
    r"<maven\.compiler\.release>\s*([^<]+)\s*</maven\.compiler\.release>",
    r"<maven\.compiler\.source>\s*([^<]+)\s*</maven\.compiler\.source>",
    r"<maven\.compiler\.target>\s*([^<]+)\s*</maven\.compiler\.target>",
):
    m = re.search(pat, text)
    if m:
        print(m.group(1).strip()); raise SystemExit
print("")
PY
)"
  if [ -n "${ver}" ]; then
    printf '%s' "${ver}"
    return 0
  fi
  # Parent-BOM specimens often omit java.version in the POM.
  if command -v mvn >/dev/null 2>&1; then
    ver="$(
      cd "${pom_dir}" \
        && mvn -q -DforceStdout help:evaluate -Dexpression=java.version 2>/dev/null \
        | tail -n 1 \
        | tr -d '[:space:]'
    )" || ver=""
    # help:evaluate can echo literal ${java.version} when unresolved
    if [[ -n "${ver}" && "${ver}" != \$\{*\} && "${ver}" != "null" ]]; then
      printf '%s' "${ver}"
      return 0
    fi
  fi
  fi
  ver=$(python3 - "${pom_dir}" <<'PY'
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
for name in ("build.gradle", "build.gradle.kts"):
    p = root / name
    if not p.is_file():
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for pat in (
        r"JavaLanguageVersion\.of\s*\(\s*(\d+)\s*\)",
        r"sourceCompatibility\s*=\s*['\"]?(\d+)",
        r"targetCompatibility\s*=\s*['\"]?(\d+)",
        r"JavaVersion\.VERSION_(\d+)",
    ):
        m = re.search(pat, text)
        if m:
            print(m.group(1).strip()); raise SystemExit
print("")
PY
)
  printf '%s' "${ver}"
}

version_ge_3() {
  local v="$1"
  [[ -n "${v}" ]] || return 1
  local major="${v%%.*}"
  [[ "${major}" =~ ^[0-9]+$ ]] || return 1
  (( major >= 3 ))
}

tree_sha256() {
  local root="$1"
  # Stable content hash of tracked-ish sources (exclude build outputs).
  (
    cd "${root}"
    find . -type f \
      ! -path './target/*' \
      ! -path './.git/*' \
      ! -path './.idea/*' \
      -print0 \
      | sort -z \
      | xargs -0 sha256sum 2>/dev/null \
      | sha256sum \
      | awk '{print $1}'
  )
}

freeze_tree() {
  local root="$1"
  # Immutable baseline: nothing may edit after production.
  chmod -R a-w "${root}" 2>/dev/null || true
  # Directories need +x to traverse while staying unwritable for creates.
  find "${root}" -type d -exec chmod a+x {} + 2>/dev/null || true
}

write_manifest() {
  # mode src_boot der_boot src_jdk der_jdk sha referent
  local mode="$1" src_boot="$2" der_boot="$3" src_jdk="$4" der_jdk="$5" sha="$6" referent="$7"
  python3 - "$MANIFEST" "$mode" "$src_boot" "$der_boot" "$src_jdk" "$der_jdk" "$sha" "$referent" \
    "${LEGACY_SRC}" "${DERIVED_ROOT}" <<'PY'
import json, sys, datetime
(path, mode, src_boot, der_boot, src_jdk, der_jdk, sha, referent,
 legacy, derived) = sys.argv[1:11]
note_identity = (
    "mode=identity: harvest_referent is the legacy mount (Spring Boot already "
    ">= 3). There is no derived_root. Do not resolve .derived/legacy-at-3."
)
note_derived = (
    "Harvest faithfulness compares destination to harvest_referent "
    "(the frozen Boot-3 derivation), never to legacy@2.x alone. JDK + Boot "
    "versions are recorded for diagnosability; derivation is still one frozen stage."
)
doc = {
    "schema": "legacy-at-3/v2",
    "mode": mode,
    "legacy_src": legacy,
    "harvest_referent": referent,
    "jdk_version_source": src_jdk,
    "jdk_version_derived": der_jdk,
    "spring_boot_version_source": src_boot,
    "spring_boot_version_derived": der_boot,
    "sha256": sha,
    "frozen_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "note": note_identity if mode == "identity" else note_derived,
}
if mode == "derived":
    doc["derived_root"] = derived
with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
print(f"Wrote manifest {path}", file=__import__("sys").stderr)
PY
}

SRC_VER="$(detect_boot_version "${LEGACY_SRC}")"
[ -n "${SRC_VER}" ] || die "could not detect spring-boot version in ${LEGACY_SRC}/pom.xml"
SRC_JDK="$(detect_jdk_version "${LEGACY_SRC}")"
[ -n "${SRC_JDK}" ] || die "could not detect JDK/language level in ${LEGACY_SRC}/pom.xml (java.version / compiler.* / mvn evaluate)"
echo "legacy mount: ${LEGACY_SRC} (spring-boot ${SRC_VER}, jdk ${SRC_JDK})" >&2

if version_ge_3 "${SRC_VER}"; then
  echo "mode=identity — already Boot 3.x; derivation is the RO mount" >&2
  SHA_ID="$(tree_sha256 "${LEGACY_SRC}")"
  write_manifest "identity" "${SRC_VER}" "${SRC_VER}" "${SRC_JDK}" "${SRC_JDK}" \
    "${SHA_ID}" "${LEGACY_SRC}"
  HUMAN="OK: harvest_referent=${LEGACY_SRC}"
  emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"derive-legacy-boot3","ok":True,"mode":"identity","harvest_referent":sys.argv[1],"sha256":sys.argv[2],"spring_boot":sys.argv[3],"jdk":sys.argv[4]}))' "${LEGACY_SRC}" "${SHA_ID}" "${SRC_VER}" "${SRC_JDK}")"
  exit 0
fi

echo "mode=derived — producing frozen legacy@3.x under ${DERIVED_ROOT}" >&2
mkdir -p "$(dirname "${DERIVED_ROOT}")"

# Rebuild cleanly when re-running (frozen trees cannot be updated in place).
if [ -e "${DERIVED_ROOT}" ]; then
  chmod -R u+w "${DERIVED_ROOT}" 2>/dev/null || true
  rm -rf "${DERIVED_ROOT}"
fi
mkdir -p "${DERIVED_ROOT}"
# Copy without .git (provenance stays on the RO mount).
# Dev Spaces tooling images often lack rsync — tar fallback keeps derive e2e
# runnable without mutating the RO mount or requiring package installs.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '.git/' \
    --exclude 'target/' \
    "${LEGACY_SRC}/" "${DERIVED_ROOT}/"
else
  echo "rsync unavailable — copying via tar (exclude .git/ and target/)" >&2
  (
    cd "${LEGACY_SRC}"
    tar -cf - \
      --exclude='.git' \
      --exclude='./.git' \
      --exclude='target' \
      --exclude='./target' \
      .
  ) | ( cd "${DERIVED_ROOT}" && tar -xf - )
fi

# FP-1: positive derived-tree marker (Deputy E-20260816T160604Z). Apply-log
# defaults write beside COMPOSITE_ROOT only when this file exists or the path
# has a `.derived` segment — "not the golden tip" is not enough.
printf '%s\n' 'schema: rhoai3.derived-tree/v1' > "${DERIVED_ROOT}/.rhoai3-derived-tree"

run_upgrade() {
  if [ -n "${DERIVE_UPGRADE_CMD:-}" ]; then
    echo "Running DERIVE_UPGRADE_CMD in ${DERIVED_ROOT}" >&2
    ( cd "${DERIVED_ROOT}" && bash -c "${DERIVE_UPGRADE_CMD}" )
    return
  fi
  # Default: free-primitives composite (W2 §12 SETTLED). Moderne
  # UpgradeSpringBoot_3_0 remains never-automatic (E-20260807T184100Z).
  [ -x "${COMPOSITE_SCRIPT}" ] || [ -f "${COMPOSITE_SCRIPT}" ] \
    || die "missing free-primitives composite at ${COMPOSITE_SCRIPT}"
  echo "Running free-primitives-boot3 composite in ${DERIVED_ROOT}" >&2
  (
    cd "${DERIVED_ROOT}"
    APPLY_LOG_PATH="${APPLY_LOG_DEFAULT}" COMPOSITE_ROOT="${DERIVED_ROOT}" \
      bash "${COMPOSITE_SCRIPT}"
  )
}

if ! run_upgrade; then
  die "upgrade failed — free-primitives composite or DERIVE_UPGRADE_CMD. RO mount left untouched."
fi

DER_VER="$(detect_boot_version "${DERIVED_ROOT}")"
version_ge_3 "${DER_VER}" || die "after upgrade spring-boot.version is '${DER_VER}' (want >= 3)"
DER_JDK="$(detect_jdk_version "${DERIVED_ROOT}")"
[ -n "${DER_JDK}" ] || die "could not detect JDK/language level after upgrade in ${DERIVED_ROOT}"

SHA="$(tree_sha256 "${DERIVED_ROOT}")"
freeze_tree "${DERIVED_ROOT}"
write_manifest "derived" "${SRC_VER}" "${DER_VER}" "${SRC_JDK}" "${DER_JDK}" \
  "${SHA}" "${DERIVED_ROOT}"
HUMAN="OK: frozen legacy@3.x at ${DERIVED_ROOT} sha256=${SHA}"
emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"derive-legacy-boot3","ok":True,"mode":"derived","harvest_referent":sys.argv[1],"sha256":sys.argv[2],"jdk_source":sys.argv[3],"jdk_derived":sys.argv[4],"boot_source":sys.argv[5],"boot_derived":sys.argv[6]}))' "${DERIVED_ROOT}" "${SHA}" "${SRC_JDK}" "${DER_JDK}" "${SRC_VER}" "${DER_VER}")"
echo "    harvest_referent=${DERIVED_ROOT} (do not compare harvest to ${LEGACY_SRC})" >&2
echo "    versions: jdk ${SRC_JDK}→${DER_JDK}; spring-boot ${SRC_VER}→${DER_VER}" >&2
