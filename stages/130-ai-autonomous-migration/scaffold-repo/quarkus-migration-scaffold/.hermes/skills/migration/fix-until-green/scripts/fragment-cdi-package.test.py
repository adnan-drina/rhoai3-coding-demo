#!/usr/bin/env python3
"""V16-4 package-level fixture: the fragment delegate's CDI exposure, packaged
with the pinned platform BOM.

fixtures/fragment-cdi-package holds two Spring Data repositories whose fragment
parents are implemented by `XRepositoryImpl` delegates, and a consumer that
injects the parents -- the shape v16 t_1118e877 produced. Asked of the real
platform, offline, from the local Maven repository:

  * the ORIGINAL delegates (@ApplicationScoped only) fail augmentation with
    AmbiguousResolutionException for each parent, naming the delegate and the
    generated repository -- and the structural check (worklist.
    fragment_cdi_exposure, from the compiler model) refuses them too;
  * the RESTRICTED delegates (@ApplicationScoped @Typed(XRepositoryImpl.class))
    package; the structural check accepts them; and the packaged bytecode shows
    the consumer's injection points wired to the GENERATED repositories, each
    generated repository wired to its delegate by the concrete class, and every
    fragment method of the generated repository delegating to the delegate's
    method of the same name.

What this does NOT prove: persistence behaviour at runtime. Nothing is started
and no database is reached; the delegation is proven from the generated
bytecode, not by executing a query.

When the local environment cannot package (no mvn or javap on PATH, or the
pinned platform's artifacts are not in the local Maven repository -- the run is
offline on purpose), the case prints SKIP with the precise reason and exits 0.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
FIXTURE = HERE.parent / "fixtures" / "fragment-cdi-package"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner.dest_model import dest_model  # noqa: E402
from planner.worklist import fragment_cdi_exposure, unit_implementation_obligations  # noqa: E402

PKG = "org.acme.inventory"
PARENTS = ("ItemRepository", "SupplierRepository")
CONSUMER = PKG + ".service.StockService"
FRAGMENT_METHODS = ("findAll", "findById", "save", "countNamed")
# the local repository is missing what the build needs: an environment fact,
# not a verdict about the fixture
_OFFLINE = ("Cannot access", "offline mode", "Could not resolve", "could not be resolved",
            "Non-resolvable import POM", "has not been downloaded")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _skip(msg: str) -> int:
    print("SKIP: fragment-cdi-package: %s" % msg)
    return 0


def _pin() -> dict:
    return json.loads((GOLDEN / ".hermes" / "pins.json").read_text(encoding="utf-8"))["pins"]["quarkus_platform"]


def _mvn(root: Path, *goals: str) -> subprocess.CompletedProcess[str]:
    pin = _pin()
    argv = ["mvn", "-B", "-q", "-o", "-s", str(GOLDEN / ".mvn" / "settings.xml"),
            "-Dquarkus.platform.group-id=%s" % pin["group_id"], "-Dquarkus.platform.version=%s" % pin["version"],
            *goals]
    return subprocess.run(argv, cwd=str(root), text=True, capture_output=True, timeout=900)


def _offline_gap(p: subprocess.CompletedProcess[str]) -> str:
    out = p.stdout + p.stderr
    hit = next((n for n in _OFFLINE if n in out), "")
    if not hit:
        return ""
    line = next((ln.strip() for ln in out.splitlines() if hit in ln), hit)
    return "the pinned platform's artifacts are not all in the local Maven repository (%s)" % line[:240]


def _delegate(root: Path, parent: str) -> Path:
    return root / "src/main/java" / PKG.replace(".", "/") / "repository" / ("%sImpl.java" % parent)


def _restrict(root: Path) -> None:
    """The V16-4 repair, and nothing else: the concrete-only bean type beside
    the scope the delegate already has."""
    for parent in PARENTS:
        p = _delegate(root, parent)
        text = p.read_text(encoding="utf-8")
        p.write_text(text.replace("@ApplicationScoped\n", "@ApplicationScoped\n@jakarta.enterprise.inject.Typed(%sImpl.class)\n"
                                  % parent, 1), encoding="utf-8")


def _structural(root: Path) -> dict[str, tuple[str, str]]:
    """The planner's own obligation for each parent, checked against the
    compiler model of the tree: {delegate fqn: (verdict, detail)}."""
    model = dest_model(root)
    by_fqn = {str(t.get("fqn") or ""): t for t in model.get("types") or []}
    parents = [{"parent": "%s.repository.%s" % (PKG, p), "path": "src/main/java/%s/repository/%s.java"
                % (PKG.replace(".", "/"), p), "members": []} for p in PARENTS]
    out = {}
    for row in unit_implementation_obligations(parents):
        typ = by_fqn.get(row["type"])
        out[row["type"]] = fragment_cdi_exposure(typ, row["cdi"]) if typ else ("inconclusive", "no type")
    return out


def _javap(classes: Path, name: str) -> str:
    p = subprocess.run(["javap", "-p", "-c", "-cp", str(classes), name], text=True, capture_output=True)
    return p.stdout if p.returncode == 0 else ""


_LDC = re.compile(r"\bldc(?:_w)?\s+#\d+\s+// String (\S+)")
_LOCAL = re.compile(r"\b([ai])(load|store)(?:_| +)(\d+)\b")
_NEW = re.compile(r"\bnew\s+#\d+\s+// class \"?([\w/$-]+)\"?")
_INIT = re.compile(r"invokespecial\s+#\d+\s+// Method \"?([\w/$-]+)\"?\.\"<init>\"")


def arc_wiring(classes: Path) -> dict[str, list[str]]:
    """bean class -> the bean classes whose suppliers its constructor
    receives, read from ArC's generated components provider: every bean is
    constructed with the Suppliers of the beans resolved for its injection
    points, each fetched from the map under the key the resolved bean was put
    in. The container's resolution, as the build decided it."""
    text = _javap(classes, "io.quarkus.arc.setup.Default_ComponentsProvider")
    local: dict[str, tuple[str, str]] = {}
    key_bean: dict[str, str] = {}
    ctor: dict[str, list[tuple[str, str]]] = {}
    last_ldc, last_load, got, building, loads, built = "", "", "", "", [], ""
    for line in text.splitlines():
        m = _LDC.search(line)
        if m:
            last_ldc = m.group(1)
            continue
        if "InterfaceMethod java/util/Map.get:" in line:
            got = last_ldc
            continue
        if "InterfaceMethod java/util/Map.put:" in line:
            v = local.get(last_load)
            if v and v[0] == "bean":
                key_bean[last_ldc] = v[1]
            continue
        m = _NEW.search(line)
        if m and m.group(1).endswith("_Bean"):
            building, loads = m.group(1).replace("/", "."), []
            continue
        m = _INIT.search(line)
        if m and building and m.group(1).replace("/", ".") == building:
            ctor[building] = [local.get(n, ("", "")) for n in loads]
            built, building = building, ""
            continue
        m = _LOCAL.search(line)
        if m and m.group(1) == "a":
            n = m.group(3)
            if m.group(2) == "load":
                last_load = n
                if building:
                    loads.append(n)
            elif got:
                local[n], got = ("key", got), ""
            elif built:
                local[n], built = ("bean", built), ""
    return {bean: [key_bean.get(v[1], "") for v in args if v[0] == "key"] for bean, args in ctor.items()}


