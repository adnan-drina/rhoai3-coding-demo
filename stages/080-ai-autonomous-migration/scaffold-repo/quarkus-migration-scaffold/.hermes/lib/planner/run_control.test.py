#!/usr/bin/env python3
"""run_control selftest (B8, B10).

  * a git checkout, reset or stash of the destination's pins cannot remove the
    run's activation: it is read from run control, never from pins.json, once
    run control exists; a destination without run control reads pins as before
  * the activation file is written read-only, and every write is journaled
  * a missing activation after a recorded binding is RUN_ACTIVATION_MISSING,
    naming the run, the event and its time from the journal
  * a seal naming another run than the factory declaration is
    RUN_ACTIVATION_FOREIGN
  * the harness release recorded at creation is the one the run executes: a
    changed harness file is HARNESS_RELEASE_MISMATCH, bytecode caches are not a
    change, and the assisted rebase is journaled permanently
Run twice, under two run names and two package layouts.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import pins as pins_mod, run_control, run_declaration  # noqa: E402

BUNDLE = "b" * 64


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _dest(td: Path, run: str) -> Path:
    root = td / "projects" / "modernized"
    (root / ".hermes" / "lib").mkdir(parents=True)
    (root / ".hermes" / "kernel").mkdir(parents=True)
    (root / ".hermes" / "skills" / "x").mkdir(parents=True)
    (root / ".hermes" / "lib" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (root / ".hermes" / "skills" / "x" / "SKILL.md").write_text("# x\n", encoding="utf-8")
    golden = {"pins": {"planner": {"activation": "not-activated", "pilot": None}, "mta_cli": {"version": "8.2"}}}
    (root / ".hermes" / "pins.json").write_text(json.dumps(golden, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "golden"],
                   check=True)
    return root


def _seal(run: str, bundle: str = BUNDLE) -> dict:
    return {"activation": "pilot", "pilot": {"run_id": run, "authorized_by": "devworkspace-creator:u1",
                                             "evidence_bundle_sha256": bundle,
                                             "authorization": {"source": "devworkspace", "devworkspace": run}}}


def _case(run: str) -> int:
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        root = _dest(td, run)
        os.environ.pop("RHOAI3_RUN_CONTROL_DIR", None)
        # without run control the repository's pins answer, as before
        if pins_mod.planner_activation(pins_mod.load_pins(root)) != "not-activated":
            return _fail("without run control the golden pins answer (%s)" % run)
        run_control.write_activation(root, _seal(run, ""), "recorded", "dest-init")
        run_control.write_activation(root, _seal(run), "bound", "M1 bundle")
        act = run_control.run_control_dir(root) / run_control.ACTIVATION
        if stat.S_IMODE(act.stat().st_mode) & 0o222:
            return _fail("the activation file is written read-only: %o" % stat.S_IMODE(act.stat().st_mode))
        events = [e["event"] for e in run_control.journal(root)]
        if events != ["recorded", "bound"]:
            return _fail("every activation write is journaled: %s" % events)
        # the v12 incident, three ways: the destination's pins go back to the golden
        for how in (["checkout", "--", ".hermes/pins.json"], ["reset", "--hard", "-q"], ["stash", "-q"]):
            (root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": _seal(run)}}), encoding="utf-8")
            subprocess.run(["git", "-C", str(root), *how], check=False, capture_output=True)
            p = pins_mod.load_pins(root)
            if pins_mod.planner_activation(p) != "pilot" or pins_mod.activation_gaps(p, BUNDLE):
                return _fail("git %s of the destination cannot remove the activation (%s): %s"
                             % (how[0], run, pins_mod.activation_gaps(p, BUNDLE)))
        # a worker that forges an activation in pins.json activates nothing
        (root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"planner": {"activation": "activated"}}}),
                                                    encoding="utf-8")
        act.chmod(0o644)
        act.unlink()
        p = pins_mod.load_pins(root)
        gaps = pins_mod.activation_gaps(p, BUNDLE)
        if pins_mod.planner_activation(p) == "activated" or not gaps or not gaps[0].startswith("RUN_ACTIVATION_MISSING"):
            return _fail("a missing activation is RUN_ACTIVATION_MISSING, never the pins.json fallback (%s): %s" % (run, gaps))
        if run not in gaps[0] or "bound" not in gaps[0] or BUNDLE[:16] not in gaps[0]:
            return _fail("the refusal names the run, the last event and the bundle from the journal: %s" % gaps[0])
        # a seal for another run is refused against the factory declaration
        run_control.write_activation(root, _seal(run + "-other"), "bound", "copied from elsewhere")
        real = run_declaration.load
        run_declaration.load = lambda _root, *a, **k: run_declaration.Declaration(run_declaration.OK, "", run_id=run)
        try:
            gaps = pins_mod.activation_gaps(pins_mod.load_pins(root), BUNDLE)
        finally:
            run_declaration.load = real
        if not gaps or not gaps[0].startswith("RUN_ACTIVATION_FOREIGN") or (run + "-other") not in gaps[0]:
            return _fail("a seal naming another run is RUN_ACTIVATION_FOREIGN (%s): %s" % (run, gaps))
        # B10: the harness release recorded at creation
        run_control.record_release(root, run_control.harness_release_digest(root), "dest-init")
        if run_control.release_gaps(root):
            return _fail("the recorded release is the one on disk: %s" % run_control.release_gaps(root))
        cache = root / ".hermes" / "lib" / "__pycache__"
        cache.mkdir()
        (cache / "a.cpython-311.pyc").write_bytes(b"\0")
        if run_control.release_gaps(root):
            return _fail("a bytecode cache is not a harness change")
        (root / ".hermes" / "lib" / "a.py").write_text("A = 2\n", encoding="utf-8")
        gaps = run_control.release_gaps(root)
        if not gaps or not gaps[0].startswith("HARNESS_RELEASE_MISMATCH"):
            return _fail("a changed harness file is HARNESS_RELEASE_MISMATCH: %s" % gaps)
        run_control.rebase_release(root, "assisted install of golden X")
        if run_control.release_gaps(root):
            return _fail("the assisted rebase records the new release")
        if "release-rebased-assisted" not in [e["event"] for e in run_control.journal(root)]:
            return _fail("the assisted rebase is journaled permanently")
        # B4: the model profile the run's worker config was generated from
        managed = td / "platform-hermes"
        managed.mkdir()
        os.environ["HERMES_MANAGED_DIR"] = str(managed)
        try:
            prof = {"default_model": "m-%s" % run, "profiles": {"m-%s" % run: {"mode": "non-thinking", "request_body":
                    {"temperature": 0.7, "presence_penalty": 1.5}, "context_length": 220000}}}
            import hashlib
            def write_profile(doc):
                d = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                (managed / "model-profile.json").write_text(json.dumps(dict(doc, digest=d)), encoding="utf-8")
            write_profile(prof)
            run_control.record_profile(root, "dest-init")
            if run_control.profile_gaps(root) or run_control.run_gaps(root):
                return _fail("the pinned profile is the one in force: %s" % run_control.run_gaps(root))
            drifted = json.loads(json.dumps(prof))
            drifted["profiles"]["m-%s" % run]["request_body"]["presence_penalty"] = 0.0
            write_profile(drifted)
            run_control.record_profile(root, "dest-init restart")  # never re-pins
            gaps = run_control.profile_gaps(root)
            if not gaps or not gaps[0].startswith("MODEL_PROFILE_MISMATCH") or "presence_penalty: expected 1.5, got 0.0" not in gaps[0]:
                return _fail("a profile regenerated differently mid-run is refused naming the field: %s" % gaps)
            (managed / "model-profile.json").unlink()
            gaps = run_control.run_gaps(root)
            if not gaps or "missing" not in gaps[0]:
                return _fail("a missing runtime profile is refused: %s" % gaps)
        finally:
            os.environ.pop("HERMES_MANAGED_DIR", None)
    return 0


def main() -> int:
    if _case("spring-petclinic-rest-legacy-v13") or _case("orders-service-v2"):
        return 1
    print("OK: run_control (a git checkout, reset or stash of the destination cannot remove the activation; a forged "
          "pins.json activates nothing; the activation is read-only and journaled; a missing one is "
          "RUN_ACTIVATION_MISSING naming the run, the event and the bundle; another run's seal is "
          "RUN_ACTIVATION_FOREIGN; a changed harness file is HARNESS_RELEASE_MISMATCH, a bytecode cache is not, and "
          "the assisted rebase is journaled; the model profile pinned at creation is the one in force, and a regenerated "
          "or missing one is MODEL_PROFILE_MISMATCH naming the field)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
