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
from planner.dest_model import DestModelUnavailable, checked_exception_delta, condition_key, dest_model, fields_of, profile_conditions, source_write_members, tree_model  # noqa: E402
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
    "org/springframework/beans/factory/annotation/Value.java":
        "package org.springframework.beans.factory.annotation;\nimport java.lang.annotation.*;\n"
        "@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.FIELD, ElementType.PARAMETER})\n"
        "public @interface Value { String value(); }\n",
    "org/eclipse/microprofile/config/inject/ConfigProperty.java":
        "package org.eclipse.microprofile.config.inject;\nimport java.lang.annotation.*;\n"
        "@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.FIELD, ElementType.PARAMETER})\n"
        "public @interface ConfigProperty { String name() default \"\"; String defaultValue() default \"\"; }\n",
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


_HOLDER = """package p;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.springframework.beans.factory.annotation.Value;
public class Holder {
    static final String KEY = "a.b";
    final String INSTANCE = "i";
    final String COMPUTED = compute();
    String mutable = "m";
    @Value("${a.b:x}") String placeholder;
    @Value("") String emptied;
    @Value(KEY) String nonLiteral;
    @ConfigProperty(name = "a.b", defaultValue = "d") String mp;
    String plain;
    private String compute() { return "x"; }
}
"""


def _fields_case() -> int:
    """A field's annotation is a fact about the tree AS IT IS NOW.

    Destination v9 (2026-09-14): a worker replaced
    @Value("#{servletContext.contextPath}") with @Value(""), the platform
    printed an EMPTY config property name, and the only model that carried the
    annotation was M1's of the frozen source -- which still had the SpEL. The
    empty string is a string literal and must be recorded as one."""
    with tempfile.TemporaryDirectory(prefix="dm-fields-") as d:
        root = Path(d)
        _tree(root, {"p/Holder.java": _HOLDER})
        rows = {r["field"]: r for r in fields_of(dest_model(root))}
        if set(rows) != {"KEY", "INSTANCE", "COMPUTED", "mutable", "placeholder", "emptied", "nonLiteral", "mp", "plain"}:
            return _fail("every field is a declaration the model must carry: %s" % sorted(rows))
        # what a field's initializer STATES, for the same reason: a constants
        # type spells the role names once and every authorization expression
        # carries only the reference (@roles.VET_ADMIN). A static final's
        # folded value and a final instance field's literal are constants;
        # a call, a mutable field and an uninitialized one are not.
        constants = {name: row["constant"] for name, row in sorted(rows.items())}
        if constants != {"KEY": "a.b", "INSTANCE": "i", "COMPUTED": "", "mutable": "", "placeholder": "",
                         "emptied": "", "nonLiteral": "", "mp": "", "plain": ""}:
            return _fail("a field's compile-time String initializer is its constant, and nothing else is: %s" % constants)
        # the same question about ANOTHER tree (the frozen input), with no
        # classpath of its own: a literal needs none, and the answer must not
        # be this tree's classpath silently reused
        external = {r["field"]: r["constant"] for r in fields_of(tree_model(root, root, classpath=None))}
        if external.get("KEY") != "a.b" or external.get("INSTANCE") != "i" or external.get("mutable") != "":
            return _fail("an external tree is modelled by the same tool and answers the same: %s" % external)
        if rows["plain"]["annotations"] or rows["plain"]["field_type"] != "String":
            return _fail("an unannotated field carries its written type and no annotations: %s" % rows["plain"])
        if rows["placeholder"]["path"] != "src/main/java/p/Holder.java" or rows["placeholder"]["type"] != "p.Holder":
            return _fail("a field row names its file from the tree root and its declaring type: %s" % rows["placeholder"])

        def ann(name: str) -> dict:
            a = rows[name]["annotations"]
            return a[0] if len(a) == 1 else {}

        spring = "org.springframework.beans.factory.annotation.Value"
        if ann("placeholder").get("fqn") != spring or ann("placeholder").get("values") != ["${a.b:x}"]:
            return _fail("a string-literal argument is recorded as written: %s" % ann("placeholder"))
        if ann("placeholder").get("named") != {"value": ["${a.b:x}"]} or ann("placeholder").get("resolution") != "full":
            return _fail("the literal is recorded under the attribute it was written for: %s" % ann("placeholder"))
        # the empty string is a literal, and the whole v9 defect is that it is
        # NOT the same as an absent argument
        if ann("emptied").get("values") != [""] or ann("emptied").get("named") != {"value": [""]}:
            return _fail("an empty string literal is a value, not an absence: %s" % ann("emptied"))
        if ann("emptied").get("resolution") != "full":
            return _fail("an empty string literal is fully readable: %s" % ann("emptied"))
        # a constant reference is a question this tool does not answer
        if ann("nonLiteral").get("values") != [] or ann("nonLiteral").get("named") != {}:
            return _fail("an argument that is not a string literal is absent, never guessed: %s" % ann("nonLiteral"))
        if ann("nonLiteral").get("resolution") != "inconclusive":
            return _fail("a non-literal argument makes the annotation inconclusive: %s" % ann("nonLiteral"))
        # two attributes are two answers: position cannot say which is the name
        if ann("mp").get("named") != {"name": ["a.b"], "defaultValue": ["d"]}:
            return _fail("each attribute's literals are recorded under its own name: %s" % ann("mp"))
        if ann("mp").get("values") != ["a.b", "d"]:
            return _fail("the flat value list is unchanged for its existing readers: %s" % ann("mp"))
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


