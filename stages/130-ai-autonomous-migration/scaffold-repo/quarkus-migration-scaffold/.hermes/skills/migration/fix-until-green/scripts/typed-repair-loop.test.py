#!/usr/bin/env python3
"""V26-1 exit: typed-repair candidates judged by the REAL verification path.

A specimen destination (planner.specimens.build_dest, bootstrapped) goes
through the shipped transaction: run-verify.sh --mode acceptance (the real
JdkDiagnostics over the real sources, verify.py, the work-list rebuild and
its unit formation), advance.py --baseline, admission, a K4-issued card,
typed-repair.py (the CLI brief.py prints as the FIRST ACTION) and then
run-verify.sh + advance.py again. Nothing judges a candidate but those two.

  handler   two controllers take UriComponentsBuilder (not on the
            destination classpath): the planner seals ONE diagnostic-family
            unit carrying the handler_parameters row and both handler sites.
            Negative control first: the v16 t_7074fcda bare rename (an
            unannotated jakarta.ws.rs.core.UriBuilder at the handler) compiles,
            removes every sealed diagnostic and is REVERTED by the unit
            checkpoint; the executor itself refuses that form (UNRESOLVED, no
            edit). Then the executor's translation of the source form is
            ACCEPTED and committed.
  cdi       a Spring Data fragment parent with no implementation and the
            platform's set-wide "No implementation of interface" package
            failure: the planner seals the declaration-closure unit owing
            <Parent>Impl with its CDI exposure. Negative controls first: the
            v16 delegate (@ApplicationScoped only) and the v29 routed-back
            delegate (annotated by hand) are REVERTED by the unit checkpoint;
            the executor refuses the routed-back one (UNRESOLVED, no edit).
            Then the v16 delegate with the executor's exposure is ACCEPTED.

Each case runs twice, the second time on a renamed package, renamed types,
renamed handler parameter and path templates (nothing keys on a name).

Stand-ins, named: Maven (`mvn` on PATH writes the measured classpath -- javac
stubs of the destination API -- and runs no tests) and the MTA analyzer (an
`mta-cli` that reports only the canary; the real mta-rescan-destination.sh,
judge-analyzer-exit.py and normalize-findings.py run on it). run-verify.sh
runs with --no-runtime, so the package and boot gates are the receipts the
existing loop tests simulate (planner.specimens.runtime): the cdi baseline's
set-wide failure, and a PASS for every cdi candidate -- negative controls
included, so their refusal is the unit checkpoint's alone. Packaging the
executor's output on the pinned platform is typed-repair-package.test.py.

Needs python3, git, java and javac (SKIP otherwise). The positive candidates
and the executor's own refusals need the executor jar (typed-repair.test.py
built_jar: installed, or built offline with Maven); without it those steps
print SKIP with the reason and the negative controls still run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _typed_repair as TR  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_ISSUED, LOOP_STEPS, WORKLIST  # noqa: E402

UCB = TR.UCB


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").replace(".", "_"), HERE / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


TT = _load("typed-repair.test.py")


class Skip(Exception):
    pass


class Fail(Exception):
    pass


# ------------------------------------------------------------------ the destination API (javac stubs)

_RT = "import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) "
DEST_API = {
    "jakarta/ws/rs/core/Context.java": "package jakarta.ws.rs.core; " + _RT + "public @interface Context {}",
    "jakarta/ws/rs/core/UriBuilder.java": ("package jakarta.ws.rs.core; public abstract class UriBuilder { "
                                           "public abstract UriBuilder path(String p); "
                                           "public abstract java.net.URI build(Object... v); }"),
    "jakarta/ws/rs/core/UriInfo.java": "package jakarta.ws.rs.core; public interface UriInfo { UriBuilder getBaseUriBuilder(); }",
    "org/springframework/web/bind/annotation/RestController.java":
        "package org.springframework.web.bind.annotation; " + _RT + "public @interface RestController {}",
    "org/springframework/web/bind/annotation/PostMapping.java":
        "package org.springframework.web.bind.annotation; " + _RT + "public @interface PostMapping { String[] value() default {}; }",
    "org/springframework/web/bind/annotation/RequestBody.java":
        "package org.springframework.web.bind.annotation; " + _RT + "public @interface RequestBody {}",
    "jakarta/enterprise/context/ApplicationScoped.java": "package jakarta.enterprise.context; " + _RT + "public @interface ApplicationScoped {}",
    "jakarta/enterprise/inject/Typed.java": ("package jakarta.enterprise.inject; " + _RT
                                             + "public @interface Typed { Class<?>[] value() default {}; }"),
    "jakarta/inject/Inject.java": "package jakarta.inject; " + _RT + "public @interface Inject {}",
    "jakarta/persistence/Entity.java": "package jakarta.persistence; " + _RT + "public @interface Entity {}",
    "jakarta/persistence/Id.java": "package jakarta.persistence; " + _RT + "public @interface Id {}",
    "jakarta/persistence/TypedQuery.java": ("package jakarta.persistence; public interface TypedQuery<X> { "
                                            "java.util.List<X> getResultList(); TypedQuery<X> setParameter(String n, Object v); }"),
    "jakarta/persistence/EntityManager.java": ("package jakarta.persistence; public interface EntityManager { "
                                               "<T> TypedQuery<T> createQuery(String q, Class<T> c); "
                                               "<T> T find(Class<T> c, Object id); void persist(Object o); }"),
    "org/springframework/data/repository/Repository.java": "package org.springframework.data.repository; public interface Repository<T, ID> {}",
}
# the retired builder API: the frozen SOURCE's dependency (M1's evidence/build/classpath.txt), never the destination's
SOURCE_API = {
    "org/springframework/web/util/UriComponents.java":
        "package org.springframework.web.util; public abstract class UriComponents { public abstract java.net.URI toUri(); }",
    "org/springframework/web/util/UriComponentsBuilder.java":
        ("package org.springframework.web.util; public class UriComponentsBuilder { "
         "public UriComponentsBuilder path(String p) { return this; } "
         "public UriComponents buildAndExpand(Object... v) { return null; } }"),
}

# the analyzer stand-in: a clean analysis in which only the canary fires (no mandatory incident, before or after)
FAKE_MTA = r'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
a = sys.argv[1:]
if a[:1] != ["analyze"]:
    print("version: 8.2.1"); raise SystemExit(0)
inp, rep = Path(a[a.index("--input") + 1]), Path(a[a.index("--output") + 1])
uri = "file://%s" % (inp / "pom.xml")
rep.mkdir(parents=True, exist_ok=True)
(rep / "output.json").write_text(json.dumps([{"name": "rs", "violations": {}, "insights": {"rhoai3-canary-00001": {
    "category": "optional", "incidents": [{"uri": uri, "lineNumber": 1, "message": "rhoai3 canary fired"}]}},
    "unmatched": [], "skipped": [], "errors": {}}]))
(rep / "output.yaml").write_text("- name: rs\n  violations: {}\n  insights:\n    rhoai3-canary-00001:\n      category: optional\n"
                                 "      incidents:\n      - uri: %s\n        message: rhoai3 canary fired\n        lineNumber: 1\n" % uri)
(rep / "analysis.log").write_text('time="t" level=info msg="finished running analysis" rulesets="[]"\n')
print("Analysis complete!")
'''
# Maven stand-in: the measured classpath is the compiled destination API; `test` runs nothing and reports one
# passing stand-in test (the test slot is the same before and after every candidate)
FAKE_MVN = r'''#!/usr/bin/env python3
import os, sys
from pathlib import Path
for a in sys.argv[1:]:
    if a.startswith("-Dmdep.outputFile="):
        open(a.split("=", 1)[1], "w").write(os.environ["TYPED_LOOP_CLASSPATH"])
if "test" in sys.argv[1:]:
    rep = Path("target") / "surefire-reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "TEST-typedloop.StandIn.xml").write_text(
        '<testsuite name="typedloop.StandIn" tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="typedloop.StandIn" name="standIn"/></testsuite>\n')
'''

# the platform's set-wide augmentation failure (worklist.test.py _SET_WIDE_LOG), naming one parent
SET_WIDE_LOG = ("[ERROR] \t[error]: Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an "
                "exception: java.lang.IllegalArgumentException: No implementation of interface %s was found\n"
                "[ERROR] \tat io.quarkus.spring.data.deployment.generate.FragmentMethodsUtil.getImplementationDotName("
                "FragmentMethodsUtil.java:38)")


def _javac(out: Path, files: dict[str, str]) -> None:
    src = out.parent / (out.name + "-src")
    paths = []
    for rel, text in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        paths.append(str(p))
    out.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["javac", "-d", str(out), *paths], capture_output=True, text=True)
    if p.returncode != 0:
        raise Fail("the API stubs compile: %s" % p.stderr[-400:])


class World:
    """The tools around the destination: API stubs, the Maven and analyzer stand-ins, the environment."""

    def __init__(self, td: Path):
        self.td = td
        self.cp = td / "dest-api"
        _javac(self.cp, DEST_API)
        _javac(td / "source-api", SOURCE_API)
        self.api_jar = td / "spring-web-source-api.jar"
        p = subprocess.run(["jar", "cf", str(self.api_jar), "-C", str(td / "source-api"), "."], capture_output=True, text=True)
        if p.returncode != 0:
            raise Skip("the jar tool could not package the source API stub: %s" % p.stderr[-200:])
        tools, cli, home = td / "tools", td / "mta-cli-home", td / "human-home"
        for d in (tools, cli, home / ".local" / "bin"):
            d.mkdir(parents=True)
        (tools / "mvn").write_text(FAKE_MVN, encoding="utf-8")
        (cli / "mta-cli").write_text(FAKE_MTA, encoding="utf-8")
        (home / ".local" / "bin" / "kantra-assert-exec").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        for f in (tools / "mvn", cli / "mta-cli", home / ".local" / "bin" / "kantra-assert-exec"):
            f.chmod(0o755)
        os.symlink(cli / "mta-cli", tools / "mta-cli")
        # no real Maven or MTA/kantra binary may be found ahead of the stand-ins
        path = [str(tools)] + [d for d in os.environ.get("PATH", "").split(os.pathsep)
                               if d and not any((Path(d) / n).exists() for n in ("mvn", "kantra", "mta-cli"))]
        self.env = dict(os.environ, PATH=os.pathsep.join(path), TYPED_LOOP_CLASSPATH=str(self.cp), HUMAN_HOME=str(home),
                        MTA_CLI_HOME=str(cli), KANTRA_HOME=str(td / "no-kantra"), MTA_RUN_CWD=str(td / "mta-run"),
                        PYTHONDONTWRITEBYTECODE="1")
        for k in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN_ID", "HERMES_KANBAN_STOP_REQUEST", "RHOAI3_TYPED_REPAIR_JAR",
                  "RHOAI3_TYPED_REPAIR_UNPINNED"):
            self.env.pop(k, None)
        for need in ("git", "java", "javac"):
            if not shutil.which(need, path=self.env["PATH"]):
                raise Skip("%s is not on PATH" % need)


class Dest:
    """One destination through the shipped scripts."""

    def __init__(self, world: World, name: str, base: str, files: dict[str, str], *, package_failure: str = ""):
        self.w = world
        decisions = specimens.admitted_decisions(max_attempts=8)
        decisions["loop"] = {"unit_formation": "v1"}   # the golden's decided former (decisions.yaml loop)
        self.root = specimens.build_dest(world.td / name, specimens.specimen("http", base=base), decisions=decisions)
        for rel, text in files.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text, encoding="utf-8")
        frozen = self.root / TR.FROZEN_CLASSPATH
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_text(str(world.api_jar), encoding="utf-8")
        pipeline.assemble_bundle(self.root)
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "scaffold")
        p = self.py(self.root / ".hermes/skills/migration/bootstrap-destination/scripts/bootstrap-destination.py",
                    "--root", str(self.root))
        if p.returncode != 0:
            raise Fail("bootstrap: %s" % (p.stdout + p.stderr)[-600:])
        if package_failure:
            specimens.runtime(self.root, package_rc=1, boot_ready=None,
                              detail="mvn verify exited 1 at quarkus-maven-plugin:build", log=package_failure)
        p = self.verify()
        if p.returncode != 0:
            raise Fail("the baseline verification runs: %s" % (p.stdout + p.stderr)[-900:])
        p = self.py(HERE / "advance.py", "--root", str(self.root), "--baseline", "--no-mint")
        if p.returncode != 0:
            raise Fail("baseline: %s" % (p.stdout + p.stderr)[-600:])
        self.originals = {rel: (self.root / rel).read_text(encoding="utf-8") for rel in files}

    def git(self, *args: str) -> str:
        p = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, env=self.w.env)
        if p.returncode != 0:
            raise Fail("git %s: %s" % (" ".join(args), p.stderr[-300:]))
        return p.stdout

    def py(self, script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                              env=dict(self.w.env, **(env or {})), timeout=900)

    def verify(self) -> subprocess.CompletedProcess:
        """THE verification: run-verify.sh --mode acceptance (runtime gates are stand-in receipts, see the docstring)."""
        return subprocess.run(["bash", str(HERE / "run-verify.sh"), "--root", str(self.root), "--mode", "acceptance",
                               "--no-runtime"], capture_output=True, text=True, env=self.w.env, timeout=900)

    def issue(self, card: str) -> dict:
        """Admission, K4's conversion of the next card, and the task binding k4_mint records."""
        pipeline.admit(self.root)
        payload = specimens.issue(self.root)
        doc = load_json(self.root / LOOP_ISSUED)
        doc["task_id"] = card
        write_canonical(self.root / LOOP_ISSUED, doc)
        wl = load_json(self.root / WORKLIST)
        cluster = next(c for c in wl["clusters"] if c["id"] == doc["cluster"])
        return {"payload": payload, "cluster": cluster, "card": card}

    def typed_repair(self, card: dict, exe_env: dict) -> subprocess.CompletedProcess:
        return self.py(HERE / "typed-repair.py", "--root", str(self.root), "--cluster", card["cluster"]["id"],
                       env=dict(exe_env, HERMES_KANBAN_TASK=card["card"]))

    def advance(self, card: dict) -> subprocess.CompletedProcess:
        return self.py(HERE / "advance.py", "--root", str(self.root), "--cluster", card["cluster"]["id"],
                       "--card", card["card"], "--no-mint")

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).write_text(text, encoding="utf-8")

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")