def _bytecode_case(root: Path) -> int:
    gen = root / "target" / "quarkus-app" / "quarkus" / "generated-bytecode.jar"
    if not gen.is_file():
        return _fail("the restricted fixture packaged but %s is absent" % gen)
    classes = root / "target" / "generated-classes-x"
    with zipfile.ZipFile(gen) as z:
        z.extractall(classes)
    wiring = arc_wiring(classes)
    if not wiring:
        return _fail("ArC's components provider could not be read from %s" % gen)
    generated: dict[str, str] = {}
    for parent in PARENTS:
        prefix = "%s.springdatajpa.SpringData%s_" % (PKG, parent)
        impls = sorted(str(p.relative_to(classes))[:-len(".class")].replace("/", ".")
                       for p in classes.rglob("*.class")
                       if str(p.relative_to(classes)).replace("/", ".").startswith(prefix)
                       and p.name.endswith("Impl.class"))
        if len(impls) != 1:
            return _fail("one generated repository for %s: %s" % (parent, impls))
        generated[parent] = impls[0]
        # the generated repository injects the delegate by its CONCRETE class
        # and every fragment method delegates to the method of the same name
        code = _javap(classes, impls[0])
        delegate = "%s.repository.%sImpl" % (PKG, parent)
        if "protected %s " % delegate not in code:
            return _fail("%s holds its delegate as the concrete %s: %s" % (impls[0], delegate, code[:400]))
        slash = delegate.replace(".", "/")
        for m in FRAGMENT_METHODS:
            if "invokevirtual" not in code or "Method %s.%s:" % (slash, m) not in code:
                return _fail("%s.%s delegates to %s.%s" % (impls[0], m, delegate, m))
        # ...and the container wires the delegate BEAN into it
        suppliers = wiring.get(impls[0] + "_Bean") or []
        if delegate + "_Bean" not in suppliers:
            return _fail("the generated repository %s is constructed with the delegate bean's supplier: %s"
                         % (impls[0], suppliers))
    # the consumer's injection points resolve to the GENERATED repositories,
    # never to a delegate
    consumer = wiring.get(CONSUMER + "_Bean") or []
    want = sorted(generated[p] + "_Bean" for p in PARENTS)
    if sorted(s for s in consumer if s) != want:
        return _fail("the consumer's injection points resolve to the generated repositories %s: %s" % (want, consumer))
    return 0


