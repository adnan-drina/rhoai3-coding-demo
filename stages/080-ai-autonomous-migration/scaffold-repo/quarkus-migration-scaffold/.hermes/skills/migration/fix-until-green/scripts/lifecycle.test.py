#!/usr/bin/env python3
"""Combined v13 lifecycle replay (design step 7), local, no model, no cluster.

One GOVERNED destination (its initial commit declares run control), one chain
of the transitions the v12 blockers broke:

  1. the platform's read-only contract authorizes the run; a worker's git
     checkout of the repository's pins changes nothing; M1 binds its bundle
     digest once (B8/R3)
  2. a loop card's candidate is verified, then its worker is halted before
     advance.py (B11): the respawned run's brief hands it the candidate and
     the one next action -- advance.py, because the verification is current
  3. the platform record is lost: advance.py refuses before anything is
     measured or promoted (R1) -- the candidate stays on the tree
  4. with the record back, a restart has lost the M1 binding: advance.py
     ACCEPTS the verified candidate, the continuation records
     admission-refused, and K2 refuses kanban_complete but allows
     kanban_block (B8: never an idle board)
  5. the binding restored (write-once, it was missing): the SAME advance.py
     call finishes the continuation without a second step
  6. with an empty work list, M4 VERIFY is still refused while the package
     and boot proof is owed, and minted once it is not (B6 debt)
Run under two run names.
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


PROFILE = {"default_model": "m-1", "profiles": {"m-1": {"provider": "p1", "mode": "non-thinking",
           "context_length": 1000, "max_tokens": 100, "request_body": {"temperature": 0.7}}}}


def _replay(run: str) -> int:
    with tempfile.TemporaryDirectory(prefix="life-") as td:
        control, state, managed = Path(td) / "control", Path(td) / "state", Path(td) / "managed"
        control.mkdir()
        managed.mkdir()
        os.environ["HERMES_MANAGED_DIR"] = str(managed)
        try:
            spec_ = specimens.specimen("http")
            root = specimens.build_dest(Path(td) / "dest", spec_, decisions=specimens.admitted_decisions(max_attempts=3))
            # the factory's declaration and a COMMITTED harness, as a real destination has
            (root / ".gitignore").write_text((root / ".gitignore").read_text().replace(".hermes/\n", ""), encoding="utf-8")
            (root / "run-budget.json").write_text(json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": run, "run_control": {
                "contract": run_control.CONTRACT_SCHEMA, "root": str(control), "state": str(state)}}), encoding="utf-8")
            paths = fug._write_uri_controllers(root, fug._BUILDER)
            owner, pet = paths[0], paths[1]
            pet_err = (pet, 3, "cannot find symbol class ResponseEntity", ATTR)
            # the scaffolding push: the initial commit, from which the platform provisions the run's record
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            fug._git(root, "add", "-A")
            fug._git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "scaffolding push")
            initial = fug._git(root, "rev-parse", "HEAD").strip()
            contract = {"schema": run_control.CONTRACT_SCHEMA, "run_id": run, "scaffold_commit": initial,
                        "activation": "pilot", "authorized_by": "provision-migration-run:tr-life"}
            (control / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
            (control / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
            (managed / "model-profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
            (managed / "config.yaml").write_text(
                "model:\n  default: m-1\n  provider: p1\n  context_length: 1000\n  max_tokens: 100\n"
                "providers:\n  p1:\n    extra_body:\n      temperature: 0.7\n", encoding="utf-8")
            (root / "WORKSPACE-START.md").write_text("the workspace starts after provisioning\n", encoding="utf-8")
            specimens.prepare_loop(root, errors=[(owner, 3, "cannot find symbol class UriComponentsBuilder", ATTR), pet_err])
            if run_control.run_gaps(root):
                return _fail("0: an intact governed fixture has no gaps: %s" % run_control.run_gaps(root))
            findings = load_json(root / MTA_FINDINGS)
            bundle = digest(load_json(root / "evidence/planning/evidence-bundle.json"))
            # 1. the platform authorizes; pins are not read; M1 binds once
            fug._git(root, "checkout", "--", ".hermes/pins.json")
            if not run_control.bind(root, bundle, "M1")[0] or pins_mod.activation_gaps(pins_mod.load_pins(root), bundle):
                return _fail("1: the platform-authorized run binds its M1 bundle: %s"
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
            # 3. the platform record is lost: nothing is measured or promoted
            (control / "contract.json").rename(control / "contract.json.lost")
            p = fug._advance(root, cluster["id"], "t_life")
            if p.returncode != 2 or "RUN_CONTROL_MISSING" not in p.stderr or "ACCEPTED" in p.stdout \
                    or owner not in fug._git(root, "status", "--porcelain"):
                return _fail("3: a lost platform record refuses before anything is promoted: rc=%s %s"
                             % (p.returncode, (p.stdout + p.stderr)[-400:]))
            (control / "contract.json.lost").rename(control / "contract.json")
            # 4. a restart lost the M1 binding: accepted, continuation refused, K2 blocks completion
            b = state / "binding.json"
            b.chmod(0o644)
            b.unlink()
            p = fug._advance(root, cluster["id"], "t_life")
            blob = p.stdout + p.stderr
            cont = load_json(root / "verification/loop/continuation.json")
            if "OK: ACCEPTED" not in p.stdout or "LOOP_ADMISSION" not in blob or cont.get("state") != "admission-refused":
                return _fail("4: accepted, and the refused continuation is recorded and named: %s %s" % (cont, blob[-500:]))
            done, blocked = _k2(root, "kanban_complete"), _k2(root, "kanban_block")
            if done.get("action") != "block" or "no successor" not in done.get("message", ""):
                return _fail("4: K2 refuses completing a card whose acceptance has no successor: %s" % done)
            if blocked.get("action") == "block":
                return _fail("4: K2 lets that card block: %s" % blocked)
            if _k2(root, "terminal", "git checkout -- .hermes/pins.json").get("action") != "block":
                return _fail("4: K2 refuses the v12 checkout")
            # 5. the binding restored: the same call finishes the continuation
            if not run_control.bind(root, bundle, "restored")[0]:
                return _fail("5: a missing binding can be written once again")
            p = fug._advance(root, cluster["id"], "t_life")
            cont = load_json(root / "verification/loop/continuation.json")
            steps = load_json(root / "verification/loop/steps.json")["steps"]
            if p.returncode != 0 or "ACCEPTED already" not in p.stdout or cont.get("state") != "admitted" \
                    or sum(1 for s in steps if s.get("card") == "t_life") != 1:
                return _fail("5: the re-run finishes the continuation without a second step: rc=%s %s %s"
                             % (p.returncode, cont, (p.stdout + p.stderr)[-400:]))
            # 6. package and boot debt keeps M4 unminted until both pass on one artifact
            empty = {"clusters": [], "items": [], "deferred": [], "blocked_clusters": [],
                     "measure": {"known": True, "tuple": [0, 0, 0]}}
            if next_card(dict(empty, runtime={"ready": False}), {"steps": steps}) is not None:
                return _fail("6: M4 is refused while package and boot are owed")
            if (next_card(dict(empty, runtime={"ready": True}), {"steps": steps}) or {}).get("title") != "M4 VERIFY":
                return _fail("6: M4 VERIFY is minted once both gates pass")
        finally:
            os.environ.pop("HERMES_MANAGED_DIR", None)
    return 0


def main() -> int:
    if _replay("orders-migration") or _replay("ledger-modernization"):
        return 1
    print("OK: v13 lifecycle replay (a governed run is authorized by the platform record and binds M1 once; a halted "
          "worker's successor is handed its verified candidate; a lost platform record refuses before anything is "
          "promoted; a lost binding leaves an accepted step with a refused, named continuation K2 will not let complete; "
          "re-binding lets the same call finish with no second step; M4 waits for the package and boot proof)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
