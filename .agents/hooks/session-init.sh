#!/bin/bash
# sessionStart hook: report the cluster login (the harness-refactoring wake relays are retired).
# Fail open. Never block the session. Drain stdin (Cursor sends JSON).
# No GNU timeout / bash 4 `wait -n` — those are missing on macOS /bin/bash 3.2.
cat >/dev/null || true
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 - "$ROOT" <<'PY' || echo '{"additional_context":""}'
import json
import os
import subprocess
import sys

root = sys.argv[1]
lines = []

try:
    who = subprocess.run(
        ["oc", "whoami"], capture_output=True, text=True, timeout=5
    )
    if who.returncode == 0 and who.stdout.strip():
        srv = subprocess.run(
            ["oc", "whoami", "--show-server"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        server = (srv.stdout or "").strip() or "(server unknown)"
        lines.append(f"Cluster: {server} (logged in as {who.stdout.strip()})")
    else:
        lines.append(
            "WARNING: Not logged in to OpenShift. Run 'oc login' before cluster operations."
        )
except Exception:
    lines.append(
        "WARNING: Not logged in to OpenShift. Run 'oc login' before cluster operations."
    )

print(json.dumps({"additional_context": "\n".join(lines) + "\n"}))
PY
