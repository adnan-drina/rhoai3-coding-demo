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
#   bash scripts/derive-legacy-boot3.sh
#
# Optional:
#   DERIVE_UPGRADE_CMD='…'   command run inside the copy when upgrade needed
#                            (default attempts OpenRewrite UpgradeSpringBoot_3_0)
set -euo pipefail

LEGACY_SRC="${LEGACY_SRC:-/projects/legacy}"
DERIVED_ROOT="${DERIVED_ROOT:-/projects/.derived/legacy-at-3}"
MODERNIZED_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST_DIR="${MODERNIZED_ROOT}/migration/derived"
MANIFEST="${MANIFEST_DIR}/legacy-at-3.json"

die() { echo "derive-legacy-boot3: $*" >&2; exit 1; }

[ -d "${LEGACY_SRC}" ] || die "missing LEGACY_SRC=${LEGACY_SRC}"
[ -f "${LEGACY_SRC}/pom.xml" ] || die "no pom.xml under ${LEGACY_SRC}"

mkdir -p "${MANIFEST_DIR}"

# Extract spring-boot.version (property) or parent version heuristic.
detect_boot_version() {
  local pom="$1"
  local ver
  ver="$(python3 - "$pom" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
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
print("")
PY
)"
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
  local mode="$1" src_ver="$2" der_ver="$3" sha="$4" referent="$5"
  python3 - "$MANIFEST" "$mode" "$src_ver" "$der_ver" "$sha" "$referent" \
    "${LEGACY_SRC}" "${DERIVED_ROOT}" <<'PY'
import json, sys, datetime
path, mode, src_ver, der_ver, sha, referent, legacy, derived = sys.argv[1:9]
doc = {
    "schema": "legacy-at-3/v1",
    "mode": mode,
    "legacy_src": legacy,
    "derived_root": derived,
    "harvest_referent": referent,
    "spring_boot_version_source": src_ver,
    "spring_boot_version_derived": der_ver,
    "sha256": sha,
    "frozen_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "note": "Harvest faithfulness compares destination to harvest_referent (legacy@3.x), never to legacy@2.x alone.",
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
print(f"Wrote manifest {path}")
PY
}

SRC_VER="$(detect_boot_version "${LEGACY_SRC}/pom.xml")"
[ -n "${SRC_VER}" ] || die "could not detect spring-boot version in ${LEGACY_SRC}/pom.xml"
echo "legacy@2.x mount: ${LEGACY_SRC} (spring-boot ${SRC_VER})"

if version_ge_3 "${SRC_VER}"; then
  echo "mode=identity — already Boot 3.x; derivation is the RO mount"
  write_manifest "identity" "${SRC_VER}" "${SRC_VER}" "$(tree_sha256 "${LEGACY_SRC}")" "${LEGACY_SRC}"
  echo "OK: harvest_referent=${LEGACY_SRC}"
  exit 0
fi

echo "mode=derived — producing frozen legacy@3.x under ${DERIVED_ROOT}"

mkdir -p "$(dirname "${DERIVED_ROOT}")"

# Rebuild cleanly when re-running (frozen trees cannot be updated in place).
if [ -e "${DERIVED_ROOT}" ]; then
  chmod -R u+w "${DERIVED_ROOT}" 2>/dev/null || true
  rm -rf "${DERIVED_ROOT}"
fi
mkdir -p "${DERIVED_ROOT}"
# Copy without .git (provenance stays on the RO mount).
rsync -a --delete \
  --exclude '.git/' \
  --exclude 'target/' \
  "${LEGACY_SRC}/" "${DERIVED_ROOT}/"

run_upgrade() {
  if [ -n "${DERIVE_UPGRADE_CMD:-}" ]; then
    echo "Running DERIVE_UPGRADE_CMD in ${DERIVED_ROOT}"
    ( cd "${DERIVED_ROOT}" && bash -c "${DERIVE_UPGRADE_CMD}" )
    return
  fi
  # Default: OpenRewrite Boot 2→3 recipe (AD-005). May require recipe artifacts
  # the workspace can resolve; override with DERIVE_UPGRADE_CMD when needed.
  echo "Running default OpenRewrite UpgradeSpringBoot_3_0 in ${DERIVED_ROOT}"
  (
    cd "${DERIVED_ROOT}"
    export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
    export PATH="${JAVA_HOME}/bin:${PATH}"
    mvn -q org.openrewrite.maven:rewrite-maven-plugin:5.40.0:run \
      -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-spring:2.14.0 \
      -Drewrite.activeRecipes=org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0
  )
}

if ! run_upgrade; then
  die "upgrade failed — set DERIVE_UPGRADE_CMD or ensure OpenRewrite Boot-3 recipes resolve (AD-005). RO mount left untouched."
fi

DER_VER="$(detect_boot_version "${DERIVED_ROOT}/pom.xml")"
version_ge_3 "${DER_VER}" || die "after upgrade spring-boot.version is '${DER_VER}' (want >= 3)"

SHA="$(tree_sha256 "${DERIVED_ROOT}")"
freeze_tree "${DERIVED_ROOT}"
write_manifest "derived" "${SRC_VER}" "${DER_VER}" "${SHA}" "${DERIVED_ROOT}"
echo "OK: frozen legacy@3.x at ${DERIVED_ROOT} sha256=${SHA}"
echo "    harvest_referent=${DERIVED_ROOT} (do not compare harvest to ${LEGACY_SRC})"
