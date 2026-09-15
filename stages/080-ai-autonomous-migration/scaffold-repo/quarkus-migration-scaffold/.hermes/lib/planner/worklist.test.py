#!/usr/bin/env python3
"""worklist unit selftest: ordering, clustering, measure, progress, conservation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.cards import card_title
from planner.worklist import CHECKED_FAMILY_RULE, EXPOSED, RETAIN, UNPROVEN, apply_supersessions, assess_checked_family, batch_scope_digest, batch_scope_path, build_batch_scope, retry_key, runtime_items  # noqa: E402
from planner.dest_model import dest_model, diagnostic_identity  # noqa: E402
from planner.worklist import APP_PROPERTIES, KIND_RANK, cluster_items, parity_items, runtime_items, compile_items, file_depths, incidents_from_findings, measure_of, obligation_keys, path_class, progress, surefire_from_reports, test_items  # noqa: E402


def surefire_from_reports_ran_flag():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        return surefire_from_reports(Path(d)).get("ran")


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _runtime_identity_case() -> int:
    """Two problems at one file are two obligations; two wordings are one."""
    def ident(detail, log=""):
        pkg = {"ran": True, "rc": 1, "detail": detail, "log_tail": log}
        items = runtime_items(pkg, None, None)
        return items[0]["id"], items[0].get("cause")

    # the same cause reported around different words: one obligation. (The
    # vocabulary is matched on the tool's own marker, so this is what
    # "reworded" can mean without the tool changing its exception class.)
    a, ca = ident("Build step SpringDataJPAProcessor#build threw an exception: No implementation of interface x.Y was found")
    b, cb = ident("[error]: Build step ...#build threw an exception: No implementation of interface x.Y was found (after 2 rounds)")
    if a != b:
        return _fail("the same cause, differently worded, is one obligation: %s vs %s" % (ca, cb))
    c, cc = ident("Build step SpringDataJPAProcessor#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException: Method findAll")
    if c == a:
        return _fail("a different cause at the same place is a different obligation: %s vs %s" % (ca, cc))
    if (ca, cc) != ("missing-implementation", "underivable-query-method"):
        return _fail("the causes come from the closed vocabulary: %s %s" % (ca, cc))
    # a cause that manifests once per METHOD is one obligation per method:
    # fixing save must count even though delete then fails the same way
    m1, _ = ident("Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException: Method 'save' of repository 'x.Y' cannot be parsed")
    m2, _ = ident("Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException: Method 'delete' of repository 'x.Y' cannot be parsed")
    if m1 == m2:
        return _fail("two underivable methods in one repository are two obligations")
    m3, _ = ident("[error] Build step Z#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException: Method 'save' of repository 'x.Y' cannot be parsed (round 2)")
    if m1 != m3:
        return _fail("the same method, reported around different words, is one obligation")
    # a platform that quotes the offending value has named the file, when
    # exactly one source carries that literal
    import tempfile
    with tempfile.TemporaryDirectory(prefix="locus-") as td:
        r = Path(td)
        f = r / "src" / "main" / "java" / "a" / "RootRestController.java"
        f.parent.mkdir(parents=True)
        f.write_text('@Value("#{servletContext.contextPath}")\nString path;\n', encoding="utf-8")
        msg = ("Build step X#build threw an exception: java.lang.IllegalArgumentException: SpEL expressions are not "
               "supported when using org.springframework.beans.factory.annotation.Value. Offending value is "
               "'@Value(\"#{servletContext.contextPath}\")'")
        items = runtime_items({"ran": True, "rc": 1, "detail": "Failed to execute goal x", "log_tail": msg}, None, r)
        if len(items) != 1 or items[0]["path"] != "src/main/java/a/RootRestController.java":
            return _fail("a uniquely quoted literal must locate the file: %s" % [(i.get("path"), i.get("cause")) for i in items])
        if items[0]["cause"] != "unsupported-spel":
            return _fail("and the cause comes from the vocabulary: %s" % items[0]["cause"])
        # two files carrying it is not a location
        g = r / "src" / "main" / "java" / "a" / "Other.java"
        g.write_text('@Value("#{servletContext.contextPath}")\nString also;\n', encoding="utf-8")
        items = runtime_items({"ran": True, "rc": 1, "detail": "Failed to execute goal x", "log_tail": msg}, None, r)
        if not items[0].get("unlocated"):
            return _fail("a literal in two files locates nothing: %s" % items[0].get("path"))

    # a failure that names no file of this tree cannot be a card
    un = runtime_items({"ran": True, "rc": 1, "detail": "Build step P#build threw an exception: java.lang.IllegalStateException: void was not part of the Quarkus index", "log_tail": ""}, None, None)
    if len(un) != 1 or not un[0].get("unlocated") or un[0]["cause"] != "unindexed-type":
        return _fail("an unlocatable augmentation failure is marked and classified: %s" % un)
    d, cd = ident("something no signature predicted")
    e, ce = ident("something else no signature predicted")
    if cd != "unclassified" or d != e:
        return _fail("an unmatched failure is one obligation however it is phrased: %s %s" % (cd, ce))
    return 0


def _gate_progress_case() -> int:
    """Acceptance inside a gate: what counts, and what only looks like it."""
    green = {"known": True, "tuple": [0, 0, 0]}
    worse = {"known": True, "tuple": [0, 1, 0]}
    failing = {"package": {"ran": True, "rc": 1}, "boot": {"ran": False, "rc": None, "ready": False}}
    passing = {"package": {"ran": True, "rc": 0}, "boot": {"ran": False, "rc": None, "ready": False}}
    both = {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 0, "ready": True}}
    boot_broken = {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 1, "ready": False}}
    A, B = "rt:package:aaaa", "rt:package:bbbb"

    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=passing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items=set())
    if not ok:
        return _fail("a gate that starts passing is progress: %s" % why)
    # the obligation is no longer reported, but the gate still fails: this tool
    # reports one failure at a time, so absence is not proof. The candidate is
    # RETAINED -- neither accepted nor thrown away.
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=failing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items={B})
    if ok is not UNPROVEN or "not proof it was repaired" not in why:
        return _fail("an unproven gate repair must be retained, not accepted: %r %s" % (ok, why))
    if ok:
        return _fail("a retained outcome must not read as accepted")
    # the same obligation, reworded: its identity is gate+kind+locus, so it is still there
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=failing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items={A})
    if ok or "still reported" not in why:
        return _fail("a failure that only reads differently is not progress: %s" % why)
    # the gate passing discharges the whole batch the card was issued for
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=failing, cur_runtime=passing,
                       issued_items=[A, B], prev_gate_items={A, B}, cur_gate_items=set())
    if not ok or "discharges" not in why:
        return _fail("a passing gate discharges every obligation on the card: %s" % why)
    # a gate repair may not break the phase before it
    ok, why = progress(green, green, set(), set(), gate="package", prev_runtime=both, cur_runtime=boot_broken,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items=set())
    if ok or "may not break the phase before it" not in why:
        return _fail("breaking startup while repairing packaging is not progress: %s" % why)
    # and it may not make compilation or tests worse
    ok, why = progress(green, worse, set(), set(), gate="package", prev_runtime=failing, cur_runtime=passing,
                       issued_items=[A], prev_gate_items={A}, cur_gate_items=set())
    if ok or "regressed" not in why:
        return _fail("a gate repair may not regress the measure: %s" % why)
    # a card with no gate is judged by the measure alone
    ok, _ = progress(green, green, set(), set())
    if ok:
        return _fail("an ordinary card still needs a strictly smaller measure")
    return 0


def _batch_scope_case() -> int:
    """The SEAL: an inventory is immutable, named by its own digest, and never
    carries the measured failure into the rule it declares.

    What the rule SAYS about each member is asked of the compiler and lives in
    dest_model.test.py; this is about identity."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        rel = "src/main/java/p/VetRepository.java"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("package p;\npublic interface VetRepository { Object first(); }\n")
        cluster = {"id": "c:abc", "items": ["rt:package:1"], "write_set": [rel]}
        items = [{"id": "rt:package:1", "source": "runtime", "gate": "package",
                  "cause": "underivable-query-method", "path": rel}]
        scope = build_batch_scope(root, cluster, items, {"candidate_sha256": "x"})
        if not scope:
            return _fail("a repository cluster must produce a scope inventory")
        if batch_scope_digest(scope) != scope["digest"]:
            return _fail("the seal must be reproducible from content alone")
        if scope["measured"] != ["rt:package:1"]:
            return _fail("the measured failure stays in item_ids; the inventory never becomes one")
        # the path IS the seal: a later inventory for the same cluster cannot
        # land on the file an outstanding card is judged against
        first = batch_scope_path(scope)
        (root / rel).write_text("package p;\npublic interface VetRepository { Object first(); Object second(); }\n")
        scope2 = build_batch_scope(root, cluster, items, {"candidate_sha256": "y"})
        if scope2["digest"] == scope["digest"]:
            return _fail("a different tree is a different inventory")
        if batch_scope_path(scope2) == first:
            return _fail("two inventories of one cluster must not share a path: %s" % first)
        if first.parent != batch_scope_path(scope2).parent:
            return _fail("both still belong to the same cluster's directory")
    return 0


