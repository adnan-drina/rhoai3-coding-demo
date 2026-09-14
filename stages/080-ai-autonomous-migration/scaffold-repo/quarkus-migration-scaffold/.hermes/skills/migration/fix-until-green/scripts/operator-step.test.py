#!/usr/bin/env python3
"""operator-step selftest: a change to a test source needs an ADR and a second seat,
and an issued card only blocks the step while it is LIVE.

A test source states what the destination must do. One seat editing both the
claim and its proof is not a reviewed intervention, so the tool refuses before
it commits anything. The control is the same change on a main source: it must
get past this guard, which is what proves the guard reads the path and not the
weather (ADR-008).

The second contract here is the issued card. A card whose worker may have a
candidate on the tree is LIVE and refuses the step. A card whose candidate is
RETAINED (VERIFICATION_PENDING) is the opposite: the accepted tree is on disk
and the prerequisite it waits for may itself be Operator-owned (dest v9,
t_7b8663f5 on c:fb2e558f39a5: the port of ValidatorTests to Jakarta
Validation), so the step is recorded BESIDE it, the card is kept, nothing is
minted -- and the retained candidate must still restore onto the tree the
Operator's change left behind.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEP = HERE / "operator-step.py"
GOLDEN = HERE.parents[4]

TEST_SRC = "src/test/java/a/ATest.java"
MAIN_SRC = "src/main/java/a/A.java"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _tree(root: Path, changed: str) -> None:
    """A destination with a baseline step, no issued card, and one changed path."""
    for rel in (MAIN_SRC, TEST_SRC):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("class X {}\n", encoding="utf-8")
    loop = root / "verification" / "loop"
    loop.mkdir(parents=True, exist_ok=True)
    (loop / "deferred.json").write_text(json.dumps({
        "schema": "rhoai3.loop-deferred/v1", "clusters": ["c:deferred"],
        "reasons": {"c:deferred": "3 rejected attempt(s)"},
    }), encoding="utf-8")
    (loop / "steps.json").write_text(json.dumps({
        "schema": "rhoai3.loop-steps/v1",
        "steps": [{"cluster": "baseline", "verdict": "baseline", "measure": {"known": True, "tuple": [1, 0, 0]}}],
        "attempts": {"c:deferred": 3},
        "rejected": [{"cluster": "c:deferred", "card": "t_rejected", "reason": "attempt 3"}],
    }), encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.email=t@local", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@local", "-c", "user.name=t", "commit", "-q", "-m", "baseline")
    (root / changed).write_text("class X { int y; }\n", encoding="utf-8")


def _run(changed: str, *args: str, issued: dict | None = None) -> tuple[int, str, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="operator-step-test-"))
    _tree(tmp, changed)
    if issued is not None:
        (tmp / "verification" / "loop" / "issued.json").write_text(json.dumps(issued), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(STEP), "--root", str(tmp), "--operator", "operator",
         "--reason", "port under ADR-008", "--verify-cmd", "true", "--no-mint", *args],
        text=True, capture_output=True)
    return proc.returncode, proc.stdout + proc.stderr, tmp


def _beside_pending_case() -> int:
    """An Operator step beside a VERIFICATION_PENDING card: recorded, the card
    kept, nothing minted -- and the retained candidate still restores onto the
    tree the Operator's change left behind, with THIS step as its baseline."""
    sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
    sys.path.insert(0, str(HERE))
    from _loop_common import candidate_sha256, load_issued, load_steps, pending_for, revert_paths, save_pending_candidate, save_steps  # noqa: E402
    from planner import specimens  # noqa: E402
    from planner.canonical import load_json  # noqa: E402
    from planner.paths import LOOP_ISSUED, LOOP_STEPS, MTA_FINDINGS  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="beside-pending-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        specimens.prepare_loop(root)
        card = specimens.issue(root)
        issued = load_issued(root) or {}
        cluster, task = str(issued.get("cluster") or ""), str(issued.get("task_id") or card.get("task_id") or "t_pending")
        rel = sorted(issued.get("write_set") or [])[0]

        # the worker's candidate, retained aside exactly as advance._pending
        # retains it: the accepted tree is what is left on disk
        target = root / rel
        target.write_text(target.read_text(encoding="utf-8") + "// candidate\n", encoding="utf-8")
        steps = load_steps(root)
        row = save_pending_candidate(
            root, cluster=cluster, card=task, changed=[rel], candidate_sha256_value=candidate_sha256(root),
            measure={"known": False, "blocked": ["tests unknown"], "tuple": []},
            reason="the prerequisite is Operator-owned", cause="harness", run={}, issued=issued)
        revert_paths(root, [rel])
        steps.setdefault("pending", []).append(row)
        save_steps(root, steps)
        n_steps = len(steps["steps"])
        issued_before = (root / LOOP_ISSUED).read_bytes()

        # the prerequisite, applied by the Operator on the accepted tree: a test
        # source ported under an ADR, which is the case that was measured
        port = root / "src/test/java/org/acme/clinic/ValidatorTests.java"
        port.parent.mkdir(parents=True, exist_ok=True)
        port.write_text("package org.acme.clinic;\nclass ValidatorTests { }\n", encoding="utf-8")
        state = specimens.write_verified_state(root, errors=[], failures=[], findings=load_json(root / MTA_FINDINGS))
        verify_cmd = " ".join(shlex.quote(a) for a in
                              [sys.executable, str(root / ".hermes/skills/migration/fix-until-green/scripts/verify.py"),
                               "--root", str(root), *state["args"]])
        # no --no-mint on purpose: the pending card owns the head, so this mode
        # must withhold the mint on its own
        p = subprocess.run([sys.executable, str(STEP), "--root", str(root), "--operator", "operator:o", "--reviewer", "reviewer:r",
                            "--adr", "ADR-008", "--reason", "port ValidatorTests to Jakarta Validation", "--verify-cmd", verify_cmd],
                           text=True, capture_output=True)
        blob = p.stdout + p.stderr
        if p.returncode != 0 or "OPERATOR STEP" not in p.stdout:
            return _fail("a step beside a retained candidate must be recorded: rc=%d %s" % (p.returncode, blob[-600:]))
        if "beside VERIFICATION_PENDING" not in p.stdout or "restore-pending.py" not in p.stdout or task not in p.stdout:
            return _fail("the OK line must say the card stays issued and name the resume commands: %s" % p.stdout[-400:])
        steps = load_json(root / LOOP_STEPS)
        if len(steps["steps"]) != n_steps + 1:
            return _fail("the operator step must be appended: %d steps" % len(steps["steps"]))
        last = steps["steps"][-1]
        if last.get("verdict") != "operator" or last.get("beside_pending") != {"cluster": cluster, "card": task, "cause": "harness"}:
            return _fail("the record must name the pending cluster, card and cause: %s" % last.get("beside_pending"))
        if "withheld" not in str(last.get("mint") or ""):
            return _fail("the record must say why nothing was minted: %s" % last.get("mint"))
        if (root / LOOP_ISSUED).read_bytes() != issued_before:
            return _fail("the issued card must be kept untouched so the pending protocol resumes on it")
        if pending_for(load_json(root / LOOP_STEPS), cluster) is None:
            return _fail("the pending row must survive the operator step")
        if not last.get("changed") or last["changed"] != ["src/test/java/org/acme/clinic/ValidatorTests.java"]:
            return _fail("the step must commit exactly the Operator's change: %s" % last.get("changed"))

        # the retained candidate still restores: its own paths come back byte
        # for byte, and the tree under it is the operator step's tree
        rp = subprocess.run([sys.executable, str(HERE / "restore-pending.py"), "--root", str(root), "--cluster", cluster],
                            text=True, capture_output=True)
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("the retained candidate must restore over the Operator's change: %s%s" % (rp.stdout, rp.stderr))
        if (root / rel).read_text(encoding="utf-8").count("// candidate") != 1 or not port.is_file():
            return _fail("the restore must put the candidate back and keep the Operator's change")

        # and the baseline the next advance compares against is THIS step:
        # advance reads steps[-1] (the operator step) and its accepted report
        # snapshot. Fixture-level: a full advance would judge the candidate's
        # own content, which is not what this case is about.
        prev = load_json(root / LOOP_STEPS)["steps"][-1]
        if prev.get("commit") != last.get("commit") or not prev.get("obligation_keys"):
            return _fail("advance's baseline (steps[-1]) must be the operator step: %s" % prev.get("commit"))
        if prev.get("candidate_sha256") == candidate_sha256(root):
            return _fail("the restored tree must differ from the operator step, or advance refuses LOOP_PENDING_NOT_RESTORED")
        snap = root / "verification" / "loop" / "accepted" / "diagnostics.json"
        if not snap.is_file():
            return _fail("the operator step must refresh the accepted report snapshot advance compares against")

        # controls, so the tolerated drift is the Operator's committed change
        # and nothing else. (a) an uncommitted edit elsewhere in the product
        # tree still makes the restored tree something other than this
        # candidate:
        stray = root / "src/main/resources/application.properties"
        stray.write_text(stray.read_text(encoding="utf-8") + "\n# stray\n", encoding="utf-8")
        rp = subprocess.run([sys.executable, str(HERE / "restore-pending.py"), "--root", str(root), "--cluster", cluster],
                            text=True, capture_output=True)
        if rp.returncode == 0 or "LOOP_PENDING_CANDIDATE_CHANGED" not in rp.stderr or "application.properties" not in rp.stderr:
            return _fail("a change outside the candidate's paths that is not committed must still refuse: %s%s" % (rp.stdout, rp.stderr))
        subprocess.run(["git", "-C", str(root), "checkout", "--", "src/main/resources/application.properties"], capture_output=True)
        # (b) a commit that touched a path this candidate also holds: restoring
        # would silently drop it, so it is refused by name
        for cmd in (["add", "--", rel], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "operator touches the candidate's file"]):
            subprocess.run(["git", "-C", str(root), *cmd], capture_output=True)
        rp = subprocess.run([sys.executable, str(HERE / "restore-pending.py"), "--root", str(root), "--cluster", cluster],
                            text=True, capture_output=True)
        if rp.returncode == 0 or "which this candidate also holds" not in rp.stderr or rel not in rp.stderr:
            return _fail("a committed change to a path the candidate holds must refuse rather than drop it: %s%s" % (rp.stdout, rp.stderr))
    return 0


