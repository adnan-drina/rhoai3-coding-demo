#!/usr/bin/env python3
"""Kernel-level qualification of the outcome-board authority boundary (architect F1).

Runs the REAL service and a REAL worker-identity client in two containers of
the workspace image under two different uids, with the layout the skeleton
devfile declares:

  service  uid SERVICE_UID  store volume (only here) + socket volume (rw) +
                            destination (read-only) + the authority code (ro)
  worker   uid WORKER_UID   destination (rw) + socket volume (READ-ONLY) +
                            the same code and an image stamp naming its identity

and asserts, as the worker's kernel sees it: the store path does not exist
(no mount, so no uid, group or user namespace reaches it), the socket cannot
be removed or replaced and nothing can be planted beside it, the service answers
across the uid boundary, authority_protected() is TRUE, and the governed
execution gate opens only with the platform's measurement-trust decision. Two
controls must fail closed: the SAME uid for both, and the store volume ALSO
mounted into the worker.

This is a local podman qualification (no Dev Spaces, no SCC, no DWO). What it
does NOT establish is the list in OUTCOME-BOARD-CONTRACT.md 8a (live Dev Spaces
qualification). Usage:

    python3 outcome-authority-two-uid.qualify.py --image localhost/rhoai3-ws-080:unreleased \\
        [--out receipt.json]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE / "scaffold-repo" / "quarkus-migration-scaffold" / ".hermes"
WORKER_UID, SERVICE_UID = 1001040000, 1001040001
SOCK = "/run/outcome-authority/authority.sock"
# the image's UDI entrypoint writes into /home/user; an arbitrary uid runs python directly
PY = ("--entrypoint", "python3", "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1")

SETUP = r'''
import json, os, subprocess
from pathlib import Path
root = Path("/projects/modernized"); control = Path("/projects/control")
root.mkdir(parents=True); control.mkdir(parents=True)
decl = {"schema": "rhoai3.run-budget/v2", "run_id": "two-uid", "board_protocol": "outcome-board/v1",
        "run_control": {"contract": "rhoai3.run-control/v1", "root": str(control), "state": "/projects/state"}}
(root / "run-budget.json").write_text(json.dumps(decl))
(root / "pom.xml").write_text("<project/>\n")
(root / ".hermes" / "home").mkdir(parents=True)
g = ["g" + "it", "-c", "user.email=q@q", "-c", "user.name=q", "-C", str(root)]
subprocess.run(g[:1] + ["init", "-q", str(root)], check=True)
subprocess.run(g + ["add", "-A"], check=True)
subprocess.run(g + ["commit", "-qm", "scaffold"], check=True)
head = subprocess.run(g + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
doc = {"schema": "rhoai3.run-control/v1", "run_id": "two-uid", "scaffold_commit": head, "activation": "pilot",
       "authorized_by": "qualification", "board_protocol": "outcome-board/v1",
       "outcome_board": {"execution": "enabled"}}
(control / "contract.json").write_text(json.dumps(doc))
os.chmod(str(control / "contract.json"), 0o644)
print("setup", head)
'''

CHECK = r'''
import errno, json, os, socket, sys
from pathlib import Path
sys.path.insert(0, "/opt/rhoai3/outcome-authority/lib")
from planner import outcome_protocol as P, outcome_authority as A
root = Path("/projects/modernized")
out = {"uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups()}
def err(fn):
    try:
        fn()
        return "SUCCEEDED"
    except OSError as exc:
        return errno.errorcode.get(exc.errno, str(exc.errno))
h = A.hello(P.AUTHORITY_SOCKET.as_posix())
out["hello"] = {k: h[k] for k in ("uid", "store_dir", "store_path", "code_sha256")}
out["stat_store_dir"] = err(lambda: os.stat(h["store_dir"]))
out["open_store"] = err(lambda: open(h["store_path"], "rb").close())
out["unlink_socket"] = err(lambda: os.unlink(P.AUTHORITY_SOCKET.as_posix()))
out["rename_socket_dir"] = err(lambda: os.rename("/run/outcome-authority", "/run/outcome-authority.x"))
out["write_socket_dir"] = err(lambda: open("/run/outcome-authority/planted", "w").close())
def bind():
    s = socket.socket(socket.AF_UNIX); s.bind("/run/outcome-authority/planted.sock")
out["plant_socket"] = err(bind)
out["status"] = A.call(P.AUTHORITY_SOCKET.as_posix(), "status", {})
out["protected"] = list(P.authority_protected(root))
out["gate_without_trust"] = P.execution_gate(root)
c = Path("/projects/control/contract.json")
doc = json.loads(c.read_text()); doc["outcome_board"]["measurement_trust"] = "cooperative-receipts"; c.write_text(json.dumps(doc))
out["gate_with_trust"] = P.execution_gate(root)
print(json.dumps(out, sort_keys=True))
'''


def podman(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["podman", *args], capture_output=capture, text=True)
    if check and p.returncode != 0:
        raise RuntimeError("podman %s exited %d: %s" % (args[0], p.returncode, (p.stderr or p.stdout)[-1500:]))
    return p


def scenario(image: str, tag: str, *, service_uid: int, store_in_worker: bool, stamp_dir: Path, baked: bool = False) -> dict:
    vols = {k: "ob-%s-%s" % (k, tag) for k in ("dest", "store", "sock")}
    for v in vols.values():
        podman("volume", "create", v)
    # --baked: the image's own root-owned /opt/rhoai3/outcome-authority and its
    # /opt/rhoai3/080.pins stamp; nothing of the source tree is mounted
    code_mount = [] if baked else ["-v", "%s:/opt/rhoai3/outcome-authority:ro" % HERMES]
    stamp_mount = [] if baked else ["-v", "%s:/opt/rhoai3/080.pins:ro" % (stamp_dir / "080.pins")]
    try:
        podman("run", "--rm", "--user", "%d:0" % WORKER_UID, "-v", "%s:/projects:U" % vols["dest"], *PY,
               image, "-c", SETUP)
        svc = podman("run", "-d", "--name", "ob-svc-" + tag, "--user", "%d:0" % service_uid,
                     "-v", "%s:/var/lib/outcome-authority:U" % vols["store"],
                     "-v", "%s:/run/outcome-authority:U" % vols["sock"],
                     "-v", "%s:/projects:ro" % vols["dest"], *code_mount, *PY, image,
                     "/opt/rhoai3/outcome-authority/kernel/outcome_authority.py", "serve",
                     "--root", "/projects/modernized", "--store-dir", "/var/lib/outcome-authority/store",
                     "--socket", SOCK, "--native-db", "/projects/modernized/.hermes/home/kanban.db").stdout.strip()
        for _ in range(100):
            logs = podman("logs", svc, check=False).stdout
            if '"serving"' in logs:
                break
            time.sleep(0.3)
        worker = ["run", "--rm", "--user", "%d:0" % WORKER_UID, "-v", "%s:/projects" % vols["dest"],
                  "-v", "%s:/run/outcome-authority:ro" % vols["sock"], *code_mount, *stamp_mount]
        if store_in_worker:
            worker += ["-v", "%s:/var/lib/outcome-authority" % vols["store"]]
        p = podman(*worker, *PY, image, "-c", CHECK, check=False)
        try:
            result = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            result = {"error": p.stdout[-2000:] + p.stderr[-2000:]}
        result["service_log"] = podman("logs", svc, check=False).stdout[-1500:]
        return result
    finally:
        podman("rm", "-f", "ob-svc-" + tag, check=False)
        for v in vols.values():
            podman("volume", "rm", "-f", v, check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--baked", action="store_true", help="use the code and stamp baked into the image (no source mounts)")
    ap.add_argument("--commit", default="", help="the frozen commit the image was built from (recorded)")
    ap.add_argument("--image-id", default="", help="the local image id (recorded)")
    ns = ap.parse_args()
    sys.path.insert(0, str(HERMES / "lib"))
    from planner.outcome_authority import code_identity
    if ns.baked:
        p = podman("run", "--rm", "--entrypoint", "sh", ns.image, "-c",
                   "grep '^outcome_authority.code_sha256=' /opt/rhoai3/080.pins | cut -d= -f2")
        digest = p.stdout.strip()
    else:
        digest = code_identity(HERMES)
    with tempfile.TemporaryDirectory() as d:
        stamp_dir = Path(d)
        (stamp_dir / "080.pins").write_text("outcome_authority.code_sha256=%s\n" % digest)
        os.chmod(stamp_dir / "080.pins", 0o644)
        tag = str(os.getpid())
        runs = {
            "two_uid": scenario(ns.image, tag + "a", service_uid=SERVICE_UID, store_in_worker=False, stamp_dir=stamp_dir, baked=ns.baked),
            "control_same_uid": scenario(ns.image, tag + "b", service_uid=WORKER_UID, store_in_worker=False, stamp_dir=stamp_dir, baked=ns.baked),
            "control_store_mounted_in_worker": scenario(ns.image, tag + "c", service_uid=SERVICE_UID, store_in_worker=True,
                                                        stamp_dir=stamp_dir, baked=ns.baked),
        }
    t = runs["two_uid"]
    verdict = {
        "store_unreachable": t.get("stat_store_dir") == "ENOENT" and t.get("open_store") == "ENOENT",
        "socket_not_replaceable": all(t.get(k) in ("EROFS", "EACCES", "EPERM", "EBUSY")
                                      for k in ("unlink_socket", "rename_socket_dir", "write_socket_dir", "plant_socket")),
        "cross_uid_request": bool((t.get("status") or {}).get("published") is False),
        "protected": bool(t.get("protected") and t["protected"][0] is True),
        "gate_needs_trust": [g[0] for g in t.get("gate_without_trust") or []] == ["MEASUREMENT_TRUST_UNDECIDED"],
        "gate_opens_with_trust": t.get("gate_with_trust") == [],
        "same_uid_refused": bool(runs["control_same_uid"].get("protected") and runs["control_same_uid"]["protected"][0] is False),
        "reachable_store_refused": bool(runs["control_store_mounted_in_worker"].get("protected")
                                        and runs["control_store_mounted_in_worker"]["protected"][0] is False),
    }
    receipt = {"schema": "rhoai3.outcome-authority-two-uid/v1", "image": ns.image, "code_sha256": digest,
               "code_source": "baked into the image" if ns.baked else "source tree bind-mounted",
               "commit": ns.commit, "image_id": ns.image_id,
               "worker_uid": WORKER_UID, "service_uid": SERVICE_UID, "verdict": verdict, "ok": all(verdict.values()),
               "runs": runs, "boundary": "local podman containers; not Dev Spaces, SCC or DWO"}
    text = json.dumps(receipt, indent=2, sort_keys=True)
    if ns.out:
        Path(ns.out).write_text(text + "\n")
    print(json.dumps({"ok": receipt["ok"], "verdict": verdict}, indent=2))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
