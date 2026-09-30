#!/usr/bin/env python3
"""V26-2 runtime qualification of the typed repair executor: semantic checks
on the pinned platform, through the real path (_typed_repair.plan -> the
pinned jar -> complete-diff inspection -> journaled apply), never through a
text edit of the test's own.

  cdi-package     fixtures/fragment-cdi-package, the v16 delegates
                  (@ApplicationScoped only): the executor adds @Typed(<Impl>.class)
                  to both; the structural check (worklist.fragment_cdi_exposure)
                  accepts them, the application packages, and the packaged
                  bytecode wires the consumer to the GENERATED repositories and
                  each generated repository to its delegate (fragment-cdi-package's
                  own bytecode check). Negative: a delegate that calls back through
                  the Spring Data repository extending its fragment is refused
                  (unresolved) and left byte for byte.
  repository-rt   fixtures/repository-effects-runtime with both delegates'
                  CDI exposure removed: the executor restores it, the packaged
                  application boots on PostgreSQL 16 and passes every read and
                  committed-write check (repository-effects-runtime's own
                  exercise). Negative control: the refused routed-back shape,
                  annotated by hand, packages and answers 500 with a
                  StackOverflowError -- the defect the refusal prevents.
  location-root   fixtures/handler-location-package with its handlers in the
                  SOURCE form (UriComponentsBuilder, one unused): the executor
                  translates them; the structural check accepts; the packaged
                  application under /ledger answers POST 201 with the absolute
                  Location .../ledger/api/entries/7 (handler-location-package's own
                  _serve).
  location-null   fixtures/repository-effects-runtime's LabelRestController in
                  the source form buildAndExpand(dto.id): the translated handler
                  answers 201 with Location .../api/labels/ for a body without an
                  id, and the row is read back (location-null-runtime's exercise).

The retired builder API is attributed from spring-web/spring-core 5.3.31 in the
local Maven repository, listed as the fixture's frozen-source classpath (M1's
evidence/build/classpath.txt). Every case prints SKIP with its reason when a
prerequisite is missing (mvn/java/javac, the pinned artifacts offline, the
spring jars, podman and the local PostgreSQL image); a SKIP is never a PASS.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _typed_repair as TR  # noqa: E402
import test_runtime_fixture as rt  # noqa: E402
from planner.worklist import unit_implementation_obligations  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").replace(".", "_"), HERE / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


TT = _load("typed-repair.test.py")
CDIPKG = _load("fragment-cdi-package.test.py")
LOCPKG = _load("handler-location-package.test.py")
EFFECTS = _load("repository-effects-runtime.test.py")
NULLRT = _load("location-null-runtime.test.py")
CATALOG = TT.CATALOG
UCB = TR.UCB
SPRING = Path.home() / ".m2" / "repository" / "org" / "springframework"
SPRING_JARS = [SPRING / "spring-web" / "5.3.31" / "spring-web-5.3.31.jar", SPRING / "spring-core" / "5.3.31" / "spring-core-5.3.31.jar"]


class Fail(Exception):
    pass


def prepare(root: Path, api: bool = False) -> None:
    """The classpath the loop measures (run-verify writes it) and, for the URI cases, M1's frozen classpath."""
    (root / ".hermes").mkdir(exist_ok=True)
    (root / ".hermes" / "pins.json").write_text('{"pins": {"quarkus_platform": {"java_release": 21}}}', encoding="utf-8")
    cp = root / TR.CLASSPATH
    cp.parent.mkdir(parents=True, exist_ok=True)
    p = CDIPKG._mvn(root, "dependency:build-classpath", "-Dmdep.outputFile=%s" % cp)
    if p.returncode != 0:
        raise rt.Skip(CDIPKG._offline_gap(p) or "the classpath could not be resolved offline: %s" % (p.stdout + p.stderr)[-300:])
    if api:
        if not all(j.is_file() for j in SPRING_JARS):
            raise rt.Skip("spring-web/spring-core 5.3.31 are not in the local Maven repository (the source API facts)")
        f = root / TR.FROZEN_CLASSPATH
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(os.pathsep.join(str(j) for j in SPRING_JARS), encoding="utf-8")


def run(root: Path, scope: dict, write_set: list[str], exe: dict) -> list[dict]:
    reqs, skipped = TR.plan(root, scope, write_set, [], CATALOG)
    if skipped or not reqs:
        raise Fail("the plan requests the sealed rows inside the write set: %s %s" % (reqs, skipped))
    return TR.execute(root, "u:qual", reqs, write_set, exe=exe)