def _blob(p: subprocess.CompletedProcess) -> str:
    return p.stdout + p.stderr


def _judge(d: Dest, card: dict, want: str) -> str:
    """run-verify.sh then advance.py on the candidate on disk; the verdict must be `want`."""
    v = d.verify()
    if v.returncode != 0:
        raise Fail("run-verify.sh on the candidate: %s" % _blob(v)[-900:])
    a = d.advance(card)
    blob = _blob(a)
    if want == "ACCEPTED" and (a.returncode != 0 or "ACCEPTED" not in blob):
        raise Fail("the candidate is ACCEPTED: rc=%s %s" % (a.returncode, blob[-1200:]))
    if want == "REVERTED" and (a.returncode == 0 or "REVERTED" not in blob):
        raise Fail("the candidate is REVERTED: rc=%s %s" % (a.returncode, blob[-1200:]))
    return blob


# ------------------------------------------------------------------ handler-uri-parameter

def _controller(base: str, typ: str, member: str, dto: str, param: str, template: str, form: str) -> str:
    """One Spring handler that builds its Location. `form`: source | bare (the v16 t_7074fcda rename)."""
    if form == "source":
        imp, ptype, body = ("import org.springframework.web.util.UriComponentsBuilder;\n", "UriComponentsBuilder",
                            '%s.path("%s").buildAndExpand(dto.id).toUri()' % (param, template))
    else:
        imp, ptype, body = ("import jakarta.ws.rs.core.UriBuilder;\n", "UriBuilder", '%s.path("%s").build(dto.id)' % (param, template))
    return ("package %s.rest;\n\nimport java.net.URI;\n%s"
            "import org.springframework.web.bind.annotation.PostMapping;\n"
            "import org.springframework.web.bind.annotation.RequestBody;\n"
            "import org.springframework.web.bind.annotation.RestController;\n\n"
            "@RestController\npublic class %s {\n"
            '    @PostMapping("%s")\n'
            "    public URI %s(@RequestBody %s dto, %s %s) {\n"
            "        return %s;\n    }\n}\n") % (base, imp, typ, template.rsplit("/", 1)[0], member, dto, ptype, param, body)


