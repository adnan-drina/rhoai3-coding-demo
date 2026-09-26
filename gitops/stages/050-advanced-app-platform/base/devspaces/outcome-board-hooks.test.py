#!/usr/bin/env python3
"""The Stage 050 producer registers the outcome-board hooks ONLY for a run that selects them.

Executes the producer's own `# >>> outcome-board hooks` block (from
maas-api-key-provisioning.yaml) against a disposable destination:
  * no run-defaults, a serial run-defaults, a malformed one, a K2-less config
    -> the hook config is untouched (byte-identical);
  * run-defaults selecting outcome-board/v1 -> the K2 matcher adds the review
    and block terminators, and on_kanban_dispatch_tick runs the destination's
    kernel/outcome_reconcile.py (the review's production-hook integration).
"""
from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
from pathlib import Path

PRODUCER = Path(__file__).resolve().parent / "maas-api-key-provisioning.yaml"
MATCHER = ("write|write_file|patch|edit_file|apply_patch|create_file|terminal|execute_code|delegate_task|"
           "skill_manage|kanban_complete|complete_task")


def block() -> str:
    text = PRODUCER.read_text()
    m = re.search(r"\n( *)# >>> outcome-board hooks.*?\n(.*?)\n *# <<< outcome-board hooks", text, re.S)
    if not m:
        raise SystemExit("FAIL: the producer's outcome-board hooks block is missing")
    indent = len(m.group(1))
    return "\n".join(line[indent:] for line in m.group(2).splitlines())


def run(safe_root: Path, cfg: dict) -> dict:
    ns = {"os": __import__("os"), "_pjson": json, "safe_root": str(safe_root), "cfg": cfg, "print": lambda *a: None}
    exec(block(), ns)
    return ns["cfg"]


def main() -> int:
    base = {"hooks": {"pre_tool_call": [{"matcher": MATCHER, "command": "/m/pre_tool_call.sh", "timeout": 5, "fail_closed": True}]}}
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for label, content in (("absent", None), ("serial", {"configuration": {}}),
                               ("other", {"configuration": {"board_protocol": "serial-loop/v1"}}), ("malformed", "{not json")):
            p = root / "run-defaults.json"
            if p.exists():
                p.unlink()
            if content is not None:
                p.write_text(content if isinstance(content, str) else json.dumps(content))
            got = run(root, copy.deepcopy(base))
            if got != base:
                fails.append("%s run-defaults changed the hooks: %s" % (label, got))
        (root / "run-defaults.json").write_text(json.dumps({"configuration": {"board_protocol": "outcome-board/v1"}}))
        got = run(root, {"hooks": {"pre_tool_call": []}})
        if got != {"hooks": {"pre_tool_call": []}}:
            fails.append("a config with no K2 hook gained outcome hooks: %s" % got)
        got = run(root, copy.deepcopy(base))
        matcher = got["hooks"]["pre_tool_call"][0]["matcher"]
        if not all(t in matcher.split("|") for t in ("kanban_block", "kanban_request_review", "request_review")):
            fails.append("selected run: matcher lacks the terminators: %s" % matcher)
        tick = got["hooks"].get("on_kanban_dispatch_tick") or []
        if not (len(tick) == 1 and tick[0]["command"] == "python3 %s/.hermes/kernel/outcome_reconcile.py --root %s" % (root, root)):
            fails.append("selected run: reconciler not registered: %s" % tick)
    if fails:
        print("FAIL: " + "; ".join(fails), file=sys.stderr)
        return 1
    print("OK: outcome-board hooks are registered only for a run that selects outcome-board/v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
