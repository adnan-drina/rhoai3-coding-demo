#!/bin/bash
# sessionStart hook: cluster login + Cursor wake-relay liveness.
# Fail open. Never block the session. Drain stdin (Cursor sends JSON).
# No GNU timeout / bash 4 `wait -n` — those are missing on macOS /bin/bash 3.2.
cat >/dev/null || true
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 - "$ROOT" <<'PY' || echo '{"additional_context":""}'
import json
import os
import subprocess
import sys
import time

root = sys.argv[1]
wake = os.path.join(root, "harness-refactoring", ".wake")
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

now = int(time.time())
ok, dead = [], []
for role in ("lead", "review", "architect", "deputy", "research"):
    pidfile = os.path.join(wake, f"{role}-relay.pid")
    hbfile = os.path.join(wake, f"{role}-relay-heartbeat")
    pid = ""
    try:
        pid = open(pidfile, encoding="utf-8").read().strip()
    except OSError:
        pid = ""
    hb = 0
    try:
        for ln in open(hbfile, encoding="utf-8"):
            if ln.startswith("epoch="):
                hb = int(ln.split("=", 1)[1].strip() or "0")
    except (OSError, ValueError):
        hb = 0
    alive = False
    if pid.isdigit():
        try:
            os.kill(int(pid), 0)
            ps = subprocess.run(
                ["ps", "-p", pid, "-o", "command="],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if f"{role}-relay.sh" in (ps.stdout or "") and (now - hb) < 90:
                alive = True
        except (OSError, subprocess.TimeoutExpired):
            alive = False
    (ok if alive else dead).append(role)

if ok:
    lines.append(
        "Wake relays alive (do NOT start a second Cursor Shell): " + " ".join(ok)
    )
if dead:
    lines.append(
        "Wake relays DEAD (re-arm in this session, notify_on_output on "
        "^AGENT_LOOP_WAKE_<role>, NO stdout redirect): " + " ".join(dead)
    )
    for role in dead:
        lines.append(f"  bash harness-refactoring/.wake/{role}-relay.sh")

print(json.dumps({"additional_context": "\n".join(lines) + "\n"}))
PY