def _annotation_shape_case() -> int:
    """B5: the two models' annotation shapes, read at the model boundary."""
    from planner.dest_model import AnnotationShapeError, annotation_literals, annotation_named
    src = {"fqn": "org.eclipse.microprofile.config.inject.ConfigProperty", "values": {"name": "shop.size", "defaultValue": "20"}}
    dst = {"fqn": "org.eclipse.microprofile.config.inject.ConfigProperty", "values": ["shop.size", "20"],
           "named": {"name": ["shop.size"], "defaultValue": ["20"]}}
    if not (sorted(annotation_literals(src)) == sorted(annotation_literals(dst)) == ["20", "shop.size"]):
        return _fail("the source named map and the destination literal list carry the same literals: %s %s"
                     % (annotation_literals(src), annotation_literals(dst)))
    if annotation_named(dst, "name") != ["shop.size"] or annotation_named(src, "defaultValue") != ["20"]:
        return _fail("a named attribute is read from the destination's named map or the source's values map")
    if annotation_named({"values": ["shop.size", "20"]}, "name") is not None:
        return _fail("a flat literal list is never guessed into a named attribute")
    kept = annotation_literals({"values": {"required": True, "size": 3, "tags": ["a", ["b"]], "empty": []}})
    if kept != ["true", "3", "a", "b"]:
        return _fail("booleans, numbers and nested arrays are kept; an empty array adds nothing: %s" % kept)
    if annotation_literals({"fqn": "x.Marker"}) != [] or annotation_literals({"values": []}) != []:
        return _fail("absent and empty values both read as no literal")
    for bad, pointer in (({"values": "shop.size"}, "/values"), ({"values": [{"k": "v"}]}, "/values/0"),
                         ({"values": {"name": {"k": "v"}}}, "/values/name")):
        try:
            annotation_literals(bad)
        except AnnotationShapeError as exc:
            if pointer not in str(exc):
                return _fail("the shape error names its JSON pointer %s: %s" % (pointer, exc))
            continue
        return _fail("an unsupported shape raises instead of being iterated: %s" % bad)
    return 0


# --- the declaration-reference walk (types[].type_refs) ---------------------
#
# rgctl offline evaluation 2026-09-25 (G03G/G03A/G03N): a fully qualified
# `java.util.List<inside.A>` field and an `inside.B[]` array left no trace of
# inside.A / inside.B anywhere the planner looks, so `inside` was minted as an
# isolated package. The walk below is the compiler's own answer: resolved
# declaration names from the declaration mirrors, bounded, with a completeness
# flag that is FALSE whenever any part could not be interpreted.

_DEEP = 40  # past the extractor's depth bound (TYPE_REF_MAX_DEPTH = 32)

