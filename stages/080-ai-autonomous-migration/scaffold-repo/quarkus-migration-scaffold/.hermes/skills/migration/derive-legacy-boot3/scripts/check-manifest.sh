#!/usr/bin/env bash
# Fail closed if the Boot 2→3 derivation manifest is missing or incomplete.
# M1 and harvest gates require harvest_referent (legacy@3.x).
# W2 §3.1: also require JDK + Spring Boot before/after version fields.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: check-manifest.sh [--help]

Fail closed if evidence/derived/legacy-at-3.json is missing or incomplete.
Interface probe only for --help (R-SK.12); does not emit gate OK/FAIL verdicts.
USAGE
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac
root="$(cd "$(dirname "$0")/../../../.." && pwd)"
manifest="${root}/evidence/derived/legacy-at-3.json"
if [ ! -f "${manifest}" ]; then
  echo "FAIL: ${manifest} missing — run the derive-legacy-boot3 skill (bash \"\${HERMES_SKILL_DIR}/scripts/derive-legacy-boot3.sh\")" >&2
  exit 1
fi
python3 - "$manifest" <<'PY'
import json, sys, os
doc = json.load(open(sys.argv[1], encoding="utf-8"))
required = (
    "schema",
    "mode",
    "harvest_referent",
    "sha256",
    "spring_boot_version_source",
    "spring_boot_version_derived",
    "jdk_version_source",
    "jdk_version_derived",
)
for k in required:
    if not doc.get(k):
        sys.exit(f"FAIL: manifest missing {k}")
ref = doc["harvest_referent"]
if not os.path.isdir(ref):
    sys.exit(f"FAIL: harvest_referent not a directory: {ref}")
if doc["schema"] != "legacy-at-3/v2":
    sys.exit(
        f"FAIL: unexpected schema {doc['schema']} (want legacy-at-3/v2) — "
        "re-run: derive-legacy-boot3 skill (bash \"${HERMES_SKILL_DIR}/scripts/derive-legacy-boot3.sh\")"
    )
print(
    f"OK: legacy-at-3 mode={doc['mode']} harvest_referent={ref} "
    f"jdk {doc['jdk_version_source']}→{doc['jdk_version_derived']} "
    f"boot {doc['spring_boot_version_source']}→{doc['spring_boot_version_derived']}"
)
PY