_URI_MSG = "unreported exception java.net.URISyntaxException; must be caught or declared to be thrown"
_URI_CODE = "compiler.err.unreported.exception.need.to.catch.or.throw"
_URI_CONTROLLERS = ("OwnerRestController", "PetRestController", "PetTypeRestController",
                   "SpecialtyRestController", "VetRestController", "VisitRestController")


def _uri_diag(path: str, line: int) -> dict:
    return {"kind": "ERROR", "path": path, "line": line, "code": _URI_CODE, "message": _URI_MSG}


_FAMILY_CTL = (
    "package org.springframework.samples.petclinic.rest;\n"
    "import java.net.URI;\n"
    "public class %s {\n"
    "    static class Headers { void setLocation(URI u) { } }\n"
    "    static class Builder { URI build(int id) { return URI.create(\"/x/\" + id); } }\n"
    "    void add%s(int id, Builder b) {\n"
    "        Headers h = new Headers();\n"
    "        h.setLocation(%s);\n"
    "    }\n"
    "}\n"
)
_BUILDER = "b.build(id)"
_CTOR = 'new URI("/api/x/" + id)'


def _family_tree(root: Path, form: str) -> list[str]:
    paths: list[str] = []
    for name in _URI_CONTROLLERS:
        rel = "src/main/java/org/springframework/samples/petclinic/rest/%s.java" % name
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_FAMILY_CTL % (name, name.replace("RestController", ""), form), encoding="utf-8")
        paths.append(rel)
    return paths


def _checked_family_case() -> int:
    """javac names one unhandled checked exception per compilation; the family is
    what ONE transformation introduced, as the compiler enumerates it."""
    import json
    import subprocess
    import tempfile

    from planner.paths import LOOP_STEPS

    def git(root: Path, *a: str) -> str:
        return subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                              check=True, capture_output=True, text=True).stdout.strip()

    with tempfile.TemporaryDirectory(prefix="chk-family-") as td:
        root = Path(td)
        paths = _family_tree(root, _BUILDER)
        owner, pet = paths[0], paths[1]
        legacy = "src/main/java/org/springframework/samples/petclinic/rest/LegacyController.java"
        (root / legacy).write_text(_FAMILY_CTL % ("LegacyController", "Legacy", _CTOR), encoding="utf-8")
        git(root, "init", "-q")
        git(root, "add", "-A")
        git(root, "commit", "-qm", "baseline")
        base = git(root, "rev-parse", "HEAD")
        _family_tree(root, _CTOR)
        git(root, "commit", "-qam", "the transformation")
        t1 = git(root, "rev-parse", "HEAD")
        (root / LOOP_STEPS).parent.mkdir(parents=True, exist_ok=True)
        (root / LOOP_STEPS).write_text(json.dumps({"schema": "rhoai3.loop-steps/v1", "steps": [
            {"cluster": "bootstrap", "commit": base}, {"cluster": "c:intro", "card": "t_intro", "commit": t1}]}), encoding="utf-8")

        items = compile_items({"diagnostics": [_uri_diag(owner, 8)]})
        clusters = cluster_items(items, {p: 0 for p in paths + [legacy]}, set())
        if len(clusters) != 1 or clusters[0]["write_set"] != [owner]:
            return _fail("javac names one file, so the cluster starts Owner-only: %s" % clusters)
        scope = build_batch_scope(root, clusters[0], items, {"candidate_sha256": "base"})
        if not scope or scope.get("rule") != CHECKED_FAMILY_RULE or scope.get("kind") != "repair-family":
            return _fail("an unhandled checked exception seals the family: %s" % scope)
        if len(scope["members"]) != 6 or set(scope["writable_paths"]) != set(paths):
            return _fail("the family is the six sites the transformation introduced -- never the legacy site it did not touch: %s" % scope["writable_paths"])
        if scope["introduced_by"]["commit"] != t1 or scope["introduced_by"]["card"] != "t_intro":
            return _fail("the family is bound to the step that introduced it: %s" % scope["introduced_by"])
        if "request-aware URI builder" not in scope["rule_note"] or "without introduced checked exceptions" not in scope["rule_note"]:
            return _fail("a Location family's note asks for source-compatible construction: %s" % scope["rule_note"])
        if scope["measured"] != [items[0]["id"]]:
            return _fail("measured failures stay in item_ids: %s" % scope["measured"])
        clusters[0]["batch_scope"] = {"rule": scope["rule"], "family_id": scope["family_id"]}
        rk_owner = retry_key(clusters[0], items)
        if not rk_owner.startswith("rk:compile:checked-family:"):
            return _fail("the family budget is the family's: %s" % rk_owner)

        model = dest_model(root)
        owner_id = diagnostic_identity(model, items[0])
        if not owner_id.startswith("chk:") or "|addOwner|" not in owner_id:
            return _fail("the compiler places the diagnostic on its member and call site: %s" % owner_id)
        text = (root / owner).read_text(encoding="utf-8")
        (root / owner).write_text(text.replace("    void add", "\n\n\n    void add"), encoding="utf-8")
        moved = compile_items({"diagnostics": [_uri_diag(owner, 11)]})
        if moved[0]["id"] == items[0]["id"] or diagnostic_identity(dest_model(root), moved[0]) != owner_id:
            return _fail("a moved line changes the err: id and NOT the identity")
        (root / owner).write_text(text.replace(_CTOR, _BUILDER), encoding="utf-8")

        pet_items = compile_items({"diagnostics": [_uri_diag(pet, 8)]})
        pet_cluster = cluster_items(pet_items, {p: 0 for p in paths}, set())[0]
        pet_scope = build_batch_scope(root, pet_cluster, pet_items, {"candidate_sha256": "cand"})
        if not pet_scope or pet_scope["family_id"] != scope["family_id"] or len(pet_scope["members"]) != 5:
            return _fail("Pet after Owner is the same family, less the repaired member: %s" % pet_scope)
        pet_cluster["batch_scope"] = {"rule": pet_scope["rule"], "family_id": pet_scope["family_id"]}
        if retry_key(pet_cluster, pet_items) != rk_owner:
            return _fail("Owner and Pet are one budget")
        cur_model = dest_model(root)
        pet_id = diagnostic_identity(cur_model, pet_items[0])
        legacy_id = diagnostic_identity(cur_model, compile_items({"diagnostics": [_uri_diag(legacy, 8)]})[0])
        family_keys = {"chk:" + m["member"] for m in scope["members"]}
        flat = {"known": True, "tuple": [0, 1, 0]}
        kw = dict(issued_items=[items[0]["id"]], issued_identities={owner_id}, family_scope=family_keys)
        ok, why = progress(flat, flat, set(), set(), cur_item_ids={pet_items[0]["id"]}, cur_identities={pet_id}, **kw)
        if ok is not RETAIN or ok:
            return _fail("Owner gone, Pet reported, inside the sealed family: CONTINUE in the same card: %r %s" % (ok, why))
        ok, why = progress(flat, flat, set(), set(), cur_identities={legacy_id}, **kw)
        if ok is not EXPOSED or "outside every sealed scope" not in why:
            return _fail("a failure outside the family is a typed diagnosis: %r %s" % (ok, why))
        ok, why = progress(flat, flat, set(), set(), cur_identities={owner_id}, **kw)
        if ok or "still reported" not in why:
            return _fail("the issued site still reported, at any line, is a reject: %r %s" % (ok, why))
        ok, why = progress(flat, flat, set(), set(), issued_items=[items[0]["id"]], issued_identities={owner_id}, cur_identities={pet_id})
        if ok is not EXPOSED:
            return _fail("with no sealed family there is no continuation: %r %s" % (ok, why))
        ok, why = progress(flat, {"known": True, "tuple": [0, 0, 0]}, set(), set(), cur_identities=set(), **kw)
        if not ok:
            return _fail("a true 1->0 drop is ACCEPTED: %s" % why)

        verdicts = {r["path"]: r for r in assess_checked_family(root, scope)}
        if verdicts[owner]["verdict"] != "ok" or any(verdicts[p]["verdict"] != "violates" for p in paths[1:]):
            return _fail("the repaired member is ok; the rest still violate: %s" % {k: v["verdict"] for k, v in verdicts.items()})
        f = root / pet
        f.write_text(f.read_text(encoding="utf-8").replace("h.setLocation(%s);" % _CTOR,
                     "try { h.setLocation(%s); } catch (java.net.URISyntaxException e) { }" % _CTOR), encoding="utf-8")
        f = root / paths[4]
        f.write_text(f.read_text(encoding="utf-8").replace("h.setLocation(%s);" % _CTOR, "URI u = b.build(id);"), encoding="utf-8")
        verdicts = {r["path"]: r for r in assess_checked_family(root, scope)}
        if verdicts[pet]["verdict"] != "violates" or "still calls" not in verdicts[pet]["detail"]:
            return _fail("catching the exception is not removing it: %s" % verdicts[pet])
        if verdicts[paths[4]]["verdict"] != "violates" or "setLocation" not in verdicts[paths[4]]["detail"]:
            return _fail("a Location is not repaired by deleting the header: %s" % verdicts[paths[4]])
        _family_tree(root, _BUILDER)
        if {r["verdict"] for r in assess_checked_family(root, scope)} != {"ok"}:
            return _fail("every member repaired with a construction that cannot throw is ok")
    return 0


