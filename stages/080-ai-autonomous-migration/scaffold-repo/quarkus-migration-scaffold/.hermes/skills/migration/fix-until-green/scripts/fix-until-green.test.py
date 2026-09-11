#!/usr/bin/env python3
"""fix-until-green loop selftest (end to end on the http specimen; simulated tool outputs; real git).

Transaction: issued card → candidate identity → scope → measure → commit / revert.
Counterexamples kept from the 2026-09-09 review: invented cluster, post-verification
edit, out-of-scope (test) edit, staged edit, rejected reports, missing/failed tool
runs, line movement, unresolved test scope, deferral stops the loop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
VERIFY = HERE / "verify.py"
ADVANCE = HERE / "advance.py"
REWIND = HERE / "rewind.py"
OPERATOR_STEP = HERE / "operator-step.py"
BRIEF = HERE / "brief.py"
BOOTSTRAP = GOLDEN / ".hermes" / "skills" / "migration" / "bootstrap-destination" / "scripts" / "bootstrap-destination.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(GOLDEN / ".hermes" / "kernel"))
from k4_convert import convert_admitted  # noqa: E402
sys.path.insert(0, str(HERE))
from _loop_common import profile_keys_lost  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.worklist import build_worklist  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, LOOP_DEFERRED, LOOP_ISSUED, LOOP_STEPS, VERIFY_DIAGNOSTICS, VERIFY_RUN, WORKLIST  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("HERMES_KANBAN_TASK", None)
    return subprocess.run(argv, text=True, capture_output=True, env=env)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True).stdout


def _advance(root: Path, cluster: str, card: str) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", cluster, "--card", card, "--no-mint"])


def _head(root: Path) -> dict:
    wl = load_json(root / WORKLIST)
    return next(c for c in wl["clusters"] if c["id"] == wl["head"])


def _profile_keys_cases() -> int:
    old = "# db\nquarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\nquarkus.datasource.username=sa\nspring.jpa.database=HSQL\nspring.datasource.password=pw\n"
    m = {"spring.datasource.password": "quarkus.datasource.password"}
    # deletion with nothing landed: every behavior-carrying key is lost; the unmapped Spring key is not
    lost = profile_keys_lost("hsqldb", old, "", "spring.profiles.active=hsqldb\n", m)
    if lost != ["quarkus.datasource.jdbc.url", "quarkus.datasource.username", "spring.datasource.password"]:
        return _fail("deleting a profile file must report its behavior-carrying keys as lost: %s" % lost)
    # the documented merge: %profile.key in application.properties (mapped name accepted)
    main = "%hsqldb.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\n%hsqldb.quarkus.datasource.username=sa\n%hsqldb.quarkus.datasource.password=pw\n"
    if profile_keys_lost("hsqldb", old, "", main, m):
        return _fail("keys landed as %profile.key (mapped) must not count as lost")
    # a bare key in application.properties also counts; keys kept in the file are not lost
    if profile_keys_lost("hsqldb", old, "quarkus.datasource.username=sa\n", "quarkus.datasource.jdbc.url=x\nquarkus.datasource.password=pw\n", m):
        return _fail("bare landing and kept keys must not count as lost")
    return 0


def _attempt_budget_case() -> int:
    """A cleared deferral raises the budget; it never deletes the attempts."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _loop_common import attempt_budget  # noqa: E402

    steps = {"attempts": {"c:x": 3}, "rejected": [{"cluster": "c:x", "card": "t_1"}], "deferral_clearances": []}
    if attempt_budget(steps, "c:x", 3) != 3:
        return _fail("with no clearance the budget is the decided limit")
    steps["deferral_clearances"].append({"cluster": "c:x", "attempts": 3, "cards": ["t_1"]})
    if attempt_budget(steps, "c:x", 3) != 6:
        return _fail("a clearance at 3 spent attempts must allow 3 more, not reset the counter")
    steps["deferral_clearances"].append({"cluster": "c:x", "attempts": 6, "cards": ["t_1"]})
    if attempt_budget(steps, "c:x", 3) != 9:
        return _fail("a second clearance moves the budget again: %d" % attempt_budget(steps, "c:x", 3))
    if attempt_budget(steps, "c:other", 3) != 3:
        return _fail("a clearance belongs to its own cluster")
    if steps["attempts"]["c:x"] != 3 or steps["rejected"][0]["card"] != "t_1":
        return _fail("the history must be untouched by the budget question")
    return 0


