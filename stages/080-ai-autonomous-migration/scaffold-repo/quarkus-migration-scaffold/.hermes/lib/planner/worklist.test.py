#!/usr/bin/env python3
"""worklist unit selftest: ordering, clustering, measure, progress, conservation."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.cards import card_title
from planner.worklist import CHECKED_FAMILY_RULE, EXPOSED, RETAIN, UNPROVEN, apply_supersessions, assess_checked_family, batch_scope_digest, batch_scope_path, build_batch_scope, retry_key, runtime_items  # noqa: E402
from planner.canonical import digest  # noqa: E402
from planner.worklist import SYMBOL_CLUSTER_MAX_FILES  # noqa: E402
from planner.worklist import RULE_CONFIG_CONSUMERS, SPRING_VALUE_ANNOTATION as SPRING_VALUE  # noqa: E402
from planner.worklist import (RULE_DECLARATION_CLOSURE, RULE_DIAGNOSTIC_FAMILY, RULE_PACKAGE_LEAF,  # noqa: E402
                              UNIT_MAX_FILES, UNIT_MAX_SITES, UNIT_MAX_SYMBOLS, build_unit_scope, form_units,
                              runtime_cause, unit_continue_scope, unit_explained_regressions, unit_formation_for,
                              unit_formation_mode, unit_id_of, assess_unit)
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
        cors = by.get((ep, "sc:cors-actual-owners", "cors-response"))
        adapter = "src/main/java/io/rhoai3/migration/response/SourceCorsResponseAdapter.java"
        if (not cors or cors["path"] != adapter or cors["kind"] != "config" or cors["rule_id"] != "PARITY_CORS"
                or (cors.get("owed") or {}).get("contract") != "source-cors-response-adapter/v1"
                or cors["advice"]["write_set"] != [adapter, APP_PROPERTIES]):
            return _fail("CORS diffs are an obligation OWED the CORS adapter, its write set the adapter and the config (ADR-019): %s" % cors)
        if ("errors, content-type" not in cors["message"] or "install-response-adapter.py" not in cors["message"]
                or "Do not restore" not in cors["message"] or APP_PROPERTIES not in cors["message"]):
            return _fail("the CORS obligation quotes the source's recorded values and names the capability and both paths: %s" % cors["message"][:300])
        loc = by.get((ep2, "sc:create-owner-location", "response"))
        cors2 = by.get((ep2, "sc:create-owner-location", "cors-response"))
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
                "schema": "rhoai3.scenario-parity/v1", "entry_point": ep_api, "scenario": "sc:plain-" + spec["api_member"],
                "verdict": "FAIL", "reason": "status 500 vs 200"})
            items = {(i["entry_point"], i["scenario"], i["cause"]): i for i in parity_items(root, bundle)}

            cors = items.get((ep_api, spec["preflight"], "cors-response"))
            if not cors or not isinstance(cors.get("advice"), dict):
                return _fail("the CORS obligation must carry advice: %s" % cors)
            a = cors["advice"]
            # ADR-019: configuration-only advice is replaced; the capability's
            # adapter AND the configuration are the write set, and the values
            # come from the source policy, not from this capture
            if "properties" in a:
                return _fail("the CORS advice must no longer prescribe configuration values from one capture: %s" % a["properties"])
            if a["write_set"] != [a["owed"]["path"], "src/main/resources/application.properties"]:
                return _fail("the CORS advice names the adapter's contract path and the config as its write set: %s" % a["write_set"])
            if a["source_policies"] != [spec["policy"]]:
                return _fail("the advice names the source policies the receipt recorded: %s" % a["source_policies"])
            obs = a["observed_headers"]
            if obs.get("Access-Control-Allow-Origin", {}).get("source") != spec["origin"] or obs.get("Access-Control-Max-Age", {}).get("source") != spec["max_age"]:
                return _fail("the advice quotes what the SOURCE sent, from the diffs: %s" % obs)
            blob = json.dumps(a)
            for needed in ("preflight", "PAIRED actual", spec["exposed"], "@CrossOrigin", "source policy",
                           "install-response-adapter.py", "--check", "BOTH security modes", "same origin",
                           "wildcard policy inferred", "turns a rejected exchange into an allowed one", "PARITY_CONTENT_TYPE"):
                if needed not in blob:
                    return _fail("the CORS advice must state %r: %s" % (needed, blob[:600]))
            if spec["origin"] not in blob:
                return _fail("the CORS advice must quote the evidence, never a preset: %s" % blob[:600])
            if "render_refused" not in a:
                return _fail("with no structural model in the tree the rendering is refused by name, never guessed: %s" % sorted(a))

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

            plain = items.get((ep_api, "sc:plain-" + spec["api_member"], "response"))
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


def _parity_navigation_case() -> int:
    """The card a dead redirect target mints.

    The comparison PASSed -- the destination answered the source's status and
    its literal Location after origin mapping -- and the separate bounded
    navigation found the address it points at dead. There is no failing
    verdict file for that: the receipt's own row is the evidence, and the card
    belongs at the controller that answers the redirect, carrying ADR-016's
    exit conditions for the address rather than for the response. Run twice on
    specimens that share no identifier, so the advice is the measurement's and
    not this one's."""
    import json
    import tempfile

    from planner.paths import PARITY_DIR

    PETCLINIC = {"pkg": "org.springframework.samples.petclinic", "type": "RootRestController",
                 "member": "redirectToSwagger", "scenario": "sc:read-root", "root_path": "petclinic",
                 "ui": "swagger-ui", "host": "dest-petclinic:8080"}
    LEDGER = {"pkg": "com.acme.ledger", "type": "EntryPointResource", "member": "toDocs",
              "scenario": "op:read-entry", "root_path": "ledger", "ui": "openapi-ui", "host": "ledger.internal:9443"}

    for spec in (PETCLINIC, LEDGER):
        ep = "ep:%s.%s#%s():http" % (spec["pkg"], spec["type"], spec["member"])
        controller = "src/main/java/%s/%s.java" % (spec["pkg"].replace(".", "/"), spec["type"])
        target = "http://%s/%s/%s/index.html" % (spec["host"], spec["root_path"], spec["ui"])
        target_path = "/%s/%s/index.html" % (spec["root_path"], spec["ui"])
        bundle = {"entry_points": [{"id": ep, "path": controller}]}
        with tempfile.TemporaryDirectory(prefix="parity-nav-") as td:
            root = Path(td)
            pdir = root / PARITY_DIR
            (pdir / "scenarios").mkdir(parents=True, exist_ok=True)
            reason = "redirect target %s is dead on the destination (404)" % target
            (pdir / "receipt.json").write_text(json.dumps(
                {"schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL",
                 "entry_points": [{"entry_point": ep, "verdict": "FAIL", "kind": "navigation", "reason": reason,
                                   "scenarios": [spec["scenario"]],
                                   "navigation_failures": [{"scenario": spec["scenario"], "target": target,
                                                            "terminal": "dead", "final_status": 404}]}]}),
                encoding="utf-8")
            items = parity_items(root, bundle)
            if len(items) != 1:
                return _fail("a navigation row mints exactly one obligation, and a PASSing comparison mints none "
                             "beside it: %s" % [(i["cause"], i["path"]) for i in items])
            it = items[0]
            if it["rule_id"] != "PARITY" or it["cause"] != "redirect-target-dead" or it["kind"] != "parity":
                return _fail("a navigation failure is a typed PARITY obligation: %s"
                             % {k: it.get(k) for k in ("rule_id", "cause", "kind")})
            if it["path"] != controller:
                return _fail("it belongs at the controller that answers the redirect, not at a config file: %s" % it["path"])
            if it.get("gate") != "parity" or it.get("scenarios") != [spec["scenario"]]:
                return _fail("it is measured by the parity gate, over the scenarios its row declares: %s"
                             % {k: it.get(k) for k in ("gate", "scenarios")})
            if target not in it["message"] or "dead" not in it["detail"]:
                return _fail("the brief must name the address and what became of it: %s | %s" % (it["message"][:200], it["detail"]))
            blob = json.dumps(it["advice"])
            for needed in (target, target_path, "quarkus.swagger-ui.always-include=true", "quarkus.swagger-ui.path",
                           "PACKAGED", "amend-scope.py", APP_PROPERTIES, "OpenAPI"):
                if needed not in blob:
                    return _fail("the navigation advice must state %r: %s" % (needed, blob[:900]))
            refused = json.dumps(it["advice"]["refused"])
            if "dead compatibility URL" not in refused or "loop" not in refused or "retired" not in refused:
                return _fail("it must refuse a dead URL, a loop and restoring the retired framework: %s" % refused)
            if "404" not in blob:
                return _fail("the status the walk ended on is the measurement's own: %s" % blob[:600])

            other = PETCLINIC if spec is LEDGER else LEDGER
            everything = json.dumps(items, default=str)
            # the platform's own property names (quarkus.swagger-ui.*) are not
            # a specimen's values, so the UI token is not one of these
            leaked = [t for t in (other["root_path"], other["host"], other["type"], other["scenario"])
                      if t in everything]
            if leaked:
                return _fail("advice must carry no other specimen's values: %s" % leaked)

            # a navigation row that PASSes, or a row nobody typed navigation,
            # mints nothing: absence of a card is the measurement too
            (pdir / "receipt.json").write_text(json.dumps(
                {"schema": "rhoai3.parity-receipt/v1", "verdict": "PASS",
                 "entry_points": [{"entry_point": ep, "verdict": "PASS", "navigation": "ok",
                                   "scenarios": [spec["scenario"]]}]}), encoding="utf-8")
            if parity_items(root, bundle):
                return _fail("a navigation that reached the UI mints no obligation: %s" % parity_items(root, bundle))
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


# ---------------------------------------------------------------------------
# unit formation (design of 2026-09-15 §1): the four typed rules, the seal,
# the bound, and the experiment's table reproduced where a fixture can say it
# ---------------------------------------------------------------------------
#
# Every case is asserted TWICE: once on world A and once on a structurally
# identical twin with every package, type, member and foreign symbol renamed
# (SAD §2.1 criterion 2). A rule that read a name of this specimen would pass
# the first and fail the second.

GOLDEN = Path(__file__).resolve().parents[3]


def _dm_ann(fqn: str) -> dict:
    return {"fqn": fqn, "simple": fqn.rsplit(".", 1)[-1], "values": {}, "resolution": "full"}


def _dm_member(name: str, signature: str, *, has_body: bool = False, calls=(), throws=(), annotations=()) -> dict:
    return {"name": name, "signature": signature, "resolution": "full", "has_body": has_body,
            "annotations": [dict(a) for a in annotations], "calls": list(calls),
            "throws_checked": list(throws), "type_refs": [], "call_names": []}


def _dm_type(fqn: str, path: str, *, kind: str = "class", imports=(), supertypes=(), annotations=(),
             declared=(), type_refs=(), resolution: str = "full") -> dict:
    return {"path": path, "fqn": fqn, "kind": kind, "resolution": resolution,
            "imports": list(imports), "supertypes": list(supertypes),
            "annotations": [dict(a) for a in annotations], "declared": [dict(d) for d in declared],
            "fields": [], "unhandled_throws": [], "inherited": [], "supertype_methods": [],
            "inherited_known": True, "type_refs": sorted(set(type_refs))}


def _javac(path: str, token: str, n: int, *, kind: str = "class") -> dict:
    return {"id": "err:%s:%s:%d" % (path.rsplit("/", 1)[-1], token, n), "source": "javac", "kind": "compile",
            # build_worklist stamps the line-free identity before clustering
            "identity": "diag:%s|%s|%d" % (path, token, n),
            "category": "mandatory", "path": path, "line": 10 + n,
            "rule_id": "compiler.err.cant.resolve.location",
            "message": "cannot find symbol\n  symbol:   %s %s\n  location: class X" % (kind, token)}


# world A and its renamed twin: nothing structural differs, every identifier does
_WORLD_A = {
    "base": "org.acme.clinic",
    "svc_pkg": "service", "rest_pkg": "rest", "leaf_pkg": "util", "gated_pkg": "repo", "frag_pkg": "frag",
    "svc": "ClinicService", "impl": "ClinicServiceImpl",
    "controllers": ("OwnerRestController", "PetRestController", "VisitRestController"),
    "member": "lookupOwner", "param": "int",
    "exc": "org.springframework.dao.DataAccessException",
    "spanning": "org.springframework.transaction.annotation.Transactional",
    "gated": "org.springframework.context.annotation.Profile",
    "leaf_symbols": ("org.springframework.util.MutableSortDefinition", "org.springframework.beans.support.PropertyComparator",
                     "org.springframework.core.style.ToStringCreator", "org.springframework.format.annotation.DateTimeFormat"),
    # one of these carries a documented catalog target; the rest do not
    "web_symbols": ("javax.ws.rs.core.Context", "org.springframework.validation.BindingResult",
                    "org.springframework.validation.FieldError", "org.springframework.http.HttpStatus",
                    "org.springframework.web.bind.annotation.CrossOrigin"),
    "frag_member": "lookupByCustomClause", "frag_n": 7,
}
_WORLD_B = {
    "base": "com.example.warehouse",
    "svc_pkg": "domain", "rest_pkg": "api", "leaf_pkg": "helper", "gated_pkg": "store", "frag_pkg": "mixin",
    "svc": "DepotGateway", "impl": "DepotGatewayBean",
    "controllers": ("CrateEndpoint", "PalletEndpoint", "ShipmentEndpoint"),
    "member": "resolveCrate", "param": "long",
    "exc": "io.legacyframework.persistence.StoreAccessFault",
    "spanning": "io.legacyframework.tx.UnitOfWork",
    "gated": "io.legacyframework.ctx.Variant",
    "leaf_symbols": ("io.legacyframework.sort.OrderSpec", "io.legacyframework.sort.AttributeRanker",
                     "io.legacyframework.text.DescriptionMaker", "io.legacyframework.fmt.InstantPattern"),
    "web_symbols": ("io.legacyframework.http.Injected", "io.legacyframework.bind.BindReport",
                    "io.legacyframework.bind.FieldFault", "io.legacyframework.http.StatusCode",
                    "io.legacyframework.web.OriginPolicy"),
    "frag_member": "resolveByHandwrittenClause", "frag_n": 7,
}
_GATED_FILES = 15