_SET_WIDE_LOG = (
    "[ERROR] \t[error]: Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: "
    "java.lang.IllegalArgumentException: No implementation of interface "
    "org.springframework.samples.petclinic.repository.%s was found\n"
    "[ERROR] \tat io.quarkus.spring.data.deployment.generate.FragmentMethodsUtil.getImplementationDotName(FragmentMethodsUtil.java:38)"
)


def _set_wide_case() -> int:
    """A failure about a SET must not take its identity from the member the
    platform happened to name first: six builds of one unchanged v8 tree named
    six different repositories (2026-09-12)."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="set-wide-") as td:
        root = Path(td)
        base = root / "src/main/java/org/springframework/samples/petclinic/repository"
        base.mkdir(parents=True, exist_ok=True)
        for name in ("OwnerRepository", "UserRepository", "VisitRepository"):
            (base / ("%s.java" % name)).write_text("package org.springframework.samples.petclinic.repository;\npublic interface %s {}\n" % name, encoding="utf-8")
        ids, rows = set(), []
        for name in ("OwnerRepository", "UserRepository", "VisitRepository"):
            pkg = {"ran": True, "rc": 1, "detail": "mvn verify exited 1 at quarkus-maven-plugin:build", "errors": _SET_WIDE_LOG % name}
            got = runtime_items(pkg, None, root)
            if len(got) != 1:
                return _fail("one gate failure is one obligation: %s" % got)
            row = got[0]
            if not row.get("unlocated") or row.get("path") or row.get("member"):
                return _fail("a set-wide failure carries no file and no member: %s" % {k: row.get(k) for k in ("unlocated", "path", "member")})
            if row.get("set_wide") != "spring-data-fragment-implementations" or row.get("cause") != "missing-implementation":
                return _fail("the blocker is typed by processor and cause: %s" % {k: row.get(k) for k in ("set_wide", "cause")})
            if name not in row["message"] or [p for p in row.get("observed") or [] if name in p] == []:
                return _fail("the raw message and what it named are kept as observations: %s" % row.get("observed"))
            ids.add(row["id"])
            rows.append(row)
        if len(ids) != 1:
            return _fail("permuted first-reported names must be ONE blocker identity, got %s" % sorted(ids))
        if cluster_items([r for r in rows if not r.get("unlocated")], {}, set()):
            return _fail("a set-wide blocker must never become a card")
        # control: a different cause that names a file of this tree still locates
        other = {"ran": True, "rc": 1, "detail": "mvn verify exited 1",
                 "errors": "UnableToParseMethodException: Method 'findByFoo' of repository class "
                           "org.springframework.samples.petclinic.repository.OwnerRepository is not supported"}
        ctl = runtime_items(other, None, root)[0]
        if ctl.get("unlocated") or not str(ctl.get("path") or "").endswith("OwnerRepository.java") or ctl.get("set_wide"):
            return _fail("a locatable cause must still locate: %s" % {k: ctl.get(k) for k in ("unlocated", "path", "set_wide")})
    return 0


# The startup log of destination v9 (2026-09-14), whose property name after
# "for:" is EMPTY because the annotation that names it was emptied.
_CV_LOG = ("[io.quarkus.runtime.Application] (main) Failed to start application:\n"
           "java.util.NoSuchElementException: SRCFG00014: Failed to load config value of type class java.lang.String for: %s")
_CV_DETAIL = "the application exited with 1 before becoming ready"
_SPRING_VALUE = "org.springframework.beans.factory.annotation.Value"
_MP_CONFIG_PROPERTY = "org.eclipse.microprofile.config.inject.ConfigProperty"


def _cv_structure(root: Path, pkg: str, type_name: str, rel: str,
                  fields: list[tuple[str, str, str, str]]) -> None:
    """M1's structural model of one type and its annotated fields, written into
    `root`. ``fields`` are (field, annotation fqn or "", attribute, value)."""
    import json

    from planner.paths import STRUCTURE

    doc = {"schema": "rhoai3.structure/v1", "producer": {"tool": "jdk-model", "version": "jdk-21", "mode": "full"},
           "source_digest": "d" * 64, "mode": "full",
           "types": [{"fqn": "%s.%s" % (pkg, type_name), "path": rel, "kind": "class", "resolution": "full",
                      "annotations": [], "supertypes": [], "constructors": [], "methods": [], "type_refs": [],
                      "fields": [{"name": f, "type": "java.lang.String",
                                  "annotations": ([{"fqn": a, "values": {attr: [v]}}] if a else [])}
                                 for f, a, attr, v in fields]}]}
    (root / STRUCTURE).parent.mkdir(parents=True, exist_ok=True)
    (root / STRUCTURE).write_text(json.dumps(doc), encoding="utf-8")


def _cv_root(td: str, pkg: str, type_name: str, fields: list[tuple[str, str, str, str]]) -> tuple[Path, str]:
    """A tree that carries ONLY M1's model of the frozen source.

    There is no src/main/java, so the destination cannot be modelled at all and
    the frozen source's model is what answers -- the behaviour that has to
    survive a tree the compiler cannot be run over."""
    root = Path(td)
    rel = "src/main/java/%s/%s.java" % (pkg.replace(".", "/"), type_name)
    _cv_structure(root, pkg, type_name, rel, fields)
    return root, rel


_CV_STUB = ("package org.springframework.beans.factory.annotation;\nimport java.lang.annotation.*;\n"
            "@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.FIELD, ElementType.PARAMETER})\n"
            "public @interface Value { String value(); }\n")


def _cv_dest_root(td: str, pkg: str, type_name: str, field: str, written: str, frozen: str) -> tuple[Path, str]:
    """A REAL destination tree whose field carries `written`, beside M1's model
    of the frozen source, where the same field still carries `frozen`.

    This is destination v9: the two models disagree because a worker edited the
    annotation, and only the compiled tree can say what it says now."""
    import subprocess

    root = Path(td)
    (root / ".hermes").mkdir(parents=True, exist_ok=True)
    (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}', encoding="utf-8")
    rel = "src/main/java/%s/%s.java" % (pkg.replace(".", "/"), type_name)
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("package %s;\n\nimport %s;\n\npublic class %s {\n\n    @Value(\"%s\")\n    private String %s;\n}\n"
                            % (pkg, _SPRING_VALUE, type_name, written, field), encoding="utf-8")
    stub = root / ".stub" / (_SPRING_VALUE.replace(".", "/") + ".java")
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(_CV_STUB, encoding="utf-8")
    classes = root / ".stubcls"
    classes.mkdir(exist_ok=True)
    subprocess.run(["javac", "-d", str(classes), str(stub)], check=True, capture_output=True)
    cp = root / "verification/build/.work/classpath.txt"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(str(classes), encoding="utf-8")
    _cv_structure(root, pkg, type_name, rel, [(field, _SPRING_VALUE, "value", frozen)])
    return root, rel


def _cv_item(root: Path, printed: str) -> dict:
    boot = {"ran": True, "rc": 1, "ready": False, "detail": _CV_DETAIL, "log_tail": _CV_LOG % printed}
    items = runtime_items(None, boot, root)
    return items[0] if len(items) == 1 else {"__count__": len(items)}


def _cv_shape(item: dict, pkg: str, type_name: str, field: str) -> tuple:
    """The DECISION, with this specimen's identifiers taken out of it."""
    def mask(s: str) -> str:
        for real, tok in (("%s.%s" % (pkg, type_name), "<TYPE>"), (pkg.replace(".", "/"), "<PKG>"),
                          (type_name, "<NAME>"), (field, "<FIELD>")):
            s = s.replace(real, tok)
        return s
    return (mask(str(item.get("path") or "")), item.get("kind"), item.get("cause"),
            mask(str(item.get("member") or "")), bool(item.get("unlocated")), mask(str(item.get("detail") or "")))


