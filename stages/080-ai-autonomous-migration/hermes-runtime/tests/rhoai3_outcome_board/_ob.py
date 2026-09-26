"""Outcome-board runtime qualification helpers (exact patched runtime, real CLI).

RHOAI3_GOLDEN_HERMES must name the golden scaffold's .hermes directory, e.g.
<repo>/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes.
The destination built here mirrors the deployed layout: HERMES_HOME inside the
destination (.hermes/home), .hermes/{lib,kernel,planning,skills} from the
golden, and the outcome protocol in qualification mode (no factory declaration).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

GOLDEN = Path(os.environ.get("RHOAI3_GOLDEN_HERMES", "")).resolve()
if not (GOLDEN / "lib" / "planner" / "outcome_graph.py").is_file():
    raise RuntimeError("RHOAI3_GOLDEN_HERMES must name the golden .hermes directory (got %r)" % str(GOLDEN))
for _p in (GOLDEN / "lib", GOLDEN / "kernel"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from planner.outcome_graph import derive_initial_graph  # noqa: E402

SHOP = json.loads((GOLDEN / "lib" / "planner" / "fixtures" / "outcome-initial-shop.json").read_text())
# the console script beside this interpreter: HERMES_BIN is also the dispatcher's worker-binary override,
# so it must be a path the dispatcher can exec (PYTHONPATH selects the patched tree)
HERMES_ARGV = os.path.join(os.path.dirname(sys.executable), "hermes")
PRODUCTION_MATCHER = ("write|write_file|patch|edit_file|apply_patch|create_file|terminal|execute_code|delegate_task|"
                      "skill_manage|kanban_complete|complete_task")
# the outcome protocol also decides these terminators (publication dependency: the Stage 050 matcher)
OUTCOME_MATCHER = PRODUCTION_MATCHER + "|kanban_block|kanban_request_review|request_review"


def git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()


def make_dest(tmp: Path, run_id: str = "q1") -> tuple[Path, dict]:
    dest = tmp / "modernized"
    (dest / ".hermes").mkdir(parents=True)
    for name in ("lib", "kernel", "planning", "skills"):
        os.symlink(GOLDEN / name, dest / ".hermes" / name)
    (dest / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                       "configuration": {"board_protocol": "outcome-board/v1"}}))
    (dest / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"outcome_board": {"execution": "qualification"}}}}))
    shutil.copy(GOLDEN.parent / "decisions.yaml", dest / "decisions.yaml")
    for c in SHOP["worklist"]["clusters"]:
        for p in c["write_set"]:
            f = dest / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("// %s v0\n" % p)
    (dest / "evidence" / "planning").mkdir(parents=True)
    (dest / "evidence" / "planning" / "worklist.json").write_text(json.dumps(SHOP["worklist"]))
    (dest / ".gitignore").write_text("verification/\nevidence/\n.hermes/home/\n")
    git(dest, "init", "-q")
    git(dest, "config", "user.email", "q@q")
    git(dest, "config", "user.name", "q")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "baseline")
    plan = derive_initial_graph(run_id=run_id, worklist=SHOP["worklist"], entry_points=SHOP["entry_points"],
                                oracles=SHOP["oracles"], references=SHOP["references"], provenance=SHOP["provenance"])
    (tmp / "plan.json").write_text(json.dumps(plan))
    return dest, plan


def env_for(dest: Path, **extra) -> dict:
    e = dict(os.environ)
    e.update(HERMES_BIN=HERMES_ARGV, K2_ALLOW_ROOT=str(dest), HERMES_WRITE_SAFE_ROOT=str(dest),
             PYTHONDONTWRITEBYTECODE="1")
    e.update({k: str(v) for k, v in extra.items()})
    return e


def publish(dest: Path, tmp: Path, m2: str, **extra) -> subprocess.CompletedProcess:
    """The K4 graph publisher as the M2 worker runs it: identity retained."""
    return subprocess.run(["python3", str(GOLDEN / "kernel" / "k4_graph.py"), "--root", str(dest),
                           "publish", "--plan-file", str(tmp / "plan.json"), "--hermes", HERMES_ARGV],
                          env=env_for(dest, HERMES_KANBAN_TASK=m2, **extra), capture_output=True, text=True, cwd=str(dest))


def store(dest: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(dest / "verification" / "outcome-board" / "authority.sqlite3"))
    con.row_factory = sqlite3.Row
    return con


def meta(dest: Path, key: str) -> str:
    con = store(dest)
    try:
        row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else ""
    finally:
        con.close()


def task_of(dest: Path, oid: str) -> str:
    con = store(dest)
    try:
        return con.execute("SELECT task_id FROM publication WHERE outcome_id=?", (oid,)).fetchone()[0]
    finally:
        con.close()


PRODUCER = GOLDEN.parents[4] / "gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml"


def _producer_block() -> str:
    import re
    text = PRODUCER.read_text()
    m = re.search(r"\n( *)# >>> outcome-board hooks.*?\n(.*?)\n *# <<< outcome-board hooks", text, re.S)
    assert m, "the producer's outcome-board hooks block is missing"
    return "\n".join(line[len(m.group(1)):] for line in m.group(2).splitlines())


def hook_config(cfg: dict, dest: Path, *, tick: bool) -> dict:
    """The hook configuration the Stage 050 producer GENERATES for this
    destination: its K2 registration (matcher and 5 s timeout, asserted against
    the producer text) plus the output of its own `outcome-board hooks` block,
    executed on this destination (the same select_protocol rule a workspace
    start applies)."""
    cfg = dict(cfg)
    cfg["hooks_auto_accept"] = True
    text = PRODUCER.read_text() if PRODUCER.is_file() else ""
    assert '"matcher": "%s"' % PRODUCTION_MATCHER in text and '"timeout": 5,' in text, "the producer's K2 registration changed"
    base = {"hooks": {"pre_tool_call": [{"matcher": PRODUCTION_MATCHER,
                                         "command": "bash %s" % (GOLDEN / "kernel" / "pre_tool_call.sh"),
                                         "timeout": 5, "fail_closed": True}]}}
    ns = {"os": os, "_pjson": json, "safe_root": str(dest), "cfg": base, "print": lambda *a: None}
    exec(_producer_block(), ns)
    hooks = ns["cfg"]["hooks"]
    assert hooks["pre_tool_call"][0]["matcher"] == OUTCOME_MATCHER, hooks
    assert hooks.get("on_kanban_dispatch_tick"), "the producer did not register the reconciler for %s" % dest
    if not tick:
        hooks.pop("on_kanban_dispatch_tick", None)
    cfg["hooks"] = hooks
    return cfg
