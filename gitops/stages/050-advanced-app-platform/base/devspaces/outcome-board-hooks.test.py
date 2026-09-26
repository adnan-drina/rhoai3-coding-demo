#!/usr/bin/env python3
"""The Stage 050 producer registers the outcome-board hooks ONLY for a run that selects them.

Executes the producer's own `# >>> outcome-board hooks` block (from
maas-api-key-provisioning.yaml) against a disposable destination:
  * no run-defaults, a serial run-defaults, a malformed one, a K2-less config
    -> the hook config is untouched (byte-identical);
  * run-defaults selecting outcome-board/v1 -> the K2 matcher adds the review
    and block terminators, and on_kanban_dispatch_tick runs the destination's
    kernel/outcome_reconcile.py (the review's production-hook integration).
With the destination's harness present (.hermes/lib), the producer uses the
harness's own selection (outcome_protocol.select_protocol), so a GOVERNED run
registers the hooks only when its initial-commit request and the read-only
run control agree on outcome-board/v1:
  * request + selection agree                    -> registered
  * request, no selection (v17's live shape)      -> nothing, reason printed
  * selection without request / downgraded       -> nothing, reason printed
  * a mutable run-defaults.json naming the board  -> nothing (never selects alone)
  * a v12-v17 run (no request, no selection)      -> untouched
"""
from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
from pathlib import Path

PRODUCER = Path(__file__).resolve().parent / "maas-api-key-provisioning.yaml"
REPO = Path(__file__).resolve().parents[5]
GOLDEN_LIB = Path(__import__("os").environ.get("GOLDEN_LIB") or
                  REPO / "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/lib")
OUTCOME, SERIAL = "outcome-board/v1", "serial-loop/v1"
MATCHER = ("write|write_file|patch|edit_file|apply_patch|create_file|terminal|execute_code|delegate_task|"
           "skill_manage|kanban_complete|complete_task")


def block(name: str = "outcome-board hooks") -> str:
    text = PRODUCER.read_text()
    m = re.search(r"\n( *)# >>> %s.*?\n(.*?)\n *# <<< %s" % (re.escape(name), re.escape(name)), text, re.S)
    if not m:
        raise SystemExit("FAIL: the producer's %s block is missing" % name)
    indent = len(m.group(1))
    return "\n".join(line[indent:] for line in m.group(2).splitlines())


def run(safe_root: Path, cfg: dict, said: list | None = None) -> dict:
    ns = {"os": __import__("os"), "_pjson": json, "safe_root": str(safe_root), "cfg": cfg,
          "print": (lambda *a: said.append(" ".join(str(x) for x in a))) if said is not None else (lambda *a: None)}
    exec(block(), ns)
    return ns["cfg"]


def governed(td: Path, *, request=None, has_request=True, selected=None, defaults=None) -> Path:
    """A destination with the harness lib, whose INITIAL commit declares run
    control, and the platform's contract in a control directory."""
    import subprocess
    root, control = td / "dest", td / "control"
    (root / ".hermes").mkdir(parents=True)
    control.mkdir()
    (root / ".hermes" / "lib").symlink_to(GOLDEN_LIB)
    decl = {"schema": "rhoai3.run-budget/v2", "run_id": "run-x",
            "run_control": {"contract": "rhoai3.run-control/v1", "root": str(control), "state": str(td / "state")}}
    if has_request:
        decl["board_protocol"] = request
    (root / "run-budget.json").write_text(json.dumps(decl))
    (root / "run-defaults.json").write_text(json.dumps({"configuration": {"board_protocol": defaults} if defaults else {}}))
    (root / ".gitignore").write_text(".hermes/\n")
    g = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a],  # noqa: E731
                                  capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    g("add", "-A")
    g("commit", "-qm", "scaffold")
    doc = {"schema": "rhoai3.run-control/v1", "run_id": "run-x", "scaffold_commit": g("rev-parse", "HEAD"),
           "activation": "pilot", "authorized_by": "provision-migration-run:tr"}
    if selected:
        doc["board_protocol"] = selected
    (control / "contract.json").write_text(json.dumps(doc))
    return root