def _config_value_case() -> int:
    """A property the platform could not load is repaired where it is NAMED.

    Measured on destination v9 (2026-09-14): a worker had replaced
    @Value("#{servletContext.contextPath}") with @Value(""), quarkus-spring-di
    looked up a config property with an empty name, and startup died. The work
    list called it unclassified and minted the card at application.properties,
    where no worker can repair an annotation.

    The first locator then searched M1's structural model -- of the FROZEN
    SOURCE, where the field still carried the SpEL -- found nothing, and raised
    an unlocated blocker while the worker on the card could name the file and
    line. What an annotation SAYS is a fact about the destination, so the
    destination's own compiled model is what answers."""
    import tempfile

    from planner.worklist import APP_PROPERTIES, _structure_config_sites, config_value_sites

    specimens = (("org.springframework.samples.petclinic.rest", "RootRestController", "servletContextPath"),
                 ("com.acme.shop.api", "EntryController", "basePath"))
    shapes: list[list[tuple]] = []
    for pkg, type_name, field in specimens:
        seen: list[tuple] = []
        # (a) the v9 case AS MEASURED: a real destination tree whose field
        # carries @Value(""), while the frozen source's model still carries the
        # SpEL the worker replaced. The two models disagree, and the obligation
        # belongs where the annotation IS, not where it was.
        with tempfile.TemporaryDirectory(prefix="cv-dest-") as td:
            root, rel = _cv_dest_root(td, pkg, type_name, field, "", "#{servletContext.contextPath}")
            if _structure_config_sites(root, ""):
                return _fail("the frozen source's model must still carry the SpEL, or this proves nothing")
            sites, model, _why = config_value_sites(root, "")
            if model != "dest-model" or [s["path"] for s in sites] != [rel]:
                return _fail("the destination's own model answers about its own annotation: %s %s" % (model, sites))
            it = _cv_item(root, "")
            if it.get("path") != rel or it.get("kind") != "compile" or it.get("cause") != "config-value":
                return _fail("an emptied @Value is repaired at its own file, not at the properties file: %s"
                             % {k: it.get(k) for k in ("path", "kind", "cause")})
            if it.get("member") != field or it.get("unlocated"):
                return _fail("the field that carries the annotation is named: %s" % {k: it.get(k) for k in ("member", "unlocated")})
            if "dest-model" not in it["detail"]:
                return _fail("the brief must say WHICH model located it: %s" % it["detail"])
            if "EMPTY" not in it["detail"] or "@Value(\"\")" not in it["detail"] or "quarkus.http.root-path" not in it["detail"]:
                return _fail("the detail must say the name is empty, quote the annotation and teach the mapping: %s" % it["detail"])
            card = cluster_items([it], {}, set())
            if len(card) != 1 or card[0]["write_set"] != [rel]:
                return _fail("the card's write set is the file that carries the annotation: %s" % card)
            seen.append(_cv_shape(it, pkg, type_name, field))
        # (a2) and when the destination cannot be modelled at all, M1's model
        # still decides the same way -- the old behaviour, fallen back to
        with tempfile.TemporaryDirectory(prefix="cv-empty-") as td:
            root, rel = _cv_root(td, pkg, type_name, [(field, _SPRING_VALUE, "value", "")])
            if config_value_sites(root, "")[1] != "structure":
                return _fail("a tree the compiler cannot be run over falls back to the frozen source's model")
            it = _cv_item(root, "")
            if it.get("path") != rel or it.get("kind") != "compile" or it.get("cause") != "config-value":
                return _fail("an emptied @Value is repaired at its own file, not at the properties file: %s"
                             % {k: it.get(k) for k in ("path", "kind", "cause")})
            if it.get("member") != field or it.get("unlocated"):
                return _fail("the field that carries the annotation is named: %s" % {k: it.get(k) for k in ("member", "unlocated")})
            if "structure model" not in it["detail"]:
                return _fail("the brief must say the fallback answered: %s" % it["detail"])
            if "EMPTY" not in it["detail"] or "@Value(\"\")" not in it["detail"] or "quarkus.http.root-path" not in it["detail"]:
                return _fail("the detail must say the name is empty, quote the annotation and teach the mapping: %s" % it["detail"])
            card = cluster_items([it], {}, set())
            if len(card) != 1 or card[0]["write_set"] != [rel]:
                return _fail("the card's write set is the file that carries the annotation: %s" % card)
            seen.append(_cv_shape(it, pkg, type_name, field))
        # (b) Spring's placeholder form names the same property as the bare one
        with tempfile.TemporaryDirectory(prefix="cv-placeholder-") as td:
            root, rel = _cv_root(td, pkg, type_name, [(field, _SPRING_VALUE, "value", "${a.b:x}")])
            it = _cv_item(root, "a.b")
            if it.get("path") != rel or it.get("member") != field or it.get("kind") != "compile":
                return _fail("${x:default} names property x: %s" % {k: it.get(k) for k in ("path", "member", "kind")})
            if "\"a.b\"" not in it["detail"]:
                return _fail("the detail quotes the property name: %s" % it["detail"])
            seen.append(_cv_shape(it, pkg, type_name, field))
            # and MicroProfile's own annotation names it the same way
            root2, rel2 = _cv_root(td + "/mp", pkg, type_name, [(field, _MP_CONFIG_PROPERTY, "name", "a.b")])
            it2 = _cv_item(root2, "a.b")
            if it2.get("path") != rel2 or it2.get("member") != field or "@ConfigProperty(name = \"a.b\")" not in it2["detail"]:
                return _fail("@ConfigProperty(name=x) names property x: %s" % {k: it2.get(k) for k in ("path", "member", "detail")})
        # (c) a real name nothing reads is a key the properties file must supply
        with tempfile.TemporaryDirectory(prefix="cv-missing-") as td:
            root, _ = _cv_root(td, pkg, type_name, [(field, _SPRING_VALUE, "value", "${other.key}")])
            it = _cv_item(root, "a.b")
            if it.get("path") != APP_PROPERTIES or it.get("kind") != "config" or it.get("unlocated"):
                return _fail("a missing key belongs to the properties file: %s" % {k: it.get(k) for k in ("path", "kind", "unlocated")})
            if it.get("cause") != "config-value" or "\"a.b\"" not in it["detail"]:
                return _fail("the cause and the name are still carried: %s" % {k: it.get(k) for k in ("cause", "detail")})
            seen.append(_cv_shape(it, pkg, type_name, field))
        # (d) an empty name nothing reads can be repaired nowhere: a properties
        # file cannot supply a key with no name, and the annotation that
        # produced it is not in the model
        with tempfile.TemporaryDirectory(prefix="cv-unlocated-") as td:
            root, _ = _cv_root(td, pkg, type_name, [(field, _SPRING_VALUE, "value", "${other.key}")])
            it = _cv_item(root, "")
            if not it.get("unlocated") or it.get("path"):
                return _fail("an empty name nobody declares is a blocker with no file: %s" % {k: it.get(k) for k in ("unlocated", "path")})
            if "an empty config property name comes from an annotation the structure model does not record" not in it["detail"]:
                return _fail("the blocker must say why nothing can be located: %s" % it["detail"])
            if cluster_items([it], {}, set()) and not it.get("unlocated"):
                return _fail("a blocker is never a card")
            seen.append(_cv_shape(it, pkg, type_name, field))
        shapes.append(seen)
    # (e) the decisions are about the structure, not about the names in it
    if shapes[0] != shapes[1]:
        first = [a for a, b in zip(shapes[0], shapes[1]) if a != b]
        return _fail("a renamed specimen must decide the same, identifiers aside: %s" % first)
    return 0