def _unit_world(n: dict) -> tuple[dict, list[dict], dict]:
    """(dest model, javac items, the keys the rules are expected to form).

    The shapes are the experiment's evidence classes: a `throws` surface across
    an interface, its implementer and its callers (WU-1); an annotation family
    over many files in one leaf directory (WU-2); a directory of helpers
    nothing outside refers to (WU-4); five independent web symbols each
    spanning two directories (WU-3); and seven fragment parents with a member
    no implementer answers (WU-5)."""
    base, pkg = n["base"], n["base"].replace(".", "/")
    types: list[dict] = []
    items: list[dict] = []

    def rel(sub: str, name: str) -> str:
        return "%s/%s/%s.java" % (pkg, sub, name)

    def full(sub: str, name: str) -> str:
        return "src/main/java/" + rel(sub, name)

    def simple(fqn: str) -> str:
        return fqn.rsplit(".", 1)[-1]

    # --- (b) the throws surface: interface + implementer + three callers
    svc = "%s.%s.%s" % (base, n["svc_pkg"], n["svc"])
    sig = "%s(%s)" % (n["member"], n["param"])
    types.append(_dm_type(svc, rel(n["svc_pkg"], n["svc"]), kind="interface", imports=[n["exc"]],
                          declared=[_dm_member(n["member"], sig, throws=[n["exc"]])]))
    impl = "%s.%s.%s" % (base, n["svc_pkg"], n["impl"])
    types.append(_dm_type(impl, rel(n["svc_pkg"], n["impl"]), supertypes=[svc],
                          imports=[n["exc"], n["spanning"]] + list(n["web_symbols"]),
                          declared=[_dm_member(n["member"], sig, has_body=True, throws=[n["exc"]],
                                               annotations=[_dm_ann(n["spanning"])])],
                          type_refs=[svc]))
    surface_files = [full(n["svc_pkg"], n["svc"]), full(n["svc_pkg"], n["impl"])]
    for i, c in enumerate(n["controllers"]):
        fqn = "%s.%s.%s" % (base, n["rest_pkg"], c)
        types.append(_dm_type(fqn, rel(n["rest_pkg"], c),
                              imports=[n["exc"], svc, n["spanning"]] + list(n["web_symbols"]),
                              declared=[_dm_member("handle", "handle(%s)" % n["param"], has_body=True,
                                                   calls=["%s.%s" % (svc, sig)],
                                                   annotations=[_dm_ann(n["spanning"])] if i == 0 else ())],
                              type_refs=[svc]))
        surface_files.append(full(n["rest_pkg"], c))
    for i, p in enumerate(surface_files):
        items.append(_javac(p, simple(n["exc"]), i))

    # --- (a) one family spanning two directories: never a leaf
    items.append(_javac(full(n["svc_pkg"], n["impl"]), simple(n["spanning"]), 90, kind="interface"))
    items.append(_javac(full(n["rest_pkg"], n["controllers"][0]), simple(n["spanning"]), 91, kind="interface"))

    # --- (a) ×5: five independent web symbols, each in one controller and the
    #     implementer, so no single directory holds a whole family (WU-3)
    for i, sym in enumerate(n["web_symbols"]):
        items.append(_javac(full(n["rest_pkg"], n["controllers"][i % len(n["controllers"])]), simple(sym), 100 + i))
        items.append(_javac(full(n["svc_pkg"], n["impl"]), simple(sym), 200 + i))

    # --- (c) a gated directory nothing outside refers to: one annotation
    #     family over fifteen files (WU-2's @Profile half)
    for i in range(_GATED_FILES):
        name = "Gated%02d" % i
        types.append(_dm_type("%s.%s.%s" % (base, n["gated_pkg"], name), rel(n["gated_pkg"], name),
                              imports=[n["gated"]], annotations=[_dm_ann(n["gated"])]))
        items.append(_javac(full(n["gated_pkg"], name), simple(n["gated"]), 300 + i, kind="interface")),

    # --- (c) a directory of helpers nothing outside refers to, four symbols (WU-4)
    for i, sym in enumerate(n["leaf_symbols"]):
        name = "Helper%d" % i
        types.append(_dm_type("%s.%s.%s" % (base, n["leaf_pkg"], name), rel(n["leaf_pkg"], name), imports=[sym]))
        items.append(_javac(full(n["leaf_pkg"], name), simple(sym), 400 + i))

    # --- (b) over a set the platform names one member of: seven parents, each
    #     with a member no implementer answers, each extended by a store (WU-5)
    frag_files: list[str] = []
    frag_children: list[str] = []
    frag_adapters: list[str] = []
    for i in range(n["frag_n"]):
        parent = "%s.%s.Fragment%d" % (base, n["frag_pkg"], i)
        child = "%s.%s.Store%d" % (base, n["frag_pkg"], i)
        types.append(_dm_type(parent, rel(n["frag_pkg"], "Fragment%d" % i), kind="interface",
                              declared=[_dm_member(n["frag_member"], "%s(%s)" % (n["frag_member"], n["param"]))]))
        # the child IMPORTS the parent it extends, which is the shape the
        # architect reproduced: a required declaration, not a retired symbol
        types.append(_dm_type(child, rel(n["frag_pkg"], "Store%d" % i), kind="interface", supertypes=[parent],
                              imports=[parent]))
        frag_files += [full(n["frag_pkg"], "Fragment%d" % i), full(n["frag_pkg"], "Store%d" % i)]
        frag_children.append(full(n["frag_pkg"], "Store%d" % i))
        frag_adapters.append(full(n["frag_pkg"], "Fragment%dImpl" % i))

    # --- a test source: never writable, never a unit member (WU-3 / R-1)
    items.append(_javac("src/test/java/%s/%s/%sTest.java" % (pkg, n["rest_pkg"], n["controllers"][0]),
                        simple(n["web_symbols"][1]), 500))

    expect = {
        "surface_key": svc, "surface_files": sorted(surface_files),
        "gated_dir": "src/main/java/%s/%s" % (pkg, n["gated_pkg"]),
        "leaf_dir": "src/main/java/%s/%s" % (pkg, n["leaf_pkg"]),
        "spanning": n["spanning"], "web": [str(s) for s in n["web_symbols"]],
        "frag_files": sorted(frag_files), "frag_n": n["frag_n"],
        "frag_children": sorted(frag_children), "frag_adapters": sorted(frag_adapters),
        "frag_write_set": sorted([p for p in frag_files if p not in set(frag_children)] + frag_adapters),
        "exc": n["exc"], "gated": n["gated"],
    }
    return {"types": types}, items, expect


def _set_wide_item(scope: str = "spring-data-fragment-implementations") -> dict:
    return {"id": "rt:boot:setwide", "source": "runtime", "gate": "boot", "kind": "config",
            "cause": "missing-implementation", "set_wide": scope, "unlocated": True, "path": "",
            "category": "mandatory", "line": 0, "rule_id": "RUNTIME_APPLICATION_CONFIGURATION",
            "message": "No implementation of interface X was found"}