def cdi_package(td: Path, exe: dict) -> str:
    root = td / "cdi"
    shutil.copytree(CDIPKG.FIXTURE, root)
    prepare(root)
    pkg = CDIPKG.PKG
    parents = [{"parent": "%s.repository.%s" % (pkg, p), "path": "src/main/java/%s/repository/%s.java"
                % (pkg.replace(".", "/"), p), "members": []} for p in CDIPKG.PARENTS]
    rows = unit_implementation_obligations(parents)
    ws = sorted(r["path"] for r in rows)
    before = {p: (root / p).read_text() for p in ws}
    recs = run(root, {"implementation_obligations": rows}, ws, exe)
    if [r["outcome"] for r in recs] != ["applied", "applied"]:
        raise Fail("both v16 delegates get their exposure: %s" % [(r["outcome"], r["reasons"]) for r in recs])
    for p in ws:
        gone = [ln for ln in before[p].splitlines() if ln not in (root / p).read_text().splitlines()]
        if gone:
            raise Fail("the executor only adds; %s lost %s" % (p, gone))
    after = CDIPKG._structural(root)
    if sorted(v for v, _d in after.values()) != ["ok", "ok"]:
        raise Fail("the structural check accepts the executor's delegates: %s" % after)
    p = CDIPKG._mvn(root, "package", "-DskipTests", "-Dquarkus.profile=prod")
    if p.returncode != 0:
        raise Fail("the repaired fixture packages: %s" % (p.stdout + p.stderr)[-900:])
    if CDIPKG._bytecode_case(root):
        raise Fail("the packaged bytecode wires the generated repositories to the delegates")
    # the v29 shape: refused before any edit
    neg = td / "cdi-recursion"
    shutil.copytree(CDIPKG.FIXTURE, neg)
    prepare(neg)
    impl = ws[0]
    recursing = ("package %s.repository;\n\nimport jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.inject.Inject;\n"
                 "import java.util.Collection;\nimport %s.model.Item;\nimport %s.springdatajpa.SpringDataItemRepository;\n\n"
                 "@ApplicationScoped\npublic class ItemRepositoryImpl implements ItemRepository {\n"
                 "    @Inject\n    SpringDataItemRepository repo;\n\n"
                 "    public Collection<Item> findAll() { return repo.findAll(); }\n"
                 "    public Item findById(int id) { return repo.findById(id); }\n"
                 "    public void save(Item value) { repo.save(value); }\n"
                 "    public int countNamed(String name) { return repo.countNamed(name); }\n}\n") % (pkg, pkg, pkg)
    (neg / impl).write_text(recursing, encoding="utf-8")
    recs = run(neg, {"implementation_obligations": [r for r in rows if r["path"] == impl]}, [impl], exe)
    if recs[0]["outcome"] != "unresolved" or "routed-back recursion" not in " ".join(recs[0]["reasons"]):
        raise Fail("the routed-back delegate is refused: %s" % recs[0])
    if (neg / impl).read_text() != recursing:
        raise Fail("a refused request edits nothing")
    return "applied x2 -> structural ok, packaged, bytecode wiring ok; routed-back delegate unresolved, unchanged"


def _strip_exposure(path: Path) -> None:
    text = path.read_text()
    for line in ("import jakarta.enterprise.context.ApplicationScoped;\n", "import jakarta.enterprise.inject.Typed;\n",
                 "@ApplicationScoped\n"):
        text = text.replace(line, "")
    text = "\n".join(ln for ln in text.split("\n") if not ln.startswith("@Typed("))
    path.write_text(text, encoding="utf-8")


