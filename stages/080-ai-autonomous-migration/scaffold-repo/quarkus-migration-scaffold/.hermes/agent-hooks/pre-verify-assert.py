#!/usr/bin/env python3
"""W2/W4 pre_verify host — exit-criteria + RW-2 dest-inventory tooth."""
import json, os, sys
from pathlib import Path

d = json.load(sys.stdin)
extra = d.get("extra") if isinstance(d.get("extra"), dict) else {}

def g(*keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
        if k in extra and extra[k] is not None:
            return extra[k]
    return default

attempt = int(g("attempt") or 0)
if attempt:
    print("{}"); raise SystemExit(0)

require = os.environ.get("HERMES_PRE_VERIFY_REQUIRE_MARKER", "")
marker = os.environ.get("HERMES_PRE_VERIFY_MARKER", "/tmp/w2-pre-verify-ok")
if require == "1" and not os.path.exists(marker):
    print(json.dumps({"action": "continue", "message": f"pre_verify: missing marker {marker}"}))
    raise SystemExit(0)

if os.environ.get("HERMES_PRE_VERIFY_REQUIRE_DEST_INV") == "1":
    evidence = os.environ.get(
        "HERMES_DEST_INV_EVIDENCE",
        "/projects/modernized/migration/receipts/destination-inventory/.w4-rw2-ok",
    )
    paths = g("changed_paths") or []
    if not isinstance(paths, list):
        paths = []
    text = f"{g('final_response') or ''} {' '.join(str(p) for p in paths)}"
    cited = (
        "destination_inventory" in text
        or "destination-inventory" in text
        or Path(evidence).is_file()
    )
    if not cited:
        print(json.dumps({
            "action": "continue",
            "message": (
                "pre_verify RW-2: dest-inventory evidence missing "
                "(cite refs.destination_inventory or stamp receipt)"
            ),
        }))
        raise SystemExit(0)

print("{}")