def _by_rule(units: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for c in units:
        out.setdefault(str(c["unit"]["rule"]), []).append(c)
    return out


def _unit_formation_case() -> int:
    """The four typed rules, each on its own evidence class, and the same
    verdicts on a twin that shares no identifier with the first."""
    for label, names in (("A", _WORLD_A), ("B", _WORLD_B)):
        model, items, want = _unit_world(names)
        rows = items + [_set_wide_item()]
        units, claimed = form_units(rows, {}, set(), model=model, root=GOLDEN)
        by_rule = _by_rule(units)

        # (b) WU-1: the surface is ONE unit -- the interface, its implementer
        # and its three callers -- not two halves of a symbol group.
        closures = [c for c in by_rule.get(RULE_DECLARATION_CLOSURE, []) if c["unit"]["family_key"].startswith(want["surface_key"])]
        if len(closures) != 1:
            return _fail("[%s] one declaration closure over the throws surface: %s" % (label, [c["unit"]["family_key"] for c in by_rule.get(RULE_DECLARATION_CLOSURE, [])]))
        surface = closures[0]
        if sorted(surface["write_set"]) != want["surface_files"]:
            return _fail("[%s] the closure writes the declaration, its implementers and its callers: %s" % (label, surface["write_set"]))
        states = {str(m["state"]) for m in surface["_unit_seal"]["members"]}
        if not {"declares", "implements", "calls"} <= states:
            return _fail("[%s] the closure's members name why each is in it: %s" % (label, sorted(states)))
        if not any(e["kind"] == "javac" for e in surface["_unit_seal"]["evidence"]) or not any(e["kind"] == "model" for e in surface["_unit_seal"]["evidence"]):
            return _fail("[%s] a closure cites both the diagnostic and the model relation" % label)

        # (c) WU-2 / WU-4: two leaves, decided by type_refs and never by a name
        leaves = {c["unit"]["family_key"]: c for c in by_rule.get(RULE_PACKAGE_LEAF, [])}
        if sorted(leaves) != sorted([want["gated_dir"], want["leaf_dir"]]):
            return _fail("[%s] the two leaf directories form: %s" % (label, sorted(leaves)))
        if len(leaves[want["gated_dir"]]["write_set"]) != _GATED_FILES:
            return _fail("[%s] the gated leaf is its whole directory: %d" % (label, len(leaves[want["gated_dir"]]["write_set"])))
        if len(leaves[want["leaf_dir"]]["unit"]["symbols"]) != 4 or len(leaves[want["leaf_dir"]]["write_set"]) != 4:
            return _fail("[%s] the helper leaf unions four families over four files: %s" % (label, leaves[want["leaf_dir"]]["unit"]))

        # (a) WU-3: five independent web symbols are five units, not one
        families = {c["unit"]["family_key"]: c for c in by_rule.get(RULE_DIAGNOSTIC_FAMILY, [])}
        for sym in want["web"]:
            if sym not in families:
                return _fail("[%s] each web symbol is its own family: %s missing from %s" % (label, sym, sorted(families)))
        if want["spanning"] not in families:
            return _fail("[%s] a family spanning two directories is (a), never a leaf: %s" % (label, sorted(families)))
        if len(families) != len(want["web"]) + 1:
            return _fail("[%s] no other family forms: %s" % (label, sorted(families)))

        # (b) WU-5: the set the platform names one member of becomes a unit
        frag = [c for c in by_rule.get(RULE_DECLARATION_CLOSURE, []) if c["unit"]["family_key"].startswith("spring-data-fragment-implementations:")]
        if len(frag) != 1 or sorted(frag[0]["write_set"]) != want["frag_write_set"]:
            return _fail("[%s] the fragment set is one unit whose write set is the parents and the adapters they owe: %s"
                         % (label, sorted(frag[0]["write_set"]) if frag else [c["unit"]["family_key"] for c in frag]))
        if len(frag[0]["unit"]["symbols"]) != want["frag_n"]:
            return _fail("[%s] one symbol per unimplemented member: %s" % (label, frag[0]["unit"]["symbols"]))
        # the NEW path each parent owes, named before it exists, with the
        # contract that names it and the parent it must implement
        owed = frag[0]["unit"].get("implementation") or []
        if sorted(r["path"] for r in owed) != want["frag_adapters"]:
            return _fail("[%s] every parent owed an implementation names the file that will carry it: %s" % (label, owed))
        if any(not r.get("contract") or not r.get("source") or not r.get("members") for r in owed):
            return _fail("[%s] and each carries its naming contract and what it owes: %s" % (label, owed[:1]))
        if any(r["type"] != r["parent"] + "Impl" for r in owed):
            return _fail("[%s] the type is derived from the parent's own name, never chosen: %s" % (label, owed[:1]))
        # the children are INVENTORY, never write set: the repair adds an
        # implementation, it does not edit the interfaces that inherit
        seal_paths = {str(m["path"]) for m in frag[0]["_unit_seal"]["members"]}
        if not set(want["frag_children"]) <= seal_paths:
            return _fail("[%s] every implementer stays in the inventory: %s" % (label, sorted(seal_paths)))
        if set(want["frag_children"]) & set(frag[0]["write_set"]):
            return _fail("[%s] an implementer this repair does not edit is not writable" % label)

        # R-1: a test source is never in a write set and never a unit member
        for c in units:
            if any(p.startswith("src/test/") for p in c["write_set"]) or any(str(m["path"]).startswith("src/test/") for m in c["_unit_seal"]["members"]):
                return _fail("[%s] a test source is never writable, for any unit: %s" % (label, c["unit"]["family_key"]))
        if any(i["id"] in claimed for i in items if str(i["path"]).startswith("src/test/")):
            return _fail("[%s] a test-only diagnostic is claimed by no unit" % label)

        # every unit is inside the bound, and every unit is an ORDINARY cluster
        for c in units:
            size = c["unit"]["size"]
            if size["files"] > UNIT_MAX_FILES or size["sites"] > UNIT_MAX_SITES or size["symbols"] > UNIT_MAX_SYMBOLS:
                return _fail("[%s] %s exceeds the bound: %s" % (label, c["unit"]["family_key"], size))
            if c["kind"] not in KIND_RANK or c["status"] not in ("open", "deferred", "blocked") or not c["id"].startswith("u:"):
                return _fail("[%s] a unit is an ordinary cluster: %s" % (label, {k: c[k] for k in ("id", "kind", "status")}))
            if not c["unit"]["completion"] or not c["unit"]["evidence"]:
                return _fail("[%s] every unit carries completion checks and evidence: %s" % (label, c["unit"]["family_key"]))
            if str(retry_key(dict(c, batch_scope={"kind": "unit", "unit_id": c["unit"]["unit_id"]}))) != "rk:unit:%s" % c["unit"]["unit_id"]:
                return _fail("[%s] a unit's budget is keyed to the unit, not the card" % label)

        # the documented target, and the counterexample it exists for
        targets = {t["to"] for c in units for t in c["unit"]["target_symbols"]}
        if label == "A":
            if "jakarta.ws.rs.core.Context" not in targets:
                return _fail("a sealed symbol with a catalog row carries its documented target: %s" % sorted(targets))
            if "jakarta.ws.rs.Context" in targets:
                return _fail("a target nobody documented is not a target (v9 t_3903f495)")
            row = [t for c in units for t in c["unit"]["target_symbols"] if t["to"] == "jakarta.ws.rs.core.Context"][0]
            if row["catalog_row"].get("catalog") != "compat-mapping.json" or not row["catalog_row"].get("block"):
                return _fail("a target names the catalog row that documents it: %s" % row)
        elif targets:
            return _fail("[B] a renamed world matches no catalog row, so it has no documented target: %s" % sorted(targets))

        # the set the model cannot enumerate stays the typed blocker it was
        bare, bare_claimed = form_units([_set_wide_item()], {}, set(), model={"types": []}, root=GOLDEN)
        if bare or bare_claimed:
            return _fail("[%s] a set the model cannot enumerate mints nothing; the blocker stands" % label)
        other, _ = form_units(items + [_set_wide_item("some-other-set")], {}, set(), model=model, root=GOLDEN)
        if any(c["unit"]["family_key"].startswith("some-other-set") for c in other):
            return _fail("[%s] only a scope RUNTIME_SET_WIDE_FORMER names may become a unit" % label)
    return 0


def _unit_bound_case() -> int:
    """Deterministic narrowing, then a typed blocker. Never an arbitrary
    file-order chunk: that is what makes a coordinated repair unrepresentable."""
    base = "org.acme.big"
    pkg = base.replace(".", "/")
    sym = "org.springframework.dao.DataAccessException"

    # one family, one group, more files than the bound: nothing to narrow
    wide_items = [_javac("src/main/java/%s/w/W%02d.java" % (pkg, i), "DataAccessException", i)
                  for i in range(UNIT_MAX_FILES + 5)]
    wide_types = [_dm_type("%s.w.W%02d" % (base, i), "%s/w/W%02d.java" % (pkg, i), imports=[sym],
                           type_refs=["%s.outside.Anchor" % base]) for i in range(UNIT_MAX_FILES + 5)]
    wide_types.append(_dm_type("%s.outside.Anchor" % base, "%s/outside/Anchor.java" % pkg,
                               type_refs=["%s.w.W00" % base]))
    units, _ = form_units(wide_items, {}, set(), model={"types": wide_types}, root=None)
    if len(units) != 1 or units[0]["status"] != "blocked":
        return _fail("a family wider than the bound is a blocked cluster: %s" % [(c["unit"]["family_key"], c["status"]) for c in units])
    block = units[0]["block"]
    if not block.startswith("UNIT_OVERSIZE: ") or "a repair this wide is a planning answer" not in block:
        return _fail("and the reason is typed and names the rule and the key: %r" % block)
    if len(units[0]["write_set"]) != UNIT_MAX_FILES + 5:
        return _fail("an oversize unit is never silently chunked: %d files" % len(units[0]["write_set"]))

    # a leaf of many small families narrows by dropping the LOWEST-cardinality
    # ones, deterministically, and records why
    many = []
    many_types = []
    for i in range(UNIT_MAX_SYMBOLS + 4):
        name = "L%02d" % i
        fqn = "org.springframework.sym.S%02d" % i
        many_types.append(_dm_type("%s.leaf.%s" % (base, name), "%s/leaf/%s.java" % (pkg, name), imports=[fqn]))
        # family i has i+1 sites, so the drop order is fixed by cardinality
        for k in range(i + 1):
            many.append(_javac("src/main/java/%s/leaf/%s.java" % (pkg, name), "S%02d" % i, 1000 * i + k))
    units, _ = form_units(many, {}, set(), model={"types": many_types}, root=None)
    leaf = [c for c in units if c["unit"]["rule"] == RULE_PACKAGE_LEAF]
    if len(leaf) != 1:
        return _fail("the leaf unions the families: %s" % [c["unit"]["rule"] for c in units])
    seal = leaf[0]["_unit_seal"]
    if seal["bounds"]["symbols"] > UNIT_MAX_SYMBOLS or "narrowed" not in seal["bounds"]:
        return _fail("narrowing brings the union inside the bound and records it: %s" % seal["bounds"])
    if seal["bounds"]["narrowed"]["reason"] != "UNIT_NARROWED" or seal["bounds"]["narrowed"]["from"]["symbols"] != UNIT_MAX_SYMBOLS + 4:
        return _fail("the narrowing records what it came from: %s" % seal["bounds"]["narrowed"])
    kept = {str(s["fqn"]) for s in seal["symbols"]}
    if "org.springframework.sym.S00" in kept or "org.springframework.sym.S11" not in kept:
        return _fail("the lowest-cardinality families are the ones dropped: %s" % sorted(kept))
    again, _ = form_units(list(reversed(many)), {}, set(), model={"types": list(reversed(many_types))}, root=None)
    twin = [c for c in again if c["unit"]["rule"] == RULE_PACKAGE_LEAF][0]
    if twin["id"] != leaf[0]["id"] or twin["write_set"] != leaf[0]["write_set"]:
        return _fail("narrowing is deterministic: %s vs %s" % (twin["id"], leaf[0]["id"]))
    if not any("UNIT_NARROWED" in str(e.get("ref")) for e in seal["evidence"]):
        return _fail("and it leaves an evidence line")

    # a closure over the bound PRESERVES its callers and refuses: a caller is
    # bound to the declaration the unit changes, so a narrowing that dropped it
    # would leave a unit that cannot compile, which is the failure the former
    # exists to prevent. The bound stands and the refusal is typed.
    svc = "%s.s.Wide" % base
    sig = "call(int)"
    ctypes = [_dm_type(svc, "%s/s/Wide.java" % pkg, kind="interface", imports=[sym],
                       declared=[_dm_member("call", sig, throws=[sym])]),
              _dm_type("%s.s.WideImpl" % base, "%s/s/WideImpl.java" % pkg, supertypes=[svc], imports=[sym],
                       declared=[_dm_member("call", sig, has_body=True, throws=[sym])], type_refs=[svc])]
    for i in range(UNIT_MAX_FILES + 3):
        ctypes.append(_dm_type("%s.c.C%02d" % (base, i), "%s/c/C%02d.java" % (pkg, i), imports=[sym, svc],
                               declared=[_dm_member("go", "go()", has_body=True, calls=["%s.%s" % (svc, sig)])],
                               type_refs=[svc]))
    citems = [_javac("src/main/java/%s/s/Wide.java" % pkg, "DataAccessException", 1)]
    units, _ = form_units(citems, {}, set(), model={"types": ctypes}, root=None)
    closure = [c for c in units if c["unit"]["rule"] == RULE_DECLARATION_CLOSURE]
    if len(closure) != 1 or closure[0]["status"] != "blocked":
        return _fail("a closure wider than the bound is refused, never narrowed by dropping callers: %s"
                     % [(c["unit"]["rule"], c["status"]) for c in units])
    block = closure[0]["block"]
    if not block.startswith("UNIT_OVERSIZE: ") or "callers are bound to the declaration" not in block:
        return _fail("and the refusal says why narrowing is not available here: %r" % block)
    paths = set(closure[0]["write_set"])
    if "src/main/java/%s/s/Wide.java" % pkg not in paths or "src/main/java/%s/s/WideImpl.java" % pkg not in paths:
        return _fail("the declaration and its implementers are in the refused unit: %s" % sorted(paths))
    callers = sorted(p for p in paths if p.startswith("src/main/java/%s/c/" % pkg))
    if len(callers) != UNIT_MAX_FILES + 3:
        return _fail("every caller is preserved in it: %d" % len(callers))
    if "narrowed" in closure[0]["_unit_seal"]["bounds"]:
        return _fail("nothing was dropped, so nothing is recorded as narrowed: %s" % closure[0]["_unit_seal"]["bounds"])

    # and a narrowing that DOES happen retains every obligation it excluded:
    # the dropped families' items are claimed by no unit, so the work list
    # still carries them as their own items
    dropped_units, dropped_claimed = form_units(many, {}, set(), model={"types": many_types}, root=None)
    leaf_seal = [c for c in dropped_units if c["unit"]["rule"] == RULE_PACKAGE_LEAF][0]["_unit_seal"]
    excluded = leaf_seal["bounds"].get("excluded") or []
    if not excluded or not all(r.get("items") for r in excluded):
        return _fail("a narrowing records the obligations it excluded: %s" % leaf_seal["bounds"])
    for row in excluded:
        for iid in row["items"]:
            if iid in dropped_claimed:
                return _fail("an excluded obligation is retained as its own item, never swallowed: %s" % iid)
    # and no file carrying an obligation the unit still measures is dropped
    kept_items = {str(i["id"]) for i in leaf_seal["items"]}
    for it in many:
        if str(it["id"]) in kept_items and str(it["path"]) not in set(leaf_seal["files"]):
            return _fail("a measured obligation always has a writable file: %s" % it["id"])
    return 0


def _unit_seal_case() -> int:
    """Files AND symbols, sealed at issue, at a path named by the seal's own
    digest. Two seals, two jobs: files are the hard boundary, symbols are the
    obligation boundary, and a reference written during the card widens
    neither."""
    import tempfile

    model, items, want = _unit_world(_WORLD_A)
    units, _ = form_units(items, {}, set(), model=model, root=GOLDEN)
    surface = [c for c in units if c["unit"]["family_key"].startswith(want["surface_key"])][0]
    with tempfile.TemporaryDirectory(prefix="unit-seal-") as d:
        root = Path(d)
        scope = build_unit_scope(root, surface, items, {"candidate_sha256": "abc"})
        if not scope:
            return _fail("a formed unit must produce a sealed inventory")
        missing = [k for k in ("schema", "kind", "rule", "unit_id", "family_key", "writable_paths", "symbols",
                               "target_symbols", "members", "evidence", "completion", "bounds", "measured",
                               "inputs", "digest", "cluster", "producer", "tool") if k not in scope]
        if missing:
            return _fail("the v4 seal is missing %s" % missing)
        if scope["schema"] != "rhoai3.batch-scope/v4" or scope["kind"] != "unit":
            return _fail("the seal names its schema and kind: %s %s" % (scope["schema"], scope["kind"]))
        if batch_scope_digest(scope) != scope["digest"]:
            return _fail("the seal must be reproducible from content alone")
        if scope["writable_paths"] != sorted(surface["write_set"]):
            return _fail("the FILE seal is the write set advance.py enforces: %s" % scope["writable_paths"])
        if not all({"kind", "fqn"} <= set(s) for s in scope["symbols"]):
            return _fail("every sealed symbol is typed: %s" % scope["symbols"])
        if not all({"path", "state"} <= set(m) for m in scope["members"]):
            return _fail("every member row says where it is and why: %s" % scope["members"][:2])
        if not all({"kind", "ref"} <= set(e) for e in scope["evidence"]):
            return _fail("every evidence line is typed: %s" % scope["evidence"][:2])
        if not all({"check", "tool"} <= set(c) for c in scope["completion"]):
            return _fail("every completion check names the tool that decides it: %s" % scope["completion"])
        if {c["check"] for c in scope["completion"]} < {"identities-gone", "unit-assessment"}:
            return _fail("the checks are derived from the members: %s" % [c["check"] for c in scope["completion"]])
        if scope["inputs"]["candidate_sha256"] != "abc" or scope["measured"] != sorted(surface["items"]):
            return _fail("the seal records what it was built from: %s" % scope["inputs"])

        first = batch_scope_path(scope)
        # a remeasurement of the same tree is a NEW inventory at a NEW path,
        # never a rewrite of the one the card was issued against
        moved = dict(surface)
        moved["_unit_seal"] = dict(surface["_unit_seal"])
        moved["_unit_seal"]["members"] = surface["_unit_seal"]["members"][:-1]
        second = build_unit_scope(root, moved, items, {"candidate_sha256": "def"})
        if second["digest"] == scope["digest"] or batch_scope_path(second) == first:
            return _fail("two inventories of one cluster must not share a path")
        if batch_scope_path(second).parent != first.parent:
            return _fail("both still belong to the same cluster's directory")

        # the budget is keyed to the PROBLEM: the same members under another
        # candidate keep one unit_id, a different member set is another problem
        same = build_unit_scope(root, surface, items, {"candidate_sha256": "zzz"})
        if same["unit_id"] != scope["unit_id"]:
            return _fail("unit_id survives remeasurement: %s vs %s" % (same["unit_id"], scope["unit_id"]))
        if unit_id_of(scope["rule"], scope["family_key"], scope["members"][:-1]) == scope["unit_id"]:
            return _fail("a different member set is a different problem")

        # a symbol the model gains AFTER the seal does not widen it
        widened = dict(model)
        widened["types"] = model["types"] + [_dm_type("org.acme.clinic.rest.Sneak", "org/acme/clinic/rest/Sneak.java",
                                                      imports=["org.springframework.security.SecurityConfig"])]
        later, _ = form_units(items, {}, set(), model=widened, root=GOLDEN)
        later_surface = [c for c in later if c["unit"]["family_key"].startswith(want["surface_key"])][0]
        if {s["fqn"] for s in later_surface["unit"]["symbols"]} != {s["fqn"] for s in scope["symbols"]}:
            return _fail("a type the candidate merely mentions does not enter the symbol seal")
    return 0


def _unit_mode_case() -> int:
    """The mode is a decision, and it may not flip under a live candidate."""
    import json
    import tempfile

    if unit_formation_mode({}) != "off" or unit_formation_mode({"loop": {"unit_formation": "v1"}}) != "v1":
        return _fail("absent means off; v1 means v1")
    if unit_formation_mode({"loop": {"unit_formation": "v2"}}) != "off":
        return _fail("an undeclared mode falls back to the one that changes nothing")
    with tempfile.TemporaryDirectory(prefix="unit-mode-") as d:
        root = Path(d)
        (root / "evidence" / "planning").mkdir(parents=True)
        (root / "verification" / "loop").mkdir(parents=True)
        decided = {"loop": {"unit_formation": "v1"}}
        if unit_formation_for(root, decided) != ("v1", ""):
            return _fail("with no previous list the decided mode stands")
        (root / "evidence" / "planning" / "worklist.json").write_text(json.dumps({"unit_formation": "off"}))
        mode, why = unit_formation_for(root, decided)
        if (mode, why) != ("v1", ""):
            return _fail("with no card issued the switch takes effect: %s %s" % (mode, why))
        (root / "verification" / "loop" / "issued.json").write_text(json.dumps({"cluster": "c:live"}))
        mode, why = unit_formation_for(root, decided)
        if mode != "off" or not why.startswith("UNIT_MODE_SWITCH: ") or "c:live" not in why:
            return _fail("a flip under an issued card is refused, naming the card: %s %s" % (mode, why))
        (root / "verification" / "loop" / "issued.json").unlink()
        (root / "verification" / "loop" / "steps.json").write_text(json.dumps({"pending": [{"cluster": "c:pend"}]}))
        mode, why = unit_formation_for(root, decided)
        if mode != "off" or "c:pend" not in why:
            return _fail("an uncleared pending candidate refuses it too: %s %s" % (mode, why))
        (root / "verification" / "loop" / "steps.json").write_text(json.dumps({"pending": [{"cluster": "c:pend", "cleared": True}]}))
        if unit_formation_for(root, decided) != ("v1", ""):
            return _fail("a cleared row is a clean boundary")
    return 0


def _unit_inert_case() -> int:
    """With formation off, clustering is byte-for-byte what it was -- which is
    what lets this ship without disturbing the run already under way."""
    model, items, _want = _unit_world(_WORLD_A)
    depths = {}
    legacy = cluster_items(items, depths, set())
    if digest(cluster_items(items, depths, set(), units=[])) != digest(legacy):
        return _fail("the new keyword changes nothing when no unit is formed")
    if digest(cluster_items(items, depths, set(), units=None)) != digest(legacy):
        return _fail("and neither does its default")
    # the legacy path is exactly the 8-file chunking a unit replaces
    gated = _WORLD_A["gated"].rsplit(".", 1)[-1]
    chunks = sorted(c["label"] for c in legacy if str(c.get("label") or "").startswith(gated + "#"))
    if chunks != ["%s#1" % gated, "%s#2" % gated]:
        return _fail("legacy clustering still chunks a %d-file symbol group into %d-file pieces: %s"
                     % (_GATED_FILES, SYMBOL_CLUSTER_MAX_FILES, chunks))
    # and with units formed, the claimed items leave the legacy passes entirely
    units, claimed = form_units(items, depths, set(), model=model, root=GOLDEN)
    formed = cluster_items(items, depths, set(), units=units)
    if {c["id"] for c in units} - {c["id"] for c in formed}:
        return _fail("a formed unit is one of the clusters")
    seen = [i for c in formed if c["id"] not in {u["id"] for u in units} for i in c["items"]]
    if set(seen) & claimed:
        return _fail("an item a unit took never reaches the per-file pass: %s" % sorted(set(seen) & claimed)[:3])
    if sorted(i for c in formed for i in c["items"]) != sorted(i["id"] for i in items):
        return _fail("and nothing is lost: clustering is still total")
    return 0


def _unit_experiment_table_case() -> int:
    """The design's table (experiments/rgctl-2026-09-15/WORK-UNITS.md, 11 units)
    as assertions, where this fixture can express them: 5 reproduce, 3 split,
    2 are Operator work the planner must NOT mint, 1 is correctly unreachable."""
    model, items, want = _unit_world(_WORLD_A)
    units, claimed = form_units(items + [_set_wide_item()], {}, set(), model=model, root=GOLDEN)
    by_key = {c["unit"]["family_key"]: c for c in units}
    rules = _by_rule(units)

    # WU-1 reproduced: one unit, and it is the unit today's loop cannot express
    surface = [c for c in units if c["unit"]["family_key"].startswith(want["surface_key"])]
    if len(surface) != 1 or len(surface[0]["write_set"]) != 5:
        return _fail("WU-1 reproduces as one coordinated unit: %s" % [(c["unit"]["family_key"], len(c["write_set"])) for c in surface])
    # WU-2 splits into two: the gated leaf, and the family that spans two directories
    if want["gated_dir"] not in by_key or want["spanning"] not in by_key:
        return _fail("WU-2 splits into a leaf and a spanning family: %s" % sorted(by_key))
    if by_key[want["gated_dir"]]["unit"]["rule"] != RULE_PACKAGE_LEAF or by_key[want["spanning"]]["unit"]["rule"] != RULE_DIAGNOSTIC_FAMILY:
        return _fail("and each under its own rule, with its own symbol seal and its own budget")
    if by_key[want["gated_dir"]]["unit"]["unit_id"] == by_key[want["spanning"]]["unit"]["unit_id"]:
        return _fail("two units, two budgets")
    # WU-3 splits into five, one per symbol
    web = [c for c in rules.get(RULE_DIAGNOSTIC_FAMILY, []) if c["unit"]["family_key"] in set(want["web"])]
    if len(web) != 5:
        return _fail("WU-3 splits into five independently checkpointable units: %d" % len(web))
    # WU-3 / R-1 unreachable, correctly: a test source is never writable
    if any(p.startswith("src/test/") for c in units for p in c["write_set"]):
        return _fail("R-1 stays unreachable: a test source is never writable, for any unit, for any evidence")
    # WU-4 reproduced by the leaf rule, decided by type_refs and not by a name
    if want["leaf_dir"] not in by_key or by_key[want["leaf_dir"]]["unit"]["rule"] != RULE_PACKAGE_LEAF:
        return _fail("WU-4 reproduces as a package leaf: %s" % sorted(by_key))
    # WU-5 reproduced -- the new capability: today this mints no card at all
    frag = [c for c in units if c["unit"]["family_key"].startswith("spring-data-fragment-implementations:")]
    if len(frag) != 1 or "rt:boot:setwide" not in claimed:
        return _fail("WU-5 becomes a mintable unit, and the set-wide row is its obligation")
    # WU-6 / WU-11 are ADR-shaped: nothing javac or the model states, so the
    # former mints nothing for them
    adr_only, adr_claimed = form_units([{"id": "rt:boot:adr", "source": "runtime", "gate": "boot", "kind": "config",
                                         "cause": "unclassified", "set_wide": "", "unlocated": True, "path": "",
                                         "category": "mandatory", "line": 0, "rule_id": "R", "message": "security is enabled"}],
                                       {}, set(), model=model, root=GOLDEN)
    if adr_only or adr_claimed:
        return _fail("WU-6 / WU-11 are Operator steps, not planner units")
    # WU-7 / WU-8: one obligation at one locus, and a gate obligation, stay the
    # single cards they already are -- a unit needs more than one locus
    single, single_claimed = form_units([_javac("src/main/java/org/acme/clinic/rest/OwnerRestController.java", "Lonely", 1)],
                                        {}, set(), model=model, root=GOLDEN)
    if single or single_claimed:
        return _fail("WU-7 / WU-8 stay one card: a lone locus forms no unit")
    # WU-9 is reproducible now: the query-invalid rows are in RUNTIME_CAUSES and
    # stand BEFORE the generic schema rows, so a Hibernate 6 strictness failure
    # is a query defect at the fragment that declares the query and not a
    # missing table at application.properties
    for text in ("org.hibernate.query.SemanticException: could not resolve attribute 'x'",
                 "jakarta.persistence.PersistenceException: QuerySyntaxException: unexpected token",
                 "could not resolve attribute 'x' -- relation \"y\" does not exist"):
        if runtime_cause(text) != "query-invalid":
            return _fail("WU-9 needs the query-invalid cause, before the schema rows: %r → %s" % (text[:40], runtime_cause(text)))
    # and the closed vocabulary is not widened: a genuine missing table is still
    # a missing table
    if runtime_cause("ERROR: relation \"owners\" does not exist") != "schema-missing-object":
        return _fail("the schema cause must survive: %s" % runtime_cause("ERROR: relation \"owners\" does not exist"))
    # WU-10 splits into its distinct causes: three parity causes are three
    # problems in three places, and the former unions none of them
    return 0



# --- the checkpoint -------------------------------------------------------
#
# The v9 counterexample in the shape the catalogue records it: a unit over a
# retired Spring type whose DOCUMENTED target is jakarta.ws.rs.core.UriBuilder,
# reached through an injected jakarta.ws.rs.core.Context. The right repair and
# the wrong import differ by one package segment, and the whole relaxation is
# only safe because the catalogue knows which of the two it wrote down.
_URI_A = {"base": "org.acme.clinic", "pkg": "rest", "controllers": ("OwnerRestController", "PetRestController"),
          "retired": "org.springframework.web.util.UriComponentsBuilder",
          "target": "jakarta.ws.rs.core.UriBuilder", "typo": "jakarta.ws.rs.Context",
          "unrelated": "org.springframework.validation.BindingResult"}
_URI_B = {"base": "com.example.warehouse", "pkg": "api", "controllers": ("CrateEndpoint", "PalletEndpoint"),
          "retired": "org.springframework.web.util.UriComponentsBuilder",
          "target": "jakarta.ws.rs.core.UriBuilder", "typo": "jakarta.ws.rs.Context",
          "unrelated": "org.springframework.validation.BindingResult"}


def _uri_world(n: dict, imports: tuple[str, ...]) -> tuple[dict, list[str]]:
    """(a model whose controllers carry exactly these imports, their paths)."""
    pkg = n["base"].replace(".", "/")
    types, paths = [], []
    for c in n["controllers"]:
        rel = "%s/%s/%s.java" % (pkg, n["pkg"], c)
        types.append(_dm_type("%s.%s.%s" % (n["base"], n["pkg"], c), rel, imports=list(imports)))
        paths.append("src/main/java/" + rel)
    return {"types": types}, paths


def _uri_unit(n: dict) -> tuple[dict, list[dict], list[str]]:
    """(the sealed v4 inventory of the unit, its items, its files)."""
    import tempfile

    model, paths = _uri_world(n, (n["retired"],))
    items = [_javac(p, n["retired"].rsplit(".", 1)[-1], i) for i, p in enumerate(paths)]
    units, _claimed = form_units(items, {}, set(), model=model, root=GOLDEN)
    # one family, one directory nothing outside refers to: the leaf rule claims
    # it, and its sealed symbol is the retired type either way
    unit = units[0]
    with tempfile.TemporaryDirectory(prefix="unit-explain-") as d:
        scope = build_unit_scope(Path(d), unit, items, {"candidate_sha256": "c0"})
    return scope, items, paths


def _leaf_unit(n: dict) -> tuple[dict, list[str]]:
    """A package leaf sealing TWO symbols: one controller per family, in one
    directory nothing outside refers to."""
    import tempfile

    pkg = n["base"].replace(".", "/")
    types, paths, items = [], [], []
    for i, (c, sym) in enumerate(zip(n["controllers"], (n["retired"], n["unrelated"]))):
        rel = "%s/%s/%s.java" % (pkg, n["pkg"], c)
        types.append(_dm_type("%s.%s.%s" % (n["base"], n["pkg"], c), rel, imports=[sym]))
        paths.append("src/main/java/" + rel)
        items.append(_javac(paths[-1], sym.rsplit(".", 1)[-1], 70 + i))
    units, _ = form_units(items, {}, set(), model={"types": types}, root=GOLDEN)
    leaf = next(c for c in units if c["unit"]["rule"] == RULE_PACKAGE_LEAF)
    with tempfile.TemporaryDirectory(prefix="unit-leaf-") as d:
        return build_unit_scope(Path(d), leaf, items, {"candidate_sha256": "c1"}), paths


def _unit_explained_case() -> int:
    """The partition the veto and the checkpoint share: a diagnostic is
    explained only by a sealed symbol or by a DOCUMENTED target, and the
    documented one is the exact name the catalogue wrote down."""
    for label, n in (("A", _URI_A), ("B", _URI_B)):
        scope, _items, paths = _uri_unit(n)
        targets = {t["to"]: t for t in scope["target_symbols"]}
        if n["target"] not in targets or not targets[n["target"]].get("catalog_row"):
            return _fail("[%s] the seal must carry the catalogued target: %s" % (label, scope["target_symbols"]))

        # (1) the unit is still working on its own sealed symbol
        still_model, _ = _uri_world(n, (n["retired"],))
        still = [_javac(paths[0], n["retired"].rsplit(".", 1)[-1], 9)]
        rows, why = unit_explained_regressions(scope, still, still_model)
        if why or [r["boundary"] for r in rows] != ["sealed"] or rows[0]["symbol"] != n["retired"]:
            return _fail("[%s] a diagnostic about the sealed symbol is explained by it: %s %s" % (label, rows, why))

        # (2) the RIGHT repair: the controllers now import the documented
        # target and the compiler names it because the extension is not on the
        # classpath yet. That gap is the next card, not a wider write set.
        good_model, _ = _uri_world(n, (n["target"],))
        good = [_javac(p, n["target"].rsplit(".", 1)[-1], 20 + i) for i, p in enumerate(paths)]
        rows, why = unit_explained_regressions(scope, good, good_model)
        if why or len(rows) != len(paths) or {r["boundary"] for r in rows} != {"target"}:
            return _fail("[%s] a catalogued target explains what it replaced: %s %s" % (label, rows, why))
        if not all(r["catalog_row"].get("key") for r in rows):
            return _fail("[%s] an explained regression names the catalogue row that documents it: %s" % (label, rows))

        # (3) THE COUNTEREXAMPLE (v9 t_3903f495): the right repair with the
        # wrong import. jakarta.ws.rs.core.Context has a catalogue row and
        # jakarta.ws.rs.Context does not, so nothing explains it.
        bad_model, _ = _uri_world(n, (n["typo"],))
        bad = [_javac(p, n["typo"].rsplit(".", 1)[-1], 30 + i) for i, p in enumerate(paths)]
        rows, why = unit_explained_regressions(scope, bad, bad_model)
        if rows:
            return _fail("[%s] an invented replacement is explained by nothing: %s" % (label, rows))

        # (4) without the model nothing resolves, and a bare name matched by
        # spelling is exactly the mistake this rule exists to refuse
        rows, why = unit_explained_regressions(scope, still, None)
        if rows or "model is unavailable" not in why:
            return _fail("[%s] no model, no explanation: %s %s" % (label, rows, why))

        # (5) a file outside the FILE seal is never explained, whatever it names
        out_model, out_paths = _uri_world(dict(n, pkg="elsewhere"), (n["retired"],))
        rows, why = unit_explained_regressions(scope, [_javac(out_paths[0], n["retired"].rsplit(".", 1)[-1], 40)], out_model)
        if rows:
            return _fail("[%s] the file seal is the first condition: %s" % (label, rows))

        # (6) a diagnostic about something the unit never sealed is explained by
        # nothing at all -- it is not tolerated, it is simply not covered
        two_model, _ = _uri_world(n, (n["retired"], n["unrelated"]))
        rows, why = unit_explained_regressions(scope, [_javac(paths[0], n["unrelated"].rsplit(".", 1)[-1], 50)], two_model)
        if rows or why:
            return _fail("[%s] an unsealed symbol explains nothing: %s %s" % (label, rows, why))

        # (7) and where a unit DOES seal two symbols (a package leaf unions its
        # families), carrying both through one checkpoint would launder a
        # second defect: the WHOLE tolerated set is refused, not the surplus.
        leaf_scope, leaf_paths = _leaf_unit(n)
        leaf_model, _ = _uri_world(n, (n["retired"], n["unrelated"]))
        both = [_javac(leaf_paths[0], n["retired"].rsplit(".", 1)[-1], 60),
                _javac(leaf_paths[1], n["unrelated"].rsplit(".", 1)[-1], 61)]
        rows, why = unit_explained_regressions(leaf_scope, both, leaf_model)
        if rows or "different symbol families" not in why:
            return _fail("[%s] a unit carries its OWN family through its checkpoint and nothing else: %s %s" % (label, rows, why))
    return 0


def _measure(tup: list[int]) -> dict:
    return {"tuple": list(tup), "known": True, "blocked": []}


def _unit_progress_case() -> int:
    """The checkpoint itself: what it accepts, what it continues, and every
    thing it still refuses."""
    scope, _items, paths = _uri_unit(_URI_A)
    issued = {str(m["identity"]) for m in scope["members"] if m.get("identity")}
    if not issued:
        return _fail("the fixture unit must seal identities")
    ok_rows = [{"member": m["path"], "verdict": "ok", "detail": "d"} for m in scope["members"]]
    same = _measure([0, len(issued), 0])

    def run(cur_measure, cur_ids, **kw):
        return progress(same, cur_measure, set(), set(),
                        unit_scope=scope, unit_assessment=kw.pop("assessment", ok_rows),
                        issued_identities=issued, cur_identities=cur_ids,
                        explained=kw.pop("explained", set()), **kw)

    # DISCHARGED with the tuple unchanged: the whole point. The count did not
    # fall because the unit traded its diagnostics for ones its own catalogued
    # target explains, and every sealed member assesses clean.
    later = {"diag:later:%d" % i for i in range(len(issued))}
    okd, reason = run(_measure([0, len(issued), 0]), later, explained=later)
    if okd is not True or "explained_regressions" not in reason:
        return _fail("a discharged unit with an unchanged tuple is ACCEPTED: %s %s" % (okd, reason))
    # and even when the compile slot is temporarily WORSE
    okd, reason = run(_measure([0, len(issued) + 3, 0]), later, explained=later)
    if okd is not True:
        return _fail("the compile slot may stand still or briefly rise for what the unit explains: %s" % reason)
    # the ordinary fall is still the ordinary fall
    okd, reason = run(_measure([0, 0, 0]), set())
    if okd is not True or "discharged at its checkpoint" not in reason:
        return _fail("a unit whose measure fell is accepted as before: %s %s" % (okd, reason))

    # ONE MEMBER REMAINING: the compiler names another site of the same unit,
    # which is the unit's own remaining work and not a new defect.
    nxt = [{"id": "err:next", "source": "javac", "kind": "compile", "path": paths[0], "line": 4,
            "identity": "diag:next", "rule_id": "compiler.err.unreported.exception.need.to.catch.or.throw",
            "category": "mandatory", "message": "unreported exception"}]
    cont = unit_continue_scope(scope, nxt)
    if cont != {"diag:next"}:
        return _fail("the continuation scope is a sealed member's own file: %s" % cont)
    okd, reason = run(_measure([0, len(issued), 0]), {"diag:next"}, family_scope=cont)
    if okd is not RETAIN or "another member of the same unit" not in reason:
        return _fail("the compiler naming the next member of the unit CONTINUES the card: %s %s" % (okd, reason))

    # OUTSIDE THE SEALED SYMBOLS: not accepted, and not silently continued
    outside = unit_continue_scope(scope, [{"id": "err:o", "source": "javac", "path": "src/main/java/other/X.java",
                                           "identity": "diag:outside", "kind": "compile"}])
    okd, reason = run(_measure([0, len(issued), 0]), {"diag:outside"}, family_scope=outside)
    if okd is not EXPOSED or "do not explain" not in reason:
        return _fail("a diagnostic the sealed symbols do not explain is never accepted: %s %s" % (okd, reason))

    # THE COUNTEREXAMPLE, at the checkpoint: the typo explains nothing, so the
    # empty explained set leaves it unexplained and the card is not accepted.
    bad_model, _ = _uri_world(_URI_A, (_URI_A["typo"],))
    bad = [_javac(p, _URI_A["typo"].rsplit(".", 1)[-1], 60 + i) for i, p in enumerate(paths)]
    explained, _why = unit_explained_regressions(scope, bad, bad_model)
    okd, reason = run(_measure([0, len(issued), 0]), {str(i["identity"]) for i in bad},
                      explained={r["identity"] for r in explained})
    if okd is True:
        return _fail("the wrong import must not be accepted by the relaxation: %s" % reason)

    # WHAT IS NOT RELAXED
    okd, reason = run(_measure([0, 0, 1]), set())
    if okd is not False or "failing-test" not in reason:
        return _fail("a regressed test slot refuses however discharged the unit is: %s %s" % (okd, reason))
    okd, reason = run(_measure([1, 0, 0]), set())
    if okd is not False or "mandatory-incident" not in reason:
        return _fail("a regressed incident slot refuses: %s %s" % (okd, reason))
    okd, reason = run(_measure([0, 0, 0]), issued)
    if okd is not False or "still reports" not in reason:
        return _fail("one of the unit's own sealed diagnostics still reported refuses: %s %s" % (okd, reason))
    bad_rows = ok_rows[:-1] + [{"member": "M", "verdict": "violates", "detail": "the member is gone"}]
    okd, reason = run(_measure([0, 0, 0]), set(), assessment=bad_rows)
    if okd is not False or "still violate" not in reason:
        return _fail("a sealed member that violates its rule refuses: %s %s" % (okd, reason))
    unk_rows = ok_rows[:-1] + [{"member": "M", "verdict": "inconclusive", "detail": "unresolved"}]
    okd, reason = run(_measure([0, 0, 0]), set(), assessment=unk_rows)
    if okd is not UNPROVEN or "not one that passed" not in reason:
        return _fail("an assessment that could not be made is retained, not accepted: %s %s" % (okd, reason))
    okd, reason = run(_measure([0, 0, 0]), set(),
                      prev_runtime={"boot": {"ran": True, "rc": 0, "ready": True}},
                      cur_runtime={"boot": {"ran": True, "rc": 1, "ready": False}})
    if okd is not False or "may not break a phase" not in reason:
        return _fail("a gate going backwards refuses: %s %s" % (okd, reason))

    # and a card with NO unit seal is judged exactly as it was
    plain = progress(same, _measure([0, len(issued), 0]), set(), set())
    if plain[0] is not False or "did not decrease" not in plain[1]:
        return _fail("without a unit seal nothing changes: %s" % (plain,))
    return 0


def _unit_budget_case() -> int:
    """One budget per PROBLEM: the retry key is the unit id, and planner.budget
    counts against it across remeasurement and revision."""
    from planner.budget import budget as _budget

    scope, _items, _paths = _uri_unit(_URI_A)
    cluster = {"id": "u:whatever", "items": [], "batch_scope": {"kind": "unit", "unit_id": scope["unit_id"]}}
    key = retry_key(cluster, [])
    if key != "rk:unit:%s" % scope["unit_id"]:
        return _fail("a unit counts against its unit_id: %s" % key)
    # the SAME problem after a remeasurement is a different cluster id and the
    # same key, so a re-plan does not hand it a fresh budget
    remeasured = {"id": "u:another", "items": [], "batch_scope": {"kind": "unit", "unit_id": scope["unit_id"]}}
    if retry_key(remeasured, []) != key:
        return _fail("the key must survive remeasurement: %s" % retry_key(remeasured, []))
    steps = {"attempts": {key: 2}, "retry_keys": {"u:whatever": key}}
    b = _budget(steps, "u:whatever", key, 3)
    if b["retry_key"] != key or b["spent"] != 2 or b["left"] != 1:
        return _fail("planner.budget must read the unit key: %s" % b)
    # an amendment changes neither the key nor what it has spent
    if _budget(steps, "u:another", key, 3)["spent"] != 2:
        return _fail("a revision never resets the budget: %s" % _budget(steps, "u:another", key, 3))
    return 0


def _unit_config_case() -> int:
    """(d) a configuration property and the code that reads it: one unit over
    the property file and every annotated consumer, on two worlds that share
    no identifier."""
    import tempfile

    for label, prop, base, field in (("A", "app.root.path", "org.acme.clinic", "contextPath"),
                                     ("B", "depot.base.uri", "com.example.warehouse", "baseUri")):
        pkg = base.replace(".", "/")
        with tempfile.TemporaryDirectory(prefix="unit-cfg-") as d:
            root = Path(d)
            res = root / "src" / "main" / "resources"
            res.mkdir(parents=True)
            (res / "application.properties").write_text("# a comment\n%%prod.%s=/x\nother.key=1\n" % prop, encoding="utf-8")
            (res / "application-other.properties").write_text("unrelated=1\n", encoding="utf-8")
            readers = []
            types = []
            for i in range(2):
                name = "Reader%d" % i
                types.append(dict(_dm_type("%s.web.%s" % (base, name), "%s/web/%s.java" % (pkg, name)),
                                  fields=[{"name": field, "type": "java.lang.String",
                                           "annotations": [{"fqn": SPRING_VALUE, "simple": "Value",
                                                            "named": {"value": [prop]}, "resolution": "full"}]}]))
                readers.append("src/main/java/%s/web/%s.java" % (pkg, name))
            item = {"id": "rt:boot:cfg", "source": "runtime", "gate": "boot", "kind": "config",
                    "cause": "config-value", "set_wide": "", "path": "src/main/resources/application.properties",
                    "category": "mandatory", "line": 0, "rule_id": "RUNTIME_APPLICATION_CONFIGURATION",
                    "message": "Failed to load config value of type class java.lang.String for: %s" % prop}
            units, claimed = form_units([item], {}, set(), model={"types": types}, root=root)
            cfg = [c for c in units if c["unit"]["rule"] == RULE_CONFIG_CONSUMERS]
            if len(cfg) != 1 or "rt:boot:cfg" not in claimed:
                return _fail("[%s] one unit over the property and its consumers: %s" % (label, [c["unit"]["rule"] for c in units]))
            unit = cfg[0]
            if unit["unit"]["family_key"] != prop:
                return _fail("[%s] the property name is the family key: %s" % (label, unit["unit"]["family_key"]))
            if sorted(unit["write_set"]) != sorted(readers + ["src/main/resources/application.properties"]):
                return _fail("[%s] the write set is the property file AND the annotation sites: %s" % (label, unit["write_set"]))
            if "src/main/resources/application-other.properties" in unit["write_set"]:
                return _fail("[%s] a properties file that does not declare the key is not in scope" % label)
            if [s["kind"] for s in unit["unit"]["symbols"]] != ["property"]:
                return _fail("[%s] the sealed symbol is the property: %s" % (label, unit["unit"]["symbols"]))
            states = {str(m["state"]) for m in unit["_unit_seal"]["members"]}
            if states != {"reads", "declares-property"}:
                return _fail("[%s] each member says whether it declares or reads the property: %s" % (label, sorted(states)))
            if unit.get("gate") != "boot" or not any(c["check"] == "gate" for c in unit["_unit_seal"]["completion"]):
                return _fail("[%s] a gate obligation carries its gate as a completion check: %s" % (label, unit["_unit_seal"]["completion"]))
            # nothing reads it: no consumer, no unit, and today's path stands
            alone, alone_claimed = form_units([item], {}, set(), model={"types": []}, root=root)
            if alone or alone_claimed:
                return _fail("[%s] a property with no annotated consumer forms no unit" % label)
    return 0


# --- the real model, end to end -------------------------------------------
#
# Everything above models the destination with hand-written rows. That is what
# let four defects through: the REAL extractor records a type's references under
# its declared members, not on the type row, and a hand-written row that carries
# type-level `type_refs` is a shape the tool never emits. So these cases build a
# Java tree, run the JDK extractor over it, and ask the producer, the planner
# and the assessor the same questions with nothing simulated between them.

_REAL_A = {"base": "org.acme.clinic", "frag_pkg": "repo.custom", "store_pkg": "repo", "leaf_pkg": "util",
           "api_pkg": "rest", "frag": "OwnerHistory", "store": "OwnerRepository", "consumer": "OwnerResource",
           "member": "lookupByCustomClause", "helper_a": "SortDefinition", "helper_b": "ToStringCreator",
           "sym": "MutableSortDefinition"}
_REAL_B = {"base": "com.example.warehouse", "frag_pkg": "mixin.extra", "store_pkg": "mixin",
           "leaf_pkg": "helper", "api_pkg": "api", "frag": "CrateLedger", "store": "CrateStore",
           "consumer": "CrateEndpoint", "member": "resolveByHandwrittenClause", "helper_a": "OrderSpec",
           "helper_b": "DescriptionMaker", "sym": "AttributeRanker"}


def _jdk_root(d, files: dict[str, str]):
    """A destination tree the real extractor can model."""
    root = Path(d)
    (root / ".hermes").mkdir(parents=True, exist_ok=True)
    (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}')
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _real_sources(n: dict, *, consumer: bool) -> dict[str, str]:
    base, src = n["base"], "src/main/java/" + n["base"].replace(".", "/")
    frag = "%s.%s.%s" % (base, n["frag_pkg"], n["frag"])
    files = {
        # the fragment parent: a member no implementer answers
        "%s/%s/%s.java" % (src, n["frag_pkg"].replace(".", "/"), n["frag"]):
            "package %s.%s;\nimport java.util.List;\npublic interface %s {\n    List<String> %s(String clause);\n}\n"
            % (base, n["frag_pkg"], n["frag"], n["member"]),
        # the child, in ANOTHER package, so it must IMPORT the parent it extends.
        # This is the shape the architect reproduced: a required declaration,
        # which an assessor that asks every sealed symbol to disappear calls a
        # retired symbol still named.
        "%s/%s/%s.java" % (src, n["store_pkg"].replace(".", "/"), n["store"]):
            "package %s.%s;\nimport %s;\npublic interface %s extends %s {\n}\n"
            % (base, n["store_pkg"], frag, n["store"], n["frag"]),
        # two helpers in one directory: the leaf candidate
        "%s/%s/%s.java" % (src, n["leaf_pkg"], n["helper_a"]):
            "package %s.%s;\npublic class %s {\n    public int rank() { return 1; }\n}\n" % (base, n["leaf_pkg"], n["helper_a"]),
        "%s/%s/%s.java" % (src, n["leaf_pkg"], n["helper_b"]):
            "package %s.%s;\npublic class %s {\n    public String render() { return \"\"; }\n}\n" % (base, n["leaf_pkg"], n["helper_b"]),
    }
    if consumer:
        # the outside consumer names a leaf type ONLY in a member signature,
        # fully qualified, so there is no import either: the sole evidence is
        # declared[].type_refs, which is where the extractor puts it
        files["%s/%s/%s.java" % (src, n["api_pkg"], n["consumer"])] = (
            "package %s.%s;\npublic class %s {\n    public %s.%s.%s pick() { return null; }\n}\n"
            % (base, n["api_pkg"], n["consumer"], base, n["leaf_pkg"], n["helper_a"]))
    return files


def _real_items(n: dict) -> list[dict]:
    src = "src/main/java/" + n["base"].replace(".", "/")
    return [_javac("%s/%s/%s.java" % (src, n["leaf_pkg"], n["helper_a"]), n["sym"], 1),
            _javac("%s/%s/%s.java" % (src, n["leaf_pkg"], n["helper_b"]), n["sym"], 2)]


def _real_leaf_case() -> int:
    """An outside consumer prevents a false leaf — asked of the model the JDK
    extractor actually writes, where references live under declared members.

    With the consumer, no leaf may form; without it, one must. A property check
    that matches nothing passes vacuously, so the control runs too."""
    import tempfile

    from planner.worklist import unit_states_relationships, unit_type_refs

    for label, n in (("A", _REAL_A), ("B", _REAL_B)):
        leaf_dir = "src/main/java/%s/%s" % (n["base"].replace(".", "/"), n["leaf_pkg"])
        for consumer in (True, False):
            with tempfile.TemporaryDirectory(prefix="wl-real-leaf-") as d:
                root = _jdk_root(d, _real_sources(n, consumer=consumer))
                model = dest_model(root)
                # the shape itself: the extractor writes no type-level type_refs,
                # and the reference is under the member
                if consumer:
                    con = next(t for t in model["types"] if str(t["fqn"]).endswith("." + n["consumer"]))
                    if con.get("type_refs"):
                        return _fail("[%s] the real extractor writes no type-level type_refs: %s" % (label, con.get("type_refs")))
                    if not any(str(n["helper_a"]) in str(r) for m in con["declared"] for r in (m.get("type_refs") or [])):
                        return _fail("[%s] the reference is under the declared member: %s" % (label, con["declared"]))
                    if not any(str(x).endswith("." + n["helper_a"]) for x in unit_type_refs(con)):
                        return _fail("[%s] and unit_type_refs must see it: %s" % (label, sorted(unit_type_refs(con))))
                units, _claimed = form_units(_real_items(n), {}, set(), model=model, root=GOLDEN)
                leaves = [c for c in units if c["unit"]["rule"] == RULE_PACKAGE_LEAF and c["unit"]["family_key"] == leaf_dir]
                if consumer and leaves:
                    return _fail("[%s] a member-level reference from another package prevents the leaf: %s"
                                 % (label, leaves[0]["write_set"]))
                if not consumer and not leaves:
                    return _fail("[%s] with nothing outside naming them, the helpers ARE a leaf: %s"
                                 % (label, [c["unit"]["rule"] for c in units]))
        # and isolation is never claimed on missing evidence: a type the
        # compiler could not finish states no relationships at all
        with tempfile.TemporaryDirectory(prefix="wl-real-leaf2-") as d:
            root = _jdk_root(d, _real_sources(n, consumer=False))
            model = dest_model(root)
            partial = [dict(t, resolution="partial") if not _dm_is_leaf(t, n) else t for t in model["types"]]
            if any(unit_states_relationships(t) for t in partial if not _dm_is_leaf(t, n)):
                return _fail("[%s] a partially resolved type states no relationships" % label)
            units, _ = form_units(_real_items(n), {}, set(), model={"types": partial}, root=GOLDEN)
            if [c for c in units if c["unit"]["rule"] == RULE_PACKAGE_LEAF]:
                return _fail("[%s] isolation is not established by a type that could not say what it names" % label)
    return 0


def _dm_is_leaf(typ: dict, n: dict) -> bool:
    return ("%s.%s." % (n["base"], n["leaf_pkg"])) in str(typ.get("fqn") or "")


def _real_fragment_case() -> int:
    """The fragment unit, end to end on the real model: formed, sealed with the
    implementation it owes, assessed before and after the adapter is written,
    and accepted only when its gate passes.

    Every verdict is repeated on a tree that shares no package, type, member or
    identifier with the first."""
    import tempfile

    for label, n in (("A", _REAL_A), ("B", _REAL_B)):
        base = n["base"]
        frag = "%s.%s.%s" % (base, n["frag_pkg"], n["frag"])
        src = "src/main/java/" + base.replace(".", "/")
        parent_path = "%s/%s/%s.java" % (src, n["frag_pkg"].replace(".", "/"), n["frag"])
        child_path = "%s/%s/%s.java" % (src, n["store_pkg"].replace(".", "/"), n["store"])
        adapter = "%s/%s/%sImpl.java" % (src, n["frag_pkg"].replace(".", "/"), n["frag"])
        with tempfile.TemporaryDirectory(prefix="wl-real-frag-") as d:
            root = _jdk_root(d, _real_sources(n, consumer=True))
            model = dest_model(root)
            items = _real_items(n) + [_set_wide_item()]
            units, claimed = form_units(items, {}, set(), model=model, root=GOLDEN)
            frags = [c for c in units if c["unit"]["family_key"].startswith("spring-data-fragment-implementations:")]
            if len(frags) != 1 or "rt:boot:setwide" not in claimed:
                return _fail("[%s] the real model enumerates the fragment set into one unit: %s"
                             % (label, [c["unit"]["family_key"] for c in units]))
            unit = frags[0]
            owed = unit["unit"].get("implementation") or []
            if [r["path"] for r in owed] != [adapter] or owed[0]["parent"] != frag:
                return _fail("[%s] the unit names the adapter it owes, derived from the parent: %s" % (label, owed))
            if sorted(unit["write_set"]) != sorted([parent_path, adapter]):
                return _fail("[%s] the write set is the parent and the file it owes: %s" % (label, sorted(unit["write_set"])))
            if child_path in unit["write_set"]:
                return _fail("[%s] the child this repair does not edit is inventory, not write set" % label)
            scope = build_unit_scope(root, unit, items, {"candidate_sha256": "c0"})
            if [r["path"] for r in (scope.get("implementation_obligations") or [])] != [adapter]:
                return _fail("[%s] and the SEAL carries the obligation, so nothing can be added to it later: %s" % (label, scope.keys()))

            # BEFORE the adapter: the obligation violates, and the child that
            # IMPORTS its required parent is ok. A sealed declaration is not a
            # retired symbol, and the architect reproduced exactly this.
            rows = {r["member"]: r for r in assess_unit(root, scope)}
            child = next(r for m, r in rows.items() if m.startswith(child_path))
            if child["verdict"] != "ok":
                return _fail("[%s] a child importing its required parent is not a residue: %s" % (label, child))
            owed_row = next(r for m, r in rows.items() if r.get("state") == "implementation")
            if owed_row["verdict"] != "violates" or "does not exist" not in owed_row["detail"]:
                return _fail("[%s] an unwritten adapter is an undischarged obligation: %s" % (label, owed_row))

            # an adapter that does NOT implement the parent is not the repair
            # the path was authorized for
            (root / adapter).write_text("package %s.%s;\npublic class %sImpl {\n}\n" % (base, n["frag_pkg"], n["frag"]),
                                        encoding="utf-8")
            wrong = next(r for r in assess_unit(root, scope) if r.get("state") == "implementation")
            if wrong["verdict"] != "violates" or "does not implement" not in wrong["detail"]:
                return _fail("[%s] the promised relationship is checked, not assumed: %s" % (label, wrong))

            # THE REPAIR: the adapter implements the parent and answers the
            # member it owed
            (root / adapter).write_text(
                "package %s.%s;\nimport java.util.List;\npublic class %sImpl implements %s {\n"
                "    public List<String> %s(String clause) { return List.of(); }\n}\n"
                % (base, n["frag_pkg"], n["frag"], n["frag"], n["member"]), encoding="utf-8")
            after = assess_unit(root, scope)
            bad = [r for r in after if r["verdict"] != "ok"]
            if bad:
                return _fail("[%s] a written adapter discharges the unit: %s" % (label, bad))

            # and the PARENT INTERFACE is preserved: severing the inheritance
            # the unit is built around is not a repair of it
            (root / child_path).write_text("package %s.%s;\npublic interface %s {\n}\n" % (base, n["store_pkg"], n["store"]),
                                           encoding="utf-8")
            severed = [r for r in assess_unit(root, scope) if r["verdict"] == "violates"]
            if not severed or "no longer implements" not in severed[0]["detail"]:
                return _fail("[%s] the inheritance the closure was formed on must survive: %s" % (label, severed))
            (root / child_path).write_text("package %s.%s;\nimport %s;\npublic interface %s extends %s {\n}\n"
                                           % (base, n["store_pkg"], frag, n["store"], n["frag"]), encoding="utf-8")
            clean = assess_unit(root, scope)

            # THE CHECKPOINT: the unit carries the boot gate, so it is accepted
            # only when that gate passes, and never on the assessment alone.
            flat, issued_ids = _measure([0, 0, 0]), {"rt:boot:setwide"}
            failing = {"boot": {"ran": True, "rc": 1}}
            passing = {"boot": {"ran": True, "rc": 0, "ready": True}}
            ok, why = progress(flat, flat, set(), set(), gate="boot", unit_scope=scope, unit_assessment=clean,
                               prev_runtime=failing, cur_runtime=failing, issued_items=sorted(issued_ids),
                               cur_gate_items=set(), issued_identities=set(), cur_identities=set())
            if ok:
                return _fail("[%s] a unit whose obligation is a gate is not discharged while the gate fails: %s" % (label, why))
            ok, why = progress(flat, flat, set(), set(), gate="boot", unit_scope=scope, unit_assessment=clean,
                               prev_runtime=failing, cur_runtime=passing, issued_items=sorted(issued_ids),
                               cur_gate_items=set(), issued_identities=set(), cur_identities=set())
            if ok is not True:
                return _fail("[%s] and IS discharged when it passes: %s" % (label, why))
            # the assessment still governs: a violating member refuses whatever
            # the gate says
            broken = list(clean) + [{"member": parent_path, "verdict": "violates", "detail": "the file is gone"}]
            ok, why = progress(flat, flat, set(), set(), gate="boot", unit_scope=scope, unit_assessment=broken,
                               prev_runtime=failing, cur_runtime=passing, issued_items=sorted(issued_ids),
                               cur_gate_items=set(), issued_identities=set(), cur_identities=set())
            if ok:
                return _fail("[%s] a passing gate does not excuse a violating member: %s" % (label, why))
            # and a gate that was passing may not be broken by this unit
            ok, why = progress(flat, flat, set(), set(), gate="boot", unit_scope=scope, unit_assessment=clean,
                               prev_runtime={"package": {"ran": True, "rc": 0}, "boot": {"ran": True, "rc": 1}},
                               cur_runtime={"package": {"ran": True, "rc": 1}, "boot": {"ran": True, "rc": 0}},
                               issued_items=sorted(issued_ids), cur_gate_items=set(),
                               issued_identities=set(), cur_identities=set())
            if ok or "was passing and is not any more" not in why:
                return _fail("[%s] an established passing gate is preserved across the checkpoint: %s" % (label, why))
    return 0


def _real_explained_case() -> int:
    """The two counterexamples, decided with the REAL model: the wrong import
    and the unresolved lookalike are both unexplained.

    Both diagnostics say `cannot find symbol: class <X>`; what separates them
    from the accepted case is only what the file's imports bind the token to,
    which is a question only the compiler model can answer."""
    import tempfile

    from planner.worklist import _symbol_match

    retired = "org.springframework.web.util.UriComponentsBuilder"
    target = "jakarta.ws.rs.core.UriBuilder"
    typo = "jakarta.ws.rs.Context"
    # the rule itself: resemblance decides nothing, an identity decides
    if _symbol_match("UriBuilder", "type", target) or _symbol_match("Context", "annotation", "jakarta.ws.rs.core.Context"):
        return _fail("an unqualified spelling matches no sealed identity")
    if _symbol_match(typo, "type", "jakarta.ws.rs.core.Context"):
        return _fail("a qualified name that is not the one written down is not it either")
    if not _symbol_match(target, "type", target) or not _symbol_match("jakarta.ws.rs.core", "package", target):
        return _fail("a qualified identity, and a package that contains it, still match")
    for label, (base, ctl) in (("A", ("org.acme.clinic", "OwnerRestController")),
                               ("B", ("com.example.warehouse", "CrateEndpoint"))):
        src = "src/main/java/" + base.replace(".", "/")
        rel = "%s/rest/%s.java" % (src, ctl)
        scope = {
            "schema": "rhoai3.batch-scope/v4", "kind": "unit", "rule": RULE_DIAGNOSTIC_FAMILY,
            "unit_id": "u:real", "family_key": retired, "writable_paths": [rel],
            "symbols": [{"kind": "type", "fqn": retired, "path": rel}],
            "target_symbols": [{"from": retired, "to": target,
                                "catalog_row": {"catalog": "compat-mapping.json", "block": "symbol_renames",
                                                "key": retired, "kind": "type"}}],
            "members": [{"path": rel, "type": "%s.rest.%s" % (base, ctl), "state": "reported"}],
        }

        def world(imports: tuple[str, ...], d) -> dict:
            files = {rel: "package %s.rest;\n%spublic class %s {\n}\n"
                          % (base, "".join("import %s;\n" % i for i in imports), ctl)}
            # the platform types the catalogued target names, so an import of
            # one binds to a type that is really there
            for fqn in (target, "jakarta.ws.rs.core.Context"):
                files["src/main/java/" + fqn.replace(".", "/") + ".java"] = (
                    "package %s;\npublic interface %s { }\n" % (fqn.rsplit(".", 1)[0], fqn.rsplit(".", 1)[-1]))
            return dest_model(_jdk_root(d, files))

        def ask(model: dict, token: str) -> list:
            item = dict(_javac(rel, token, 7), identity="diag:%s|%s" % (rel, token))
            rows, why = unit_explained_regressions(scope, [item], model)
            return rows if not why else []

        # (1) the wrong import: one package segment from the catalogued target,
        # and the catalogue wrote down the other one
        with tempfile.TemporaryDirectory(prefix="wl-real-exp1-") as d:
            if ask(world((typo,), d), "Context"):
                return _fail("[%s] an invented replacement is explained by nothing (v9 t_3903f495)" % label)
        # (2) the unresolved lookalike: nothing imports UriBuilder at all, so
        # the token names no type, whatever it is spelled like
        with tempfile.TemporaryDirectory(prefix="wl-real-exp2-") as d:
            if ask(world((), d), "UriBuilder"):
                return _fail("[%s] a simple name nobody bound is not the catalogued target" % label)
        # (3) the control, without which the two above pass vacuously: with the
        # documented target imported, the same diagnostic IS explained, and it
        # carries the catalogue row that documented it
        with tempfile.TemporaryDirectory(prefix="wl-real-exp3-") as d:
            rows = ask(world((target,), d), "UriBuilder")
            if len(rows) != 1 or rows[0]["symbol"] != target or rows[0]["boundary"] != "target":
                return _fail("[%s] a resolved catalogued target IS explained: %s" % (label, rows))
            if rows[0]["catalog_row"].get("key") != retired:
                return _fail("[%s] and names the row that documented it: %s" % (label, rows))
    return 0


def _owed_adapter_case() -> int:
    """ADR-019: a parity obligation OWED a harness adapter is sealed with the
    adapter's contract path and the configuration BEFORE editing; the CORS and
    the Content-Type obligations are separate units that never authorize each
    other; the rendered rows come from the SOURCE policy; the checkpoint
    assesses the installed bytes, the model's type and every rendered row."""
    import json
    import tempfile

    import response_adapters as ra
    from planner.paths import PARITY_DIR
    from planner.worklist import (RULE_OWED_ADAPTER, _assess_owed_adapter, owed_adapter_units,
                                  representation_diffs)

    fixture = Path(__file__).resolve().parents[2] / "skills" / "migration" / "restore-source-response-shape" / "fixtures" / "runtime"
    ep = "ep:org.example.shop.rest.ItemController#create():http"
    ep2 = "ep:org.example.shop.rest.ItemController#list():http"
    ctl = "src/main/java/org/example/shop/rest/ItemController.java"
    bundle = {"entry_points": [{"id": ep, "path": ctl}, {"id": ep2, "path": ctl}]}
    cors_path, media_path = ra.adapter_path(ra.CORS), ra.adapter_path(ra.MEDIA_TYPE)

    # the splitter keeps a parameter list together; a different media type is not a representation difference
    rep, rest = representation_diffs(["header content-type application/json;charset=UTF-8 vs application/json",
                                      "header content-type text/html vs application/json", "status 500 vs 200"])
    if len(rep) != 1 or rep[0]["extra"] != [("charset", "UTF-8")] or len(rest) != 2:
        return _fail("only a same-media-type parameter difference is a representation difference: %s | %s" % (rep, rest))

    with tempfile.TemporaryDirectory(prefix="owed-adapter-") as td:
        root = Path(td)
        (root / "evidence" / "structure").mkdir(parents=True)
        shutil.copy2(fixture / "evidence" / "structure" / "structure.json", root / "evidence" / "structure" / "structure.json")
        (root / "src" / "main" / "resources").mkdir(parents=True)
        (root / APP_PROPERTIES).write_text("quarkus.http.root-path=/shop/\nquarkus.http.cors.origins=http://stale.example\n", encoding="utf-8")
        pdir = root / PARITY_DIR
        (pdir / "scenarios").mkdir(parents=True)

        def w(rel, doc):
            (pdir / rel).write_text(json.dumps(doc), encoding="utf-8")

        w("receipt.json", {"schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL",
                           "cors": {"source_policies": ["crossorigin:7b1a3d9234cd"], "gaps": []}})
        w("scenarios/pre.json", {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": "sc:pre", "verdict": "FAIL",
                                 "reason": "header Access-Control-Allow-Origin http://client.example vs *; header Access-Control-Allow-Credentials false vs None"})
        w("scenarios/act.json", {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep2, "scenario": "sc:act", "verdict": "FAIL",
                                 "reason": "header Access-Control-Allow-Origin http://client.example vs *; header content-type application/json;charset=UTF-8 vs application/json"})
        w("scenarios/read.json", {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep2, "scenario": "sc:read", "verdict": "FAIL",
                                  "reason": "header content-type application/json;charset=UTF-8 vs application/json; status 500 vs 200"})
        items = parity_items(root, bundle)
        kinds = sorted((i["scenario"], i["rule_id"], i["path"]) for i in items)
        want = sorted([("sc:pre", "PARITY_CORS", cors_path), ("sc:act", "PARITY_CORS", cors_path),
                       ("sc:act", "PARITY_CONTENT_TYPE", media_path), ("sc:read", "PARITY_CONTENT_TYPE", media_path),
                       ("sc:read", "PARITY", ctl)])
        if kinds != want:
            return _fail("CORS, representation and response differences are three separate obligation kinds: %s" % kinds)
        cors_item = next(i for i in items if i["rule_id"] == "PARITY_CORS")
        if cors_item["advice"].get("rendered", {}).get("source_policies") != sorted(["crossorigin:7b1a3d9234cd", "crossorigin:3068ac3cbdd1"]):
            return _fail("the CORS advice carries the rendering of the SOURCE policy: %s" % cors_item["advice"].get("rendered"))
        if "content-type" in json.dumps(cors_item["detail"]).lower():
            return _fail("a CORS obligation never carries the Content-Type difference: %s" % cors_item["detail"])

        units, claimed = owed_adapter_units(items, root, {}, set())
        by_rule = {u["unit"]["family_key"]: u for u in units}
        cu, mu = by_rule.get("source-cors-response-adapter/v1"), by_rule.get("source-media-type-parameter-adapter/v1")
        if not cu or not mu or len(units) != 2:
            return _fail("one sealed unit per owed adapter: %s" % [u["unit"]["family_key"] for u in units])
        if cu["write_set"] != sorted([cors_path, APP_PROPERTIES]) or mu["write_set"] != sorted([media_path, APP_PROPERTIES]):
            return _fail("each unit's write set is its adapter's contract path and the configuration: %s | %s" % (cu["write_set"], mu["write_set"]))
        if media_path in cu["write_set"] or cors_path in mu["write_set"]:
            return _fail("CORS ownership never authorizes the media-type adapter, nor the reverse")
        if cu["status"] != "open" or mu["status"] != "open" or cu["gate"] != "parity" or cu["kind"] != "config":
            return _fail("an owed-adapter unit is an open parity-gated config card: %s" % {k: cu[k] for k in ("status", "gate", "kind", "block")})
        if claimed != {i["id"] for i in items if i["rule_id"] != "PARITY"}:
            return _fail("the units claim exactly the owed obligations: %s" % claimed)
        clusters = cluster_items(items, {}, set(), units=units)
        if sorted(c["path"] for c in clusters if not c["id"].startswith("u:")) != [ctl]:
            return _fail("a claimed obligation is not clustered again per file: %s" % [(c["id"], c["path"]) for c in clusters])
        scope = build_unit_scope(root, cu, items, {"candidate_sha256": "x"})
        impl = (scope or {}).get("implementation_obligations") or []
        if (not scope or scope["rule"] != RULE_OWED_ADAPTER or len(impl) != 1 or impl[0]["verify"] != "template"
                or impl[0]["path"] != cors_path or impl[0]["type"] != ra.adapter_type(ra.CORS)
                or impl[0]["template_sha256"] != ra.template_sha256(ra.CORS)):
            return _fail("the seal names the owed path, type and template digest: %s" % impl)
        rendered = [tuple(r) for r in impl[0]["properties"]]
        if rendered != ra.cors_properties(ra.cors_policy(root)):
            return _fail("the sealed rows are the capability's rendering of the source policy")
        if batch_scope_digest(scope) != scope["digest"] or build_unit_scope(root, cu, items, {"candidate_sha256": "x"})["digest"] != scope["digest"]:
            return _fail("the owed-adapter seal is reproducible from content")
        props = dict(rendered)
        # the SOURCE decides: the restrictive policy is not widened by the permissive one next to it
        if props.get("rhoai3.source-cors.rule.0.origins") != "http://allowed.example" or props.get("rhoai3.source-cors.rule.0.methods") != "GET":
            return _fail("a restrictive source policy is rendered as it is, never widened: %s" % props)
        if any(k.startswith("rhoai3.source-cors.rule.") and v == "*" and ".0." in k for k, v in props.items()):
            return _fail("no wildcard enters a policy whose source names its values: %s" % props)

        # the checkpoint, before and after the capability ran
        row = impl[0]
        typ = {"fqn": ra.adapter_type(ra.CORS), "resolution": "full", "supertypes": [], "declared": []}
        before = _assess_owed_adapter(root, row, {}, RULE_OWED_ADAPTER)
        if before["verdict"] != "violates":
            return _fail("an owed adapter that is not there violates: %s" % before)
        ra.install(root, ra.CORS, rendered, basis={}, authority={"kind": "test"})
        if _assess_owed_adapter(root, row, {}, RULE_OWED_ADAPTER)["verdict"] != "inconclusive":
            return _fail("an adapter the model cannot see is not assessed as a pass")
        ok = _assess_owed_adapter(root, row, {cors_path: [typ]}, RULE_OWED_ADAPTER)
        if ok["verdict"] != "ok":
            return _fail("the installed adapter and rows discharge the obligation: %s" % ok)
        wrong = _assess_owed_adapter(root, row, {cors_path: [dict(typ, fqn="x.Other")]}, RULE_OWED_ADAPTER)
        if wrong["verdict"] != "violates":
            return _fail("a file that declares another type violates the naming contract: %s" % wrong)
        text = (root / APP_PROPERTIES).read_text(encoding="utf-8")
        (root / APP_PROPERTIES).write_text(text + "quarkus.http.cors.methods=GET,POST,PUT,DELETE,PATCH\n", encoding="utf-8")
        if _assess_owed_adapter(root, row, {cors_path: [typ]}, RULE_OWED_ADAPTER)["verdict"] != "violates":
            return _fail("a hand-widened row of the capability's family after the block violates")
        (root / APP_PROPERTIES).write_text(text, encoding="utf-8")
        (root / cors_path).write_text((root / cors_path).read_text(encoding="utf-8") + "// edited\n", encoding="utf-8")
        if _assess_owed_adapter(root, row, {cors_path: [typ]}, RULE_OWED_ADAPTER)["verdict"] != "violates":
            return _fail("an edited adapter is not the template and violates")
        stale = dict(row, template_sha256="0" * 64)
        if _assess_owed_adapter(root, stale, {cors_path: [typ]}, RULE_OWED_ADAPTER)["verdict"] != "inconclusive":
            return _fail("a seal made against another template is not assessable")

        # a rendering the evidence cannot support blocks the unit by name
        (root / "evidence" / "structure" / "structure.json").unlink()
        blocked, _c = owed_adapter_units(items, root, {}, set())
        cb = next(u for u in blocked if u["unit"]["family_key"] == "source-cors-response-adapter/v1")
        if cb["status"] != "blocked" or "ADAPTER_UNRENDERABLE" not in cb["block"] or "CORS_POLICY_UNKNOWN" not in cb["block"]:
            return _fail("no source policy, no CORS rendering: a typed blocker, never a guess: %s" % cb)
        mixed = [dict(i, owed=dict(i["owed"], differences=[{"media_type": "application/json", "extra": [("charset", "UTF-8")], "missing": []},
                                                           {"media_type": "application/json", "extra": [("charset", "ISO-8859-1")], "missing": []}]))
                 if i["rule_id"] == "PARITY_CONTENT_TYPE" else i for i in items]
        mb = next(u for u in owed_adapter_units(mixed, root, {}, set())[0] if u["unit"]["family_key"].startswith("source-media-type"))
        if mb["status"] != "blocked" or "MEDIA_TYPE_UNDECIDED" not in mb["block"]:
            return _fail("two different parameters decide nothing: %s" % mb.get("block"))
    return 0


def _harness_owned_guard_case() -> int:
    """ADR-015/ADR-019: the generated roots come from the generator's own
    declaration, and no write set -- whatever formed it -- keeps such a path."""
    import json
    import tempfile

    from planner.worklist import _guard_owned, harness_owned_roots, is_harness_owned

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "gates" / "generate-product-tests" / "scripts"))
    import parity_pom  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="owned-guard-") as td:
        root = Path(td)
        owned = harness_owned_roots(root)
        if owned["roots"] != sorted({parity_pom.DEFAULT_OUT, parity_pom.DEFAULT_RESOURCES}) or owned["owner"] != "generate-product-tests":
            return _fail("the generator's declaration names the roots: %s" % owned)
        man = root / parity_pom.GENERATED_MANIFEST
        man.parent.mkdir(parents=True)
        man.write_text(json.dumps({"out": "gen/java", "files": [{"path": "src/main/resources/generated-seed.sql"}]}))
        owned = harness_owned_roots(root)
        if "gen/java" not in owned["roots"] or not is_harness_owned("src/main/resources/generated-seed.sql", owned):
            return _fail("the manifest's recorded roots and files are owned too: %s" % owned)
        if is_harness_owned("src/main/java/a/B.java", owned) or is_harness_owned("src/parity-testing/x", owned):
            return _fail("a product path, or one that merely shares a prefix, is not owned")
        gen = parity_pom.DEFAULT_OUT + "/a/generated/XParityTest.java"
        clusters = [{"id": "c:1", "status": "open", "write_set": [gen], "block": ""},
                    {"id": "c:2", "status": "open", "write_set": [gen, "src/main/java/a/B.java"], "block": ""},
                    {"id": "c:3", "status": "open", "write_set": ["pom.xml"], "block": ""}]
        _guard_owned(clusters, owned)
        if clusters[0]["status"] != "blocked" or clusters[0]["write_set"] or "harness-owned" not in clusters[0]["block"]:
            return _fail("a cluster left with only owned paths is a typed blocker: %s" % clusters[0])
        if clusters[1]["write_set"] != ["src/main/java/a/B.java"] or clusters[1]["status"] != "open" or clusters[1]["harness_owned_paths"] != [gen]:
            return _fail("an owned path is dropped from a mixed write set, on the record: %s" % clusters[1])
        if clusters[2] != {"id": "c:3", "status": "open", "write_set": ["pom.xml"], "block": ""}:
            return _fail("an unrelated cluster is untouched: %s" % clusters[2])
    return 0