def _parity_typing_case() -> int:
    """A parity mismatch is typed by its own diffs: CORS permission the
    destination did not grant is application configuration; a Location, an
    exposed header, a status, a body or an effect is the operation's own
    behaviour at the controller. Scenario verdicts count; the receipt does not."""
    import json
    import tempfile

    from planner.paths import PARITY_DIR

    ep = "ep:a.OwnerRestController#getOwners():http"
    ep2 = "ep:a.OwnerRestController#addOwner(a.OwnerDto):http"
    bundle = {"entry_points": [{"id": ep, "path": "src/main/java/a/OwnerRestController.java"},
                               {"id": ep2, "path": "src/main/java/a/OwnerRestController.java"}]}
    with tempfile.TemporaryDirectory(prefix="parity-typing-") as td:
        root = Path(td)
        pdir = root / PARITY_DIR
        (pdir / "scenarios").mkdir(parents=True, exist_ok=True)
        def w(rel, doc):
            (pdir / rel).write_text(json.dumps(doc), encoding="utf-8")
        w("receipt.json", {"schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL", "reason": "1 of 3 not passed"})
        w("ep_get.json", {"schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "FAIL", "reason": "status 500 vs 200"})
        w("ep_ok.json", {"schema": "rhoai3.parity/v1", "entry_point": ep2, "verdict": "PASS", "reason": ""})
        w("scenarios/sc_cors.json", {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": "sc:cors-actual-owners", "verdict": "FAIL",
                                     "reason": "header Access-Control-Allow-Origin None vs *; header Access-Control-Expose-Headers None vs errors, content-type"})
        w("scenarios/sc_create.json", {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep2, "scenario": "sc:create-owner-location", "verdict": "FAIL",
                                       "reason": "header Location http://d/api/owners/11 vs http://d/petclinic/api/owners/11; header Access-Control-Allow-Origin None vs *"})
        w("scenarios/sc_inc.json", {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep2, "scenario": "sc:x", "verdict": "INCONCLUSIVE", "reason": "no capture"})
        items = parity_items(root, bundle)
        by = {(i["entry_point"], i.get("scenario") or "", i["cause"]): i for i in items}
        # every parity obligation carries the gate that measures it and the
        # scenarios the acceptance path has to re-run to say whether it landed
        if [i for i in items if i.get("gate") != "parity"]:
            return _fail("a parity obligation is measured by the parity gate and must carry it: %s"
                         % [(i["id"], i.get("gate")) for i in items])
        scen = {(i.get("scenario") or ""): i.get("scenarios") for i in items}
        if scen.get("sc:cors-actual-owners") != ["sc:cors-actual-owners"] or scen.get("") != []:
            return _fail("a scenario obligation is made of its own scenario; a read-oracle obligation of none: %s" % scen)
        if len(items) != 4:
            return _fail("read-oracle FAIL + CORS scenario + a split mixed scenario = 4 obligations; receipt/PASS/INCONCLUSIVE none: %s" % [(i["entry_point"][-20:], i.get("scenario"), i["cause"], i["path"]) for i in items])
        ro = by.get((ep, "", "response"))
        if not ro or ro["path"] != "src/main/java/a/OwnerRestController.java" or "status 500 vs 200" not in ro["detail"]:
            return _fail("a read-oracle status diff lands on the controller with its diff in the detail: %s" % ro)
        cors = by.get((ep, "sc:cors-actual-owners", "cors-config"))
        if not cors or cors["path"] != APP_PROPERTIES or cors["kind"] != "config" or cors["rule_id"] != "PARITY_CORS":
            return _fail("CORS-only diffs are a config obligation at application.properties: %s" % cors)
        if "errors, content-type" not in cors["message"] or "quarkus.http.cors.enabled=true" not in cors["message"] or "Do not restore" not in cors["message"]:
            return _fail("the CORS obligation quotes the source's recorded values and names the config path: %s" % cors["message"][:300])
        loc = by.get((ep2, "sc:create-owner-location", "response"))
        cors2 = by.get((ep2, "sc:create-owner-location", "cors-config"))
        if not loc or not cors2 or "Location" not in loc["detail"] or "Location" in cors2["detail"]:
            return _fail("a verdict with a Location diff AND a CORS diff is two obligations, each carrying only its own diffs: %s | %s" % (loc, cors2))
        if len({i["id"] for i in items}) != 4:
            return _fail("obligation ids must be distinct per scenario and kind")
        # and the receipt alone (a FAIL summary with no entry point) is never an obligation
        for f in ("ep_get.json", "scenarios/sc_cors.json", "scenarios/sc_create.json"):
            (pdir / f).unlink()
        if parity_items(root, bundle):
            return _fail("the parity receipt is a summary, not an obligation: %s" % parity_items(root, bundle))
    return 0


def _parity_advice_case() -> int:
    """The two cards v9's first M4 verdict mints carry their exit conditions.

    Both receipts are the shapes the comparator prints today: a CORS preflight
    that granted nothing, and a root read answering the wrong redirect status
    at a doubled root path. Every value in the advice is quoted from the diffs,
    so a specimen that shares no name with this one gets the same advice about
    its own values -- asserted by running the whole case twice."""
    import json
    import tempfile

    from planner.paths import PARITY_DIR

    PETCLINIC = {
        "pkg": "org.springframework.samples.petclinic",
        "root_type": "RootRestController", "root_member": "redirectToSwagger",
        "api_type": "OwnerRestController", "api_member": "getOwners",
        "preflight": "sc:cors-preflight-owners", "read_root": "sc:read-root",
        "root_path": "petclinic", "ui": "swagger-ui",
        "origin": "http://localhost:4200", "methods": "GET,POST,PUT,DELETE,OPTIONS",
        "headers": "Content-Type", "exposed": "errors", "max_age": "1800",
        "policy": "crossorigin:9f1c2b3a4d5e",
    }
    LEDGER = {
        "pkg": "com.acme.ledger",
        "root_type": "EntryPointResource", "root_member": "toDocs",
        "api_type": "AccountResource", "api_member": "listAccounts",
        "preflight": "op:preflight-accounts", "read_root": "op:read-entry",
        "root_path": "ledger", "ui": "openapi-ui",
        "origin": "https://console.acme.test", "methods": "GET,PATCH,OPTIONS",
        "headers": "Accept,Content-Type", "exposed": "x-violations", "max_age": "600",
        "policy": "crossorigin:11aa22bb33cc",
    }

    for spec in (PETCLINIC, LEDGER):
        ep_root = "ep:%s.%s#%s():http" % (spec["pkg"], spec["root_type"], spec["root_member"])
        ep_api = "ep:%s.%s#%s():http" % (spec["pkg"], spec["api_type"], spec["api_member"])
        root_file = "src/main/java/%s/%s.java" % (spec["pkg"].replace(".", "/"), spec["root_type"])
        api_file = "src/main/java/%s/%s.java" % (spec["pkg"].replace(".", "/"), spec["api_type"])
        bundle = {"entry_points": [{"id": ep_root, "path": root_file}, {"id": ep_api, "path": api_file}]}
        # the destination doubles the root path onto a value that already had it
        want_loc = "http://dest:8080/%s/%s/index.html" % (spec["root_path"], spec["ui"])
        raw_loc = "http://source:9966/%s/%s/index.html" % (spec["root_path"], spec["ui"])
        have_loc = "http://dest:8080/%s/%s/%s/index.html" % (spec["root_path"], spec["root_path"], spec["ui"])
        with tempfile.TemporaryDirectory(prefix="parity-advice-") as td:
            root = Path(td)
            pdir = root / PARITY_DIR
            (pdir / "scenarios").mkdir(parents=True, exist_ok=True)

            def w(rel, doc):
                (pdir / rel).write_text(json.dumps(doc), encoding="utf-8")

            w("receipt.json", {"schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL",
                               "cors": {"source_policies": [spec["policy"]], "gaps": []}})
            w("scenarios/preflight.json", {
                "schema": "rhoai3.scenario-parity/v1", "entry_point": ep_api, "scenario": spec["preflight"], "verdict": "FAIL",
                "reason": ("header Access-Control-Allow-Origin None vs %s; header Access-Control-Allow-Methods None vs %s; "
                           "header Access-Control-Allow-Headers None vs %s; header Access-Control-Expose-Headers None vs %s; "
                           "header Access-Control-Max-Age None vs %s"
                           % (spec["origin"], spec["methods"], spec["headers"], spec["exposed"], spec["max_age"]))})
            w("scenarios/read_root.json", {
                "schema": "rhoai3.scenario-parity/v1", "entry_point": ep_root, "scenario": spec["read_root"], "verdict": "FAIL",
                "reason": "status 303 vs 302; header Location %s vs %s (source %s)" % (have_loc, want_loc, raw_loc)})
            w("scenarios/plain.json", {
                "schema": "rhoai3.scenario-parity/v1", "entry_point": ep_api, "scenario": spec["preflight"] + "-actual",
                "verdict": "FAIL", "reason": "status 500 vs 200"})
            items = {(i["entry_point"], i["scenario"], i["cause"]): i for i in parity_items(root, bundle)}

            cors = items.get((ep_api, spec["preflight"], "cors-config"))
            if not cors or not isinstance(cors.get("advice"), dict):
                return _fail("the CORS obligation must carry advice: %s" % cors)
            a = cors["advice"]
            want_props = {
                "quarkus.http.cors.enabled": "true",
                "quarkus.http.cors.origins": spec["origin"],
                "quarkus.http.cors.methods": spec["methods"],
                "quarkus.http.cors.headers": spec["headers"],
                "quarkus.http.cors.exposed-headers": spec["exposed"],
                "quarkus.http.cors.access-control-max-age": spec["max_age"],
            }
            if a["properties"] != want_props:
                return _fail("every CORS property is the SOURCE's own value, quoted from the diffs: %s" % a["properties"])
            if a["source_policies"] != [spec["policy"]]:
                return _fail("the advice names the source policies the receipt recorded: %s" % a["source_policies"])
            blob = json.dumps(a)
            for needed in ("preflight", "PAIRED actual", spec["exposed"], "@CrossOrigin", "ANY origin"):
                if needed not in blob:
                    return _fail("the CORS advice must state %r: %s" % (needed, blob[:600]))
            if "quarkus.http.cors" not in blob or spec["origin"] not in blob:
                return _fail("the CORS advice must quote the evidence, never a preset: %s" % blob[:600])

            red = items.get((ep_root, spec["read_root"], "response"))
            if not red or not isinstance(red.get("advice"), dict):
                return _fail("the redirect obligation must carry advice: %s" % red)
            r = red["advice"]
            blob = json.dumps(r)
            if red["path"] != root_file:
                return _fail("a redirect difference is the operation's own behaviour, at its controller: %s" % red["path"])
            if "302" not in r["exit"][0] or "303" not in r["exit"][0]:
                return _fail("the source's status is the expectation and the destination's is named: %s" % r["exit"][0])
            for needed in (want_loc, raw_loc, have_loc, "ORIGIN mapped",
                           "%r" % spec["root_path"], "already carries its slashes",
                           "quarkus.swagger-ui.always-include=true", "quarkus.swagger-ui.path",
                           "packaged", "amend-scope.py"):
                if needed not in blob:
                    return _fail("the redirect advice must state %r: %s" % (needed, blob[:900]))
            if "following the redirect" not in blob or "404" not in blob or "another redirect status" not in blob:
                return _fail("the redirect advice must refuse 303, redirect following and a dead URL: %s" % blob[:900])

            plain = items.get((ep_api, spec["preflight"] + "-actual", "response"))
            if not plain or "swagger" in json.dumps(plain["advice"]) or "redirect" in json.dumps(plain["advice"]["refused"]):
                return _fail("a status-only difference is not a redirect and gets no redirect advice: %s" % plain)

            other = PETCLINIC if spec is LEDGER else LEDGER
            everything = json.dumps(sorted(items.values(), key=lambda i: i["id"]), default=str)
            # the platform's own property names (quarkus.swagger-ui.*) are not a
            # specimen's values; these tokens are
            leaked = [t for t in (other["root_path"], other["origin"], other["exposed"],
                                  other["root_type"], other["preflight"]) if t in everything]
            if leaked:
                return _fail("advice must carry no other specimen's values: %s" % leaked)
    return 0


def _parity_gate_case() -> int:
    """The parity gate: what discharges a parity card, and what only looks like
    it. v9 card t_77cae2b2 wrote the CORS properties the brief asked for, passed
    the whole acceptance path, and was REVERTED with "measure [0,0,0] did not
    decrease from [0,0,0]" — because nothing ever re-ran the comparison. The
    tuple cannot see a parity repair; only the receipt can."""
    import json
    import tempfile

    from planner.paths import PARITY_DIR

    ep = "ep:a.OwnerRestController#getOwners():http"
    ep2 = "ep:a.OwnerRestController#addOwner(a.OwnerDto):http"
    bundle = {"entry_points": [{"id": ep, "path": "src/main/java/a/OwnerRestController.java"},
                               {"id": ep2, "path": "src/main/java/a/OwnerRestController.java"}]}

    def receipt(verdicts: dict) -> dict:
        return {"schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL" if any(v != "PASS" for v in verdicts.values()) else "PASS",
                "entry_points": [{"entry_point": e, "verdict": v, "reason": "",
                                  "scenarios": ["sc:cors-actual-owners"] if e == ep else ["sc:create-owner-location"]}
                                 for e, v in sorted(verdicts.items())]}

    # the obligation an entry point's READ ORACLE mints is made of the
    # scenarios its receipt row declares: the runner has to be told what to
    # replay, and the verdict has no scenario of its own
    with tempfile.TemporaryDirectory(prefix="parity-gate-") as td:
        root = Path(td)
        pdir = root / PARITY_DIR
        (pdir / "scenarios").mkdir(parents=True, exist_ok=True)
        (pdir / "receipt.json").write_text(json.dumps(receipt({ep: "FAIL", ep2: "PASS"})), encoding="utf-8")
        (pdir / "ep_get.json").write_text(json.dumps(
            {"schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "FAIL", "reason": "status 500 vs 200"}), encoding="utf-8")
        ro = parity_items(root, bundle)
        if len(ro) != 1 or ro[0].get("gate") != "parity" or ro[0].get("scenarios") != ["sc:cors-actual-owners"]:
            return _fail("a read-oracle obligation takes the scenarios its receipt row declares: %s"
                         % [(i.get("gate"), i.get("scenarios")) for i in ro])
        issued = ro[0]["id"]

    green = {"known": True, "tuple": [0, 0, 0], "parity_mismatches": 1}
    done = {"known": True, "tuple": [0, 0, 0], "parity_mismatches": 0}
    both = {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 0, "ready": True}}
    before = receipt({ep: "FAIL", ep2: "PASS"})

    # discharged: the comparison came back PASS for this card's scenario
    ok, why = progress(green, done, set(), set(), gate="parity", prev_runtime=both, cur_runtime=both,
                       prev_parity=before, cur_parity=receipt({ep: "PASS", ep2: "PASS"}),
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items=set())
    if not ok or "discharges" not in why:
        return _fail("a parity repair its own comparison confirms must be accepted with the tuple unchanged: %s" % why)

    # still reported: the same obligation is in the new measurement
    ok, why = progress(green, green, set(), set(), gate="parity", prev_runtime=both, cur_runtime=both,
                       prev_parity=before, cur_parity=before,
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items={issued})
    if ok or "still reported" not in why:
        return _fail("an obligation the comparison still reports is not progress: %r %s" % (ok, why))

    # the obligation is gone from the list but its scenario did not PASS
    # (INCONCLUSIVE mints no obligation at all): absence is not a repair
    ok, why = progress(green, done, set(), set(), gate="parity", prev_runtime=both, cur_runtime=both,
                       prev_parity=before, cur_parity=receipt({ep: "INCONCLUSIVE", ep2: "PASS"}),
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items=set())
    if ok or "still reported" not in why:
        return _fail("a scenario that became INCONCLUSIVE has not been repaired: %r %s" % (ok, why))

    # another scenario regressed: a parity repair may not break one that passed
    ok, why = progress(green, done, set(), set(), gate="parity", prev_runtime=both, cur_runtime=both,
                       prev_parity=before, cur_parity=receipt({ep: "PASS", ep2: "FAIL"}),
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items=set())
    if ok or "may not break another scenario" not in why:
        return _fail("breaking another entry point while repairing this one is not progress: %s" % why)

    # no receipt: nothing was compared, so nothing is proved either way
    ok, why = progress(green, done, set(), set(), gate="parity", prev_runtime=both, cur_runtime=both,
                       prev_parity=before, cur_parity={},
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items=set())
    if ok is not UNPROVEN or "not a measurement" not in why:
        return _fail("an un-composed receipt must retain the candidate, not accept or reject it: %r %s" % (ok, why))
    if ok:
        return _fail("a retained outcome must not read as accepted")

    # the parity slot of the measure itself unknown is the same answer
    ok, why = progress(green, {"known": True, "tuple": [0, 0, 0], "parity_mismatches": None}, set(), set(),
                       gate="parity", prev_runtime=both, cur_runtime=both,
                       prev_parity=before, cur_parity=receipt({ep: "PASS", ep2: "PASS"}),
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items=set())
    if ok is not UNPROVEN:
        return _fail("an unknown parity slot cannot accept a parity card: %r %s" % (ok, why))

    # and the phase before it still stands
    broken = {"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 1, "ready": False}}
    ok, why = progress(green, done, set(), set(), gate="parity", prev_runtime=both, cur_runtime=broken,
                       prev_parity=before, cur_parity=receipt({ep: "PASS", ep2: "PASS"}),
                       issued_items=[issued], prev_gate_items={issued}, cur_gate_items=set())
    if ok or "may not break the phase before it" not in why:
        return _fail("breaking startup while repairing parity is not progress: %s" % why)
    return 0


def main() -> int:
    if (_runtime_identity_case() or _gate_progress_case() or _batch_scope_case() or _checked_family_case()
            or _set_wide_case() or _config_value_case() or _parity_typing_case() or _parity_advice_case()
            or _parity_gate_case()):
        return 1

    if path_class("pom.xml") != "build" or path_class("src/main/resources/application.properties") != "config" or path_class("src/test/java/A.java") != "test" or path_class("src/main/java/A.java") != "source":
        return _fail("path classes")
    if path_class("src/test/resources/application.properties") != "config" or path_class("src/test/resources/data.sql") != "test":
        return _fail("test configuration files are config (migration work); other test files are not writable")
    cfg = cluster_items([{"id": "x", "source": "mta", "kind": "incident", "category": "mandatory", "path": "src/test/resources/application.properties", "line": 1, "rule_id": "r", "message_sha256": "", "detail": ""}], {}, set())
    if cfg[0]["status"] != "open" or cfg[0]["write_set"] != ["src/test/resources/application.properties"]:
        return _fail("a test properties file must be its own write set: %s" % cfg[0])
    findings = {"violations": {
        "r-web": {"category": "mandatory", "incidents": [
            {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m1", "variables": {"k": "1"}},
            {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m2", "variables": {"k": "2"}},
            {"message": "global"},
            {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m1", "variables": {"k": "1"}},
        ]},
        "r-pom": {"category": "mandatory", "incidents": [{"uri": "file:///x/pom.xml", "lineNumber": 1, "message": "p"}]},
        "r-opt": {"category": "optional", "incidents": [{"uri": "file:///x/src/main/java/a/C.java", "lineNumber": 1, "message": "o"}]},
        "rhoai3-canary-00001": {"category": "optional", "incidents": [{"uri": "file:///x/pom.xml", "lineNumber": 1, "message": "c"}]},
    }}
    items = incidents_from_findings(findings, ["/x"], "rhoai3-canary-00001")
    mand = [i for i in items if i["category"] == "mandatory"]
    ids = [i["id"] for i in mand]
    if len(mand) != 5 or len(set(ids)) != 4:
        return _fail("every incident is an item (exact repeat shares the id): %d items, %d ids" % (len(mand), len(set(ids))))
    # identity is line-free: the same obligation on another line is the same id
    moved = incidents_from_findings({"violations": {"r-web": {"category": "mandatory", "incidents": [{"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 11, "message": "m1", "variables": {"k": "1"}}]}}}, ["/x"], "")
    if moved[0]["id"] not in set(ids) or moved[0]["line"] != 11:
        return _fail("line movement must keep the obligation id (and record the new line)")
    if not any(i["path"] == "GLOBAL" and i["kind"] == "build" for i in mand):
        return _fail("a global incident is kept as a build item")
    if any(i["rule_id"] == "rhoai3-canary-00001" for i in items):
        return _fail("canary is not work")
    # the destination rescan sees the frozen legacy copy and the BOM probe under .derived/: never work
    derived = incidents_from_findings({"violations": {"r-web": {"category": "mandatory", "incidents": [
        {"uri": "file:///x/.derived/frozen-input/src/main/java/a/B.java", "lineNumber": 3, "message": "m1"},
        {"uri": "file:///x/.derived/bom-probe/pom.xml", "lineNumber": 1, "message": "p"},
        {"uri": "file:///x/evidence/mta/report/index.html", "lineNumber": 1, "message": "h"},
        {"uri": "file:///x/src/main/java/a/B.java", "lineNumber": 3, "message": "m1"},
    ]}}}, ["/x"], "")
    if [i["path"] for i in derived] != ["src/main/java/a/B.java"]:
        return _fail("incidents outside the product tree must not become items: %s" % [i["path"] for i in derived])
    # compile items + tests
    comp = compile_items({"diagnostics": [{"kind": "ERROR", "path": "src/main/java/a/A.java", "line": 2, "code": "x", "message": "e"}, {"kind": "WARNING", "path": "src/main/java/a/A.java", "line": 2, "code": "w", "message": "w"}]})
    if len(comp) != 1 or comp[0]["kind"] != "compile":
        return _fail("only ERROR diagnostics are items")
    gen = compile_items({"diagnostics": [{"kind": "ERROR", "path": "target/generated-sources/openapi/src/main/java/a/PetDto.java", "line": 9, "code": "compiler.err.doesnt.exist", "message": "package javax.validation does not exist"}]})
    if gen[0]["kind"] != "build" or gen[0]["path"] != "pom.xml" or gen[0]["rule_id"] != "GENERATED_SOURCE_ERROR" or "PetDto.java:9" not in gen[0]["message"] or gen[0]["generated_path"] != "target/generated-sources/openapi/src/main/java/a/PetDto.java":
        return _fail("an error in generated source is a build item on the pom carrying the generated path: %s" % gen[0])
    unres = compile_items({"diagnostics": [], "build_unresolvable": True, "reason": "no classpath"})
    if unres[0]["kind"] != "build" or unres[0]["path"] != "pom.xml":
        return _fail("unresolvable build is a pom item")
    tst = test_items({"failures": [{"classname": "a.ATest", "name": "t", "message": "m", "path": "src/test/java/a/ATest.java"}]})
    if tst[0]["kind"] != "test":
        return _fail("test items")
    if surefire_from_reports_ran_flag() is not False:
        return _fail("no surefire report must mean ran=False")
    # ordering: build < config < compile (leaf-first) < incident < test
    bundle = {"structure": {"types": [
        {"fqn": "a.A", "path": "src/main/java/a/A.java", "type_refs": ["a.B"]},
        {"fqn": "a.B", "path": "src/main/java/a/B.java", "type_refs": []},
    ]}}
    depths = file_depths(bundle)
    if depths["src/main/java/a/B.java"] != 0 or depths["src/main/java/a/A.java"] != 1:
        return _fail("depths %s" % depths)
    all_items = mand + comp + tst + compile_items({"diagnostics": [{"kind": "ERROR", "path": "src/main/java/a/B.java", "line": 9, "code": "x", "message": "e2"}]})
    clusters = cluster_items(all_items, depths, set())
    kinds = [c["kind"] for c in clusters]
    ranks = [KIND_RANK[k] for k in kinds]
    if ranks != sorted(ranks):
        return _fail("cluster order %s" % kinds)
    comp_paths = [c["path"] for c in clusters if c["kind"] == "compile"]
    if comp_paths != ["src/main/java/a/B.java", "src/main/java/a/A.java"]:
        return _fail("compile clusters must be leaf-first: %s" % comp_paths)
    b_cluster = next(c for c in clusters if c["path"] == "src/main/java/a/B.java")
    if b_cluster["kind"] != "compile" or len(b_cluster["items"]) != 4:
        return _fail("B.java clusters its compile error with its incidents: %s" % b_cluster)
    t_cluster = next(c for c in clusters if c["kind"] == "test")
    if t_cluster["write_set"] != ["src/main/java/a/A.java"] or t_cluster["status"] != "open":
        return _fail("a failing test scopes its production twin, never the test: %s" % t_cluster)
    orphan = cluster_items(test_items({"failures": [{"classname": "z.ZTest", "name": "t", "message": "m", "path": ""}]}), depths, set())
    if orphan[0]["write_set"] or orphan[0]["status"] != "blocked":
        return _fail("an unresolvable test failure is a typed blocker with no write set: %s" % orphan[0])
    # measure + progress
    m0 = measure_of(all_items, incidents_known=True, compile_known=True, tests_known=True, parity_known=False)
    if m0["tuple"] != [5, 2, 1] or not m0["known"] or m0["parity_mismatches"] is not None:
        return _fail("measure %s" % m0)
    m1 = measure_of([i for i in all_items if i["source"] != "javac"], incidents_known=True, compile_known=True, tests_known=True, parity_known=False)
    ok, why = progress(m0, m1, {i["id"] for i in all_items}, {i["id"] for i in all_items if i["source"] != "javac"})
    if not ok:
        return _fail("fewer compile errors must be progress: %s" % why)
    ok, why = progress(m0, m0, {i["id"] for i in all_items}, {i["id"] for i in all_items})
    if ok:
        return _fail("equal measure is not progress")
    # lexicographic: fewer incidents but more compile errors is progress; more incidents never is
    m2 = dict(m0, tuple=[4, 9, 1]); m3 = dict(m0, tuple=[6, 0, 0])
    if not progress(m0, m2, set(), set())[0] or progress(m0, m3, set(), set())[0]:
        return _fail("lexicographic order")
    ok, why = progress(m0, m2, {"inc:a"}, {"inc:a", "inc:new"})
    if ok or "new mandatory" not in why:
        return _fail("a new mandatory incident is never progress")
    # veto identity: rule + file + occurrence; a re-hash of the same obligation (variables/message
    # changed by the fix) is NOT new, one more occurrence or a new (rule, file) pair IS
    def _doc(rows):
        return {"items": [{"source": "mta", "category": "mandatory", "rule_id": r, "path": pth, "id": "inc:%s:%s" % (r, h)} for r, pth, h in rows]}
    before = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc")]))
    rehashed = obligation_keys(_doc([("r1", "pom.xml", "ffff"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc")]))
    if rehashed != before or not progress(m0, m2, before, rehashed)[0]:
        return _fail("a re-hashed obligation on the same rule and file must not be new: %s" % (rehashed - before))
    more = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc"), ("r2", "pom.xml", "dddd")]))
    if progress(m0, m2, before, more)[0]:
        return _fail("one more occurrence of a rule on a file is a new obligation")
    # relocation: one fewer occurrence on the old file, one more on a new file (the rule's total did not grow) is NOT new
    other = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "src/main/java/A.java", "cccc")]))
    if not progress(m0, m2, before, other)[0]:
        return _fail("a relocated occurrence of a rule must not veto (the documented profile merge moves incidents with the keys)")
    # the same rule on a new file while every old occurrence stays IS new (the total grew)
    grown = obligation_keys(_doc([("r1", "pom.xml", "aaaa"), ("r2", "pom.xml", "bbbb"), ("r2", "pom.xml", "cccc"), ("r2", "src/main/java/A.java", "dddd")]))
    ok, why = progress(m0, m2, before, grown)
    if ok or "new mandatory" not in why or "A.java" not in why:
        return _fail("a rule spreading to a new file with its old occurrences intact is a new obligation: %s" % why)
    unknown = measure_of(all_items, incidents_known=True, compile_known=False, tests_known=True, parity_known=False)
    if unknown["known"] or progress(m0, unknown, set(), set())[0]:
        return _fail("unknown measure never advances")
    ok, why = progress(unknown, m0, set(), set())
    if not ok or "became known" not in why:
        return _fail("a known measure must beat an unknown baseline: %s" % why)
    if progress(unknown, m0, {"inc:a"}, {"inc:a", "inc:new"})[0]:
        return _fail("becoming known never excuses a new obligation")
    if compile_items({"diagnostics": [], "build_unresolvable": True, "reason": "missing version"})[0].get("message") != "missing version":
        return _fail("the unresolvable item must carry the resolver's reason for the brief")
    # the same unresolved symbol across files is one cluster with a multi-file write set (capped); a lone item stays per file
    def _c(path, sym, n):
        return {"id": "err:%s%d" % (sym, n), "source": "javac", "kind": "compile", "category": "mandatory", "path": path, "line": n, "rule_id": "compiler.err.cant.resolve.location", "message": "cannot find symbol\n  symbol:   class %s\n  location: class X" % sym}
    rows = [_c("src/main/java/a/A.java", "DataAccessException", 1), _c("src/main/java/b/B.java", "DataAccessException", 2), _c("src/main/java/b/B.java", "DataAccessException", 3), _c("src/main/java/c/C.java", "Lonely", 4)]
    cl = cluster_items(rows, {"src/main/java/a/A.java": 3, "src/main/java/b/B.java": 1, "src/main/java/c/C.java": 2}, set())
    sym = [c for c in cl if c.get("label") == "DataAccessException"]
    if len(sym) != 1 or sym[0]["write_set"] != ["src/main/java/a/A.java", "src/main/java/b/B.java"] or len(sym[0]["items"]) != 3 or sym[0]["order_key"][1] != 1:
        return _fail("a symbol seen in two files must be one cluster writing both, ordered by the shallowest file: %s" % sym)
    lone = [c for c in cl if c["path"] == "src/main/java/c/C.java"]
    if len(lone) != 1 or lone[0].get("label") or lone[0]["write_set"] != ["src/main/java/c/C.java"]:
        return _fail("a symbol seen in one file stays a per-file cluster: %s" % lone)
    many = [_c("src/main/java/p/F%02d.java" % i, "Profile", i) for i in range(10)]
    caps = [c for c in cluster_items(many, {}, set()) if c.get("label")]
    if [c["label"] for c in caps] != ["Profile#1", "Profile#2"] or len(caps[0]["write_set"]) != 8 or len(caps[1]["write_set"]) != 2:
        return _fail("a symbol across more than 8 files splits into capped clusters: %s" % [(c["label"], len(c["write_set"])) for c in caps])
    if card_title(sym[0], 1) != "M3 compile DataAccessException (3 items, 2 files, attempt 1)":
        return _fail("symbol clusters get a readable title: %s" % card_title(sym[0], 1))
    # a profile file's cluster writes the profile file AND the sibling application.properties (the documented merge)
    prof = cluster_items([{"id": "inc:p", "source": "mta", "kind": "config", "category": "mandatory", "path": "src/main/resources/application-hsqldb.properties", "line": 0, "rule_id": "springboot-properties-to-quarkus-00001"}], {}, set())
    if prof[0]["write_set"] != ["src/main/resources/application-hsqldb.properties", "src/main/resources/application.properties"]:
        return _fail("profile-file config cluster must scope the main properties file too: %s" % prof[0]["write_set"])
    plain = cluster_items([{"id": "inc:q", "source": "mta", "kind": "config", "category": "mandatory", "path": "src/main/resources/application.properties", "line": 3, "rule_id": "r"}], {}, set())
    if plain[0]["write_set"] != ["src/main/resources/application.properties"]:
        return _fail("the main properties file scopes only itself: %s" % plain[0]["write_set"])
    # the measure may never be greener than the build
    from planner.worklist import build_worklist as _bw  # noqa: F401  (import guard only)
    m_clean = measure_of([], incidents_known=True, compile_known=True, tests_known=True, parity_known=False)
    if not m_clean["known"] or m_clean["tuple"] != [0, 0, 0]:
        return _fail("a clean measure with every component known: %s" % m_clean)
    # supersession (catalog, guarded by a present artifact) and waiver (ADR) reclassify, never drop
    rows = [
        {"id": "inc:a", "source": "mta", "category": "mandatory", "rule_id": "springboot-web-to-quarkus-00010", "path": "pom.xml"},
        {"id": "inc:b", "source": "mta", "category": "mandatory", "rule_id": "jakarta-jaxrs-to-quarkus-00010", "path": "pom.xml"},
        {"id": "inc:c", "source": "mta", "category": "mandatory", "rule_id": "r-waived", "path": "src/main/java/A.java"},
        {"id": "inc:d", "source": "mta", "category": "mandatory", "rule_id": "r-waived", "path": "src/main/java/B.java"},
        {"id": "inc:e", "source": "mta", "category": "mandatory", "rule_id": "r-keep", "path": "pom.xml"},
    ]
    sup = {"springboot-web-to-quarkus-00010": {"requires_present": "io.quarkus:quarkus-rest-jackson", "reason": "renamed"},
           "jakarta-jaxrs-to-quarkus-00010": {"requires_present": "io.quarkus:quarkus-rest", "reason": "transitive"}}
    out = apply_supersessions(rows, sup, [{"rule_id": "r-waived", "path": "src/main/java/A.java", "adr": "ADR-009", "reason": "x"}], {"io.quarkus:quarkus-rest-jackson"}, platform="p")
    cats = {r["id"]: r["category"] for r in out}
    if cats != {"inc:a": "superseded", "inc:b": "mandatory", "inc:c": "waived", "inc:d": "mandatory", "inc:e": "mandatory"}:
        return _fail("supersession needs its artifact present; a waiver binds rule+path: %s" % cats)
    if out[0].get("superseded_by", {}).get("platform") != "p" or out[2].get("waived_by", {}).get("adr") != "ADR-009" or len(out) != 5:
        return _fail("reclassified items keep their authority and are never dropped")
    if measure_of(all_items, incidents_known=False, compile_known=True, tests_known=True, parity_known=False)["known"]:
        return _fail("unknown incidents never advance")
    print("OK: worklist (lossless line-free incidents; canary excluded; only ERROR diagnostics; build→config→compile(leaf-first)→incident→test order; tests never writable; lexicographic 3-tuple progress; new-incident veto; unknown never advances; gate progress is the issued obligation disappearing, never a reworded one; a second cause at one file is a second obligation); a repository card's inventory is sealed by its own digest and two measurements never share a path; checked-exception family: bound to its introducing step (a legacy site stays out), one budget, line-free identity across a moved line, CONTINUE / EXPOSED / still-reported / 1→0 accept, per-member assessment (catch-wrapped and header-deleted members violate); a set-wide packaging cause is one typed blocker under permuted first-reported names and never a card; an unloadable config value is located at the annotation that names the property IN THE DESTINATION'S OWN MODEL (the frozen source's model answers only when the destination cannot be modelled, and the brief says which did; ${x:d} and a bare x are one property), at application.properties only when the name is real and unread, and is a blocker when the name is empty and unread -- the same decisions under renamed identifiers; parity mismatches are typed by their diffs (CORS → application.properties, the rest → the controller; scenario verdicts count, the receipt does not) and carry their exit conditions as advice built from those diffs (CORS properties are the source's own recorded values with the paired actual request and the exposed headers as the exit; a redirect is the source's status and its literal Location after origin mapping only, the doubled root path named, the legacy address served from the packaged UI, a property outside the write set entering through amend-scope) — the same advice, about its own values, on a specimen that shares no name with this one; the PARITY GATE: an obligation carries gate=parity and the scenarios it is made of (a read oracle takes its receipt row's), and a card is discharged only by the re-composed receipt recording those scenarios PASS -- still reported, gone but INCONCLUSIVE, another entry point broken, a startup gate broken and an un-composed receipt all refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