def main() -> int:
    if _attempt_budget_case():
        return 1
    if _profile_keys_cases():
        return 1
    with tempfile.TemporaryDirectory(prefix="fug-") as tmp:
        t = Path(tmp).resolve()
        spec = specimens.specimen("http")
        base = spec["base"].replace(".", "/")
        root = specimens.build_dest(t / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=2))
        pipeline.assemble_bundle(root)
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "scaffold")
        p = _run([sys.executable, str(BOOTSTRAP), "--root", str(root)])
        if p.returncode != 0:
            return _fail("bootstrap: %s%s" % (p.stdout, p.stderr))
        findings = load_json(root / "evidence" / "mta-findings.json")
        owner = "src/main/java/%s/owner/OwnerController.java" % base
        pet = "src/main/java/%s/pet/PetController.java" % base
        errors = [(owner, 3, "cannot find symbol ResponseEntity"), (pet, 5, "cannot find symbol")]

        # --- measurement contract before the baseline ---
        # tests did not run → unknown; mvn test failed without a recorded failure → unknown
        p = specimens.verify(root, errors=[], failures=[], findings=findings)
        wl = load_json(root / WORKLIST)
        if not wl["measure"]["known"]:
            return _fail("clean tests with rc 0 must be known: %s" % wl["measure"])
        # an absent MTA scan is zero obligations in the bundle, not in the code: unknown
        bundle_p = root / "evidence/planning/evidence-bundle.json"
        bundle_doc = load_json(bundle_p)
        saved_bundle = bundle_p.read_bytes()
        bundle_doc["producers"]["mta"]["status"] = "missing"
        bundle_doc["obligations"] = []
        write_canonical(bundle_p, bundle_doc)
        specimens.verify(root, errors=[], failures=[])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or wl["measure"]["mandatory_incidents"] is not None or "MTA producer status" not in " ".join(wl["measure"]["blocked"]):
            return _fail("a missing MTA producer must leave obligations unknown: %s" % wl["measure"])
        bundle_p.write_bytes(saved_bundle)
        st = specimens.write_verified_state(root, errors=[], failures=[], findings=findings)
        args = [a for a in st["args"] if not a.startswith("--surefire") and not a.endswith("surefire.json")]
        _run([sys.executable, str(VERIFY), "--root", str(root)] + [a for i, a in enumerate(args) if not (args[i - 1] == "--test-rc" if i else False) and a != "--test-rc"])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or wl["measure"]["failing_tests"] is not None:
            return _fail("tests that did not run must be unknown: %s" % wl["measure"])
        specimens.verify(root, errors=[], failures=[], findings=findings, test_rc=1)
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or "no failing test recorded" not in " ".join(wl["measure"]["blocked"]):
            return _fail("mvn test rc 1 without a recorded failure must be unknown: %s" % wl["measure"])
        empty = t / "empty-surefire"
        empty.mkdir()
        _run([sys.executable, str(VERIFY), "--root", str(root), "--diagnostics", str(root / "verification/loop/sim/diagnostics.json"), "--surefire-dir", str(empty), "--test-rc", "0", "--findings", str(root / "verification/loop/sim/findings.json")])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or wl["measure"]["tuple"][2] is not None:
            return _fail("an empty surefire directory must never be green: %s" % wl["measure"])

        # --- baseline (two compile errors; tests skipped because compilation fails) ---
        p = specimens.verify(root, errors=errors, failures=[], findings=findings)
        if p.returncode != 0:
            return _fail("verify: %s%s" % (p.stdout, p.stderr))
        wl = load_json(root / WORKLIST)
        m = wl["measure"]
        if not m["known"] or m["tuple"] != [5, 2, 0] or m["parity_mismatches"] is not None:
            return _fail("initial measure %s" % m)
        if wl["clusters"][0]["kind"] != "build" or wl["clusters"][0]["path"] != "pom.xml":
            return _fail("build cluster must come first: %s" % wl["clusters"][0])
        # a tree edited after verification cannot become the baseline
        (root / "pom.xml").write_text((root / "pom.xml").read_text(encoding="utf-8") + "\n<!-- late -->\n", encoding="utf-8")
        p = _run([sys.executable, str(ADVANCE), "--root", str(root), "--baseline", "--no-mint"])
        if p.returncode != 2 or "LOOP_CANDIDATE_CHANGED" not in p.stderr:
            return _fail("baseline after a late edit must refuse: %s" % p.stderr)
        specimens.verify(root, errors=errors, failures=[], findings=findings)
        p = _run([sys.executable, str(ADVANCE), "--root", str(root), "--baseline", "--no-mint"])
        if p.returncode != 0:
            return _fail("baseline: %s%s" % (p.stdout, p.stderr))
        if _git(root, "status", "--porcelain").strip():
            return _fail("baseline must commit the bootstrapped tree")
        baseline_head = _git(root, "rev-parse", "HEAD").strip()
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("admission after baseline: %s" % rec["reasons"][:4])

        # --- issued card ---
        head = specimens.issue(root)
        issued = load_json(root / LOOP_ISSUED)
        if head["kind"] != "build" or issued["cluster"] != head["logical_id"] or issued["write_set"] != ["pom.xml"] or issued["attempt"] != 1:
            return _fail("issued card %s" % issued)
        p = _run([sys.executable, str(BRIEF), "--root", str(root)])
        if p.returncode != 0 or "pom.xml" not in p.stdout:
            return _fail("brief: %s" % p.stderr)
        brief = json.loads(p.stdout)
        if brief.get("previous_attempts") != [] or brief.get("attempts_left") != 2:
            return _fail("a first attempt has no previous attempts and the full budget: %s / %s" % (brief.get("previous_attempts"), brief.get("attempts_left")))
        if brief.get("write_set") != ["pom.xml"] or "one item at a time" not in brief.get("procedure", ""):
            return _fail("brief must name the write set and the patch-per-item procedure: %s" % {k: brief.get(k) for k in ("write_set", "procedure")})
        pom_items = [i for i in brief["items"] if i.get("source") == "mta" and i.get("path") == "pom.xml"]
        if not pom_items or any("advice" not in i or "element" not in i for i in pom_items):
            return _fail("every pom incident in the brief carries the rule advice and the element at its line: %s" % pom_items[:1])
        if any(i["element"].get("kind") not in ("dependency", "plugin", "extension", "project") for i in pom_items):
            return _fail("element kinds: %s" % [i["element"] for i in pom_items])
        pom_before = (root / "pom.xml").read_text(encoding="utf-8")

        # legacy baseline: strip the recorded obligation_keys; every later accept/revert below must re-key the
        # baseline from the accepted rescan findings instead of comparing content-hash ids against rule|file keys
        st = load_json(root / "verification/loop/steps.json")
        if st["steps"][0].pop("obligation_keys", None) is None:
            return _fail("the baseline step must record obligation_keys")
        write_canonical(root / "verification/loop/steps.json", st)
        # --- review counterexample 1: invented cluster + post-verification edit ---
        f2 = json.loads(json.dumps(findings))
        f2["violations"].pop("javaee-pom-to-quarkus-00003")
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)  # decreasing measure
        (root / "src/test/java/Bad.java").write_text("this is not java\n", encoding="utf-8")  # edit AFTER verification
        p = _advance(root, "c:never-issued", "t_x")
        if p.returncode != 1 or "LOOP_CANDIDATE_CHANGED" not in p.stderr:
            return _fail("post-verification edit must refuse: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if _git(root, "rev-parse", "HEAD").strip() != baseline_head or (root / "src/test/java/Bad.java").exists() or (root / "pom.xml").read_text(encoding="utf-8") != pom_before:
            return _fail("refusal must leave the accepted baseline and working tree unchanged")
        specimens.issue(root)
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, "c:never-issued", "t_x")
        if p.returncode != 1 or "LOOP_NOT_ISSUED" not in p.stderr or (root / "pom.xml").read_text(encoding="utf-8") != pom_before:
            return _fail("an unissued cluster must refuse and discard: %s" % p.stderr[-300:])

        # --- review counterexample 4/1: an edit outside the write set (a test) is rejected and reverted ---
        specimens.issue(root)
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        test_file = root / "src/test/java" / base / "owner/OwnerControllerTest.java"
        test_before = test_file.read_text(encoding="utf-8")
        test_file.write_text(test_before + "// weakened\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, head["logical_id"], "t_c1")
        if p.returncode != 1 or "outside the write set" not in p.stderr or test_file.read_text(encoding="utf-8") != test_before or (root / "pom.xml").read_text(encoding="utf-8") != pom_before:
            return _fail("out-of-scope edit must reject and revert everything: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        steps = load_json(root / LOOP_STEPS)
        if steps["attempts"].get(head["logical_id"]) != 1:
            return _fail("scope violation counts an attempt: %s" % steps["attempts"])
        # the rejected candidate's reports are gone: the work list is the accepted one again
        wl = load_json(root / WORKLIST)
        if wl["measure"]["tuple"] != [5, 2, 0]:
            return _fail("rejected reports must not survive: %s" % wl["measure"])

        # --- step 1 accepted (attempt 2 after the scope rejection) ---
        card1 = specimens.issue(root)
        if card1["attempt"] != 2:
            return _fail("retry must carry attempt 2: %s" % card1["attempt"])
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, head["logical_id"], "t_c1")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout or _git(root, "status", "--porcelain").strip():
            return _fail("accept: %s%s" % (p.stdout, p.stderr))
        steps = load_json(root / LOOP_STEPS)
        if steps["steps"][-1]["cluster"] != head["logical_id"] or steps["steps"][-1]["attempt"] != 2 or (root / LOOP_ISSUED).exists():
            return _fail("accepted step record: %s" % steps["steps"][-1])
        wl2 = load_json(root / WORKLIST)
        if wl2["measure"]["tuple"] != [4, 2, 0] or wl2["head"] == head["logical_id"]:
            return _fail("work list not advanced: %s head=%s" % (wl2["measure"], wl2["head"]))
        cl2 = _head(root)
        if cl2["kind"] != "compile":
            return _fail("after build, compile clusters come first: %s" % cl2)
        target = root / cl2["path"]
        original = target.read_text(encoding="utf-8")

        # --- review counterexample 2: a STAGED no-progress edit is reverted from index and tree ---
        key_c2 = specimens.issue(root)["idempotency_key"]
        target.write_text(original + "// staged, no progress\n", encoding="utf-8")
        _git(root, "add", "--", cl2["path"])
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, cl2["id"], "t_c2")
        if p.returncode != 1 or "REVERTED" not in p.stderr:
            return _fail("no-progress step must revert: rc=%s %s" % (p.returncode, p.stderr[-200:]))
        if target.read_text(encoding="utf-8") != original or _git(root, "diff", "--cached", "--name-only").strip():
            return _fail("revert must restore the file in the working tree AND the index")
        if load_json(root / LOOP_STEPS)["attempts"].get(cl2["id"]) != 1:
            return _fail("rejection must count an attempt")
        p = _run([sys.executable, str(BRIEF), "--root", str(root), "--cluster", cl2["id"]])
        b2 = json.loads(p.stdout)
        if len(b2.get("previous_attempts") or []) != 1 or "did not decrease" not in b2["previous_attempts"][0]["reason"] or b2.get("attempts_left") != 1:
            return _fail("the retry's brief must carry the refused attempt and the remaining budget: %s" % {k: b2.get(k) for k in ("previous_attempts", "attempts_left")})

        # --- review counterexample 7: line movement is not a new obligation ---
        specimens.issue(root)
        target.write_text("// one more line at the top\n" + original, encoding="utf-8")
        f3 = json.loads(json.dumps(f2))
        for v in f3["violations"].values():
            for inc in v.get("incidents", []):
                if inc["uri"].endswith(cl2["path"]):
                    inc["lineNumber"] = int(inc["lineNumber"]) + 1
        one_less = [e for e in errors if e[0] != cl2["path"]]
        specimens.verify(root, errors=one_less, failures=[], findings=f3)
        p = _advance(root, cl2["id"], "t_c3")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("a shifted incident must not veto progress: %s%s" % (p.stdout, p.stderr))
        accepted_head = _git(root, "rev-parse", "HEAD").strip()

        # --- deferral stops the loop (threshold 2) ---
        cl3 = _head(root)
        t3 = root / cl3["path"]
        orig3 = t3.read_text(encoding="utf-8")
        for attempt in (1, 2):
            specimens.issue(root)
            t3.write_text(orig3 + "// attempt %d\n" % attempt, encoding="utf-8")
            # attempt 1: a candidate Maven cannot resolve is an UNKNOWN compile count, never a smaller one
            specimens.verify(root, errors=one_less, failures=[], findings=f3, unresolvable="'dependencies.dependency.version' for io.quarkus:x is missing" if attempt == 1 else None)
            p = _advance(root, cl3["id"], "t_c%d" % (3 + attempt))
            if p.returncode != 1:
                return _fail("no-progress attempt %d must fail: %s" % (attempt, p.stdout))
            if attempt == 1 and ("REVERTED" not in p.stderr or "build unresolvable" not in p.stderr):
                return _fail("an unresolvable candidate must revert as unknown: %s" % p.stderr[-300:])
        if "DEFERRED" not in p.stderr or "STOPS" not in p.stderr:
            return _fail("threshold must defer and stop: %s" % p.stderr[-300:])
        if t3.read_text(encoding="utf-8") != orig3 or _git(root, "rev-parse", "HEAD").strip() != accepted_head:
            return _fail("deferral must leave the baseline intact")
        rec = load_json(root / ADMISSION_RECEIPT)
        if rec["status"] != "INCONCLUSIVE" or not any(b["class"] == "MANUAL_CLUSTER" for b in rec["blocks"]):
            return _fail("a deferred cluster must stop admission: %s" % rec["reasons"][:3])
        if convert_admitted(root)[0] is not None:
            return _fail("K4 must mint nothing while a cluster is deferred")
        # --- the Operator rewinds to the step before t_c3: the tree, the budget and the deferral go back; the record grows ---
        steps_before = load_json(root / LOOP_STEPS)
        n = len(steps_before["steps"])
        sim = root / "verification" / "loop" / "rewind-sim.py"
        sim.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=json.loads(%r), failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                       % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps(errors), json.dumps(f2)), encoding="utf-8")
        rew = [sys.executable, str(REWIND), "--root", str(root), "--operator", "adnan.drina", "--reason", "measure defect", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, sim)]
        p = _run(rew + ["--to-step", "99"])
        if p.returncode != 1 or "LOOP_REWIND" not in p.stderr or "steps:" not in p.stderr:
            return _fail("rewind to an unrecorded step must refuse and print the step table: %s" % p.stderr[-200:])
        p = _run(rew + ["--to-step", "0", "--to-card", "t_c1"])
        if p.returncode != 1 or "exactly one" not in p.stderr:
            return _fail("two targets must refuse: %s" % p.stderr[-200:])
        p = _run(rew + ["--before-card", "t_nobody"])
        if p.returncode != 1 or "accepted no recorded step" not in p.stderr:
            return _fail("an unknown card must refuse: %s" % p.stderr[-200:])
        # --before-card t_c3 == --to-step n-2 (undo the step t_c3 accepted)
        p = _run(rew + ["--before-card", "t_c3"])
        if p.returncode != 0 or "REWOUND" not in p.stdout:
            return _fail("rewind: %s%s" % (p.stdout[-400:], p.stderr[-400:]))
        if target.read_text(encoding="utf-8") != original or _git(root, "status", "--porcelain").strip():
            return _fail("rewind must restore the product tree at the step and commit it")
        steps = load_json(root / LOOP_STEPS)
        if len(steps["steps"]) != n - 1 or steps["attempts"] or len(steps["rewinds"]) != 1 or steps["rewinds"][0]["moved_steps"] != ["t_c3"]:
            return _fail("rewind record: %s" % {k: steps[k] for k in ("attempts", "rewinds")})
        if not all(r.get("rewound") for r in steps["rejected"]) or "t_c3" not in [r["card"] for r in steps["rejected"]]:
            return _fail("rewound steps and old rejections stay on the record as closed cards: %s" % [(r["card"], r.get("rewound")) for r in steps["rejected"]])
        if load_json(root / LOOP_DEFERRED)["clusters"] or load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("rewind must clear the deferral and re-seal admission")
        if _head(root)["id"] != cl2["id"]:
            return _fail("after the rewind the earlier cluster is the head again: %s" % _head(root)["id"])
        again = specimens.issue(root)
        if again["attempt"] != 1 or again["idempotency_key"] == key_c2:
            return _fail("a new epoch must not hand back the old attempt-1 card: %s vs %s" % (again["idempotency_key"], key_c2))
        target.write_text("// one more line at the top\n" + original, encoding="utf-8")
        specimens.verify(root, errors=one_less, failures=[], findings=f3)
        p = _advance(root, cl2["id"], "t_c3b")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("re-landing the rewound step: %s%s" % (p.stdout, p.stderr))
        # --- an Operator step: a decided change (ADR retirement) recorded as a loop step, not card work ---
        victim = next(p for p in sorted((root / "src" / "main" / "java").rglob("*.java")) if p.name != target.name)
        vrel = str(victim.relative_to(root))
        op_sim = root / "verification" / "loop" / "op-sim.py"
        op_sim.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=json.loads(%r), failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                          % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps([e for e in one_less if e[0] != vrel]), json.dumps(f3)), encoding="utf-8")
        opcmd = [sys.executable, str(OPERATOR_STEP), "--root", str(root), "--operator", "adnan.drina", "--reason", "retired by test", "--adr", "ADR-009", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, op_sim)]
        p = _run(opcmd)
        if p.returncode != 1 or "nothing changed" not in p.stderr:
            return _fail("an operator step with a clean tree must refuse: %s" % p.stderr[-200:])
        victim.unlink()
        n_before = len(load_json(root / LOOP_STEPS)["steps"])
        p = _run(opcmd)
        if p.returncode != 0 or "OPERATOR STEP" not in p.stdout:
            return _fail("operator step: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        st = load_json(root / LOOP_STEPS)["steps"][-1]
        if len(load_json(root / LOOP_STEPS)["steps"]) != n_before + 1 or st.get("verdict") != "operator" or st.get("adr") != "ADR-009" or st.get("changed") != [vrel] or not st.get("obligation_keys") or not st["measure"]["known"]:
            return _fail("the operator step must be recorded with verdict, adr, changed paths, keys and a known measure: %s" % {k: st.get(k) for k in ("verdict", "adr", "changed")})
        if _git(root, "status", "--porcelain").strip() or _git(root, "log", "-1", "--format=%s").strip().find("operator step by adnan.drina (ADR-009)") < 0:
            return _fail("the operator step must commit exactly the change with provenance: %s" % _git(root, "log", "-1", "--format=%s"))
        if load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("admission must be re-sealed after an operator step")
        # --- the measure definition changed under an issued card (harness fix): rewind to the LAST step with --remeasure, closing the orphaned card ---
        specimens.issue(root)
        n = len(load_json(root / LOOP_STEPS)["steps"])
        sim2 = root / "verification" / "loop" / "rewind-sim2.py"
        f5 = json.loads(json.dumps(f3))
        drop = next(k for k, v in f5["violations"].items() if v.get("category") == "mandatory")
        f5["violations"].pop(drop)  # one fewer obligation: as if a rule were superseded
        sim2.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=json.loads(%r), failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                        % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps(one_less), json.dumps(f5)), encoding="utf-8")
        rew2 = [sys.executable, str(REWIND), "--root", str(root), "--operator", "adnan.drina", "--reason", "rule superseded", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, sim2), "--to-step", str(n - 1)]
        p = _run(rew2)
        if p.returncode != 1 or "issued card is open" not in p.stderr:
            return _fail("an open issued card must refuse without --close-card: %s" % p.stderr[-200:])
        p = _run(rew2 + ["--close-card", "t_orphan"])
        if p.returncode != 1 or "--remeasure" not in p.stderr:
            return _fail("a changed measure must refuse without --remeasure: %s" % p.stderr[-300:])
        p = _run(rew2 + ["--close-card", "t_orphan", "--remeasure"])
        if p.returncode != 0 or "REWOUND" not in p.stdout:
            return _fail("remeasure rewind: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        steps = load_json(root / LOOP_STEPS)
        last = steps["steps"][-1]
        if len(steps["steps"]) != n or not last.get("remeasured") or last["remeasured"]["after"] != last["measure"]["tuple"] or (root / LOOP_ISSUED).exists():
            return _fail("remeasure must keep the step, record before/after and drop the issued card: %s" % {k: last.get(k) for k in ("remeasured",)})
        if not any(r["card"] == "t_orphan" and r.get("rewound") for r in steps["rejected"]) or steps["rewinds"][-1]["closed_cards"] != ["t_orphan"]:
            return _fail("the orphaned card must be on the record as closed: %s" % steps["rewinds"][-1])
        if load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("after a remeasure rewind admission must be re-sealed")
        # the deferred cluster is open again with a fresh budget; the fix lands
        specimens.issue(root)
        t3.write_text(orig3 + "// human fix\n", encoding="utf-8")
        f4 = json.loads(json.dumps(f3))
        f4["violations"] = {k: v for k, v in f4["violations"].items() if v.get("category") != "mandatory"}
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl3["id"], "t_c6")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("human fix step: %s%s" % (p.stdout, p.stderr))
        rec = load_json(root / ADMISSION_RECEIPT)
        if rec["status"] != "ADMITTED" or not rec["loop_complete"] or rec["measure"]["tuple"] != [0, 0, 0]:
            return _fail("green state must be ADMITTED + loop_complete: %s %s" % (rec["status"], rec["reasons"][:3]))

        # --- the transition out of the repair loop: packaging, then startup ---
        # An empty list means the tree compiles and its tests pass. Until the
        # packaged application has been built and started against the decided
        # database, both gates are UNKNOWN and the closing card is not minted.
        wl = load_json(root / WORKLIST)
        if (wl.get("runtime") or {}).get("ready") or not any("packaging is unknown" in r for r in wl["runtime"]["reasons"]):
            return _fail("with no packaging receipt the runtime must be unknown: %s" % wl.get("runtime"))
        try:
            specimens.issue(root)
            return _fail("M4 must not mint while packaging and startup are unknown")
        except RuntimeError:
            pass

        # packaging fails on a plugin: one build obligation, at pom.xml, with its gate
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal org.jacoco:jacoco-maven-plugin:0.8.7:report", log="Unsupported class file major version 65")
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        rt_items = [i for i in wl["items"] if i["source"] == "runtime"]
        if len(rt_items) != 1 or rt_items[0]["gate"] != "package" or rt_items[0]["obligation"] != "build-configuration" or rt_items[0]["path"] != "pom.xml":
            return _fail("a packaging failure must be one build obligation carrying its gate: %s" % rt_items)
        cl = [c for c in wl["clusters"] if c["status"] == "open"][0]
        if cl.get("gate") != "package":
            return _fail("the cluster must carry the gate it repairs: %s" % cl)
        # a failure that NAMES a type in this tree lands on that type, not on
        # pom.xml (measured live: SpringDataJPAProcessor named VetRepository)
        named = sorted(root.glob("src/main/java/**/*.java"))[0].relative_to(root).as_posix()
        fqn = named[len("src/main/java/"):-len(".java")].replace("/", ".")
        specimens.runtime(root, package_rc=1, boot_ready=None,
                          detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: No implementation of interface %s was found" % fqn)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        named_items = [i for i in load_json(root / WORKLIST)["items"] if i["source"] == "runtime"]
        if len(named_items) != 1 or named_items[0]["path"] != named or named_items[0]["kind"] != "compile":
            return _fail("an augmentation failure must land on the type it names: %s (wanted %s)" % (named_items, named))
        # back to the plugin failure for the acceptance case below
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal org.jacoco:jacoco-maven-plugin:0.8.7:report", log="Unsupported class file major version 65")
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        cl = [c for c in wl["clusters"] if c["status"] == "open"][0]
        rec_pkg = load_json(root / ADMISSION_RECEIPT)
        if rec_pkg["status"] != "ADMITTED":
            return _fail("a packaging obligation must still admit: %s %s" % (rec_pkg["status"], rec_pkg.get("reasons")))
        issued = specimens.issue(root)
        if issued["logical_id"] != cl["id"]:
            return _fail("the packaging obligation must be the card: %s" % issued["logical_id"])

        # the repair leaves the compile/test tuple untouched. Acceptance is
        # phase-aware: the step is accepted because its own gate now passes.
        pom_p = root / "pom.xml"
        pom_p.write_text(pom_p.read_text(encoding="utf-8").replace("</project>", "  <!-- coverage plugin pinned for the toolchain -->\n</project>"), encoding="utf-8")
        specimens.runtime(root, package_rc=0, boot_ready=None)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl["id"], "t_pkg")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout or "went from failing to passing" not in p.stdout:
            return _fail("a packaging repair with an unchanged measure must be accepted on its gate: %s%s" % (p.stdout, p.stderr))

        # --- two independent packaging defects, one repaired ---
        # The gate holds one obligation per place it fails. Repairing the one
        # this card was issued for is progress even while the gate still fails
        # somewhere else; a rewording at the same place is not.
        srcs = sorted(root.glob("src/main/java/**/*.java"))
        one, two = srcs[0].relative_to(root).as_posix(), srcs[1].relative_to(root).as_posix()
        fqn = lambda rel: rel[len("src/main/java/"):-len(".java")].replace("/", ".")
        two_defects = ("Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: "
                       "No implementation of interface %s was found, and none of %s either" % (fqn(one), fqn(two)))
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build", log=two_defects)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        first = [i for i in wl["items"] if i["source"] == "runtime"]
        if len(first) != 1 or first[0]["path"] != one:
            return _fail("the gate reports the place it is failing now: %s" % first)
        cl2 = [c for c in wl["clusters"] if c["status"] == "open"][0]
        issued2 = specimens.issue(root)
        if issued2["logical_id"] != cl2["id"]:
            return _fail("the packaging obligation must be the card")

        # a) the same failure, reworded, at the same place: NOT progress
        (root / one).write_text((root / one).read_text(encoding="utf-8") + "// touched\n", encoding="utf-8")
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step SpringDataJPAProcessor#build threw an exception: could not satisfy %s (rephrased)" % fqn(one))
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl2["id"], "t_pkg2")
        if p.returncode == 0 or "still open" not in (p.stdout + p.stderr):
            return _fail("a reworded failure at the same place must not count as progress: %s%s" % (p.stdout, p.stderr))

        # the rejection restored the accepted tree AND its receipts; the next
        # verification measures that tree again and re-derives the same
        # obligation, which is what the loop really does after a revert
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build", log=two_defects)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        # b) that place repaired, another still failing: progress
        specimens.issue(root)
        (root / one).write_text((root / one).read_text(encoding="utf-8") + "// repaired\n", encoding="utf-8")
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step SpringDataJPAProcessor#build threw an exception: No implementation of interface %s was found" % fqn(two))
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl2["id"], "t_pkg3")
        if p.returncode != 0 or "is gone and the gate holds no more than before" not in p.stdout:
            return _fail("repairing this card's obligation while the gate still fails elsewhere must be accepted: %s%s" % (p.stdout, p.stderr))

        # settle: the gate passes again for the rest of the walk
        specimens.runtime(root, package_rc=0, boot_ready=None)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)

        # startup still unknown: the closing card stays unminted
        try:
            specimens.issue(root)
            return _fail("M4 must not mint while startup is unknown")
        except RuntimeError:
            pass
        # an environment blocker is not a repair card
        specimens.runtime(root, package_rc=0, boot_ready=False, blocker="environment: Connection refused", detail="database unreachable")
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        if [i for i in wl["items"] if i["source"] == "runtime"]:
            return _fail("an environment blocker must not become a repair obligation: %s" % wl["items"])
        if not any("blocked by the environment" in r for r in wl["measure"]["blocked"]):
            return _fail("an environment blocker must be recorded as blocked: %s" % wl["measure"])
        # both gates passing on the SAME artifact: now M4 mints
        specimens.runtime(root, package_rc=0, boot_ready=True)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        if not wl["runtime"]["ready"]:
            return _fail("packaging + startup on one artifact must be ready: %s" % wl["runtime"])
        m4 = specimens.issue(root)
        if m4["logical_id"] != "M4_VERIFY" or m4["title"] != "M4 VERIFY":
            return _fail("an empty list with both gates passing must mint M4 VERIFY: %s" % m4["logical_id"])

        # --- review counterexample 4: an unresolved failing test never yields a test write set ---
        specimens.verify(root, errors=[], failures=[("x.NoSuchTest", "t")], findings=f4)
        wl = load_json(root / WORKLIST)
        bad = [c for c in wl["clusters"] if any(w.startswith("src/test/") for w in c["write_set"])]
        if bad:
            return _fail("tests are never in a write set: %s" % bad)
        if not wl["blocked_clusters"]:
            return _fail("an unresolvable test failure must be a typed blocker")
        rec = pipeline.admit(root)
        if not any(b["class"] == "SCOPE_UNDERIVED" for b in rec["blocks"]):
            return _fail("blocked cluster must block admission: %s" % rec["reasons"][:3])
        # a resolvable failing test scopes its production twin
        specimens.verify(root, errors=[], failures=[("org.acme.clinic.owner.OwnerControllerTest", "t")], findings=f4)
        wl = load_json(root / WORKLIST)
        tc = next(c for c in wl["clusters"] if c["kind"] == "test")
        if tc["write_set"] != ["src/main/java/%s/owner/OwnerController.java" % base]:
            return _fail("failing test must scope its production twin: %s" % tc["write_set"])
        # rescan that did not run after the baseline → incidents unknown
        st = specimens.write_verified_state(root, errors=[], failures=[], findings=None)
        _run([sys.executable, str(VERIFY), "--root", str(root)] + st["args"])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or "rescan did not run" not in " ".join(wl["measure"]["blocked"]):
            return _fail("a skipped rescan must make incidents unknown: %s" % wl["measure"])
        # tampered work list → advance refuses
        specimens.verify(root, errors=[], failures=[], findings=f4)
        doc = load_json(root / WORKLIST)
        doc["head"] = "c:tampered"
        write_canonical(root / WORKLIST, doc)
        p = _advance(root, "c:tampered", "t_z")
        if p.returncode != 2 or "LOOP_STALE_STATE" not in p.stderr:
            return _fail("tampered work list must refuse advance: %s" % p.stderr)
    print("OK: fix-until-green (measurement contract: unrun tests / empty reports / failed runner / skipped rescan are unknown; baseline; issued card; post-verify edit + unissued cluster refused with baseline intact; out-of-scope test edit rejected + reverted + reports discarded; accept commits; staged no-progress reverted from index; line shift is not a new obligation; unresolvable candidate is unknown; deferral stops the loop; Operator rewind restores tree+budget in a new epoch; green → packaging → startup → M4 (unknown gates never mint; an environment blocker is not a card; a gate repair is accepted phase-aware); unresolved test = typed blocker; tampered list refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