def handler_case(world: World, exe_env: dict | None, base: str, names: dict[str, str]) -> str:
    pkg = "src/main/java/%s/rest/" % base.replace(".", "/")
    ctrls = []
    files = {}
    for n in ("a", "b"):
        typ, dto, member, template = names["ctl_" + n], names["dto_" + n], names["member_" + n], names["template_" + n]
        rel = pkg + typ + ".java"
        ctrls.append((rel, typ, dto, member, template))
        files[rel] = _controller(base, typ, member, dto, names["param"], template, "source")
        files[pkg + dto + ".java"] = "package %s.rest;\n\npublic class %s {\n    public Integer id;\n}\n" % (base, dto)
    d = Dest(world, "handler-" + names["ctl_a"], base, files)
    sealed = sorted(r for r, *_ in ctrls)
    wl = load_json(d.root / WORKLIST)
    if not wl["clusters"] or any((c.get("batch_scope") or {}).get("kind") != "unit" or sorted(c["write_set"]) != sealed
                                 for c in wl["clusters"]):
        raise Fail("the planner seals the retired builder's diagnostics as units over both controllers: %s"
                   % [(c["id"], c.get("write_set"), (c.get("batch_scope") or {}).get("rule")) for c in wl["clusters"]])
    out = []

    # --- negative control: the bare rename at both handlers ---
    card = d.issue("t_bare")
    scope = load_json(d.root / card["cluster"]["batch_scope"]["path"])
    hp = [t for t in scope.get("target_symbols") or [] if t.get("handler_parameter") and t.get("from") == UCB]
    if not hp or sorted((s["path"], s["member"], s["parameter"]) for s in hp[0]["sites"]) != sorted(
            (r, m, names["param"]) for r, _t, _d, m, _tp in ctrls):
        raise Fail("the issued unit carries the handler_parameters row at both handler sites: %s" % scope.get("target_symbols"))
    for rel, typ, dto, member, template in ctrls:
        d.write(rel, _controller(base, typ, member, dto, names["param"], template, "bare"))
    if exe_env is not None:
        p = d.typed_repair(card, exe_env)
        if "handler-uri-parameter UNRESOLVED" not in p.stdout or "not %s" % UCB not in p.stdout:
            raise Fail("the executor refuses the bare-rename form: %s" % _blob(p)[-700:])
        if any(d.read(rel) != _controller(base, typ, member, dto, names["param"], template, "bare")
               for rel, typ, dto, member, template in ctrls):
            raise Fail("a refused request edits nothing")
        out.append("executor UNRESOLVED on the bare form")
    blob = _judge(d, card, "REVERTED")
    if "without @Context" not in blob or "jakarta.ws.rs.core.UriBuilder" not in blob:
        raise Fail("the bare rename is refused by the unit checkpoint, naming the unannotated parameter: %s" % blob[-900:])
    if any(d.read(rel) != d.originals[rel] for rel, *_ in ctrls):
        raise Fail("the refused candidate is reverted to the accepted tree")
    out.append("bare rename REVERTED (handler takes jakarta.ws.rs.core.UriBuilder without @Context)")

    # --- the typed repair of the source form ---
    if exe_env is None:
        return "; ".join(out) + "; SKIP typed candidate: no executor jar"
    card = d.issue("t_typed")
    p = d.typed_repair(card, exe_env)
    if p.returncode != 0 or "handler-uri-parameter APPLIED" not in p.stdout:
        raise Fail("the executor translates both handlers: %s" % _blob(p)[-900:])
    for rel, _typ, _dto, _member, template in ctrls:
        text = d.read(rel)
        if ("@Context UriInfo uriInfo" not in text or "UriComponentsBuilder" in text
                or 'uriInfo.getBaseUriBuilder().path("%s").build(Objects.toString(dto.id, ""))' % template not in text):
            raise Fail("the translation keeps the template and the argument, null-tolerantly: %s" % text)
    rec = TR.latest(d.root, card["cluster"]["id"])
    if [r["outcome"] for r in rec] != ["applied"] or rec[0]["card"] != "t_typed" or rec[0]["establishes_requirement"]:
        raise Fail("one applied record for the card, which establishes nothing: %s" % rec)
    translated = {rel: d.read(rel) for rel, *_ in ctrls}
    blob = _judge(d, card, "ACCEPTED")
    step = (load_json(d.root / LOOP_STEPS)["steps"] or [{}])[-1]
    if (step.get("unit") or {}).get("unit_id") != scope.get("unit_id"):
        raise Fail("the accepted step records the unit it discharged: %s" % step.get("unit"))
    shown = d.git("show", "--name-only", "--format=", "HEAD").split()
    if sorted(shown) != sealed or any(d.git("show", "HEAD:" + rel) != translated[rel] for rel in sealed):
        raise Fail("exactly the executor's patch is committed: %s" % shown)
    if load_json(d.root / WORKLIST)["measure"]["tuple"] != [0, 0, 0]:
        raise Fail("the accepted tree measures clean: %s" % load_json(d.root / WORKLIST)["measure"])
    out.append("typed translation ACCEPTED and committed (measure [0, 0, 0])")
    return "; ".join(out)


