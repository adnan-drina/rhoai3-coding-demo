#!/usr/bin/env python3
"""dest-model selftest: the three questions regex answered wrongly.

Each case is a counterexample the architect reproduced against the regex
implementations (review of 80b8bf7e, 2026-09-11), with the positive path
beside it: fixing a false positive by refusing everything is not a fix.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.dest_model import DestModelUnavailable, checked_exception_delta, condition_key, dest_model, profile_conditions, source_write_members  # noqa: E402
from planner.worklist import assess_batch_scope  # noqa: E402

STUBS = {
    "org/springframework/context/annotation/Profile.java":
        "package org.springframework.context.annotation;\nimport java.lang.annotation.*;\n"
        "@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.TYPE, ElementType.METHOD})\n"
        "public @interface Profile { String[] value(); }\n",
    "io/quarkus/arc/profile/IfBuildProfile.java":
        "package io.quarkus.arc.profile;\nimport java.lang.annotation.*;\n"
        "@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.TYPE, ElementType.METHOD})\n"
        "public @interface IfBuildProfile { String value(); }\n",
    "org/springframework/data/jpa/repository/JpaRepository.java":
        "package org.springframework.data.jpa.repository;\nimport java.util.List;\n"
        "public interface JpaRepository<T, ID> { List<T> findAll(); T save(T e); void delete(T e); }\n",
    "org/springframework/data/jpa/repository/Query.java":
        "package org.springframework.data.jpa.repository;\nimport java.lang.annotation.*;\n"
        "@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD)\n"
        "public @interface Query { String value(); }\n",
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


# M1's model of the SOURCE: `save` persists, `findById` only reads. The regex
# it replaced attributed one member's call to the member declared above it.
FROZEN = {
    "types": [{"path": "src/main/java/p/JpaVetRepositoryImpl.java", "methods": [
        {"name": "findById", "signature": "findById(int)",
         "calls": [{"name": "find", "owner": "javax.persistence.EntityManager"}]},
        {"name": "save", "signature": "save(p.Vet)",
         "calls": [{"name": "persist", "owner": "javax.persistence.EntityManager"}]},
        {"name": "vetsOfTheMonth", "signature": "vetsOfTheMonth()",
         "calls": [{"name": "getResultList", "owner": "javax.persistence.Query"}]},
    ]}],
}


def _tree(root: Path, files: dict[str, str], *, classpath: bool = True, frozen: bool = True) -> None:
    (root / ".hermes").mkdir(parents=True, exist_ok=True)
    (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}')
    if frozen:
        st = root / "evidence/structure/structure.json"
        st.parent.mkdir(parents=True, exist_ok=True)
        st.write_text(json.dumps(FROZEN))
    for rel, text in files.items():
        p = root / "src/main/java" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    if not classpath:
        return
    stub_src = root / ".stub"
    for rel, text in STUBS.items():
        p = stub_src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    out = root / ".stubcls"
    out.mkdir(exist_ok=True)
    subprocess.run(["javac", "-d", str(out), *[str(p) for p in stub_src.rglob("*.java")]],
                   check=True, capture_output=True)
    cp = root / "verification/build/.work/classpath.txt"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(str(out))


TWO_IDENTICAL = ("package p;\nimport org.springframework.context.annotation.Profile;\n"
                 "public class Config {\n"
                 "    @Profile(\"spring-data-jpa\")\n    Object first() { return new Object(); }\n"
                 "    @Profile(\"spring-data-jpa\")\n    Object second() { return new Object(); }\n"
                 "    @io.quarkus.arc.profile.IfBuildProfile(\"secret\")\n    Object third() { return new Object(); }\n}\n")


def _conditions_case() -> int:
    with tempfile.TemporaryDirectory(prefix="dm-cond-") as d:
        root = Path(d)
        _tree(root, {"p/Config.java": TWO_IDENTICAL})
        rows = profile_conditions(dest_model(root))
        if len(rows) != 3:
            return _fail("three declarations carry a condition, not %d: %s" % (len(rows), rows))
        if not any(r["annotation"] == "IfBuildProfile" and r["profile"] == "secret" for r in rows):
            return _fail("a fully qualified annotation is a condition and must be visible: %s" % rows)
        keys = {condition_key(r) for r in rows}
        if len(keys) != 3:
            return _fail("two identical annotations on two members are two decisions: %s" % keys)
        if any(r["resolution"] != "full" for r in rows):
            return _fail("with the classpath present every condition resolves: %s" % rows)
        if any(r["start"] < 0 or r["end"] <= r["start"] for r in rows):
            return _fail("each condition must carry the range the compiler gave it: %s" % rows)

        # The bootstrap runs before the first build, so there is no classpath
        # then. An import binds a simple name as surely as the compiler does,
        # and a fully qualified use needs no binding at all: both stay
        # retirable. What stays INCONCLUSIVE is a name nothing binds.
        (root / "verification/build/.work/classpath.txt").unlink()
        rows2 = profile_conditions(dest_model(root, refresh=True))
        if len(rows2) != 3:
            return _fail("an unbuildable tree still declares its conditions: %s" % rows2)
        if any(r["resolution"] != "full" for r in rows2):
            return _fail("an import binds the annotation even with no classpath: %s" % rows2)
        if {r["resolved_by"] for r in rows2} != {"import", "compiler"}:
            return _fail("the model must say HOW each condition was resolved: %s" % [r["resolved_by"] for r in rows2])

        unbound = ("package p;\nimport org.springframework.context.annotation.*;\n"
                   "public class Loose {\n    @Profile(\"x\")\n    Object m() { return null; }\n}\n")
        (root / "src/main/java/p/Loose.java").write_text(unbound)
        rows3 = [r for r in profile_conditions(dest_model(root, refresh=True)) if r["path"].endswith("Loose.java")]
        if not rows3 or any(r["resolution"] == "full" for r in rows3):
            return _fail("a wildcard import binds nothing; that condition is inconclusive: %s" % rows3)
        if any(not r["value_known"] for r in rows3):
            return _fail("the profile it names is still readable, so accounting can still see it: %s" % rows3)

        nonliteral = ("package p;\nimport org.springframework.context.annotation.Profile;\n"
                      "public class Const {\n    static final String P = \"y\";\n"
                      "    @Profile(P)\n    Object m() { return null; }\n}\n")
        (root / "src/main/java/p/Const.java").write_text(nonliteral)
        rows4 = [r for r in profile_conditions(dest_model(root, refresh=True)) if r["path"].endswith("Const.java")]
        if not rows4 or any(r["value_known"] for r in rows4):
            return _fail("an argument that is not a string literal is a question, not a profile name: %s" % rows4)
    return 0


def _assess_case() -> int:
    repo = ("package p;\nimport java.util.List;\n"
            "import org.springframework.data.jpa.repository.JpaRepository;\n"
            "import org.springframework.data.jpa.repository.Query;\n"
            "public interface VetRepository extends JpaRepository<Vet, Integer> {\n"
            "    List<Vet> findAll();\n"
            "    List<Vet> findByLastName(String lastName);\n"
            "    @Query(\"SELECT DISTINCT v FROM Vet v\")\n    List<Vet> allVets();\n"
            "    List<Vet> vetsOfTheMonth();\n"
            "}\n")
    with tempfile.TemporaryDirectory(prefix="dm-assess-") as d:
        root = Path(d)
        _tree(root, {"p/Vet.java": "package p;\npublic class Vet {}\n", "p/VetRepository.java": repo})
        rel = "src/main/java/p/VetRepository.java"
        scope = {"repository": rel, "rule": "spring-data-repository-contract/v1", "members": [
            {"member": "findAll", "signature": "findAll()"},
            {"member": "findByLastName", "signature": "findByLastName(java.lang.String)"},
            {"member": "allVets", "signature": "allVets()"},
            {"member": "vetsOfTheMonth", "signature": "vetsOfTheMonth()"},
        ]}
        got = {r["member"]: r["verdict"] for r in assess_batch_scope(root, scope)}
        want = {"findAll": "ok", "findByLastName": "ok", "allVets": "ok", "vetsOfTheMonth": "violates"}
        if got != want:
            return _fail("a redeclared inherited method is answered by the supertype, not underivable: %s" % got)

        # a member that is GONE, from a type that inherits nothing, is not
        # "inherited" -- absence is not evidence
        (root / "src/main/java/p/Bare.java").write_text("package p;\npublic interface Bare {}\n")
        bare = {"repository": "src/main/java/p/Bare.java", "rule": "r",
                "members": [{"member": "customLookup", "signature": "customLookup()"}]}
        rows = assess_batch_scope(root, bare)
        if rows[0]["verdict"] != "violates":
            return _fail("a deleted member on a type that extends nothing is a violation: %s" % rows)

        # a member the SOURCE implemented as a state change, answered with a
        # read, is the defect SI-1 exists to catch -- and findById, which only
        # reads, must not be mistaken for one
        writes, why = source_write_members(root)
        if why or writes != {"save"}:
            return _fail("the write set comes from resolved calls, not from text near a name: %s %s" % (writes, why))

        # and with no model of the source, a member that might have been a
        # write is not quietly passed
        (root / "evidence/structure/structure.json").unlink()
        rows = {r["member"]: r["verdict"] for r in assess_batch_scope(root, scope)}
        if rows.get("allVets") != "inconclusive" or rows.get("findAll") != "ok":
            return _fail("without the source model a query-bearing member is inconclusive, an inherited one still ok: %s" % rows)

        # and when the compiler cannot resolve the type, nothing is claimed
        (root / "verification/build/.work/classpath.txt").unlink()
        rows = assess_batch_scope(root, scope)
        if rows[0]["verdict"] != "inconclusive":
            return _fail("an unresolvable type must be inconclusive, never a pass: %s" % rows)
    return 0


def _source_root_case() -> int:
    """Two roots are two models, in either order."""
    with tempfile.TemporaryDirectory(prefix="dm-root-") as d:
        root = Path(d)
        _tree(root, {"p/Main.java": "package p;\npublic class Main {}\n"})
        (root / "src/test/java/p").mkdir(parents=True, exist_ok=True)
        (root / "src/test/java/p/OnlyTest.java").write_text(
            "package p;\n@io.quarkus.arc.profile.IfBuildProfile(\"secret\")\npublic class OnlyTest {}\n")
        for first, second in (("src/main/java", "src/test/java"), ("src/test/java", "src/main/java")):
            a = dest_model(root, source_root=first)
            b = dest_model(root, source_root=second)
            if a.get("source_root") != first or b.get("source_root") != second:
                return _fail("asking for %s must not return %s: %s / %s" % (second, first, a.get("source_root"), b.get("source_root")))
            names = {str(t.get("fqn")) for t in b.get("types") or []}
            want = {"p.OnlyTest"} if second == "src/test/java" else {"p.Main"}
            if names != want:
                return _fail("the model for %s carries %s, not %s" % (second, names, want))
    return 0


def _overload_case() -> int:
    """A member is a SIGNATURE. A different overload is a different member."""
    repo = ("package p;\nimport java.util.List;\n"
            "import org.springframework.data.jpa.repository.JpaRepository;\n"
            "public interface VetRepository extends JpaRepository<Vet, Integer> {\n"
            "    List<Vet> customLookup(String name);\n}\n")
    with tempfile.TemporaryDirectory(prefix="dm-over-") as d:
        root = Path(d)
        _tree(root, {"p/Vet.java": "package p;\npublic class Vet {}\n", "p/VetRepository.java": repo})
        rel = "src/main/java/p/VetRepository.java"
        scope = {"repository": rel, "rule": "r", "members": [
            {"member": "customLookup", "signature": "customLookup(int)"},
            {"member": "findAll", "signature": "findAll(java.lang.String)"},
            {"member": "save", "signature": "save(p.Vet)"},
        ]}
        got = {r["signature"]: r["verdict"] for r in assess_batch_scope(root, scope)}
        if got.get("customLookup(int)") != "violates":
            return _fail("customLookup(int) is not answered by customLookup(String): %s" % got)
        if got.get("findAll(java.lang.String)") != "violates":
            return _fail("a deleted findAll(String) is not answered by an inherited findAll(): %s" % got)
        # and the generic inherited member IS matched, substituted for this type
        if got.get("save(p.Vet)") != "ok":
            return _fail("save(T) on JpaRepository<Vet,Integer> is save(p.Vet) here and must match: %s" % got)
    return 0


_CTL = """package p;
import java.net.URI;
public class %sCtl {
    static class Headers { void setLocation(URI u) { } }
    static class Builder { URI build(int id) { return URI.create("/api/x/" + id); } }
    void add(int id, Builder b) {
        Headers h = new Headers();
        h.setLocation(%s);
    }
}
"""


def _checked_case() -> int:
    """javac names one unhandled checked exception per compilation; the model
    names every one, without its line, and says which a candidate introduced."""
    def git(root: Path, *a: str) -> str:
        return subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True, text=True).stdout.strip()

    with tempfile.TemporaryDirectory(prefix="dm-checked-") as td:
        root = Path(td)
        paths = []
        for n in ("Owner", "Pet"):
            f = root / "src/main/java/p" / ("%sCtl.java" % n)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(_CTL % (n, "b.build(id)"), encoding="utf-8")
            paths.append(f.relative_to(root).as_posix())
        git(root, "init", "-q")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline")
        base = git(root, "rev-parse", "HEAD")
        for rel in paths:
            f = root / rel
            f.write_text(f.read_text(encoding="utf-8").replace("b.build(id)", 'new URI("/api/x/" + id)'), encoding="utf-8")
        d = checked_exception_delta(root, base, paths)
        if d["state"] != "known" or len(d["introduced"]) != 2 or d["exposed"]:
            return _fail("a transformation that adds two unhandled constructors introduces two sites: %s" % d)
        if {r["consumer"] for r in d["introduced"]} != {"p.OwnerCtl.Headers.setLocation(java.net.URI)", "p.PetCtl.Headers.setLocation(java.net.URI)"}:
            return _fail("each site names the operation its value feeds: %s" % [r["consumer"] for r in d["introduced"]])
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "the transformation")
        t1 = git(root, "rev-parse", "HEAD")
        owner, pet = root / paths[0], root / paths[1]
        owner.write_text(owner.read_text(encoding="utf-8").replace('new URI("/api/x/" + id)', 'URI.create("/api/x/" + id)'), encoding="utf-8")
        d = checked_exception_delta(root, t1, paths)
        if d["introduced"] or [r["path"] for r in d["exposed"]] != [paths[1]] or [r["path"] for r in d["resolved"]] != [paths[0]]:
            return _fail("repairing Owner resolves Owner and EXPOSES Pet, which the candidate did not make: %s" % d)
        keys = {r["key"] for r in d["exposed"]}
        pet.write_text(pet.read_text(encoding="utf-8").replace("    void add(", "\n\n\n    void add("), encoding="utf-8")
        d = checked_exception_delta(root, t1, paths)
        if {r["key"] for r in d["exposed"]} != keys or d["introduced"]:
            return _fail("moving Pet's site three lines does not make it a new site: %s" % d)
        pet.write_text(pet.read_text(encoding="utf-8").replace("void add(int id, Builder b) {", "void add(int id, Builder b) throws java.net.URISyntaxException {"), encoding="utf-8")
        d = checked_exception_delta(root, t1, paths)
        if [r["exceptions"] for r in d["throws_added"]] != [["java.net.URISyntaxException"]]:
            return _fail("declaring what used to be unhandled is an introduction, not a repair: %s" % d)
        # a baseline the compiler could not attribute is still PARSED: a member
        # that made no call named URI cannot have held a URI site
        pet.write_text((_CTL % ("Pet", "b.build(id)")).replace("Builder b)", "Builder b, Missing m)"), encoding="utf-8")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "unresolvable baseline")
        t2 = git(root, "rev-parse", "HEAD")
        pet.write_text(_CTL % ("Pet", 'new URI("/api/x/" + id)'), encoding="utf-8")
        d = checked_exception_delta(root, t2, [paths[1]])
        if len(d["introduced"]) != 1 or "made 0 call(s) named URI" not in str(d["introduced"][0].get("proof")):
            return _fail("an unattributed baseline member with no call named URI proves the site new: %s" % d)
        # a site the baseline COULD decide, in a file it could not fully attribute,
        # is decided where it stands: the same unhandled site, exposed not new
        pet.write_text((_CTL % ("Pet", 'new URI("/api/y/" + id)')).replace("Builder b)", "Builder b, Missing m)"), encoding="utf-8")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "unresolvable baseline with the call")
        t3 = git(root, "rev-parse", "HEAD")
        pet.write_text(_CTL % ("Pet", 'new URI("/api/y/" + id)'), encoding="utf-8")
        d = checked_exception_delta(root, t3, [paths[1]])
        if d["introduced"] or len(d["exposed"]) != 1:
            return _fail("a baseline site decidable in a partially attributed file is the same site: %s" % d)
        # a baseline that could NOT decide the site (its catch type is unresolved)
        # cannot make the candidate's site new or old: INCONCLUSIVE, never a pass
        body = (_CTL % ("Pet", "u")).replace("Headers h = new Headers();",
                                             'Headers h = new Headers(); URI u = null; try { u = new URI("/z"); } catch (MissingException e) { }')
        pet.write_text(body, encoding="utf-8")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "undecidable baseline")
        t4 = git(root, "rev-parse", "HEAD")
        pet.write_text(body.replace("try { u = new URI(\"/z\"); } catch (MissingException e) { }", 'u = new URI("/z");'), encoding="utf-8")
        d = checked_exception_delta(root, t4, [paths[1]])
        if d["introduced"] or d["state"] != "inconclusive" or "baseline could not decide" not in str(d["inconclusive"]):
            return _fail("an undecidable baseline site makes the candidate INCONCLUSIVE: %s" % d)
    return 0


def main() -> int:
    if not shutil.which("javac"):
        print("SKIP: dest-model selftest needs a JDK on PATH")
        return 0
    if _conditions_case() or _assess_case() or _source_root_case() or _overload_case() or _checked_case():
        return 1
    print("OK: dest-model (a fully qualified condition is visible; two identical annotations are two decisions with "
          "their own ranges; an import binds a condition with no classpath while a wildcard import does not, and a non-literal argument is never a profile name; a redeclared inherited findAll "
          "is answered by its supertype; a deleted member is not inherited; a member is a signature, so an overload never answers for another and a generic save(T) matches as save(Vet); two source roots are two models in either order; the source write set comes from resolved calls; an unreadable source model or type is inconclusive; unhandled checked exceptions: a transformation's sites are introduced, a partial repair exposes rather than introduces, a moved line is the same site, an added throws is an introduction, an unattributed baseline is proved by its parse tree or left INCONCLUSIVE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