def post_hook_cases(base: dict) -> list:
    """V17-6b: the terminal post_tool_call observer is registered exactly when
    the destination ships .hermes/kernel/post_tool_call.sh; the K2
    pre_tool_call registrations keep fail_closed: true (honoured by the pinned
    runtime for pre_tool_call only)."""
    import os
    import shutil
    import tempfile
    fails = []
    text = PRODUCER.read_text()
    k2 = re.findall(r'cfg\["hooks"\]\["pre_tool_call"\] = \[\s*\{(.*?)\}\s*\]', text, re.S)
    if len(k2) != 2 or not all('"fail_closed": True' in e and '"timeout": 5' in e for e in k2):
        fails.append("K2 pre_tool_call registrations are not fail_closed with a 5 s timeout: %d found" % len(k2))
    for ships in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root, hooks = Path(tmp) / "dest", Path(tmp) / "managed" / "agent-hooks"
            (root / ".hermes" / "kernel").mkdir(parents=True)
            if ships:
                (root / ".hermes" / "kernel" / "post_tool_call.sh").write_text("#!/bin/bash\ncat >/dev/null\n")
            ns = {"os": os, "shutil": shutil, "safe_root": str(root), "hooks_dir": str(hooks),
                  "cfg": copy.deepcopy(base), "print": lambda *a: None}
            exec(block("post-tool-call observer"), ns)
            got = ns["cfg"]["hooks"].get("post_tool_call")
            if not ships and got is not None:
                fails.append("post_tool_call registered without the script: %s" % got)
            if ships:
                want = [{"matcher": "terminal", "command": str(hooks / "post_tool_call.sh"), "timeout": 5}]
                if got != want or not os.access(str(hooks / "post_tool_call.sh"), os.X_OK):
                    fails.append("post_tool_call registration %s, want %s" % (got, want))
                if ns["cfg"]["hooks"]["pre_tool_call"] != base["hooks"]["pre_tool_call"]:
                    fails.append("the post block changed the K2 registration")
    return fails


def governed_cases(base: dict) -> list:
    fails = []
    if not (GOLDEN_LIB / "planner" / "outcome_protocol.py").is_file():
        print("SKIP: governed cases -- %s has no planner/outcome_protocol.py (set GOLDEN_LIB)" % GOLDEN_LIB)
        return fails
    cases = (
        ("agree", dict(request=OUTCOME, selected=OUTCOME), True, ""),
        ("v17 shape: request, no selection", dict(request=OUTCOME), False, "PROTOCOL_UNBOUND"),
        ("selection without request", dict(has_request=False, selected=OUTCOME), False, "PROTOCOL_UNREQUESTED"),
        ("downgraded", dict(request=OUTCOME, selected=SERIAL), False, "PROTOCOL_DOWNGRADED"),
        ("mutable run-defaults alone", dict(request=SERIAL, defaults=OUTCOME), False, "PROTOCOL_UNREQUESTED"),
        ("v12-v17 run", dict(has_request=False), False, ""),
        ("serial request", dict(request=SERIAL, selected=SERIAL), False, ""),
    )
    import tempfile
    for label, kw, want, reason in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = governed(Path(tmp).resolve(), **kw)
            said: list = []
            got = run(root, copy.deepcopy(base), said)
            registered = got != base
            if registered != want:
                fails.append("%s: registered=%s, want %s (%s)" % (label, registered, want, said))
            if want:
                tick = got["hooks"].get("on_kanban_dispatch_tick") or []
                if not (len(tick) == 1 and tick[0]["command"].endswith("--root %s" % root)):
                    fails.append("%s: reconciler not registered: %s" % (label, tick))
            if reason and not any(reason in line for line in said):
                fails.append("%s: the refusal is not reported (%s)" % (label, said))
            if not want and not reason and said:
                fails.append("%s: a consistent serial run printed %s" % (label, said))
    return fails


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
    fails.extend(governed_cases(base))
    fails.extend(post_hook_cases(base))
    if fails:
        print("FAIL: " + "; ".join(fails), file=sys.stderr)
        return 1
    print("OK: outcome-board hooks are registered only for a run that selects outcome-board/v1 (governed: the initial-commit "
          "request agreed by the read-only run control; a mutable file alone never selects; disagreements register "
          "nothing and say why; v12-v17 runs untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