# ------------------------------------------------------------------ spring-data-fragment-impl (CDI exposure)

def _delegate(base: str, n: dict[str, str], form: str) -> str:
    """The owed <Parent>Impl. `form`: v16 (@ApplicationScoped only, bodies through an EntityManager), routed
    (v29: answers through the Spring Data repository that extends the parent, annotated by hand)."""
    ent, parent, sd = n["entity"], n["parent"], n["springdata"]
    if form == "routed":
        return ("package {b}.repository;\n\nimport jakarta.enterprise.context.ApplicationScoped;\n"
                "import jakarta.enterprise.inject.Typed;\nimport jakarta.inject.Inject;\nimport java.util.Collection;\n"
                "import {b}.model.{e};\nimport {b}.springdatajpa.{sd};\n\n"
                "@ApplicationScoped\n@Typed({p}Impl.class)\npublic class {p}Impl implements {p} {{\n"
                "    @Inject\n    {sd} repo;\n\n"
                "    public Collection<{e}> findAll() {{\n        return repo.findAll();\n    }}\n\n"
                "    public {e} findById(int id) {{\n        return repo.findById(id);\n    }}\n\n"
                "    public void save({e} value) {{\n        repo.save(value);\n    }}\n\n"
                "    public int {c}(String name) {{\n        return repo.{c}(name);\n    }}\n}}\n"
                ).format(b=base, e=ent, p=parent, sd=sd, c=n["count"])
    return ("package {b}.repository;\n\nimport jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.inject.Inject;\n"
            "import jakarta.persistence.EntityManager;\nimport java.util.Collection;\nimport {b}.model.{e};\n\n"
            "@ApplicationScoped\npublic class {p}Impl implements {p} {{\n    @Inject\n    EntityManager em;\n\n"
            "    public Collection<{e}> findAll() {{\n        return em.createQuery(\"from {e}\", {e}.class).getResultList();\n    }}\n\n"
            "    public {e} findById(int id) {{\n        return em.find({e}.class, id);\n    }}\n\n"
            "    public void save({e} value) {{\n        em.persist(value);\n    }}\n\n"
            "    public int {c}(String name) {{\n        return em.createQuery(\"from {e} v where v.name = :n\", {e}.class)"
            ".setParameter(\"n\", name).getResultList().size();\n    }}\n}}\n").format(b=base, e=ent, p=parent, c=n["count"])