def repository_runtime(td: Path, exe: dict, pg: dict) -> str:
    root = td / "effects"
    shutil.copytree(EFFECTS.FIXTURE, root)
    prepare(root)
    base = "org.acme.depot.repository."
    parents = [{"parent": base + n, "path": EFFECTS.PKG + n + ".java", "members": []} for n in ("CrateRepository", "LabelRepository")]
    rows = unit_implementation_obligations(parents)
    ws = sorted(r["path"] for r in rows)
    for p in ws:
        _strip_exposure(root / p)
    recs = run(root, {"implementation_obligations": rows}, ws, exe)
    if [r["outcome"] for r in recs] != ["applied", "applied"]:
        raise Fail("both delegates get their exposure back: %s" % [(r["outcome"], r["reasons"]) for r in recs])
    ok, out = rt.package(root)
    if not ok:
        raise Fail("the repaired fixture packages: %s" % out[-900:])
    props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
             "quarkus.datasource.password": pg["password"]}
    with rt.boot(root, "/api/crates", props) as url:
        table = EFFECTS.exercise(url)
    bad = {k: d for k, (ok, d) in table.items() if not ok}
    if bad:
        raise Fail("repository access after the executor's exposure: %s" % bad)
    # negative control: the refused routed-back shape, annotated by hand, really recurses
    neg = td / "effects-recursion"
    shutil.copytree(EFFECTS.FIXTURE, neg)
    crate = EFFECTS.PKG + "CrateRepositoryImpl.java"
    (neg / crate).write_text(
        "package org.acme.depot.repository;\n\nimport jakarta.enterprise.context.ApplicationScoped;\n"
        "import jakarta.enterprise.inject.Typed;\nimport jakarta.inject.Inject;\nimport java.util.Collection;\n"
        "import org.acme.depot.model.Crate;\nimport org.acme.depot.springdatajpa.SpringDataCrateRepository;\n\n"
        "@ApplicationScoped\n@Typed(CrateRepositoryImpl.class)\npublic class CrateRepositoryImpl implements CrateRepository {\n"
        "    @Inject\n    SpringDataCrateRepository repo;\n"
        "    public Collection<Crate> findAll() { return repo.findAll(); }\n"
        "    public Crate findById(int id) { return repo.findById(id); }\n"
        "    public void save(Crate crate) { repo.save(crate); }\n"
        "    public void delete(Crate crate) { repo.delete(crate); }\n}\n", encoding="utf-8")
    prepare(neg)
    recs = run(neg, {"implementation_obligations": [r for r in rows if r["path"] == crate]}, [crate], exe)
    if recs[0]["outcome"] != "unresolved":
        raise Fail("the executor refuses the routed-back delegate: %s" % recs[0])
    ok, out = rt.package(neg)
    if not ok:
        raise Fail("the hand-annotated routed-back delegate packages (the defect is at runtime): %s" % out[-600:])
    with rt.boot(neg, "/api/labels/1", props) as url:
        st, _h, _b = rt.http("GET", url + "/api/crates/1000")
    log = (neg / "run.log").read_text(errors="replace")
    if st != 500 or "StackOverflowError" not in log:
        raise Fail("the routed-back shape answers 500 with a StackOverflowError: %s %s" % (st, log[-400:]))
    return ("applied x2 -> packaged, booted, %d read/committed-write checks pass; negative control: routed-back delegate "
            "refused, and by hand it answers 500 StackOverflowError" % len(table))


def _source_form_ledger(path: Path) -> None:
    text = path.read_text()
    text = text.replace("import jakarta.ws.rs.core.Context;\n", "").replace("import jakarta.ws.rs.core.UriInfo;\n", "")
    text = text.replace("import org.springframework.web.bind.annotation.RestController;\n",
                        "import org.springframework.web.bind.annotation.RestController;\nimport org.springframework.web.util.UriComponentsBuilder;\n")
    text = text.replace("@RequestBody Entry entry, @Context UriInfo uriInfo)", "@RequestBody Entry entry, UriComponentsBuilder ucBuilder)")
    text = text.replace('URI location = uriInfo.getBaseUriBuilder().path("/api/entries/{id}").build(entry.id);',
                        'URI location = ucBuilder.path("/api/entries/{id}").buildAndExpand(entry.id).toUri();')
    if "UriInfo" in text.replace("UriBuilder", ""):
        raise Fail("the ledger fixture changed shape; the source form could not be written")
    path.write_text(text, encoding="utf-8")


def location_root(td: Path, exe: dict) -> str:
    root = td / "ledger"
    shutil.copytree(LOCPKG.FIXTURE, root)
    prepare(root, api=True)
    ctrl = LOCPKG.CONTROLLER
    _source_form_ledger(root / ctrl)
    fqn = "org.acme.ledger.rest.EntryRestController"
    sealed = [{"path": ctrl, "type": fqn, "member": m, "parameter": "ucBuilder"} for m in ("addEntry", "touch")]
    scope = {"target_symbols": [{"from": UCB, "handler_parameter": True, "sites": sealed}]}
    recs = run(root, scope, [ctrl], exe)
    if recs[0]["outcome"] != "applied":
        raise Fail("the source-form handlers are translated: %s" % recs[0])
    text = (root / ctrl).read_text()
    if 'uriInfo.getBaseUriBuilder().path("/api/entries/{id}").build(Objects.toString(entry.id, ""))' not in text \
            or text.count("@Context UriInfo uriInfo") != 2 or "UriComponentsBuilder" in text \
            or "archiveLink(UriBuilder.fromPath(\"/archive\"), id)" not in text:
        raise Fail("both handlers take @Context UriInfo, the Location is translated and the helper is untouched: %s" % text)
    verdicts = LOCPKG._structural(root, sealed)
    if set(verdicts.values()) != {"ok"}:
        raise Fail("the structural check accepts the translation: %s" % verdicts)
    p = LOCPKG._mvn(root, "package", "-DskipTests")
    if p.returncode != 0:
        raise Fail("the translated fixture packages: %s" % (p.stdout + p.stderr)[-900:])
    if LOCPKG._serve(root):
        raise Fail("the packaged application answers the source's Location")
    again = run(root, scope, [ctrl], exe)
    if again[0]["outcome"] != "already-in-required-form" or (root / ctrl).read_text() != text:
        raise Fail("a second application changes nothing: %s" % again[0])
    return "applied -> structural ok, packaged, POST 201 Location .../ledger/api/entries/7, unused handler 200; re-run already"