def _cors_scenario_case() -> int:
    """ADR-020: a cross-origin scenario's status (and a preflight's whole
    response) is the CORS adapter's obligation; stricter is never waived; an
    actual request's body stays the operation's; a non-CORS scenario is untouched."""
    import json
    import tempfile

    from planner.paths import PARITY_DIR

    ep = "ep:com.acme.ledger.AccountResource#list():http"
    ctl = "src/main/java/com/acme/ledger/AccountResource.java"
    bundle = {"entry_points": [{"id": ep, "path": ctl}]}
    with tempfile.TemporaryDirectory(prefix="cors-scen-") as td:
        root = Path(td)
        pdir = root / PARITY_DIR
        (pdir / "scenarios").mkdir(parents=True)
        corpus = root / "verification" / "scenarios" / "corpus.json"
        corpus.parent.mkdir(parents=True)
        corpus.write_text(json.dumps({"scenarios": [
            {"id": "sc:xo-options-accounts", "method": "OPTIONS", "cors_policy": "crossorigin:1",
             "headers": {"Origin": "http://self", "Access-Control-Request-Method": "PATCH"}}]}))

        def w(name, sid, reason, **extra):
            (pdir / "scenarios" / name).write_text(json.dumps(dict(
                {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": sid, "verdict": "FAIL", "reason": reason}, **extra)))

        w("a.json", "sc:cors-same-origin-unmapped-accounts", "status 403 vs 405; header Allow None vs GET, OPTIONS",
          request={"method": "DELETE"})
        w("b.json", "sc:cors-actual-accounts", "body 11aa vs 22bb; status 500 vs 200; header Access-Control-Allow-Origin None vs *")
        w("c.json", "sc:cors-preflight-enabled-accounts", "status 200 vs 401; body  vs {}; header WWW-Authenticate None vs Basic realm=x")
        w("d.json", "sc:xo-options-accounts", "status 403 vs 200; header Allow None vs GET")
        w("e.json", "sc:read-accounts", "status 403 vs 405")
        w("f.json", "sc:cors-preflight-x", "status 403 vs 200", verdict="INCONCLUSIVE")
        # F3: body + Content-Type only is body parity and PARITY_CONTENT_TYPE, never PARITY_CORS
        w("g.json", "sc:cors-actual-bodyonly", "body 11aa vs 22bb; header content-type application/json;charset=UTF-8 vs application/json")
        w("h.json", "sc:cors-preflight-bodyonly", "body 11aa vs 22bb; header content-type application/json;charset=UTF-8 vs application/json")
        items = parity_items(root, bundle)
        by = {(i["scenario"], i["rule_id"]): i for i in items}
        want = {("sc:cors-same-origin-unmapped-accounts", "PARITY_CORS"), ("sc:cors-actual-accounts", "PARITY_CORS"),
                ("sc:cors-actual-accounts", "PARITY"), ("sc:cors-preflight-enabled-accounts", "PARITY_CORS"),
                ("sc:xo-options-accounts", "PARITY_CORS"), ("sc:read-accounts", "PARITY"),
                ("sc:cors-actual-bodyonly", "PARITY"), ("sc:cors-actual-bodyonly", "PARITY_CONTENT_TYPE"),
                ("sc:cors-preflight-bodyonly", "PARITY"), ("sc:cors-preflight-bodyonly", "PARITY_CONTENT_TYPE")}
        if set(by) != want:
            return _fail("cross-origin scenario diffs are typed by ADR-020: %s" % sorted(by))
        if "status 403 vs 405" not in by[("sc:cors-same-origin-unmapped-accounts", "PARITY_CORS")]["detail"]:
            return _fail("a stricter same-origin status is a CORS obligation: %s" % by[("sc:cors-same-origin-unmapped-accounts", "PARITY_CORS")])
        actual_cors, actual_resp = by[("sc:cors-actual-accounts", "PARITY_CORS")], by[("sc:cors-actual-accounts", "PARITY")]
        if "status 500 vs 200" not in actual_cors["detail"] or "body" in actual_cors["detail"] or "body 11aa" not in actual_resp["detail"]:
            return _fail("an actual request's status is the CORS decision; its body is the operation's: %s | %s"
                         % (actual_cors["detail"], actual_resp["detail"]))
        pre = by[("sc:cors-preflight-enabled-accounts", "PARITY_CORS")]["detail"]
        if not all(t in pre for t in ("status 200 vs 401", "body", "WWW-Authenticate")):
            return _fail("a preflight's complete response, challenge included, is the CORS obligation: %s" % pre)
        if by[("sc:read-accounts", "PARITY")]["path"] != ctl or by[("sc:cors-same-origin-unmapped-accounts", "PARITY_CORS")]["path"] == ctl:
            return _fail("a non-CORS scenario keeps its controller locus; a CORS one is the adapter's")
        if "ADR-020" not in json.dumps(by[("sc:xo-options-accounts", "PARITY_CORS")]["advice"]):
            return _fail("the CORS advice states the complete-response rule")
    return 0


def _scoped_carry_case() -> int:
    """F1 (v9 t_91e9a0a1, t_c076813e, t_a97e890b): a SCOPED comparison reports
    every entry point it did not re-run INCONCLUSIVE; that is carried from the
    accepted baseline, never a regression. A re-run scenario is judged strictly,
    a carry never turns FAIL into PASS, and an UNMEASURED baseline retains."""
    from planner.worklist import PARITY_UNMEASURED, carry_unmeasured, parity_remeasured, parity_obligation_id

    epa, epb, epc = "ep:x.A#a():http", "ep:x.B#b():http", "ep:x.C#c():http"
    ida = parity_obligation_id(epa, "sc:cors-preflight-a", "cors")

    def receipt(rows, sha):
        return {"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": sha, "verdict": "FAIL",
                "entry_points": [{"entry_point": e, "verdict": v, "reason": r, "scenarios": sc} for e, v, r, sc in rows]}

    before = receipt([(epa, "FAIL", "sc:cors-preflight-a: header x", ["sc:cors-preflight-a"]),
                      (epb, "PASS", "1 required", ["sc:read-b"]), (epc, "FAIL", "status 500 vs 200", ["sc:read-c"])], "a409f225ccfd")
    after = receipt([(epa, "PASS", "1 required", ["sc:cors-preflight-a"]),
                     (epb, "INCONCLUSIVE", "sc:read-b is bound to receipt a409f225ccfd", ["sc:read-b"]),
                     (epc, "INCONCLUSIVE", "sc:read-c is bound to receipt a409f225ccfd", ["sc:read-c"])], "b0")
    run = {"runtime": {"parity": {"ran": True, "scoped": True, "scenarios": ["sc:cors-preflight-a"], "trigger": "issued-card"}}}
    remeasured = parity_remeasured(run)
    if remeasured != {"cors-preflight-a"} or parity_remeasured({"runtime": {"parity": {"ran": True, "scoped": False}}}) is not None:
        return _fail("the re-measured set is run.json's scoped scenario list: %s" % remeasured)
    eff, carried = carry_unmeasured(before, after, remeasured)
    rows = {r["entry_point"]: r for r in eff["entry_points"]}
    if rows[epb]["verdict"] != "PASS" or "carried_from" not in rows[epb] or rows[epb]["carried_from"]["receipt_sha256"] != "a409f225ccfd":
        return _fail("B, passing before and not re-run, is carried and says from where: %s" % rows[epb])
    if rows[epc]["verdict"] != "FAIL" or [c["entry_point"] for c in carried] != [epb, epc]:
        return _fail("a carry keeps a FAIL a FAIL: %s %s" % (rows[epc], carried))
    m = {"known": True, "tuple": [0, 0, 0], "parity_mismatches": 1}
    common = dict(gate="parity", issued_items=[ida], prev_gate_items={ida}, cur_gate_items=set(),
                  prev_runtime={}, cur_runtime={}, prev_parity=before, cur_parity=after)
    ok, why = progress(m, m, set(), set(), parity_remeasured=remeasured, **common)
    if ok is not True:
        return _fail("a scoped repair whose own scenario passes is accepted, B carried: %s" % why)
    ok, why = progress(m, m, set(), set(), **common)
    if ok is not False or "was PASS before" not in why:
        return _fail("the control: without the scope the INCONCLUSIVE row is still read as a regression: %s %s" % (ok, why))
    # A re-run AND regressed: strict
    regressed = receipt([(epa, "FAIL", "sc:cors-preflight-a: header y", ["sc:cors-preflight-a"]),
                         (epb, "INCONCLUSIVE", "bound", ["sc:read-b"])], "b1")
    ok, why = progress(m, m, set(), set(), parity_remeasured=remeasured, **dict(common, cur_parity=regressed, cur_gate_items={ida}))
    if ok is not False:
        return _fail("a re-run scenario that still fails is judged strictly: %s" % why)
    before2 = receipt([(epa, "PASS", "", ["sc:cors-preflight-a"]), (epb, "PASS", "", ["sc:read-b"])], "c0")
    after2 = receipt([(epa, "INCONCLUSIVE", "no capture", ["sc:cors-preflight-a"]), (epb, "INCONCLUSIVE", "bound", ["sc:read-b"])], "c1")
    ok, why = progress(m, m, set(), set(), parity_remeasured=remeasured, **dict(common, prev_parity=before2, cur_parity=after2, issued_items=[], prev_gate_items=set()))
    if ok is not False or "cors-preflight-a" not in why and epa not in why:
        return _fail("a re-measured scenario that became INCONCLUSIVE is a regression, never carried: %s %s" % (ok, why))
    # an UNMEASURED baseline: retained, never reverted
    unmeasured = {"schema": "rhoai3.parity-receipt/v1", "verdict": PARITY_UNMEASURED, "entry_points": [],
                  "unmeasured": {"reason": "operator step 2410082 changed the product after the last comparison"}}
    ok, why = progress(m, m, set(), set(), parity_remeasured=remeasured, **dict(common, prev_parity=unmeasured))
    if ok is not UNPROVEN or "refresh-accepted-parity.py" not in why:
        return _fail("an UNMEASURED baseline retains the candidate and names the refresh: %s %s" % (ok, why))
    return 0


def _receipt_v2_case() -> int:
    """The composer's current receipt: navigation_obligations[], enabled-mode
    CORS scenario types, cors.outcomes browser_access, and a refused write
    whose source effect was never observed."""
    import json
    import tempfile

    from planner.paths import PARITY_DIR
    from planner.worklist import parity_obligation_id, parity_state

    ep = "ep:com.acme.ledger.EntryResource#toDocs():http"
    ep2 = "ep:com.acme.ledger.AccountResource#delete(int):http"
    ctl = "src/main/java/com/acme/ledger/EntryResource.java"
    bundle = {"entry_points": [{"id": ep, "path": ctl}, {"id": ep2, "path": "src/main/java/com/acme/ledger/AccountResource.java"}]}
    with tempfile.TemporaryDirectory(prefix="receipt-v2-") as td:
        root = Path(td)
        pdir = root / PARITY_DIR
        (pdir / "scenarios").mkdir(parents=True)
        corpus = root / "verification" / "scenarios" / "corpus.json"
        corpus.parent.mkdir(parents=True)
        corpus.write_text(json.dumps({"scenarios": [
            {"id": "sc:cors-enabled-preflight-p1", "method": "OPTIONS", "cors_policy": "crossorigin:1", "scenario_type": "browser-preflight"},
            {"id": "sc:cors-enabled-actual-anonymous-p1", "method": "GET", "cors_policy": "crossorigin:1", "scenario_type": "cors-actual"},
            {"id": "sc:cors-enabled-probe-authenticated-p1", "method": "OPTIONS", "cors_policy": "crossorigin:1", "scenario_type": "diagnostic-probe"},
            {"id": "sc:cors-enabled-actual-authenticated-p1", "method": "GET", "cors_policy": "crossorigin:1", "scenario_type": "cors-actual"}]}))
        (pdir / "receipt.json").write_text(json.dumps({
            "schema": "rhoai3.parity-receipt/v1", "verdict": "FAIL",
            "entry_points": [{"entry_point": ep, "verdict": "PASS", "navigation": "failed", "scenarios": ["sc:read-entry"]}],
            "navigation_obligations": [{"entry_point": ep, "kind": "navigation", "verdict": "FAIL", "scenarios": ["sc:read-entry"],
                                        "reason": "redirect target http://d/ui/index.html is dead on the destination (404)",
                                        "navigation_failures": [{"scenario": "sc:read-entry", "target": "http://d/ui/index.html",
                                                                 "terminal": "dead", "final_status": 404}]}],
            "cors": {"source_policies": ["crossorigin:1"], "gaps": [], "outcomes": {
                "sc:cors-enabled-actual-authenticated-p1": {"policy": "crossorigin:1", "type": "cors-actual", "browser_access": "prevents"},
                "sc:cors-enabled-actual-authenticated-p1-granting": {"policy": "crossorigin:1", "type": "cors-actual", "browser_access": "prevents"}}}}))

        def w(name, sid, reason, **extra):
            (pdir / "scenarios" / name).write_text(json.dumps(dict(
                {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep2, "scenario": sid, "verdict": "FAIL", "reason": reason}, **extra)))

        w("a.json", "sc:cors-enabled-preflight-p1", "status 200 vs 401; header WWW-Authenticate None vs Basic realm=x; body  vs {}")
        w("b.json", "sc:cors-enabled-actual-anonymous-p1", "header Access-Control-Allow-Origin * vs None; body 1 vs 2; header content-type application/json;charset=UTF-8 vs application/json")
        w("c.json", "sc:cors-enabled-probe-authenticated-p1", "status 200 vs 401")
        w("d.json", "sc:cors-enabled-actual-authenticated-p1", "header Access-Control-Allow-Origin None vs *; header Access-Control-Expose-Headers None vs errors")
        w("e.json", "sc:cors-enabled-actual-authenticated-p1-granting", "header Access-Control-Allow-Origin * vs None")
        w("f.json", "sc:refuse-delete-accounts", "effect eff:accounts-after (the refused write changed the state it reads): status 200 vs 200, body 1 vs 2",
          results={"response": "PASS", "destination_no_effect": "FAIL", "source_effect": {"verdict": "INCONCLUSIVE", "reason": "the source's post-request state was not observed"}})
        notes: list = []
        items = parity_items(root, bundle, notes)
        by = {(i["scenario"], i["rule_id"]): i for i in items}
        nav = [i for i in items if i.get("cause") == "redirect-target-dead"]
        if len(nav) != 1 or nav[0]["path"] != ctl or nav[0]["scenarios"] != ["sc:read-entry"]:
            return _fail("a navigation obligation is read from navigation_obligations[]: %s" % nav)
        st = parity_state(json.loads((pdir / "receipt.json").read_text()))
        if st["obligations"][parity_obligation_id(ep, "", "navigation")]["verdict"] != "FAIL" or st["entry_points"][ep] != "PASS":
            return _fail("a passing redirect with a dead target keeps PASS and its navigation obligation is FAIL: %s" % st["entry_points"])
        pre = by.get(("sc:cors-enabled-preflight-p1", "PARITY_CORS"))
        if not pre or "WWW-Authenticate" not in pre["detail"] or ("sc:cors-enabled-preflight-p1", "PARITY") in by:
            return _fail("an enabled browser preflight's whole response is the CORS obligation (typed by the corpus): %s" % sorted(by))
        if not {("sc:cors-enabled-actual-anonymous-p1", r) for r in ("PARITY_CORS", "PARITY", "PARITY_CONTENT_TYPE")} <= set(by):
            return _fail("an enabled actual request: CORS headers, body at the controller, charset its own: %s" % sorted(by))
        if any(k[0] == "sc:cors-enabled-probe-authenticated-p1" for k in by) or not any(n["kind"] == "diagnostic-probe" for n in notes):
            return _fail("a diagnostic probe owes no worker anything and is noted: %s" % notes)
        if any(k[0] == "sc:cors-enabled-actual-authenticated-p1" for k in by) or not any(n["kind"] == "cors-prevented" for n in notes):
            return _fail("a source that prevents the exchange owes no permission the destination also withholds: %s" % sorted(by))
        if ("sc:cors-enabled-actual-authenticated-p1-granting", "PARITY_CORS") not in by:
            return _fail("a destination granting what a preventing source did not is still owed (control)")
        if any(k[0] == "sc:refuse-delete-accounts" for k in by) or not any(n["kind"] == "source-effect-unobserved" for n in notes):
            return _fail("an effect judged without the source's own effect is a note, never a repair card: %s" % sorted(by))
    return 0


def _split_discharge_case() -> int:
    """G1 (v9 t_55220d84) and G2: a scenario whose diffs F3 split across
    obligations discharges each obligation by its OWN diffs; a mid-card
    rebuild from a scoped receipt keeps what nobody re-ran."""
    import json
    import tempfile

    from planner.paths import LOOP_ACCEPTED, PARITY_DIR, VERIFY_RUN
    from planner.worklist import judged_parity_receipt, parity_obligation_discharged, parity_obligation_id, parity_state

    ep = "ep:com.acme.ledger.AccountResource#list():http"
    nav_ep = "ep:com.acme.ledger.EntryResource#toDocs():http"
    sid = "sc:cors-actual-accounts"
    bundle = {"entry_points": [{"id": ep, "path": "src/main/java/com/acme/ledger/AccountResource.java"},
                               {"id": nav_ep, "path": "src/main/java/com/acme/ledger/EntryResource.java"}]}
    charset = "header content-type application/json;charset=UTF-8 vs application/json"
    rep_id, body_id = parity_obligation_id(ep, sid, "representation"), parity_obligation_id(ep, sid, "response")

    def rec(reason, verdict="FAIL"):
        return {"schema": "rhoai3.scenario-parity/v1", "entry_point": ep, "scenario": sid, "verdict": verdict, "reason": reason}

    def receipt(verdict, nav=True, sha="before"):
        doc = {"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": sha, "verdict": "FAIL",
               "entry_points": [{"entry_point": ep, "verdict": verdict, "reason": "", "scenarios": [sid]},
                                {"entry_point": nav_ep, "verdict": "PASS" if nav else "INCONCLUSIVE", "reason": "" if nav else "sc:read-entry is bound to receipt before",
                                 "scenarios": ["sc:read-entry"], **({"navigation": "failed"} if nav else {})}]}
        if nav:
            doc["navigation_obligations"] = [{"entry_point": nav_ep, "kind": "navigation", "verdict": "FAIL", "scenarios": ["sc:read-entry"],
                                              "reason": "redirect target http://d/ui is dead (404)", "navigation_failures": []}]
        return doc

    with tempfile.TemporaryDirectory(prefix="split-discharge-") as td:
        root = Path(td)
        acc = root / LOOP_ACCEPTED / "parity"
        (acc / "scenarios").mkdir(parents=True)
        (root / PARITY_DIR / "scenarios").mkdir(parents=True)
        (root / VERIFY_RUN).parent.mkdir(parents=True)
        (acc / "receipt.json").write_text(json.dumps(receipt("FAIL")))
        (acc / "scenarios" / "sc.json").write_text(json.dumps(rec("body 11aa vs 22bb; " + charset)))
        (root / VERIFY_RUN).write_text(json.dumps({"runtime": {"parity": {"ran": True, "scoped": True, "scenarios": [sid]}}}))
        before = json.loads((acc / "receipt.json").read_text())
        m = {"known": True, "tuple": [0, 0, 0], "parity_mismatches": 1}

        def attempt(live_reason, issued, live_verdict="FAIL"):
            (root / PARITY_DIR / "scenarios" / "sc.json").write_text(json.dumps(rec(live_reason, live_verdict)))
            (root / PARITY_DIR / "receipt.json").write_text(json.dumps(receipt(live_verdict, nav=False, sha="after")))
            judged, _carried = judged_parity_receipt(root)
            obl = parity_state(judged)["obligations"]
            discharged = {issued: parity_obligation_discharged(root, obl[issued], {"cors-actual-accounts"}, judged)}
            items = parity_items(root, bundle, receipt=judged)
            cur = {i["id"] for i in items}
            return progress(m, m, set(), set(), gate="parity", issued_items=[issued],
                            prev_gate_items={rep_id, body_id, parity_obligation_id(nav_ep, "", "navigation")},
                            cur_gate_items=cur, prev_runtime={}, cur_runtime={}, prev_parity=before,
                            cur_parity=(root / PARITY_DIR / "receipt.json").read_text() and json.loads((root / PARITY_DIR / "receipt.json").read_text()),
                            parity_remeasured={"cors-actual-accounts"}, parity_discharged=discharged), cur

        (ok, why), cur = attempt("body 11aa vs 22bb", rep_id)
        if ok is not True:
            return _fail("the charset card that removed only the charset is ACCEPTED: %s" % why)
        if parity_obligation_id(nav_ep, "", "navigation") not in cur or body_id not in cur or rep_id in cur:
            return _fail("G2: the rebuild from the scoped receipt keeps the carried navigation and the body obligation: %s" % sorted(cur))
        (ok, why), _ = attempt("body 33cc vs 22bb", rep_id)
        if ok is not False or "33cc" not in why:
            return _fail("a charset card that also moved the body digest is REVERTED, naming it: %s %s" % (ok, why))
        (ok, why), _ = attempt(charset, body_id)
        if ok is not True:
            return _fail("the body card that fixed the body, charset remaining, is ACCEPTED for the body: %s" % why)
        (ok, why), _ = attempt("body 11aa vs 22bb; " + charset, rep_id)
        if ok is not False:
            return _fail("an unchanged scenario discharges nothing: %s" % why)
        (acc / "scenarios" / "sc.json").write_text(json.dumps(rec("body 11aa vs 22bb; " + charset)))
        (root / PARITY_DIR / "scenarios" / "sc.json").write_text(json.dumps(rec("body 11aa vs 22bb")))
        row = {"entry_point": ep, "scenario": sid, "what": "representation", "verdict": "FAIL"}
        if parity_obligation_discharged(root, row, {"other"})[0] or parity_obligation_discharged(root, row, None)[0]:
            return _fail("an obligation whose scenario was not re-run is never discharged")
        if parity_obligation_discharged(root, dict(row, scenario=""), {"cors-actual-accounts"})[0]:
            return _fail("a read oracle is discharged only by PASS")
    return 0


def main() -> int:
    if (_runtime_identity_case() or _gate_progress_case() or _batch_scope_case() or _checked_family_case()
            or _set_wide_case() or _config_value_case() or _parity_typing_case() or _parity_advice_case()
            or _parity_navigation_case() or _owed_adapter_case() or _cors_scenario_case() or _scoped_carry_case() or _receipt_v2_case() or _split_discharge_case() or _harness_owned_guard_case() or _parity_gate_case() or _unit_formation_case() or _unit_bound_case() or _unit_seal_case()
            or _unit_mode_case() or _unit_inert_case() or _unit_config_case()
            or _unit_experiment_table_case() or _unit_explained_case() or _unit_progress_case()
            or _unit_budget_case()):
        return 1
    # the same questions with nothing simulated: the JDK extractor's own model
    if shutil.which("javac"):
        if _real_leaf_case() or _real_fragment_case() or _real_explained_case():
            return 1
    else:
        print("SKIP: the real-model cases need a JDK on PATH", file=sys.stderr)

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
    print("OK: worklist (lossless line-free incidents; canary excluded; only ERROR diagnostics; build→config→compile(leaf-first)→incident→test order; tests never writable; lexicographic 3-tuple progress; new-incident veto; unknown never advances; gate progress is the issued obligation disappearing, never a reworded one; a second cause at one file is a second obligation); a repository card's inventory is sealed by its own digest and two measurements never share a path; checked-exception family: bound to its introducing step (a legacy site stays out), one budget, line-free identity across a moved line, CONTINUE / EXPOSED / still-reported / 1→0 accept, per-member assessment (catch-wrapped and header-deleted members violate); a set-wide packaging cause is one typed blocker under permuted first-reported names and never a card; an unloadable config value is located at the annotation that names the property IN THE DESTINATION'S OWN MODEL (the frozen source's model answers only when the destination cannot be modelled, and the brief says which did; ${x:d} and a bare x are one property), at application.properties only when the name is real and unread, and is a blocker when the name is empty and unread -- the same decisions under renamed identifiers; parity mismatches are typed by their diffs (CORS → an obligation OWED the harness CORS adapter, a Content-Type parameter difference → its own PARITY_CONTENT_TYPE obligation, the rest → the controller; scenario verdicts count, the receipt does not) and carry their exit conditions as advice built from those diffs (ADR-019: the CORS write set is the adapter's contract path plus the configuration, permissions come from the SOURCE policy and never from one capture, with the paired actual request, the exposed headers, both security modes and the capability's --check as the exit; each owed adapter is ONE sealed unit/owed-adapter/v1 whose checkpoint assesses the template bytes, the contract type and every rendered row, and a rendering the evidence cannot support is a typed blocker; findings in harness-owned generated roots are never obligations; a redirect is the source's status and its literal Location after origin mapping only, the doubled root path named, the legacy address served from the packaged UI, a property outside the write set entering through amend-scope) — the same advice, about its own values, on a specimen that shares no name with this one; the PARITY GATE: an obligation carries gate=parity and the scenarios it is made of (a read oracle takes its receipt row's), and a card is discharged only by the re-composed receipt recording those scenarios PASS -- still reported, gone but INCONCLUSIVE, another entry point broken, a startup gate broken and an un-composed receipt all refuse; UNIT FORMATION (decisions.loop.unit_formation v1): four typed rules over one measurement -- a throws surface closes over its interface, implementers and callers as ONE unit; an annotation family confined to a directory nothing outside refers to is a package leaf (decided by type_refs, never by a package name); a family spanning two directories and five independent web symbols stay five separate families; a set-wide packaging cause whose parents the model CAN enumerate becomes a mintable unit while one it cannot stays the typed blocker; a test source is never writable and a lone locus forms no unit; a property and its annotated consumers are one unit and a properties file that does not declare the key is out of scope -- every verdict repeated on a twin that shares no package, type, member or foreign symbol. The SEAL is rhoai3.batch-scope/v4: files AND symbols, typed evidence, completion checks naming the tool that decides them, reproducible from content, at a path named by its own digest, with unit_id surviving remeasurement (one budget per PROBLEM) and a type the candidate merely mentions never widening it; a documented target carries its compat-mapping symbol_renames row and an undocumented one is no target (v9 t_3903f495). The BOUND preserves what a repair needs: a union narrows by whole families, lowest cardinality first, and every \
obligation it excludes stays in the work list as its own item with its file still writable, while a closure keeps \
its callers and reaches the typed UNIT_OVERSIZE refusal rather than dropping them. With the mode off clustering is byte-for-byte what it was, and the mode may not flip while a card is issued or a pending row is open (UNIT_MODE_SWITCH). The CHECKPOINT: a \
unit whose sealed identities are gone and whose members assess clean is ACCEPTED with the tuple unchanged, and even \
with the compile slot briefly worse, for exactly the diagnostics its sealed symbols or its catalogued targets explain \
-- the wrong import (jakarta.ws.rs.Context for jakarta.ws.rs.core.Context) is explained by nothing and is never \
accepted, no model means no explanation, a file outside the file seal is never explained, and a unit that would carry \
two symbol families through one checkpoint has its whole tolerated set refused; the compiler naming another member of \
the same unit CONTINUES the card, anything else is EXPOSED; a regressed test or incident slot, one of the unit's own \
diagnostics still reported, a member that violates, an assessment that could not be made and a gate going backwards \
all refuse, and a card with no unit seal is judged exactly as before. The BUDGET is rk:unit:<unit_id>, which survives \
remeasurement and revision, and planner.budget counts against it. WU-9's query-invalid cause row is in RUNTIME_CAUSES \
before the schema rows. THE REAL MODEL, end to end (the JDK extractor, no simulated rows): references live under \
DECLARED MEMBERS, so an outside consumer naming a helper only in a member signature prevents the leaf a type row \
could not see, a partially resolved type establishes no isolation at all, and the control leaf still forms; the \
fragment set is one unit whose write set is the parents and the adapters they OWE -- each named from the parent's \
own fqn under the fragment naming contract -- with the children as inventory; before the adapter the obligation \
violates while the child that IMPORTS its required parent is ok, because a sealed declaration is not a retired \
symbol; an adapter that does not implement the parent violates, a written one discharges, and severing the \
inheritance violates; the unit's boot gate must pass before acceptance, a passing gate never excuses a violating \
member, and a gate that was passing may not be broken; and the two counterexamples are decided from the compiler's \
own imports -- the wrong jakarta.ws.rs.Context and an unbound UriBuilder explain nothing while the imported \
catalogued target does. Each of them repeated on a twin sharing no identifier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