def cdi_case(world: World, exe_env: dict | None, base: str, n: dict[str, str]) -> str:
    src = "src/main/java/%s/" % base.replace(".", "/")
    ent, parent, sd = n["entity"], n["parent"], n["springdata"]
    files = {
        src + "model/%s.java" % ent: ("package %s.model;\n\nimport jakarta.persistence.Entity;\nimport jakarta.persistence.Id;\n\n"
                                      "@Entity\npublic class %s {\n    @Id\n    public Integer id;\n    public String name;\n}\n"
                                      % (base, ent)),
        src + "repository/%s.java" % parent: ("package {b}.repository;\n\nimport java.util.Collection;\nimport {b}.model.{e};\n\n"
                                              "public interface {p} {{\n    Collection<{e}> findAll();\n\n    {e} findById(int id);\n\n"
                                              "    void save({e} value);\n\n    int {c}(String name);\n}}\n"
                                              ).format(b=base, e=ent, p=parent, c=n["count"]),
        src + "springdatajpa/%s.java" % sd: ("package {b}.springdatajpa;\n\nimport {b}.model.{e};\nimport {b}.repository.{p};\n"
                                             "import org.springframework.data.repository.Repository;\n\n"
                                             "public interface {sd} extends {p}, Repository<{e}, Integer> {{\n}}\n"
                                             ).format(b=base, e=ent, p=parent, sd=sd),
        src + "service/%s.java" % n["consumer"]: ("package {b}.service;\n\nimport jakarta.enterprise.context.ApplicationScoped;\n"
                                                  "import jakarta.inject.Inject;\nimport {b}.repository.{p};\n\n"
                                                  "@ApplicationScoped\npublic class {s} {{\n    @Inject\n    {p} store;\n\n"
                                                  "    public int count(String name) {{\n        return store.{c}(name);\n    }}\n}}\n"
                                                  ).format(b=base, p=parent, s=n["consumer"], c=n["count"]),
    }
    impl = src + "repository/%sImpl.java" % parent
    d = Dest(world, "cdi-" + parent, base, files, package_failure=SET_WIDE_LOG % ("%s.repository.%s" % (base, parent)))
    wl = load_json(d.root / WORKLIST)
    unit = [c for c in wl["clusters"] if (c.get("batch_scope") or {}).get("kind") == "unit"]
    if len(unit) != 1 or impl not in unit[0]["write_set"] or str(unit[0].get("gate") or "") != "package":
        raise Fail("the planner seals ONE package-gate unit owing %s: %s" % (impl, [(c["id"], c.get("write_set"), c.get("gate"))
                                                                                  for c in wl["clusters"]]))
    scope = load_json(d.root / unit[0]["batch_scope"]["path"])
    owed = [r for r in scope.get("implementation_obligations") or [] if r.get("path") == impl]
    if len(owed) != 1 or (owed[0].get("cdi") or {}).get("types") != ["%s.repository.%sImpl" % (base, parent)]:
        raise Fail("the unit owes the delegate its concrete-only CDI exposure: %s" % scope.get("implementation_obligations"))
    out = []

    def candidate(form: str) -> None:
        d.write(impl, _delegate(base, n, form))
        # the package/boot stand-in PASSES for every candidate: what refuses a negative control is the checkpoint
        specimens.runtime(d.root, package_rc=0, boot_ready=True)

    # --- negative control 1: the v16 delegate, no @Typed ---
    card = d.issue("t_v16")
    candidate("v16")
    blob = _judge(d, card, "REVERTED")
    if "exposes every interface it implements as a CDI bean type" not in blob:
        raise Fail("the v16 delegate is refused for its CDI exposure: %s" % blob[-900:])
    if (d.root / impl).exists():
        raise Fail("the refused delegate is not left on the tree")
    out.append("v16 delegate (no @Typed) REVERTED")

    # --- negative control 2: the v29 routed-back delegate, exposure by hand ---
    card = d.issue("t_routed")
    candidate("routed")
    if exe_env is not None:
        routed = d.read(impl)
        p = d.typed_repair(card, exe_env)
        if "spring-data-fragment-impl UNRESOLVED" not in p.stdout or "routed-back recursion" not in p.stdout:
            raise Fail("the executor refuses the routed-back delegate: %s" % _blob(p)[-700:])
        if d.read(impl) != routed:
            raise Fail("a refused request edits nothing")
        out.append("executor UNRESOLVED on the routed-back delegate")
    blob = _judge(d, card, "REVERTED")
    if "StackOverflowError" not in blob or "routes every %s method to %sImpl" % (parent, parent) not in blob:
        raise Fail("the routed-back delegate is refused for the recursion: %s" % blob[-900:])
    out.append("routed-back delegate REVERTED")

    # --- the v16 delegate with the executor's exposure ---
    if exe_env is None:
        return "; ".join(out) + "; SKIP typed candidate: no executor jar"
    card = d.issue("t_typed")
    candidate("v16")
    before = d.read(impl)
    p = d.typed_repair(card, exe_env)
    if p.returncode != 0 or "spring-data-fragment-impl APPLIED" not in p.stdout:
        raise Fail("the executor adds the exposure: %s" % _blob(p)[-900:])
    after = d.read(impl)
    gone = [ln for ln in before.splitlines() if ln not in after.splitlines()]
    if gone or "@Typed(%sImpl.class)" % parent not in after:
        raise Fail("the executor only adds @Typed(<Impl>.class) (lost %s): %s" % (gone, after))
    _judge(d, card, "ACCEPTED")
    if d.git("show", "HEAD:" + impl) != after:
        raise Fail("the delegate with the executor's exposure is committed")
    step = (load_json(d.root / LOOP_STEPS)["steps"] or [{}])[-1]
    wiring = step.get("cdi_wiring") or {}
    # the stand-in package receipt is bound to no candidate: the acceptance claims no wiring, package and boot stay owed
    if ((step.get("unit") or {}).get("unit_id") != scope.get("unit_id") or wiring.get("verified") is not False
            or wiring.get("debt") != {"package": "owed", "boot": "owed"}):
        raise Fail("the step records the unit and the CDI wiring as unverified debt: %s %s" % (step.get("unit"), wiring))
    out.append("v16 delegate + typed exposure ACCEPTED and committed (wiring recorded unverified: package/boot owed)")
    return "; ".join(out)


