#!/usr/bin/env python3
"""Combined v13 lifecycle replay (design step 7), local, no model, no cluster.

One destination, one chain of the transitions the v12 blockers broke:

  1. run control holds the run's activation, bound to the M1 evidence bundle;
     a worker's git checkout of the repository's pins cannot remove it (B8)
  2. a loop card's candidate is verified, then its worker is halted before
     advance.py (B11): the respawned run's brief hands it the candidate and
     the one next action -- advance.py, because the verification is current
  3. a restart at the transition boundary loses the activation: advance.py
     ACCEPTS the verified candidate, the continuation records
     admission-refused naming RUN_ACTIVATION_MISSING, and K2 refuses
     kanban_complete but allows kanban_block (B8: never an idle board)
  4. the activation is restored: the SAME advance.py call finishes the
     continuation without a second step; K2 now allows completion
  5. with an empty work list, M4 VERIFY is still refused while the package
     and boot proof is owed, and minted once it is not (B6 debt)
Run under two package roots.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fug_test", HERE / "fix-until-green.test.py")
fug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fug)
from planner import pins as pins_mod, run_control, specimens  # noqa: E402
from planner.canonical import digest, load_json  # noqa: E402
from planner.cards import next_card  # noqa: E402
from planner.paths import MTA_FINDINGS, WORKLIST  # noqa: E402

K2 = HERE.parents[3] / "kernel" / "pre_tool_call.sh"
ATTR = "compiler.err.cant.resolve.location"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _k2(root: Path, tool: str, cmd: str = "") -> dict:
    env = dict(os.environ, K2_ALLOW_ROOT=str(root), HERMES_PROFILE="implementer", K2_BOUND_GATE_EXIT="0",
               HERMES_KANBAN_TASK="t_life", K2_HOOK_DIR=str(K2.parent))
    payload = {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(root)}
    p = subprocess.run(["bash", str(K2)], input=json.dumps(payload), text=True, capture_output=True, env=env)
    if p.returncode != 0 or not (p.stdout or "").strip() and p.stderr.strip():
        return {"action": "hook-error", "message": "rc=%s %s" % (p.returncode, p.stderr.strip()[-400:])}
    return json.loads((p.stdout or "").strip() or "{}")


def _replay(base_pkg: str) -> int:
    with tempfile.TemporaryDirectory(prefix="life-") as td:
        os.environ["RHOAI3_RUN_CONTROL_DIR"] = str(Path(td) / "platform" / "run-control")
        try:
            spec_ = specimens.specimen("http")
            root = specimens.build_dest(Path(td) / "dest", spec_, decisions=specimens.admitted_decisions(max_attempts=3))
            paths = fug._write_uri_controllers(root, fug._BUILDER)
            owner, pet = paths[0], paths[1]
            pet_err = (pet, 3, "cannot find symbol class ResponseEntity", ATTR)
            specimens.prepare_loop(root, errors=[(owner, 3, "cannot find symbol class UriComponentsBuilder", ATTR), pet_err])
            findings = load_json(root / MTA_FINDINGS)
            bundle = digest(load_json(root / "evidence/planning/evidence-bundle.json"))
            # 1. the run's activation lives in run control, bound to the M1 bundle
            seal = {"activation": "pilot", "pilot": {"run_id": "life-%s" % base_pkg, "authorized_by": "devworkspace-creator:u",
                                                     "evidence_bundle_sha256": bundle,
                                                     "authorization": {"source": "devworkspace", "creator": "u"}}}
            run_control.write_activation(root, seal, "bound", "M1 bundle")
            fug._git(root, "checkout", "--", ".hermes/pins.json")
            if pins_mod.activation_gaps(pins_mod.load_pins(root), bundle):
                return _fail("1: a checkout of the repository's pins leaves the run activated: %s"
                             % pins_mod.activation_gaps(pins_mod.load_pins(root), bundle))
            # 2. a verified candidate, then the worker is halted before advance.py
            cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if owner in (c.get("write_set") or []))
            fug._issue_cluster(root, cluster, "t_life")
            f = root / owner
            f.write_text(f.read_text(encoding="utf-8").replace("import java.net.URI;\n", "import java.net.URI;\n// repaired\n"),
                         encoding="utf-8")
            specimens.verify(root, errors=[pet_err], failures=[], findings=findings)
            p = subprocess.run([sys.executable, str(HERE / "brief.py"), "--root", str(root), "--cluster", cluster["id"]],
                               text=True, capture_output=True, env=dict(os.environ, HERMES_KANBAN_TASK="t_life"))
            ck = (json.loads(p.stdout or "{}").get("candidate_on_tree") or {}) if p.returncode == 0 else {}
            if not ck.get("verified") or owner not in ck.get("changed", []) or "advance.py" not in ck.get("next", ""):
                return _fail("2: the respawned run is handed its verified candidate and advance.py: rc=%s %s %s"
                             % (p.returncode, ck, p.stderr[-300:]))
            # 3. restart at the boundary: the activation is gone when advance.py runs
            act = run_control.run_control_dir(root) / run_control.ACTIVATION
            act.chmod(0o644)
            act.unlink()
            p = fug._advance(root, cluster["id"], "t_life")
            blob = p.stdout + p.stderr
            cont = load_json(root / "verification/loop/continuation.json")
            if "OK: ACCEPTED" not in p.stdout or "RUN_ACTIVATION_MISSING" not in blob or cont.get("state") != "admission-refused":
                return _fail("3: accepted, and the refused continuation is recorded and named: %s %s" % (cont, blob[-500:]))
            done, blocked = _k2(root, "kanban_complete"), _k2(root, "kanban_block")
            if done.get("action") != "block" or "no successor" not in done.get("message", ""):
                return _fail("3: K2 refuses completing a card whose acceptance has no successor: %s" % done)
            if blocked.get("action") == "block":
                return _fail("3: K2 lets that card block: %s" % blocked)
            if _k2(root, "terminal", "git checkout -- .hermes/pins.json").get("action") != "block":
                return _fail("3: K2 refuses the v12 checkout")
            # 4. the activation restored: the same call finishes the continuation
            run_control.write_activation(root, seal, "restored", "assisted: restored from backup")
            p = fug._advance(root, cluster["id"], "t_life")
            cont = load_json(root / "verification/loop/continuation.json")
            steps = load_json(root / "verification/loop/steps.json")["steps"]
            if p.returncode != 0 or "ACCEPTED already" not in p.stdout or cont.get("state") != "admitted" \
                    or sum(1 for s in steps if s.get("card") == "t_life") != 1:
                return _fail("4: the re-run finishes the continuation without a second step: rc=%s %s %s"
                             % (p.returncode, cont, (p.stdout + p.stderr)[-400:]))
            if [e["event"] for e in run_control.journal(root)] != ["bound", "restored"]:
                return _fail("4: the restore is journaled beside the binding: %s" % run_control.journal(root))
            # 5. package and boot debt keeps M4 unminted until both pass on one artifact
            empty = {"clusters": [], "items": [], "deferred": [], "blocked_clusters": [],
                     "measure": {"known": True, "tuple": [0, 0, 0]}}
            if next_card(dict(empty, runtime={"ready": False}), steps and {"steps": steps}) is not None:
                return _fail("5: M4 is refused while package and boot are owed")
            if (next_card(dict(empty, runtime={"ready": True}), {"steps": steps}) or {}).get("title") != "M4 VERIFY":
                return _fail("5: M4 VERIFY is minted once both gates pass")
        finally:
            os.environ.pop("RHOAI3_RUN_CONTROL_DIR", None)
    return 0


def main() -> int:
    if _replay("orders") or _replay("ledger"):
        return 1
    print("OK: v13 lifecycle replay (activation survives a checkout; a halted worker's successor is handed its verified "
          "candidate; a restart that loses the activation leaves an accepted step with a refused, named continuation "
          "that K2 will not let complete; restoring it lets the same call finish with no second step; M4 waits for the "
          "package and boot proof)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
