#!/usr/bin/env python3
"""V17-6b: the post_tool_call observer records positive execution evidence.

Runs the executable exactly as the Stage 050 producer registers it (one file,
hook JSON on stdin) and checks the ledger rows the paved-road audit grades."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "post_tool_call.py"


def fire(home: Path, payload: dict, **env) -> subprocess.CompletedProcess:
    e = dict(os.environ, HERMES_HOME=str(home), HERMES_KANBAN_TASK="t_obs1", HERMES_KANBAN_RUN_ID="9",
             HERMES_PROFILE="Implementer", **env)
    return subprocess.run([str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=e)


def main() -> int:
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "kanban" / "logs").mkdir(parents=True)
        ledger = home / "kanban" / "logs" / "t_obs1.exec.jsonl"
        term = lambda cmd, result: {"hook_event_name": "post_tool_call", "tool_name": "terminal",  # noqa: E731
                                    "tool_input": {"command": cmd}, "extra": {"result": result, "tool_call_id": "c-%d" % len(cmd)}}
        cases = [
            (term("python3 audit.py", json.dumps({"output": "", "exit_code": 1})), 1),   # unmarked in the log, red here
            (term("python3 audit.py", json.dumps({"output": "ok", "exit_code": 0})), 0),
            (term("python3 audit.py", "not json at all"), None),                          # unknown, never success
            (term("python3 audit.py", json.dumps({"output": "", "exit_code": True})), None),
        ]
        for payload, _ in cases:
            p = fire(home, payload)
            if p.returncode != 0 or p.stdout:
                fails.append("observer must exit 0 with no stdout: rc=%s out=%r" % (p.returncode, p.stdout))
        rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
        if [r["exit_code"] for r in rows] != [c[1] for c in cases]:
            fails.append("exit codes recorded %s" % [r["exit_code"] for r in rows])
        if {(r["run"], r["profile"], r["task"]) for r in rows} != {("9", "implementer", "t_obs1")}:
            fails.append("run binding %s" % rows[0])
        # the output a call returned is kept bounded: its tail, digest and length (V26-6 item 2)
        if rows[1].get("output_tail") != "ok" or rows[1].get("output_chars") != 2 or len(rows[1].get("output_sha256") or "") != 64:
            fails.append("output tail not recorded %s" % rows[1])
        big = "x" * 5000 + "THE END"
        fire(home, term("python3 long.py", json.dumps({"output": big, "exit_code": 0})))
        last = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
        if not last["output_tail"].endswith("THE END") or len(last["output_tail"]) != 800 or last["output_chars"] != len(big):
            fails.append("long output not bounded to its tail: %d chars" % len(last.get("output_tail") or ""))
        cases.append((None, 0))
        # not a terminal call: nothing recorded
        fire(home, {"tool_name": "write_file", "tool_input": {"path": "x"}, "extra": {"result": "{}"}})
        if len(ledger.read_text(encoding="utf-8").splitlines()) != len(cases):
            fails.append("a non-terminal call was recorded")
        # a profile home resolves to the base kanban root, as the official log does
        prof = home / "profiles" / "reviewer"
        prof.mkdir(parents=True)
        fire(prof, term("ls", json.dumps({"exit_code": 0})))
        if len(ledger.read_text(encoding="utf-8").splitlines()) != len(cases) + 1:
            fails.append("profile HERMES_HOME did not resolve to the base kanban root")
        # no task: nothing recorded, still exit 0
        e = dict(os.environ, HERMES_HOME=str(home))
        e.pop("HERMES_KANBAN_TASK", None)
        p = subprocess.run([str(HOOK)], input=json.dumps(term("ls", "{}")), capture_output=True, text=True, env=e)
        if p.returncode != 0:
            fails.append("no-task call must still exit 0")
    for f in fails:
        print("FAIL:", f, file=sys.stderr)
    if fails:
        return 1
    print("OK: post_tool_call observer (exit codes 1/0/unknown recorded; bounded output tail; non-terminal ignored; profile home -> base "
          "kanban root; never blocks, never writes stdout)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