HANDLER_NAMES = (
    ("org.acme.depot", {"ctl_a": "CrateRestController", "dto_a": "CrateDto", "member_a": "addCrate", "template_a": "/api/crates/{id}",
                        "ctl_b": "LabelRestController", "dto_b": "LabelDto", "member_b": "addLabel", "template_b": "/api/labels/{id}",
                        "param": "ucBuilder"}),
    ("com.example.ledger.web", {"ctl_a": "EntryResource", "dto_a": "EntryForm", "member_a": "post", "template_a": "/v2/entries/{key}",
                                "ctl_b": "AccountResource", "dto_b": "AccountForm", "member_b": "open", "template_b": "/v2/accounts/{key}",
                                "param": "builder"}),
)
CDI_NAMES = (
    ("org.acme.inventory", {"entity": "Item", "parent": "ItemRepository", "springdata": "SpringDataItemRepository",
                            "consumer": "StockService", "count": "countNamed"}),
    ("com.example.depot.core", {"entity": "Crate", "parent": "CrateStore", "springdata": "JpaCrateStore",
                                "consumer": "Dispatch", "count": "tally"}),
)


def main() -> int:
    results: dict[str, str] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="typed-repair-loop-") as tds:
            world = World(Path(tds))
            jar, why = TT.built_jar()
            exe_env: dict | None = None
            if jar is not None:
                exe = TT.executor_for(jar)
                exe_env = {"RHOAI3_TYPED_REPAIR_JAR": str(jar)}
                if not exe["pinned"]:
                    exe_env["RHOAI3_TYPED_REPAIR_UNPINNED"] = "1"
            else:
                print("NOTE: no executor jar (%s): the typed candidates SKIP, the negative controls run" % why)
            for base, names in HANDLER_NAMES:
                results["handler %s" % base] = handler_case(world, exe_env, base, names)
            for base, names in CDI_NAMES:
                results["cdi %s" % base] = cdi_case(world, exe_env, base, names)
    except Skip as exc:
        print("SKIP: typed-repair-loop: %s" % exc)
        return 0
    except Fail as exc:
        for k, v in results.items():
            print("%-30s PASS: %s" % (k, v))
        print("FAIL: typed-repair-loop: %s" % exc, file=sys.stderr)
        return 1
    for k, v in results.items():
        print("%-30s PASS: %s" % (k, v))
    skipped = sum("SKIP" in v for v in results.values())
    print("OK: typed-repair-loop (%d case(s)%s; real run-verify.sh + advance.py, Maven/MTA/runtime gates stand-ins)"
          % (len(results), ", %d without the executor" % skipped if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