def location_null(td: Path, exe: dict, pg: dict) -> str:
    root = td / "labels"
    shutil.copytree(EFFECTS.FIXTURE, root)
    prepare(root, api=True)
    ctrl = NULLRT.CONTROLLER
    p = root / ctrl
    text = p.read_text()
    text = text.replace("import jakarta.ws.rs.core.Context;\n", "").replace("import jakarta.ws.rs.core.UriInfo;\n", "")
    text = text.replace("import org.springframework.web.bind.annotation.RestController;\n",
                        "import org.springframework.web.bind.annotation.RestController;\nimport org.springframework.web.util.UriComponentsBuilder;\n")
    text = text.replace("@RequestBody LabelDto dto, @Context UriInfo uriInfo)", "@RequestBody LabelDto dto, UriComponentsBuilder ucBuilder)")
    p.write_text(text, encoding="utf-8")
    rt.edit(root, ctrl, "// LOCATION", "// END-LOCATION",
            '        URI location = ucBuilder.path("/api/labels/{id}").buildAndExpand(dto.id).toUri();\n')
    sealed = [{"path": ctrl, "type": "org.acme.depot.rest.LabelRestController", "member": "create", "parameter": "ucBuilder"}]
    recs = run(root, {"target_symbols": [{"from": UCB, "handler_parameter": True, "sites": sealed}]}, [ctrl], exe)
    if recs[0]["outcome"] != "applied":
        raise Fail("the source-form create is translated: %s" % recs[0])
    if 'build(Objects.toString(dto.id, ""))' not in p.read_text():
        raise Fail("the request DTO's id stays the argument, null-tolerantly: %s" % p.read_text())
    ok, out = rt.package(root)
    if not ok:
        raise Fail("the translated fixture packages: %s" % out[-900:])
    props = {"quarkus.datasource.jdbc.url": pg["url"], "quarkus.datasource.username": pg["user"],
             "quarkus.datasource.password": pg["password"]}
    with rt.boot(root, "/api/crates", props) as url:
        got = NULLRT.exercise(url)
    if got["status"] != 201 or got["location"] != url + "/api/labels/" or got["read_back"] != 200:
        raise Fail("the translated handler answers the source's null Location: %s" % got)
    return "applied -> packaged, booted, POST 201 Location .../api/labels/ (null id, source semantics), row read back"


def main() -> int:
    results: dict[str, str] = {}
    try:
        rt.need_tools("mvn", "java", "javac")
        jar, why = TT.built_jar()
        if jar is None:
            raise rt.Skip(why)
        exe = TT.executor_for(jar)
        with tempfile.TemporaryDirectory(prefix="typed-repair-pkg-") as tds:
            td = Path(tds)
            for name, fn in (("cdi-package", cdi_package), ("location-root", location_root)):
                try:
                    results[name] = "PASS: " + fn(td, exe)
                except rt.Skip as exc:
                    results[name] = "SKIP: %s" % exc
            try:
                rt.need_tools("podman")
                with rt.postgres() as pg:
                    for name, fn in (("repository-rt", repository_runtime), ("location-null", location_null)):
                        try:
                            results[name] = "PASS: " + fn(td, exe, pg)
                        except rt.Skip as exc:
                            results[name] = "SKIP: %s" % exc
            except rt.Skip as exc:
                results.setdefault("repository-rt", "SKIP: %s" % exc)
                results.setdefault("location-null", "SKIP: %s" % exc)
    except rt.Skip as exc:
        print("SKIP: typed-repair-package: %s" % exc)
        return 0
    except Fail as exc:
        for k, v in results.items():
            print("%-14s %s" % (k, v))
        print("FAIL: typed-repair-package: %s" % exc, file=sys.stderr)
        return 1
    for k, v in results.items():
        print("%-14s %s" % (k, v))
    print("OK: typed-repair-package (executor %s, pinned=%s; pinned platform %s; %d case(s) passed, %d skipped)"
          % (exe["sha256"][:12], exe["pinned"], rt.pin()["version"], sum(v.startswith("PASS") for v in results.values()),
             sum(v.startswith("SKIP") for v in results.values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
