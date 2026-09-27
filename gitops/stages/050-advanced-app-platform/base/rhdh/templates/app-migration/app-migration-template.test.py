#!/usr/bin/env python3
"""The app-migration factory's board-protocol request (native control, no sidecar).

Renders the skeleton (devfile.yaml, run-budget.json) the way the scaffolder does
(fetch:template: Nunjucks with ${{ }} variables; rendered here with Jinja2,
which implements the same constructs the skeleton uses) for both protocol
values, and checks:
  * the template offers boardProtocol with default outcome-board/v2 (native
    Hermes Kanban control; a default run never launches on the serial
    fallback) and exactly serial-loop/v1 and outcome-board/v2, passes it to
    the skeleton, and offers NO execution value;
  * run-budget.json stamps the request (the harness reads it from the initial
    commit only);
  * neither protocol renders an authority component, volume or mount: the
    outcome-board/v1 sidecar is retired for new runs (architect review
    2026-09-27); Hermes Kanban is the one lifecycle authority.
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
    if bp.get("default") != "outcome-board/v2" or bp.get("enum") != ["serial-loop/v1", "outcome-board/v2"]:
        fails.append("template boardProtocol parameter: %s" % bp)
    if any("execution" in k.lower() for k in props):
        fails.append("the template offers an execution value: %s" % sorted(props))
    step = next(s for s in tmpl["spec"]["steps"] if s["id"] == "add-catalog-info")
    if step["input"]["values"].get("boardProtocol") != "${{ parameters.boardProtocol }}":
        fails.append("the skeleton does not receive boardProtocol")

    for protocol in ("serial-loop/v1", "outcome-board/v2"):
        budget = json.loads(render("run-budget.json", protocol))
        if budget.get("board_protocol") != protocol:
            fails.append("%s: run-budget.json stamps %r" % (protocol, budget.get("board_protocol")))
        text = render("devfile.yaml", protocol)
        dev = yaml.safe_load(text)
        if "outcome-authority" in text or "/run/outcome-authority" in text:
            fails.append("%s renders authority parts" % protocol)
        containers = sorted(c["name"] for c in dev["components"] if "container" in c)
        if containers != ["development-tooling", "initialize-legacy"]:
            fails.append("%s renders containers %s (the worker and its init only)" % (protocol, containers))
    if fails:
        print("FAIL: " + "; ".join(fails), file=sys.stderr)
        return 1
    print("OK: app-migration template (boardProtocol default outcome-board/v2, no execution value; run-budget.json "
          "stamps the request; neither protocol renders an authority sidecar, volume or mount; the worker and its init container only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
