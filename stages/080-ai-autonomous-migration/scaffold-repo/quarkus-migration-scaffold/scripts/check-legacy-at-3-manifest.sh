#!/usr/bin/env bash
# Fail closed if the Boot 2→3 derivation manifest is missing or incomplete.
# M1 and harvest gates require harvest_referent (legacy@3.x).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
manifest="${root}/migration/derived/legacy-at-3.json"
if [ ! -f "${manifest}" ]; then
  echo "FAIL: ${manifest} missing — run: bash scripts/derive-legacy-boot3.sh" >&2
  exit 1
fi
python3 - "$manifest" <<'PY'
import json, sys, os
doc = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("schema", "mode", "harvest_referent", "sha256", "spring_boot_version_source"):
    if not doc.get(k):
        sys.exit(f"FAIL: manifest missing {k}")
ref = doc["harvest_referent"]
if not os.path.isdir(ref):
    sys.exit(f"FAIL: harvest_referent not a directory: {ref}")
if doc["schema"] != "legacy-at-3/v1":
    sys.exit(f"FAIL: unexpected schema {doc['schema']}")
print(f"OK: legacy-at-3 mode={doc['mode']} harvest_referent={ref}")
PY
