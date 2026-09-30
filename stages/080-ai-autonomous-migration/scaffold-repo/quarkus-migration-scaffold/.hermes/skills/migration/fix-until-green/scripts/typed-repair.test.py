#!/usr/bin/env python3
"""V26-1/V26-2 selftest of the typed repair path around the executor.

Planning (the issued unit's sealed rows and owned requirements only, never a
path outside the write set), the executor identity pin, complete-diff
inspection (an unexpected path, a moved candidate or an empty diff refuses
and applies nothing), journaled application with interruption recovery (a
partial patch is never left on the tree), the record, and what brief.py shows
(FIRST ACTION, then the unresolved reason and the bounded fallback, or the
next step). The executor is simulated here except in the last case, which runs
the pinned jar -- built from source when absent -- on a disposable tree
(prints SKIP with the reason when Maven or the jar cannot be had).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _typed_repair as TR  # noqa: E402
from planner.worklist import unit_implementation_obligations  # noqa: E402

GOLDEN = HERE.parents[4]
CATALOG = json.loads((GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text(encoding="utf-8"))
MODULE = HERE.parent / "typed-repair"
UCB = "org.springframework.web.util.UriComponentsBuilder"
IMPL = "src/main/java/org/acme/inv/repository/ItemRepositoryImpl.java"
CTRL = "src/main/java/org/acme/inv/rest/ItemController.java"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="typed-repair-"))
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (root / ".hermes" / "planning" / "catalogs").mkdir(parents=True)
    (root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").write_text(json.dumps(CATALOG), encoding="utf-8")
    cp = root / TR.CLASSPATH
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text("/nonexistent/a.jar", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    return root


def scope_with(impl: bool = True, handler: bool = True) -> dict:
    rows = unit_implementation_obligations([{"parent": "org.acme.inv.repository.ItemRepository",
                                            "path": "src/main/java/org/acme/inv/repository/ItemRepository.java",
                                            "members": [{"signature": "findAll()"}]}]) if impl else []
    targets = [{"from": UCB, "to": "jakarta.ws.rs.core.UriInfo", "handler_parameter": True, "action": "...",
                "sites": [{"path": CTRL, "type": "org.acme.inv.rest.ItemController", "member": "add",
                           "parameter": "ucBuilder"}]}] if handler else []
    return {"implementation_obligations": rows, "target_symbols": targets}


def fake(outcome: str, staged: dict[str, str] | None = None, patch: str = "--- a\n+++ b\n@@\n-x\n+y\n",
         reasons: list[str] | None = None, touch_before_return: tuple[Path, str] | None = None):
    """A simulated executor: writes the result record and staged files the real one would."""
    def invoke(_jar: Path, _req: Path, out: Path):
        out.mkdir(parents=True, exist_ok=True)
        changes = []
        for rel, text in (staged or {}).items():
            p = out / "staged" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            changes.append({"path": rel, "diff": patch})
        if staged:
            (out / "patch.diff").write_text(patch, encoding="utf-8")
        (out / "result.json").write_text(json.dumps({"outcome": outcome, "reasons": reasons or [], "changes": changes,
                                                     "matched_symbols": ["x"]}), encoding="utf-8")
        if touch_before_return:
            touch_before_return[0].write_text(touch_before_return[1], encoding="utf-8")
        return subprocess.CompletedProcess([], 0, "", "")
    return invoke


EXE = {"jar": "/fake.jar", "sha256": "0" * 64, "pinned": True, "reason": ""}


class Planning(unittest.TestCase):
    def test_the_sealed_rows_become_requests_inside_the_write_set(self):
        root = tree({IMPL: "class A {}\n", CTRL: "class B {}\n"})
        reqs, skipped = TR.plan(root, scope_with(), [IMPL, CTRL], [], CATALOG)
        self.assertEqual(sorted(r["recipe"] for r in reqs), ["handler-uri-parameter", "spring-data-fragment-impl"])
        cdi = next(r for r in reqs if r["recipe"] == "spring-data-fragment-impl")
        self.assertEqual(cdi["target"]["types"], ["org.acme.inv.repository.ItemRepositoryImpl"])
        self.assertEqual(cdi["target"]["scope"], "jakarta.enterprise.context.ApplicationScoped")
        self.assertEqual(skipped, [])

    def test_a_path_outside_the_write_set_is_never_requested(self):
        root = tree({IMPL: "class A {}\n", CTRL: "class B {}\n"})
        reqs, skipped = TR.plan(root, scope_with(), [CTRL], [], CATALOG)
        self.assertEqual([r["recipe"] for r in reqs], ["handler-uri-parameter"])
        self.assertIn("outside the issued write set", skipped[0]["reason"])

    def test_owned_requirements_supply_sites_and_fragment_rows(self):
        root = tree({IMPL: "class A {}\n", CTRL: "class B {}\n"})
        reqs = [{"id": "req:handler-parameter-binding:x", "status": "applicable", "paths": [CTRL],
                 "subject": "org.acme.inv.rest.ItemController#add(org.acme.inv.Dto,%s)|ucBuilder" % UCB,
                 "recipe": {"id": "handler-uri-parameter"}, "facts": {"parameter_type": UCB}},
                {"id": "req:repository-architecture:y", "status": "applicable", "paths": [IMPL],
                 "recipe": {"id": "spring-data-fragment-impl"},
                 "facts": {"fragment": "org.acme.inv.repository.ItemRepository", "owed_implementation": IMPL,
                           "members": ["findAll()"]}}]
        got, _s = TR.plan(root, {}, [IMPL, CTRL], reqs, CATALOG)
        uri = next(r for r in got if r["recipe"] == "handler-uri-parameter")
        self.assertEqual(uri["target"]["sites"], [{"path": CTRL, "type": "org.acme.inv.rest.ItemController", "member": "add",
                                                   "parameter": "ucBuilder"}])
        cdi = next(r for r in got if r["recipe"] == "spring-data-fragment-impl")
        self.assertEqual(cdi["target"]["path"], IMPL)

    def test_an_agent_bounded_row_is_never_a_typed_request(self):
        cat = json.loads(json.dumps(CATALOG))
        cat["migration_recipes"]["handler-uri-parameter"]["implementation"]["kind"] = "agent-bounded"
        root = tree({IMPL: "class A {}\n", CTRL: "class B {}\n"})
        reqs, _s = TR.plan(root, scope_with(), [IMPL, CTRL], [], cat)
        self.assertEqual([r["recipe"] for r in reqs], ["spring-data-fragment-impl"])


class Identity(unittest.TestCase):
    def test_a_jar_that_is_not_the_pinned_one_is_refused(self):
        root = tree({})
        jar = root / "x.jar"
        jar.write_bytes(b"not the executor")
        os.environ["RHOAI3_TYPED_REPAIR_JAR"] = str(jar)
        try:
            os.environ.pop("RHOAI3_TYPED_REPAIR_UNPINNED", None)
            got = TR.executor(root)
        finally:
            os.environ.pop("RHOAI3_TYPED_REPAIR_JAR", None)
        self.assertFalse(got["pinned"])
        self.assertIn("is not the pinned", got["reason"])

    def test_an_unpinned_executor_yields_unresolved_and_edits_nothing(self):
        root = tree({CTRL: "class B {}\n"})
        req, _s = TR.plan(root, scope_with(impl=False), [CTRL], [], CATALOG)
        rec = TR.execute(root, "c:1", req, [CTRL], exe={"jar": "", "sha256": "", "pinned": False, "reason": "not installed"})
        self.assertEqual(rec[0]["outcome"], "unresolved")
        self.assertEqual((root / CTRL).read_text(), "class B {}\n")


class Inspection(unittest.TestCase):
    def setUp(self):
        self.root = tree({CTRL: "class B {}\n", IMPL: "class A {}\n"})
        self.req, _s = TR.plan(self.root, scope_with(impl=False), [CTRL], [], CATALOG)

    def test_applied_patch_is_written_whole_and_recorded(self):
        rec = TR.execute(self.root, "c:1", self.req, [CTRL], exe=EXE, invoke=fake("applied", {CTRL: "class B2 {}\n"}))[0]
        self.assertEqual(rec["outcome"], "applied")
        self.assertEqual((self.root / CTRL).read_text(), "class B2 {}\n")
        self.assertEqual(rec["changed_files"], [CTRL])
        self.assertNotEqual(rec["candidate"]["before"], rec["candidate"]["after"])
        self.assertFalse(rec["establishes_requirement"])
        latest = TR.latest(self.root, "c:1")
        self.assertEqual(latest[0]["outcome"], "applied")
        self.assertTrue((self.root / TR.RECORD_DIR / "records.jsonl").is_file())

    def test_a_patch_outside_the_grant_applies_nothing(self):
        rec = TR.execute(self.root, "c:1", self.req, [CTRL], exe=EXE,
                         invoke=fake("applied", {CTRL: "class B2 {}\n", IMPL: "class A2 {}\n"}))[0]
        self.assertEqual(rec["outcome"], "failed")
        self.assertIn("outside the issued write set", " ".join(rec["reasons"]))
        self.assertEqual((self.root / CTRL).read_text(), "class B {}\n")
        self.assertEqual((self.root / IMPL).read_text(), "class A {}\n")

    def test_a_candidate_that_moved_underneath_applies_nothing(self):
        rec = TR.execute(self.root, "c:1", self.req, [CTRL], exe=EXE,
                         invoke=fake("applied", {CTRL: "class B2 {}\n"},
                                     touch_before_return=(self.root / CTRL, "class Bx {}\n")))[0]
        self.assertEqual(rec["outcome"], "failed")
        self.assertEqual((self.root / CTRL).read_text(), "class Bx {}\n")

    def test_an_applied_result_without_a_diff_is_refused(self):
        rec = TR.execute(self.root, "c:1", self.req, [CTRL], exe=EXE, invoke=fake("applied", {CTRL: "class B2 {}\n"}, patch=""))[0]
        self.assertEqual(rec["outcome"], "failed")
        self.assertEqual((self.root / CTRL).read_text(), "class B {}\n")

    def test_a_no_op_is_recorded_as_already_and_establishes_nothing(self):
        rec = TR.execute(self.root, "c:1", self.req, [CTRL], exe=EXE, invoke=fake("already-in-required-form"))[0]
        self.assertEqual(rec["outcome"], "already-in-required-form")
        self.assertFalse(rec["establishes_requirement"])
        self.assertEqual(rec["changed_files"], [])

    def test_no_measured_classpath_is_unresolved(self):
        (self.root / TR.CLASSPATH).unlink()
        rec = TR.execute(self.root, "c:1", self.req, [CTRL], exe=EXE, invoke=fake("applied", {CTRL: "x"}))[0]
        self.assertEqual(rec["outcome"], "unresolved")
        self.assertEqual((self.root / CTRL).read_text(), "class B {}\n")


class Interruption(unittest.TestCase):
    def test_an_interrupted_application_is_rolled_back_whole(self):
        root = tree({CTRL: "class B {}\n", "src/main/java/org/acme/inv/rest/Other.java": "class O {}\n"})
        other = "src/main/java/org/acme/inv/rest/Other.java"
        scope = scope_with(impl=False)
        scope["target_symbols"][0]["sites"].append({"path": other, "type": "org.acme.inv.rest.Other", "member": "add",
                                                    "parameter": "ucBuilder"})
        req, _s = TR.plan(root, scope, [CTRL, other], [], CATALOG)
        with self.assertRaises(KeyboardInterrupt):
            TR.execute(root, "c:1", req, [CTRL, other], exe=EXE,
                       invoke=fake("applied", {CTRL: "class B2 {}\n", other: "class O2 {}\n"}), crash_after=1)
        # one file of the patch is on the tree: a partial patch
        self.assertEqual(sorted([(root / CTRL).read_text(), (root / other).read_text()]), ["class B2 {}\n", "class O {}\n"])
        got = TR.recover(root)
        self.assertTrue(got["recovered"])
        self.assertEqual((root / CTRL).read_text(), "class B {}\n")
        self.assertEqual((root / other).read_text(), "class O {}\n")
        self.assertFalse((root / TR.JOURNAL).exists())
        self.assertIsNone(TR.recover(root))


class Brief(unittest.TestCase):
    def test_first_action_then_unresolved_fallback_then_next(self):
        root = tree({CTRL: "class B {}\n"})
        req, sk = TR.plan(root, scope_with(impl=False), [CTRL], [], CATALOG)
        sec = TR.brief_section(root, "c:1", req, sk, CATALOG)
        self.assertEqual(sec["first_action"], TR.COMMAND % "c:1")
        self.assertTrue(TR.digest_lines(sec)[0].startswith("FIRST ACTION (typed repair, handler-uri-parameter)"))
        TR.execute(root, "c:1", req, [CTRL], exe=EXE, invoke=fake("unresolved", reasons=["unsupported builder use"]))
        sec = TR.brief_section(root, "c:1", req, sk, CATALOG)
        self.assertNotIn("first_action", sec)
        lines = TR.digest_lines(sec)
        self.assertIn("TYPED REPAIR UNRESOLVED (handler-uri-parameter", lines[0])
        self.assertIn("unsupported builder use", lines[0])
        self.assertIn("uriInfo.getBaseUriBuilder()", lines[1])      # the bounded agent procedure's shape
        # the agent edits the file: the record no longer describes it, and the executor may run again
        (root / CTRL).write_text("class B3 {}\n", encoding="utf-8")
        self.assertIn("first_action", TR.brief_section(root, "c:1", req, sk, CATALOG))
        TR.execute(root, "c:1", req, [CTRL], exe=EXE, invoke=fake("applied", {CTRL: "class B4 {}\n"}))
        lines = TR.digest_lines(TR.brief_section(root, "c:1", req, sk, CATALOG))
        self.assertIn("run run-verify.sh --mode acceptance, then advance.py", lines[0])


class RealExecutor(unittest.TestCase):
    """The pinned jar on a disposable tree: the scan -> generate -> edit path through execute()."""

    def test_the_real_executor_translates_and_a_second_run_changes_nothing(self):
        jar, why = built_jar()
        if jar is None:
            self.skipTest(why)
        stubs = tree({})
        cp_dir = stubs / "cp"
        api_dir = stubs / "api"
        compile_stubs(cp_dir, {
            "jakarta/ws/rs/core/Context.java": "package jakarta.ws.rs.core; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface Context {}",
            "jakarta/ws/rs/core/UriBuilder.java": "package jakarta.ws.rs.core; public interface UriBuilder { UriBuilder path(String p); java.net.URI build(Object... v); }",
            "jakarta/ws/rs/core/UriInfo.java": "package jakarta.ws.rs.core; public interface UriInfo { UriBuilder getBaseUriBuilder(); }"})
        compile_stubs(api_dir, {
            "org/springframework/web/util/UriComponents.java": "package org.springframework.web.util; public abstract class UriComponents { public abstract java.net.URI toUri(); }",
            "org/springframework/web/util/UriComponentsBuilder.java": "package org.springframework.web.util; public class UriComponentsBuilder { public UriComponentsBuilder path(String p) { return this; } public UriComponents buildAndExpand(Object... v) { return null; } }"})
        apijar = stubs / "spring-web-api.jar"
        subprocess.run(["jar", "cf", str(apijar), "-C", str(api_dir), "."], check=True)
        src = ("package org.acme.inv.rest;\n\nimport java.net.URI;\nimport org.springframework.web.util.UriComponentsBuilder;\n\n"
               "public class ItemController {\n    public URI add(Dto dto, UriComponentsBuilder ucBuilder) {\n"
               "        return ucBuilder.path(\"/api/items/{id}\").buildAndExpand(dto.id).toUri();\n    }\n}\n")
        root = tree({CTRL: src, "src/main/java/org/acme/inv/rest/Dto.java": "package org.acme.inv.rest; public class Dto { public Integer id; }\n"})
        (root / TR.CLASSPATH).write_text(str(cp_dir), encoding="utf-8")
        (root / TR.FROZEN_CLASSPATH).parent.mkdir(parents=True, exist_ok=True)
        (root / TR.FROZEN_CLASSPATH).write_text(str(apijar), encoding="utf-8")
        req, _s = TR.plan(root, scope_with(impl=False), [CTRL], [], CATALOG)
        exe = executor_for(jar)
        rec = TR.execute(root, "c:1", req, [CTRL], exe=exe)[0]
        self.assertEqual(rec["outcome"], "applied", rec["reasons"])
        text = (root / CTRL).read_text()
        self.assertIn("@Context UriInfo uriInfo", text)
        self.assertIn('uriInfo.getBaseUriBuilder().path("/api/items/{id}").build(Objects.toString(dto.id, ""))', text)
        self.assertEqual(rec["api_classpath"][0]["provides"], UCB)
        again = TR.execute(root, "c:1", req, [CTRL], exe=exe)[0]
        self.assertEqual(again["outcome"], "already-in-required-form", again["reasons"])
        self.assertEqual((root / CTRL).read_text(), text)


def compile_stubs(out: Path, files: dict[str, str]) -> None:
    src = out.parent / (out.name + "-src")
    paths = []
    for rel, text in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        paths.append(str(p))
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["javac", "-d", str(out), *paths], check=True, capture_output=True)


def built_jar() -> tuple[Path | None, str]:
    """The executor jar: RHOAI3_TYPED_REPAIR_JAR, the image path, or built from the module (offline) into a
    directory OUTSIDE the harness tree (a build under .hermes is release drift: run_control.release_gaps)."""
    for c in ([Path(os.environ["RHOAI3_TYPED_REPAIR_JAR"])] if os.environ.get("RHOAI3_TYPED_REPAIR_JAR") else []) + [TR.IMAGE_JAR]:
        if c.is_file():
            return c, ""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(MODULE.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(MODULE)).encode() + b"\0" + p.read_bytes())
    out = Path(tempfile.gettempdir()) / ("rhoai3-typed-repair-%s" % h.hexdigest()[:16])
    jar = out / "typed-repair-1.0.0.jar"
    if not jar.is_file():
        if not (shutil.which("mvn") and shutil.which("java") and shutil.which("javac")):
            return None, "mvn/java/javac not on PATH, and no executor jar is installed"
        p = subprocess.run(["mvn", "-B", "-q", "-o", "-f", str(MODULE / "pom.xml"), "-Dtyped-repair.build.dir=%s" % out,
                            "package", "-DskipTests"], capture_output=True, text=True, timeout=900)
        if p.returncode != 0 or not jar.is_file():
            return None, "the executor could not be built offline: %s" % (p.stdout + p.stderr)[-300:]
    return jar, ""


def executor_for(jar: Path) -> dict:
    """The jar's identity against the pin; a jar built here with another JDK is run UNPINNED and says so."""
    got = TR._sha(jar)
    want = json.loads((GOLDEN / ".hermes" / "pins.json").read_text())["pins"]["typed_repair"]["executor"]["jar_sha256"]
    if got != want:
        print("NOTE: the executor jar %s is not the pinned build (%s != %s): run unpinned for this test" % (jar, got[:12], want[:12]))
    return {"jar": str(jar), "sha256": got, "pinned": got == want, "reason": ""}


if __name__ == "__main__":
    unittest.main(verbosity=1)
