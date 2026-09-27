#!/usr/bin/env python3
"""The app-migration factory's board-protocol request and the authority sidecar.

Renders the skeleton (devfile.yaml, run-budget.json) the way the scaffolder does
(fetch:template: Nunjucks with ${{ }} variables; rendered here with Jinja2,
which implements the same constructs the skeleton uses) for both protocol
values, and checks:
  * the template offers boardProtocol with default outcome-board/v1 (a default
    run never launches on the serial fallback) and exactly
    the two protocols, passes it to the skeleton, and offers NO execution value;
  * run-budget.json stamps the request (the harness reads it from the initial
    commit only);
  * serial-loop/v1 renders no authority component, volume or mount at all;
  * outcome-board/v1 renders the sidecar: a runAsUser inside the namespace's
    measured SCC range and different from the worker's, privilege escalation
    off, capabilities dropped; the store volume mounted ONLY in the sidecar;
    the socket volume in both, read-only on the worker side; the root-owned
    image code path; the same image digest as the worker.
Requires jinja2 and PyYAML (platform-side test; SKIP without them).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKELETON = HERE / "skeleton"
TEMPLATE = HERE / "template.yaml"
RANGE = (1001040000, 1001040000 + 10000)          # wksp-ai-developer openshift.io/sa.scc.uid-range, measured 2026-09-26
WORKER_UID = RANGE[0]                              # MustRunAsRange: the first uid of the range


def render(name: str, protocol: str) -> str:
    import jinja2
    env = jinja2.Environment(variable_start_string="${{", variable_end_string="}}", undefined=jinja2.StrictUndefined,
                             keep_trailing_newline=True)
    env.filters["dump"] = json.dumps
    values = {"name": "orders-migration", "legacyRepoUrl": "https://example.test/orders.git", "autoStartMigration": True,
              "scaffolderTaskId": "task-1", "maasHost": "maas.example.test", "maasInternalIp": "172.30.1.1",
              "sonarqubeUrl": "https://sonar.example.test", "devspacesUrl": "https://devspaces.example.test",
              "boardProtocol": protocol}
    return env.from_string((SKELETON / name).read_text()).render(values=values)


def main() -> int:
    try:
        import jinja2  # noqa: F401
        import yaml
    except ImportError as exc:
        print("SKIP: %s (needs jinja2 and PyYAML)" % exc)
        return 0
    fails: list[str] = []
    tmpl = yaml.safe_load(TEMPLATE.read_text())
    props = {k: v for page in tmpl["spec"]["parameters"] for k, v in (page.get("properties") or {}).items()}
    bp = props.get("boardProtocol") or {}
    if bp.get("default") != "outcome-board/v1" or bp.get("enum") != ["serial-loop/v1", "outcome-board/v1"]:
        fails.append("template boardProtocol parameter: %s" % bp)
    if any("execution" in k.lower() for k in props):
        fails.append("the template offers an execution value: %s" % sorted(props))
    step = next(s for s in tmpl["spec"]["steps"] if s["id"] == "add-catalog-info")
    if step["input"]["values"].get("boardProtocol") != "${{ parameters.boardProtocol }}":
        fails.append("the skeleton does not receive boardProtocol")

    for protocol in ("serial-loop/v1", "outcome-board/v1"):
        budget = json.loads(render("run-budget.json", protocol))
        if budget.get("board_protocol") != protocol:
            fails.append("%s: run-budget.json stamps %r" % (protocol, budget.get("board_protocol")))
        dev = yaml.safe_load(render("devfile.yaml", protocol))
        comps = {c["name"]: c for c in dev["components"]}
        tool = comps["development-tooling"]
        mounts = {m["name"]: m["path"] for m in tool["container"].get("volumeMounts") or []}
        overrides = tool["attributes"]["container-overrides"]["volumeMounts"]
        if protocol == "serial-loop/v1":
            text = render("devfile.yaml", protocol)
            if "outcome-authority" in text or "/run/outcome-authority" in text:
                fails.append("serial run renders authority parts")
            continue
        side = comps.get("outcome-authority")
        if not side:
            fails.append("outcome run renders no authority sidecar")
            continue
        sc = side["attributes"]["container-overrides"]["securityContext"]
        uid = sc.get("runAsUser")
        if not (isinstance(uid, int) and RANGE[0] <= uid < RANGE[1] and uid != WORKER_UID):
            fails.append("sidecar runAsUser %r is not a distinct uid inside %s" % (uid, RANGE))
        if sc.get("allowPrivilegeEscalation") is not False or sc.get("capabilities", {}).get("drop") != ["ALL"]:
            fails.append("sidecar securityContext %s" % sc)
        smounts = {m["name"]: m["path"] for m in side["container"].get("volumeMounts") or []}
        if smounts.get("outcome-authority-store") != "/var/lib/outcome-authority":
            fails.append("the store is not mounted in the sidecar: %s" % smounts)
        for name, c in comps.items():
            if name != "outcome-authority" and "container" in c and any(
                    m["name"] == "outcome-authority-store" for m in c["container"].get("volumeMounts") or []):
                fails.append("the store volume is mounted in %s" % name)
        if smounts.get("outcome-authority-socket") != "/run/outcome-authority" or \
                mounts.get("outcome-authority-socket") != "/run/outcome-authority":
            fails.append("the socket volume is not shared: sidecar %s worker %s" % (smounts, mounts))
        if {"mountPath": "/run/outcome-authority", "readOnly": True} not in overrides:
            fails.append("the worker's socket mount is not read-only: %s" % overrides)
        if not comps.get("outcome-authority-store", {}).get("volume") or comps["outcome-authority-store"]["volume"].get("ephemeral"):
            fails.append("the store volume is not persistent")
        if not comps.get("outcome-authority-socket", {}).get("volume", {}).get("ephemeral"):
            fails.append("the socket volume is not ephemeral")
        if side["container"]["image"] != tool["container"]["image"]:
            fails.append("the sidecar runs another image")
        cmd = side["container"].get("command") or []
        if not (len(cmd) == 2 and cmd[1].startswith("/opt/rhoai3/outcome-authority/")):
            fails.append("the sidecar does not run the image's root-owned code: %s" % cmd)
        args = side["container"].get("args") or []
        if "/projects/modernized" not in args or "/var/lib/outcome-authority/store" not in args:
            fails.append("sidecar args %s" % args)
    if fails:
        print("FAIL: " + "; ".join(fails), file=sys.stderr)
        return 1
    print("OK: app-migration template (boardProtocol default outcome-board/v1, no execution value; run-budget.json "
          "stamps the request; serial renders no authority parts; outcome renders the sidecar with a distinct in-range "
          "uid, the store mounted only in it, the socket shared and read-only for the worker, the image's root-owned code)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