def main() -> int:
    for name, args, needle in (
        ("no ADR", ("--reviewer", "reviewer"), "names no ADR"),
        ("no reviewer", ("--adr", "ADR-008"), "names no reviewer"),
        ("reviewer is the operator", ("--adr", "ADR-008", "--reviewer", "operator"), "other than the operator"),
    ):
        rc, blob, tmp = _run(TEST_SRC, *args)
        if rc != 1 or needle not in blob:
            return _fail("a test-source change with %s must refuse naming %r: rc=%d %s" % (name, needle, rc, blob[:300]))
        if TEST_SRC not in blob:
            return _fail("the refusal must name the offending path: %s" % blob[:300])
        head = subprocess.run(["git", "-C", str(tmp), "log", "--oneline"], text=True, capture_output=True).stdout
        if len(head.strip().splitlines()) != 1:
            return _fail("the guard must refuse before committing anything: %s" % head)

    # A deferral is the loop's record that a human must decide. Clearing one
    # that is not open would silently invent that decision, and clearing one
    # before the tree measures green would lift it on an intention.
    rc, blob, tmp = _run(TEST_SRC, "--adr", "ADR-008", "--reviewer", "reviewer", "--clear-deferred", "c:never-deferred")
    if rc != 1 or "is not deferred" not in blob or "c:deferred" not in blob:
        return _fail("clearing a cluster that is not deferred must refuse and name the open deferrals: rc=%d %s" % (rc, blob[:300]))
    rc, blob, tmp = _run(MAIN_SRC, "--adr", "ADR-002", "--clear-deferred", "c:deferred")
    if rc == 0 or "measure not known" not in blob:
        return _fail("the main-source control must reach the re-measure: %s" % blob[:300])
    still = json.loads((tmp / "verification" / "loop" / "deferred.json").read_text())
    if still.get("clusters") != ["c:deferred"]:
        return _fail("a deferral must survive a step whose re-measure failed: %s" % still)
    kept = json.loads((tmp / "verification" / "loop" / "steps.json").read_text())
    if [r["card"] for r in kept.get("rejected") or []] != ["t_rejected"]:
        return _fail("the rejected rows are the record of what the cluster minted and must never be dropped: %s" % kept.get("rejected"))

    # An issued card with no retained candidate is LIVE: a worker's candidate
    # may be on the tree, and a step recorded over it would commit that work as
    # the Operator's. The refusal says what is true of that card.
    rc, blob, tmp = _run(MAIN_SRC, "--adr", "ADR-004",
                         issued={"cluster": "c:fb2e558f39a5", "task_id": "t_7b8663f5", "write_set": [MAIN_SRC]})
    if rc != 1 or "an issued card is live" not in blob:
        return _fail("an issued card with no retained candidate must refuse as live: rc=%d %s" % (rc, blob[:300]))
    if "t_7b8663f5" not in blob or "c:fb2e558f39a5" not in blob or "let it finish or revert it" not in blob:
        return _fail("the live refusal must name the card, its cluster and the way out: %s" % blob[:300])
    log = subprocess.run(["git", "-C", str(tmp), "log", "--oneline"], text=True, capture_output=True).stdout
    if len(log.strip().splitlines()) != 1:
        return _fail("the live refusal must come before the commit: %s" % log)

    # A metadata-only disposition is for a cause removed OUTSIDE the product
    # tree; with a product change on disk it would record an intention.
    rc, blob, tmp = _run(MAIN_SRC, "--clear-deferred", "c:deferred", "--disposition-only")
    if rc != 1 or "has changes" not in blob:
        return _fail("--disposition-only with a product change must refuse: rc=%d %s" % (rc, blob[:300]))
    rc, blob, tmp = _run(MAIN_SRC, "--disposition-only")
    if rc != 1 or "name the cluster" not in blob:
        return _fail("--disposition-only records a clearance and needs --clear-deferred: rc=%d %s" % (rc, blob[:300]))

    # Control: the same change on a main source is not this guard's business. It
    # gets past it (and stops later, on the missing measure) — so a red above is
    # the path, not the tool refusing everything.
    rc, blob, tmp = _run(MAIN_SRC, "--adr", "ADR-004")
    if rc == 0 or "reviewer" in blob:
        return _fail("a main-source change must pass the reviewer guard: rc=%d %s" % (rc, blob[:300]))
    if "measure not known" not in blob:
        return _fail("the main-source control must stop on the re-measure, not earlier: %s" % blob[:300])
    log = subprocess.run(["git", "-C", str(tmp), "log", "--oneline"], text=True, capture_output=True).stdout
    if len(log.strip().splitlines()) != 2:
        return _fail("the main-source control must have committed the change: %s" % log)

    if _beside_pending_case():
        return 1

    print("OK: operator-step selftest (test-source change refuses without an ADR, without a reviewer, and with the operator as reviewer, before committing; main-source control passes the guard and commits; a deferral that is not open refuses and one whose re-measure failed survives; a metadata-only disposition refuses with a product change or no cluster; a LIVE issued card refuses by name; a step beside a VERIFICATION_PENDING card is recorded with beside_pending, keeps the card, mints nothing, and the retained candidate still restores onto it as the new baseline -- while a stray uncommitted edit, and a commit that touched a path the candidate holds, still refuse the restore)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