def main() -> int:
    for tool in ("mvn", "javap", "javac"):
        if not shutil.which(tool):
            return _skip("%s is not on PATH, so the platform cannot package the fixture here" % tool)
    if not FIXTURE.is_dir():
        return _fail("the fixture %s is missing" % FIXTURE)
    with tempfile.TemporaryDirectory(prefix="fragment-cdi-pkg-") as td:
        root = Path(td) / "fixture"
        shutil.copytree(FIXTURE, root)
        (root / ".hermes").mkdir()
        (root / ".hermes" / "pins.json").write_text(json.dumps({"pins": {"quarkus_platform": {"java_release": 21}}}),
                                                    encoding="utf-8")
        cp = root / "verification" / "build" / ".work" / "classpath.txt"
        cp.parent.mkdir(parents=True)
        p = _mvn(root, "dependency:build-classpath", "-Dmdep.outputFile=%s" % cp)
        if p.returncode != 0:
            return _skip(_offline_gap(p) or "the classpath could not be resolved offline: %s" % (p.stdout + p.stderr)[-300:])

        # --- the delegates as v16 t_1118e877 wrote them ---
        before = _structural(root)
        if [v for v, _d in before.values()] != ["violates", "violates"]:
            return _fail("the structural check refuses delegates that expose their parent as a bean type: %s" % before)
        p = _mvn(root, "package", "-DskipTests", "-Dquarkus.profile=prod")
        out = p.stdout + p.stderr
        if p.returncode == 0:
            return _fail("the original delegates must NOT package: the parents are ambiguous")
        if "AmbiguousResolutionException" not in out:
            gap = _offline_gap(p)
            return _skip(gap) if gap else _fail("the original delegates fail for another reason: %s" % out[-600:])
        for parent in PARENTS:
            fqn = "%s.repository.%s" % (PKG, parent)
            if "Ambiguous dependencies for type %s" % fqn not in out:
                return _fail("augmentation names the ambiguous parent %s: %s" % (fqn, out[-900:]))
            if "target=%sImpl]" % fqn not in out or "target=%s.springdatajpa.SpringData%s_" % (PKG, parent) not in out:
                return _fail("and names both beans: the delegate and the generated repository (%s)" % parent)

        # --- the V16-4 repair: concrete-only CDI exposure ---
        _restrict(root)
        after = _structural(root)
        if [v for v, _d in after.values()] != ["ok", "ok"]:
            return _fail("the structural check accepts the restricted delegates: %s" % after)
        p = _mvn(root, "package", "-DskipTests", "-Dquarkus.profile=prod")
        if p.returncode != 0:
            return _fail("the restricted delegates package: %s" % (p.stdout + p.stderr)[-900:])
        if _bytecode_case(root):
            return 1
    print("OK: fragment-cdi-package (pinned platform %s, offline: the original XRepositoryImpl delegates fail "
          "augmentation with AmbiguousResolutionException naming both beans and the structural check refuses them; "
          "restricted to @Typed(XRepositoryImpl.class) they package, the structural check accepts them, the consumer's "
          "injection points resolve to the generated repositories, each generated repository receives its delegate bean "
          "and delegates every fragment method to it by the concrete class; bytecode only -- persistence was not "
          "executed)" % _pin()["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
