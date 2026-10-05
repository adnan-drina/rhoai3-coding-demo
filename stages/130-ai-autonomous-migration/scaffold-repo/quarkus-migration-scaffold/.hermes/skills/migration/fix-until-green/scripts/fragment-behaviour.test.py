#!/usr/bin/env python3
"""V17-3: an owed fragment implementation is judged by what its bodies DO.

v17 t_eca28a3c accepted seven <Fragment>Impl delegates that compiled,
packaged and carried the owed CDI exposure while every query member threw
UnsupportedOperationException and save/delete were no-ops. Through the
PRODUCTION path (real javac -> JDK dest model -> worklist.form_units ->
build_unit_scope -> assess_unit, and brief.main for the rendered card):

1. the sealed obligation carries the SELECTED source behaviour per member,
   bound to the decided build profiles: the repository's @Query, the override
   fragment's method (with the Hibernate 6 flush-order translation its
   remove-then-query call order needs), the base repository's CRUD
   semantics -- and names the inactive-profile implementation as NOT the
   behaviour source;
2. broken bodies are refused at the checkpoint from the parse tree, whatever
   the exception type: a throw as the whole body, an empty mutator, a
   placeholder-only query, a private helper hiding a stub, a delegation
   cycle; a stub is refused even with the correct CDI shape
   (@ApplicationScoped @Typed(XImpl.class));
3. a real implementation passes, including one member that delegates to
   another real owed member;
4. the brief renders the behaviour rows, the not-a-source row and the
   functional evidence (reads, and writes proven by a committed read-back;
   an uncovered write is an unresolved debt, never PASS);
5. everything again on a renamed structural twin with another profile name.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(HERE))
from planner.canonical import load_json, write_canonical  # noqa: E402

CDI = {
    "src/main/java/jakarta/enterprise/context/ApplicationScoped.java":
        "package jakarta.enterprise.context;\npublic @interface ApplicationScoped { }\n",
    "src/main/java/jakarta/enterprise/inject/Typed.java":
        "package jakarta.enterprise.inject;\npublic @interface Typed { Class<?>[] value() default {}; }\n",
}
PROFILE = "org.springframework.context.annotation.Profile"
QUERY = "org.springframework.data.jpa.repository.Query"
EM = "javax.persistence.EntityManager"

A = {"base": "org.acme.clinic", "repo_pkg": "repository", "sd_pkg": "springdatajpa", "parent": "OwnerRepository",
     "entity": "Owner", "profile": "spring-data-jpa", "alt_profile": "jpa", "rest": "OwnerRestController",
     "svc": "ClinicService", "q": "findByLastName", "q2": "findAll", "id": "findById", "save": "save", "delete": "delete"}
B = {"base": "com.example.depot", "repo_pkg": "store", "sd_pkg": "springdata", "parent": "CrateStore",
     "entity": "Crate", "profile": "depot-orm", "alt_profile": "depot-sql", "rest": "CrateEndpoint",
     "svc": "DepotService", "q": "findByLabel", "q2": "findAll", "id": "findById", "save": "save", "delete": "delete"}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _m(name: str, sig: str, *, returns: str = "void", anns=None, calls=None, params=None) -> dict:
    return {"name": name, "signature": sig, "returns": returns, "annotations": anns or [], "calls": calls or [],
            "params": params or [], "resolution": "full", "type_refs": []}


def source_types(n: dict) -> tuple[list[dict], list[dict]]:
    """The FROZEN source model (M1 JdkModelExtract rows), shaped like the
    preserved PetClinic evidence: the parent interface, the selected Spring
    Data repository with a @Query and an override fragment, the override
    implementation whose delete removes first and then bulk-deletes
    dependents, an inactive-profile implementation, and a controller ->
    service -> repository call chain."""
    b, rp = n["base"], "%s.%s" % (n["base"], n["repo_pkg"])
    sd = "%s.%s" % (rp, n["sd_pkg"])
    ent = "%s.model.%s" % (b, n["entity"])
    parent = "%s.%s" % (rp, n["parent"])
    src = "src/main/java/" + b.replace(".", "/")
    path = lambda fqn: "src/main/java/%s.java" % fqn.replace(".", "/")  # noqa: E731
    ov = "%s.%sOverride" % (sd, n["parent"])
    types = [
        {"fqn": parent, "kind": "interface", "path": path(parent), "supertypes": [], "annotations": [], "resolution": "full",
         "methods": [_m(n["q"], "%s(java.lang.String)" % n["q"], returns="java.util.Collection"),
                     _m(n["q2"], "%s()" % n["q2"], returns="java.util.Collection"),
                     _m(n["id"], "%s(int)" % n["id"], returns=ent),
                     _m(n["save"], "%s(%s)" % (n["save"], ent)), _m(n["delete"], "%s(%s)" % (n["delete"], ent))]},
        {"fqn": "%s.SpringData%s" % (sd, n["parent"]), "kind": "interface", "path": path("%s.SpringData%s" % (sd, n["parent"])),
         "supertypes": ["org.springframework.data.repository.Repository", parent, ov], "resolution": "full",
         "annotations": [{"fqn": PROFILE, "values": {"value": [n["profile"]]}}],
         "methods": [_m(n["q"], "%s(java.lang.String)" % n["q"], returns="java.util.Collection",
                        anns=[{"fqn": QUERY, "values": {"value": ["SELECT DISTINCT e FROM %s e WHERE e.name LIKE :name%%" % n["entity"]]}}])]},
        {"fqn": ov, "kind": "interface", "path": path(ov), "supertypes": [], "resolution": "full",
         "annotations": [{"fqn": PROFILE, "values": {"value": [n["profile"]]}}],
         "methods": [_m(n["delete"], "%s(%s)" % (n["delete"], ent))]},
        {"fqn": "%s.SpringData%sImpl" % (sd, n["parent"]), "kind": "class", "path": path("%s.SpringData%sImpl" % (sd, n["parent"])),
         "supertypes": [ov], "resolution": "full", "annotations": [{"fqn": PROFILE, "values": {"value": [n["profile"]]}}],
         "methods": [_m(n["delete"], "%s(%s)" % (n["delete"], ent),
                        calls=[{"owner": EM, "name": "remove"}, {"owner": EM, "name": "contains"}, {"owner": EM, "name": "merge"},
                               {"owner": "javax.persistence.Query", "name": "executeUpdate"}, {"owner": EM, "name": "createQuery"}])]},
        {"fqn": "%s.jpa.Jpa%sImpl" % (rp, n["parent"]), "kind": "class", "path": path("%s.jpa.Jpa%sImpl" % (rp, n["parent"])),
         "supertypes": [parent], "resolution": "full", "annotations": [{"fqn": PROFILE, "values": {"value": [n["alt_profile"]]}}],
         "methods": [_m(n["q2"], "%s()" % n["q2"], returns="java.util.Collection", calls=[{"owner": EM, "name": "createQuery"}])]},
        {"fqn": "%s.service.%s" % (b, n["svc"]), "kind": "interface", "path": path("%s.service.%s" % (b, n["svc"])),
         "supertypes": [], "annotations": [], "resolution": "full",
         "methods": [_m("remove%s" % n["entity"], "remove%s(int)" % n["entity"]), _m("all%s" % n["entity"], "all%s()" % n["entity"])]},
        {"fqn": "%s.service.%sImpl" % (b, n["svc"]), "kind": "class", "path": path("%s.service.%sImpl" % (b, n["svc"])),
         "supertypes": ["%s.service.%s" % (b, n["svc"])], "annotations": [], "resolution": "full",
         "methods": [_m("remove%s" % n["entity"], "remove%s(int)" % n["entity"],
                        calls=[{"owner": parent, "name": n["id"]}, {"owner": parent, "name": n["delete"]}]),
                     _m("all%s" % n["entity"], "all%s()" % n["entity"], calls=[{"owner": parent, "name": n["q2"]}])]},
        {"fqn": "%s.rest.%s" % (b, n["rest"]), "kind": "class", "path": path("%s.rest.%s" % (b, n["rest"])),
         "supertypes": [], "annotations": [], "resolution": "full",
         "methods": [_m("remove", "remove(int)", calls=[{"owner": "%s.service.%s" % (b, n["svc"]), "name": "remove%s" % n["entity"]}]),
                     _m("list", "list()", calls=[{"owner": "%s.service.%s" % (b, n["svc"]), "name": "all%s" % n["entity"]}])]},
    ]
    eps = [{"id": "ep:%s.rest.%s#remove(int):http" % (b, n["rest"]), "kind": "http", "type": "%s.rest.%s" % (b, n["rest"]),
            "member": "remove(int)"},
           {"id": "ep:%s.rest.%s#list():http" % (b, n["rest"]), "kind": "http", "type": "%s.rest.%s" % (b, n["rest"]),
            "member": "list()"}]
    del src
    return types, eps


def dest_sources(n: dict, impl_body: str) -> dict[str, str]:
    """The DESTINATION tree: the parent the generated repository needs an
    implementation of, the Spring Data repository extending it, the entity,
    and (when given) the owed <Parent>Impl."""
    b, rp = n["base"], "%s.%s" % (n["base"], n["repo_pkg"])
    src = "src/main/java/" + b.replace(".", "/")
    e = n["entity"]
    files = {
        "%s/model/%s.java" % (src, e): "package %s.model;\npublic class %s { public Integer id; public String name; }\n" % (b, e),
        "%s/%s/%s.java" % (src, n["repo_pkg"], n["parent"]):
            ("package %s;\nimport java.util.Collection;\nimport %s.model.%s;\npublic interface %s {\n"
             "    Collection<%s> %s(String name);\n    Collection<%s> %s();\n    %s %s(int id);\n    void %s(%s e);\n    void %s(%s e);\n}\n"
             % (rp, b, e, n["parent"], e, n["q"], e, n["q2"], e, n["id"], n["save"], e, n["delete"], e)),
        "%s/%s/%s/SpringData%s.java" % (src, n["repo_pkg"], n["sd_pkg"], n["parent"]):
            "package %s.%s;\npublic interface SpringData%s extends %s.%s { }\n" % (rp, n["sd_pkg"], n["parent"], rp, n["parent"]),
        **CDI,
    }
    if impl_body is not None:
        files["%s/%s/%sImpl.java" % (src, n["repo_pkg"], n["parent"])] = (
            "package %s;\nimport java.util.*;\nimport %s.model.%s;\nimport jakarta.enterprise.context.ApplicationScoped;\n"
            "import jakarta.enterprise.inject.Typed;\n@ApplicationScoped\n@Typed(%sImpl.class)\npublic class %sImpl implements %s {\n"
            "    private final Map<Integer, %s> rows = new HashMap<>();\n%s}\n"
            % (rp, b, e, n["parent"], n["parent"], n["parent"], e, impl_body))
    return files


def bodies(n: dict, **override: str) -> str:
    """A REAL implementation of every owed member, then the named overrides."""
    e = n["entity"]
    real = {
        "q": "    public Collection<%s> %s(String name) { List<%s> out = new ArrayList<>(); for (%s r : rows.values()) "
             "{ if (r.name != null && r.name.startsWith(name)) { out.add(r); } } return out; }\n" % (e, n["q"], e, e),
        "q2": "    public Collection<%s> %s() { return new ArrayList<>(rows.values()); }\n" % (e, n["q2"]),
        "id": "    public %s %s(int id) { return rows.get(id); }\n" % (e, n["id"]),
        "save": "    public void %s(%s x) { rows.put(x.id, x); }\n" % (n["save"], e),
        "delete": "    public void %s(%s x) { rows.remove(x.id); }\n" % (n["delete"], e),
    }
    real.update(override)
    return "".join(real[k] for k in ("q", "q2", "id", "save", "delete"))


def make_root(d: str, n: dict, impl_body: str | None) -> Path:
    root = Path(d)
    for rel, text in dest_sources(n, impl_body).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (root / ".hermes").mkdir(exist_ok=True)
    (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}', encoding="utf-8")
    shutil.copytree(GOLDEN / ".hermes/planning/catalogs", root / ".hermes/planning/catalogs")
    shutil.copytree(GOLDEN / ".hermes/planning/schemas", root / ".hermes/planning/schemas")
    dec = (GOLDEN / "decisions.yaml").read_text(encoding="utf-8")
    dec = dec.replace("    - spring-data-jpa\n", "    - %s\n" % n["profile"])
    (root / "decisions.yaml").write_text(dec, encoding="utf-8")
    types, eps = source_types(n)
    write_canonical(root / "evidence/planning/evidence-bundle.json",
                    {"schema": "rhoai3.evidence-bundle/v1", "structure": {"available": True, "mode": "full", "types": types},
                     "entry_points": eps})
    b = n["base"]
    write_canonical(root / "verification/scenarios/corpus.json", {"schema": "rhoai3.scenario-corpus/v1", "scenarios": [
        # a WRITE with its committed effect read back in another request
        {"id": "sc:delete-%s-1" % n["entity"].lower(), "entry_point": eps[0]["id"], "method": "DELETE", "path": "/x/1",
         "effects": [{"id": "eff:after-delete", "method": "GET", "path": "/x/1"}]},
        # a READ
        {"id": "sc:list-%s" % n["entity"].lower(), "entry_point": eps[1]["id"], "method": "GET", "path": "/x", "effects": []},
    ]})
    del b
    return root


def unit_of(root: Path) -> tuple[dict, list[dict]]:
    from planner.dest_model import dest_model
    from planner.worklist import form_units
    items = [{"id": "rt:boot:setwide", "source": "runtime", "gate": "boot", "kind": "config", "cause": "missing-implementation",
              "set_wide": "spring-data-fragment-implementations", "unlocated": True, "path": "", "category": "mandatory",
              "line": 0, "rule_id": "RUNTIME_APPLICATION_CONFIGURATION", "message": "No implementation of interface X was found"}]
    units, _ = form_units(items, {}, set(), model=dest_model(root), root=root)
    frags = [c for c in units if c["unit"]["family_key"].startswith("spring-data-fragment-implementations:")]
    if len(frags) != 1:
        raise AssertionError("no fragment unit: %s" % [c["unit"]["family_key"] for c in units])
    return frags[0], items


def impl_verdict(root: Path, scope: dict) -> dict:
    from planner.worklist import assess_unit
    return next(r for r in assess_unit(root, scope) if r.get("state") == "implementation")


def case(n: dict) -> int:
    from planner.worklist import build_unit_scope
    label = n["base"]
    rp = "%s.%s" % (n["base"], n["repo_pkg"])
    impl_path = "src/main/java/%s/%sImpl.java" % (rp.replace(".", "/"), n["parent"])
    e = n["entity"]
    with tempfile.TemporaryDirectory(prefix="frag-beh-") as d:
        root = make_root(d, n, None)
        cl, items = unit_of(root)
        scope = build_unit_scope(root, cl, items, {"candidate_sha256": "c0"})
        owed = [r for r in scope.get("implementation_obligations") or [] if r.get("path") == impl_path]
        if len(owed) != 1:
            return _fail("[%s] the seal owes %s: %s" % (label, impl_path, scope.get("implementation_obligations")))
        beh = {m["signature"].split("(", 1)[0]: m for m in owed[0]["behaviour"]["members"]}
        want = {n["q"]: "query", n["q2"]: "crud-default", n["id"]: "crud-default", n["save"]: "crud-default",
                n["delete"]: "source-override"}
        got = {k: v["kind"] for k, v in beh.items()}
        if got != want:
            return _fail("[%s] the selected source behaviour per member: %s != %s" % (label, got, want))
        if "LIKE :name%" not in " ".join(beh[n["q"]].get("query") or []):
            return _fail("[%s] the @Query text is carried: %s" % (label, beh[n["q"]]))
        tr = [t["id"] for t in beh[n["delete"]].get("translations") or []]
        if tr != ["hibernate6-flush-before-query"]:
            return _fail("[%s] remove-then-bulk-delete carries the flush-order translation: %s" % (label, beh[n["delete"]]))
        nots = [x["type"] for x in owed[0]["behaviour"]["not_behaviour_sources"]]
        if nots != ["%s.jpa.Jpa%sImpl" % (rp, n["parent"])]:
            return _fail("[%s] the inactive-profile implementation is named NOT the behaviour source: %s" % (label, nots))
        if any("jpa.Jpa" in str(m.get("source")) for m in beh.values()):
            return _fail("[%s] no member points at the inactive-profile implementation" % label)
        ver = {v["member"].rsplit("#", 1)[-1].split("(", 1)[0]: v for v in owed[0]["verification"]}
        if ver[n["delete"]]["status"] != "applicable" or ver[n["delete"]]["scenarios"] != ["sc:delete-%s-1" % e.lower()]:
            return _fail("[%s] the delete write is covered by the scenario that reads its effect back: %s" % (label, ver[n["delete"]]))
        if ver[n["save"]]["status"] != "unresolved" or ver[n["save"]]["scenarios"]:
            return _fail("[%s] a write no captured scenario reaches is an unresolved debt, never PASS: %s" % (label, ver[n["save"]]))
        if ver[n["q2"]]["status"] != "applicable":
            return _fail("[%s] a read reached by a captured read scenario is covered: %s" % (label, ver[n["q2"]]))

        # the broken forms, each with the CORRECT CDI shape, refused from the parse tree
        broken = {
            "throw UnsupportedOperationException": {"q2": "    public Collection<%s> %s() { throw new UnsupportedOperationException(\"todo\"); }\n" % (e, n["q2"])},
            "throw another exception type": {"id": "    public %s %s(int id) { throw new IllegalStateException(\"later\"); }\n" % (e, n["id"])},
            "empty mutator": {"save": "    public void %s(%s x) { }\n" % (n["save"], e)},
            "bare return mutator": {"delete": "    public void %s(%s x) { return; }\n" % (n["delete"], e)},
            "placeholder-only query": {"q": "    public Collection<%s> %s(String name) { return Collections.emptyList(); }\n" % (e, n["q"])},
            "null-returning query": {"id": "    public %s %s(int id) { return null; }\n" % (e, n["id"])},
            "private helper hiding a stub": {"q2": "    public Collection<%s> %s() { return load(); }\n"
                                                   "    private Collection<%s> load() { throw new RuntimeException(\"x\"); }\n" % (e, n["q2"], e)},
            "delegation cycle": {"q2": "    public Collection<%s> %s() { return again(); }\n"
                                       "    private Collection<%s> again() { return %s(); }\n" % (e, n["q2"], e, n["q2"])},
        }
        for why, over in broken.items():
            (root / impl_path).write_text(dest_sources(n, bodies(n, **over))[impl_path], encoding="utf-8")
            v = impl_verdict(root, scope)
            if v["verdict"] != "violates" or "STUB" not in v["detail"]:
                return _fail("[%s] %s must be refused as a stub: %s" % (label, why, v))
        # correct: real bodies; one owed member delegating to another real one
        good = bodies(n, q="    public Collection<%s> %s(String name) { return %s(); }\n" % (e, n["q"], n["q2"]))
        (root / impl_path).write_text(dest_sources(n, good)[impl_path], encoding="utf-8")
        v = impl_verdict(root, scope)
        if v["verdict"] != "ok":
            return _fail("[%s] a real implementation (one member delegating to another real owed member) passes: %s" % (label, v))

        # the brief renders the behaviour, the not-a-source row and the functional evidence
        from planner.paths import LOOP_DIR, LOOP_ISSUED, WORKLIST
        cid = str(cl["id"])
        sp = Path("evidence/planning/batch-scope") / cid.replace(":", "-") / ("%s.json" % scope["digest"][:32])
        write_canonical(root / sp, scope)
        ws = sorted(scope["writable_paths"])
        write_canonical(root / WORKLIST, {"schema": "rhoai3.worklist/v1", "head": cid, "unit_formation": "v1",
                                          "measure": {"tuple": [1, 0, 0], "known": True, "blocked": []},
                                          "clusters": [{"id": cid, "kind": "config", "path": ws[0], "write_set": ws,
                                                        "items": ["rt:boot:setwide"], "label": "fragments", "retry_key": "rk:unit:%s" % cid,
                                                        "batch_scope": {"path": sp.as_posix(), "digest": scope["digest"], "rule": scope["rule"],
                                                                        "kind": "unit", "unit_id": scope["unit_id"], "members": len(scope["members"])}}],
                                          "not_counted": [], "items": items})
        write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": cid, "task_id": "t_fragbeh", "write_set": ws})
        prev = os.environ.get("HERMES_KANBAN_TASK")
        os.environ["HERMES_KANBAN_TASK"] = "t_fragbeh"
        try:
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = __import__("brief").main(["--root", str(root)])
        finally:
            if prev is None:
                os.environ.pop("HERMES_KANBAN_TASK", None)
            else:
                os.environ["HERMES_KANBAN_TASK"] = prev
        if rc != 0:
            return _fail("[%s] brief.py serves the fragment unit: %s" % (label, err.getvalue()[:300]))
        unit = load_json(root / LOOP_DIR / ("brief-%s.json" % cid.replace(":", "-"))).get("unit") or {}
        imp = next((i for i in unit.get("implementation") or [] if i.get("path") == impl_path), {})
        text = json.dumps(imp)
        for token in ("LIKE :name%", "hibernate6-flush-before-query", "SpringData%sImpl#%s" % (n["parent"], n["delete"]),
                      "NOT the behaviour source", "Jpa%sImpl" % n["parent"], "committed", "unresolved"):
            if token not in text:
                return _fail("[%s] the brief renders %r: %s" % (label, token, text[:600]))
        if "@Typed" not in text:
            return _fail("[%s] the approved CDI shape stays in the brief" % label)
    return 0


def main() -> int:
    if not shutil.which("javac"):
        print("SKIP fragment-behaviour: no javac (not run)")
        return 0
    for n in (A, B):
        if case(n):
            return 1
    print("OK: fragment behaviour (V17-3): the seal carries the selected source behaviour per member bound to the decided "
          "profiles (@Query, override with the Hibernate 6 flush-order translation, CRUD defaults) and names the "
          "inactive-profile implementation as not the source; a throw of any type, an empty or bare-return mutator, a "
          "placeholder or null query, a private helper hiding a stub and a delegation cycle are refused with the approved "
          "CDI shape; a real implementation passes, delegation to a real owed member included; the brief renders the "
          "behaviour and the functional evidence (a covered write needs a committed read-back, an uncovered one stays "
          "unresolved); the same on a renamed twin with another profile name")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