_REF_SOURCES = {
    "inside/A.java": "package inside;\npublic class A {}\n",
    "inside/B.java": "package inside;\npublic class B {}\n",
    "inside/Boom.java": "package inside;\npublic class Boom extends Exception {}\n",
    "inside/Outer.java": ("package inside;\npublic class Outer<X> {\n    public class Inner {}\n"
                          "    public static class Nested<Y> {}\n}\n"),
    "other/A.java": "package other;\npublic class A {}\n",
    # one holder per shape, so every assertion is about exactly one mechanism
    "h/GenericField.java": "package h;\npublic class GenericField {\n    java.util.List<inside.A> values;\n}\n",
    "h/ArrayField.java": "package h;\npublic class ArrayField {\n    inside.B[][] grid;\n}\n",
    "h/NestedMap.java": ("package h;\npublic class NestedMap {\n"
                         "    java.util.Map<String, java.util.List<inside.A>> nested;\n}\n"),
    "h/WildExtends.java": "package h;\npublic class WildExtends {\n    java.util.List<? extends inside.A> up;\n}\n",
    "h/WildSuper.java": "package h;\npublic class WildSuper {\n    java.util.List<? super inside.B> down;\n}\n",
    "h/Returns.java": ("package h;\npublic class Returns {\n"
                       "    public java.util.Optional<inside.A> find() { return null; }\n}\n"),
    "h/Params.java": "package h;\npublic class Params {\n    public void put(java.util.Set<inside.B[]> s) { }\n}\n",
    "h/Throws.java": "package h;\npublic class Throws {\n    public void fail() throws inside.Boom { }\n}\n",
    "h/ThrowsVar.java": ("package h;\npublic class ThrowsVar {\n"
                         "    public <X extends inside.Boom> void fail() throws X { }\n}\n"),
    "h/GenericSuper.java": ("package h;\npublic abstract class GenericSuper extends java.util.ArrayList<inside.A>\n"
                            "        implements java.util.function.Supplier<inside.B> {\n}\n"),
    "h/Enclosing.java": "package h;\npublic class Enclosing {\n    inside.Outer<inside.A>.Inner inner;\n}\n",
    "h/StaticNested.java": "package h;\npublic class StaticNested {\n    inside.Outer.Nested<inside.B> nested;\n}\n",
    "h/ClassBound.java": "package h;\npublic class ClassBound<T extends inside.A> {\n}\n",
    "h/MethodBound.java": "package h;\npublic class MethodBound {\n    public <T extends inside.B> void m() { }\n}\n",
    "h/Intersection.java": ("package h;\npublic class Intersection<T extends inside.A & java.io.Serializable\n"
                            "        & Comparable<inside.B>> {\n    T value;\n}\n"),
    "h/Imported.java": ("package h;\nimport inside.A;\nimport inside.B;\nimport java.util.List;\n"
                        "public class Imported {\n    List<A> values;\n    B[] others;\n}\n"),
    # identical simple names, a wildcard import and a variable spelled like a class
    "h/Precise.java": ("package h;\nimport inside.*;\npublic class Precise<A> {\n"
                       "    java.util.List<other.A> theirs;\n    A mine;\n    java.util.List<A> list;\n}\n"),
    # two declarations that each bind their own T; neither may shadow the other
    "h/SameName.java": ("package h;\npublic class SameName {\n"
                        "    public <T extends inside.A> void first(T t) { }\n"
                        "    public <T extends inside.B> void second(T t) { }\n}\n"),
    # one container, two arguments: List<A> must not suppress List<B>
    "h/Repeated.java": ("package h;\npublic class Repeated {\n"
                        "    java.util.List<inside.A> a;\n    java.util.List<inside.B> b;\n}\n"),
    # legal recursive bounds: they END a branch, they are not unknowns
    "h/Rec.java": "package h;\npublic class Rec<T extends Comparable<T>> {\n    T value;\n}\n",
    "h/EnumLike.java": "package h;\npublic class EnumLike<E extends Enum<E>> {\n    E value;\n}\n",
    "h/Mutual.java": ("package h;\npublic class Mutual<P extends java.util.List<Q>, Q extends java.util.List<P>> {\n"
                      "    P p;\n    Q q;\n}\n"),
    "h/Color.java": "package h;\npublic enum Color { RED, GREEN }\n",
    "h/Unrelated.java": "package h;\npublic class Unrelated {\n    int n;\n    String s;\n    void go() { }\n}\n",
    # unknowns: an unresolved argument, a nested error and a missing library
    "h/Unresolved.java": ("package h;\npublic class Unresolved {\n    java.util.List<missing.Gone> gone;\n"
                          "    java.util.List<inside.A> known;\n}\n"),
    "h/NestedError.java": ("package h;\npublic class NestedError {\n"
                           "    java.util.Map<String, java.util.List<Nope>> m;\n    inside.B[] kept;\n}\n"),
    "h/MissingLib.java": ("package h;\npublic interface MissingLib extends "
                          "org.springframework.data.jpa.repository.JpaRepository<inside.A, Integer> {\n}\n"),
    # a declaration past the depth bound: the walk stops and SAYS so
    "h/Deep.java": ("package h;\npublic class Deep {\n    %sinside.A%s deep;\n}\n"
                    % ("java.util.List<" * _DEEP, ">" * _DEEP)),
}


def _run_extractor(root: Path, *extra: str, timeout: int = 60) -> dict:
    """The tool itself, under a hard wall-clock bound: a traversal that does
    not terminate is a TIMEOUT here, never a hung suite."""
    from planner.dest_model import _jdk, _tool_classes
    _javac, java = _jdk()
    work = root / "verification/build/.dest-model-direct"
    classes = _tool_classes(work, _javac)
    out = work / "direct.json"
    proc = subprocess.run([java, "-cp", str(classes), "DestModel", "--source", str(root / "src/main/java"),
                           "--out", str(out), "--release", "21", *extra],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("DestModel exited %s: %s" % (proc.returncode, proc.stderr[-400:]))
    return json.loads(out.read_text(encoding="utf-8"))


def _refs_by_type(model: dict) -> dict[str, dict]:
    return {str(t["fqn"]): t for t in model.get("types") or [] if t.get("fqn")}


def _type_refs_case() -> int:
    """Exact resolved membership for every supported mirror shape, recursive
    bounds that terminate, and unknowns that say so while keeping every
    positive edge they did establish."""
    with tempfile.TemporaryDirectory(prefix="dm-refs-") as d:
        root = Path(d)
        _tree(root, _REF_SOURCES, classpath=False, frozen=False)
        try:
            model = _run_extractor(root)
        except subprocess.TimeoutExpired:
            return _fail("the declaration walk did not terminate within 60s (recursive bounds)")
        except RuntimeError as exc:
            return _fail("the extractor must survive recursive bounds and unknowns: %s" % exc)
        rows = _refs_by_type(model)

        def refs(fqn: str) -> set[str]:
            got = rows[fqn].get("type_refs")
            return set(got) if isinstance(got, list) else set()

        def complete(fqn: str):
            return rows[fqn].get("type_refs_complete")

        want = {
            "h.GenericField": {"java.util.List", "inside.A"},
            "h.ArrayField": {"inside.B"},
            "h.NestedMap": {"java.util.Map", "java.lang.String", "java.util.List", "inside.A"},
            "h.WildExtends": {"java.util.List", "inside.A"},
            "h.WildSuper": {"java.util.List", "inside.B"},
            "h.Returns": {"java.util.Optional", "inside.A"},
            "h.Params": {"java.util.Set", "inside.B"},
            "h.Throws": {"inside.Boom"},
            "h.ThrowsVar": {"inside.Boom"},
            "h.GenericSuper": {"java.util.ArrayList", "inside.A", "java.util.function.Supplier", "inside.B"},
            "h.Enclosing": {"inside.Outer", "inside.Outer.Inner", "inside.A"},
            "h.StaticNested": {"inside.Outer.Nested", "inside.B"},
            "h.ClassBound": {"inside.A"},
            "h.MethodBound": {"inside.B"},
            "h.Intersection": {"inside.A", "java.io.Serializable", "java.lang.Comparable", "inside.B"},
            "h.Imported": {"java.util.List", "inside.A", "inside.B"},
            "h.SameName": {"inside.A", "inside.B"},
            "h.Repeated": {"java.util.List", "inside.A", "inside.B"},
            "h.Rec": {"java.lang.Comparable"},
            "h.EnumLike": {"java.lang.Enum"},
            "h.Mutual": {"java.util.List"},
            "h.Precise": {"java.util.List", "other.A"},
        }
        for fqn, expected in sorted(want.items()):
            if fqn not in rows:
                return _fail("%s has no row" % fqn)
            missing = expected - refs(fqn)
            if missing:
                return _fail("%s must name %s through its declaration mirrors: %s" % (fqn, sorted(missing), sorted(refs(fqn))))
            if complete(fqn) is not True or rows[fqn].get("type_refs_incomplete"):
                return _fail("%s is fully interpretable, so its walk is complete: %s %s"
                             % (fqn, complete(fqn), rows[fqn].get("type_refs_incomplete")))
        # nothing guessed: only resolved declared names, never a variable, a
        # primitive, an array spelling or an unrelated same-named type
        for fqn in want:
            bad = {r for r in refs(fqn) if "<" in r or "[" in r or "." not in r}
            if bad:
                return _fail("%s carries a non-declaration reference %s" % (fqn, sorted(bad)))
        for fqn, absent in (("h.GenericField", "inside.B"), ("h.ArrayField", "inside.A"), ("h.WildExtends", "inside.B"),
                            ("h.WildSuper", "inside.A"), ("h.ClassBound", "inside.B"), ("h.MethodBound", "inside.A"),
                            ("h.Precise", "inside.A"), ("h.Unrelated", "inside.A"), ("h.Unrelated", "inside.B")):
            if absent in refs(fqn):
                return _fail("%s names no %s; a guessed edge is a false dependency: %s" % (fqn, absent, sorted(refs(fqn))))
        if complete("h.Unrelated") is not True:
            return _fail("a type with no declared reference to anything interesting is COMPLETE, not unknown")
        if complete("h.Color") is not True or "java.lang.Enum" not in refs("h.Color"):
            return _fail("an enum's Enum<Color> supertype terminates and is complete: %s" % rows["h.Color"])

        # unknowns: completeness false, the reason and locus recorded, every
        # positive reference already established kept, and no error spelling
        # passed off as a resolved name
        for fqn, locus, kept in (("h.Unresolved", "field:gone", "inside.A"),
                                 ("h.NestedError", "field:m", "inside.B"),
                                 ("h.MissingLib", "implements", "")):
            if complete(fqn) is not False:
                return _fail("%s has an unresolved declared type, so its walk is INCOMPLETE: %s" % (fqn, rows[fqn]))
            reasons = rows[fqn].get("type_refs_incomplete") or []
            if not any(r.get("locus") == locus and str(r.get("reason") or "").startswith("unresolved") for r in reasons):
                return _fail("%s records why and where it is incomplete (%s): %s" % (fqn, locus, reasons))
            if kept and kept not in refs(fqn):
                return _fail("%s keeps the known reference %s despite the unknown: %s" % (fqn, kept, sorted(refs(fqn))))
            if any(("Gone" in r) or ("Nope" in r) or ("springframework" in r) for r in refs(fqn)):
                return _fail("%s must not emit an unresolved spelling as a resolved name: %s" % (fqn, sorted(refs(fqn))))
        # the depth bound: a finite refusal, never an empty complete set
        if complete("h.Deep") is not False or not any(r.get("reason") == "depth-limit" for r in rows["h.Deep"].get("type_refs_incomplete") or []):
            return _fail("a declaration past the depth bound is incomplete by depth-limit: %s" % rows["h.Deep"].get("type_refs_incomplete"))
        if "java.util.List" not in refs("h.Deep") or "inside.A" in refs("h.Deep"):
            return _fail("the depth bound keeps what it reached and claims nothing past it: %s" % sorted(refs("h.Deep")))
        # the node bound, forced: the same refusal, positives kept
        try:
            tight = _refs_by_type(_run_extractor(root, "--type-ref-budget", "3"))
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            return _fail("a forced node budget is a refusal, not a crash: %s" % exc)
        nm = tight["h.NestedMap"]
        if nm.get("type_refs_complete") is not False or not any(r.get("reason") == "node-limit" for r in nm.get("type_refs_incomplete") or []):
            return _fail("an exhausted node budget is explicit incomplete evidence: %s" % nm)
        if not nm.get("type_refs"):
            return _fail("the node budget keeps the references it reached: %s" % nm)
        # inside.A: its Object superclass and its constructor's void, 2 nodes
        if tight["inside.A"].get("type_refs_complete") is not True:
            return _fail("a walk inside the budget stays complete under the same budget: %s" % tight["inside.A"])
        # the existing facts are untouched: field spellings, member refs, supertypes
        gf = rows["h.GenericField"]
        if [f.get("type") for f in gf.get("fields") or []] != ["java.util.List<inside.A>"]:
            return _fail("fields[].type keeps its source spelling for its existing readers: %s" % gf.get("fields"))
        if rows["h.GenericSuper"].get("supertypes") != ["java.util.ArrayList<inside.A>", "java.util.function.Supplier<inside.B>"]:
            return _fail("supertypes keep their generic spelling: %s" % rows["h.GenericSuper"].get("supertypes"))
        if rows["h.Unresolved"].get("resolution") != "partial" or rows["h.GenericField"].get("resolution") != "full":
            return _fail("the compiler's resolution is its own fact, not the walk's: %s / %s"
                         % (rows["h.Unresolved"].get("resolution"), rows["h.GenericField"].get("resolution")))

        # determinism: a second run and a relocated copy give the same answer
        def norm(m: dict) -> list:
            return sorted((str(t.get("fqn")), tuple(t.get("type_refs") or []), t.get("type_refs_complete"),
                           json.dumps(t.get("type_refs_incomplete"), sort_keys=True)) for t in m.get("types") or [])
        again = _run_extractor(root)
        with tempfile.TemporaryDirectory(prefix="dm-refs-moved-") as d2:
            moved = Path(d2) / "elsewhere"
            shutil.copytree(root / "src", moved / "src")
            (moved / ".hermes").mkdir(parents=True)
            shutil.copy2(root / ".hermes/pins.json", moved / ".hermes/pins.json")
            relocated = _run_extractor(moved)
        if norm(again) != norm(model) or norm(relocated) != norm(model):
            return _fail("the walk is deterministic across runs and locations")
    return 0


def _type_refs_cache_case() -> int:
    """A model cached by another extractor is not served after the tool
    changes: the tool's content is part of the cache key and of the compiled
    classes' stamp, so no forced refresh is needed to see the new facts."""
    import planner.dest_model as dm
    with tempfile.TemporaryDirectory(prefix="dm-refs-cache-") as d:
        root = Path(d)
        _tree(root, {"inside/A.java": "package inside;\npublic class A {}\n",
                     "h/GenericField.java": "package h;\npublic class GenericField {\n    java.util.List<inside.A> values;\n}\n"},
              classpath=False, frozen=False)
        real = dm._TOOL
        older = Path(d) / "older" / "DestModel.java"
        older.parent.mkdir()
        older.write_text(real.read_text(encoding="utf-8") + "\n// an older build of the tool\n", encoding="utf-8")
        try:
            dm._TOOL = older
            first = dest_model(root)
            cache_dir = root / "verification/build/.dest-model"
            cached = [p for p in cache_dir.glob("src-main-java-*.json")]
            if len(cached) != 1:
                return _fail("one cached model for one tool: %s" % cached)
            # make the cached entry OLD-SHAPED: what a model from before the
            # walk carried, under that tool's key
            doc = json.loads(cached[0].read_text())
            for t in doc["types"]:
                t.pop("type_refs", None)
                t.pop("type_refs_complete", None)
                t.pop("type_refs_incomplete", None)
            cached[0].write_text(json.dumps(doc))
            if "type_refs_complete" in json.dumps(dest_model(root)):
                return _fail("while the tool is unchanged the cache is what is served (control)")
        finally:
            dm._TOOL = real
        fresh = dest_model(root)
        if fresh.get("sources_digest") == first.get("sources_digest"):
            return _fail("the tool's content is part of the model's identity")
        row = next(t for t in fresh["types"] if t["fqn"] == "h.GenericField")
        if row.get("type_refs_complete") is not True or "inside.A" not in (row.get("type_refs") or []):
            return _fail("the changed tool's facts are served without a forced refresh: %s" % row)
        stamp = root / "verification/build/.dest-model/classes/.tool-sha256"
        if stamp.read_text(encoding="utf-8").strip() != dm._tool_sha():
            return _fail("and the compiled tool is rebuilt for the new source")
    return 0


def main() -> int:
    if _annotation_shape_case():
        return 1
    if not shutil.which("javac"):
        print("SKIP: dest-model selftest needs a JDK on PATH")
        return 0
    if (_conditions_case() or _fields_case() or _assess_case() or _source_root_case()
            or _overload_case() or _checked_case() or _type_refs_case() or _type_refs_cache_case()):
        return 1
    print("OK: dest-model (a fully qualified condition is visible; two identical annotations are two decisions with "
          "their own ranges; an import binds a condition with no classpath while a wildcard import does not, and a non-literal argument is never a profile name; a redeclared inherited findAll "
          "is answered by its supertype; every field carries its annotations, an empty string literal among them, with each literal under the attribute it was written for and a non-literal argument absent, and each field's compile-time String initializer as its constant -- in this tree and in another one modelled with no classpath of its own; a deleted member is not inherited; a member is a signature, so an overload never answers for another and a generic save(T) matches as save(Vet); two source roots are two models in either order; the source write set comes from resolved calls; an unreadable source model or type is inconclusive; unhandled checked exceptions: a transformation's sites are introduced, a partial repair exposes rather than introduces, a moved line is the same site, an added throws is an introduction, an unattributed baseline is proved by its parse tree or left INCONCLUSIVE; the declaration walk names exact resolved types through generic arguments, arrays, wildcards, type-variable and intersection bounds and enclosing owners, terminates on recursive bounds, keeps same-named variables and repeated containers apart, marks unresolved parts and its depth and node bounds INCOMPLETE while keeping every known reference, is deterministic across runs and locations, and a changed tool invalidates the cached model)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
