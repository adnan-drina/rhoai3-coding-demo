#!/usr/bin/env python3
"""Planned units end to end on the outcome board: derive -> admit/publish ->
issue a bounded scope -> execute a (scripted) candidate -> measure -> accept
-> continue, through the production entry points.

Derivation: planner.source_requirements.for_root on a destination root whose
M1 evidence (structure, entry points, captured corpus) names a Spring
controller with @CrossOrigin, a BindingResult guard and a UriComponentsBuilder
Location built from the REQUEST DTO, a Spring Data repository whose fragment
parent has no implementation in the decided build profile (an alternative
profile's does), and a decided build profile. Graph: the ONE builder,
outcome_graph.derive_initial_graph. Board: k4_graph publish/release (FakeNative,
qualification mode, SYNTHETIC). Issue, write check, verdict, acceptance and
completion: outcome_lifecycle.issue / check_write / record_verdict /
accept_commit / check_complete -- the acceptance recomputes each owner's
requirement checks on the committed tree (planner.requirement_checks) with the
real JDK model and the real frozen-source model.

Planned-unit kinds exercised (each with a BROKEN candidate the recomputed
checks refuse, then the correct one):
  * request-validation + handler-parameter-binding (with the Location
    obligation) + annotation-retirement, joined to the controller's finding
    cluster: inverted guard / bare build(dto.getId()) / CrossOrigin kept are
    refused; the faithful migration is accepted;
  * repository-architecture, a REQUIREMENT-ONLY planned unit (the owed
    <Parent>Impl): stub bodies are refused; the real implementation with the
    concrete-only CDI exposure is accepted once its read and committed-write
    scenarios are measured and discharged;
  * configuration-decision (build profiles), requirement-only: a candidate
    that decides another profile is refused; the decided one is accepted.

THE ISSUE PATH (wired by workstream B in outcome_lifecycle.issue; the test
seam that stood in for it is kept below for reference and NOT installed): when _allowed_paths finds no OPEN cluster for an outcome that has
planned_units or owns requirements, grant
outcome_graph.planned_unit_grant(node, revision["requirements"],
exists=<the tree>, cluster_open=False) -- its paths when refusal == "", under
cluster id "planned:<outcome_id>:1" -- and nothing otherwise. (Found by this
test: a finding outcome whose findings are gone while a requirement check
still fails would otherwise never be issued a scope again.) Everything else
is production code.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import source_requirements as SR  # noqa: E402
from planner import specimens as S  # noqa: E402
from planner import worklist as W  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402
from planner.evidence import derive_entry_points, load_catalogs  # noqa: E402

HERMES = HERE.parents[1]
SP = "org.springframework"
ANN = SP + ".web.bind.annotation"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


STUBS = {
    "src/main/java/org/springframework/web/bind/annotation/PostMapping.java":
        "package org.springframework.web.bind.annotation;\npublic @interface PostMapping { String[] value() default {}; }\n",
    "src/main/java/org/springframework/web/bind/annotation/GetMapping.java":
        "package org.springframework.web.bind.annotation;\npublic @interface GetMapping { String[] value() default {}; }\n",
    "src/main/java/org/springframework/web/bind/annotation/DeleteMapping.java":
        "package org.springframework.web.bind.annotation;\npublic @interface DeleteMapping { String[] value() default {}; }\n",
    "src/main/java/org/springframework/web/bind/annotation/RequestBody.java":
        "package org.springframework.web.bind.annotation;\npublic @interface RequestBody { }\n",
    "src/main/java/org/springframework/web/bind/annotation/CrossOrigin.java":
        "package org.springframework.web.bind.annotation;\npublic @interface CrossOrigin { String[] exposedHeaders() default {}; }\n",
    "src/main/java/org/springframework/data/repository/Repository.java":
        "package org.springframework.data.repository;\npublic interface Repository<T, ID> { }\n",
    "src/main/java/jakarta/validation/Valid.java": "package jakarta.validation;\npublic @interface Valid { }\n",
}
DEST_ONLY = {
    "src/main/java/jakarta/validation/Validator.java":
        "package jakarta.validation;\npublic interface Validator { <T> java.util.Set<Object> validate(T t); }\n",
    "src/main/java/jakarta/ws/rs/core/Context.java": "package jakarta.ws.rs.core;\npublic @interface Context { }\n",
    "src/main/java/jakarta/ws/rs/core/UriBuilder.java":
        "package jakarta.ws.rs.core;\npublic abstract class UriBuilder {\n"
        "    public abstract UriBuilder path(String p);\n    public abstract java.net.URI build(Object... v);\n}\n",
    "src/main/java/jakarta/ws/rs/core/UriInfo.java": "package jakarta.ws.rs.core;\npublic interface UriInfo { UriBuilder getBaseUriBuilder(); }\n",
    "src/main/java/jakarta/enterprise/context/ApplicationScoped.java":
        "package jakarta.enterprise.context;\npublic @interface ApplicationScoped { }\n",
    "src/main/java/jakarta/enterprise/inject/Typed.java":
        "package jakarta.enterprise.inject;\npublic @interface Typed { Class<?>[] value() default {}; }\n",
}


class World:
    def __init__(self, base: str, names: dict[str, str]):
        self.base, self.n = base, names
        self.pkg = base.replace(".", "/")
        self.ctrl = "src/main/java/%s/api/%s.java" % (self.pkg, names["ctrl"])
        self.dto = "src/main/java/%s/dto/%s.java" % (self.pkg, names["dto"])
        self.entity = "src/main/java/%s/store/%s.java" % (self.pkg, names["entity"])
        self.parent = "src/main/java/%s/store/%s.java" % (self.pkg, names["parent"])
        self.repo = "src/main/java/%s/store/%s.java" % (self.pkg, names["repo"])
        self.alt = "src/main/java/%s/store/sql/Sql%s.java" % (self.pkg, names["parent"])
        self.impl = "src/main/java/%s/store/%sImpl.java" % (self.pkg, names["parent"])

    def fq(self, sub: str, name: str) -> str:
        return "%s.%s.%s" % (self.base, sub, name)

    # --- sources ---------------------------------------------------------
    def spring_ctrl(self) -> str:
        n = self.n
        return ("package %s.api;\nimport %s.PostMapping;\nimport %s.GetMapping;\nimport %s.DeleteMapping;\nimport %s.RequestBody;\n"
                "import %s.CrossOrigin;\nimport jakarta.validation.Valid;\nimport %s.validation.BindingResult;\n"
                "import %s.web.util.UriComponentsBuilder;\nimport %s;\n"
                "@CrossOrigin(exposedHeaders = \"errors\")\npublic class %s {\n"
                '    @PostMapping("/api/%s")\n'
                "    public String %s(@RequestBody @Valid %s dto, BindingResult bindingResult, UriComponentsBuilder ucBuilder) {\n"
                '        if (bindingResult.hasErrors()) { return "400"; }\n'
                '        return ucBuilder.path("/api/%s/{id}").buildAndExpand(dto.getId()).toUri().toString();\n    }\n}\n'
                % (self.base, ANN, ANN, ANN, ANN, ANN, SP, SP, self.fq("dto", n["dto"]), n["ctrl"], n["route"], n["add"],
                   n["dto"], n["route"]))

    def dest_ctrl(self, *, guard: str = "!validator.validate(dto).isEmpty()", arg: str = 'dto.getId() == null ? "" : dto.getId()',
                  cross: bool = False) -> str:
        n = self.n
        return ("package %s.api;\nimport %s.PostMapping;\nimport %s.RequestBody;\nimport %s.CrossOrigin;\n"
                "import jakarta.validation.Validator;\nimport jakarta.ws.rs.core.Context;\nimport jakarta.ws.rs.core.UriInfo;\n"
                "import %s;\n%spublic class %s {\n    Validator validator;\n"
                '    @PostMapping("/api/%s")\n'
                "    public String %s(@RequestBody %s dto, @Context UriInfo uriInfo) {\n"
                '        if (%s) { return "400"; }\n'
                '        return uriInfo.getBaseUriBuilder().path("/api/%s/{id}").build(%s).toString();\n    }\n}\n'
                % (self.base, ANN, ANN, ANN, self.fq("dto", n["dto"]), '@CrossOrigin(exposedHeaders = "errors")\n' if cross else "",
                   n["ctrl"], n["route"], n["add"], n["dto"], guard, n["route"], arg))

    def domain(self) -> dict[str, str]:
        n, b = self.n, self.base
        return {
            self.dto: "package %s.dto;\npublic class %s { public Integer getId() { return null; } }\n" % (b, n["dto"]),
            self.entity: "package %s.store;\npublic class %s { public Integer id; }\n" % (b, n["entity"]),
            self.parent: "package %s.store;\nimport java.util.List;\npublic interface %s {\n    List<%s> findAll();\n    void delete(%s e);\n}\n"
                         % (b, n["parent"], n["entity"], n["entity"]),
            self.repo: "package %s.store;\npublic interface %s extends org.springframework.data.repository.Repository<%s, Integer>, %s { }\n"
                       % (b, n["repo"], n["entity"], n["parent"]),
        }

    def impl_src(self, *, stub: bool) -> str:
        n = self.n
        body = ("    public List<%s> findAll() { throw new UnsupportedOperationException(); }\n"
                "    public void delete(%s e) { }\n" % (n["entity"], n["entity"])) if stub else (
            "    private final Map<Integer, %s> rows = new HashMap<>();\n"
            "    public List<%s> findAll() { return new ArrayList<>(rows.values()); }\n"
            "    public void delete(%s e) { rows.remove(e.id); }\n" % (n["entity"], n["entity"], n["entity"]))
        return ("package %s.store;\nimport java.util.*;\nimport jakarta.enterprise.context.ApplicationScoped;\n"
                "import jakarta.enterprise.inject.Typed;\n@ApplicationScoped\n@Typed(%sImpl.class)\npublic class %sImpl implements %s {\n%s}\n"
                % (self.base, n["parent"], n["parent"], n["parent"], body))

    # --- M1 evidence -------------------------------------------------------
    def types(self) -> list[dict]:
        n = self.n
        dto = self.fq("dto", n["dto"])
        ctrl = self.fq("api", n["ctrl"])
        parent, ent = self.fq("store", n["parent"]), self.fq("store", n["entity"])

        def ann(fqn, **values):
            return {"fqn": fqn, "values": {k: (v if isinstance(v, list) else [v]) for k, v in values.items()}}

        def m(name, sig, anns, params, calls=()):
            return {"name": name, "signature": sig, "annotations": anns, "params": params, "resolution": "full",
                    "returns": "java.lang.String", "type_refs": [], "calls": [{"owner": o, "name": c} for o, c in calls]}

        return [
            {"fqn": ctrl, "kind": "class", "path": self.ctrl, "resolution": "full", "supertypes": [],
             "annotations": [ann(ANN + ".RestController"), ann(ANN + ".CrossOrigin", exposedHeaders=["errors"])],
             "methods": [
                 m(n["add"], "%s(%s,%s.validation.BindingResult,%s.web.util.UriComponentsBuilder)" % (n["add"], dto, SP, SP),
                   [ann(ANN + ".PostMapping", value=["/api/%s" % n["route"]])],
                   [{"name": "dto", "type": dto, "annotations": [ann(ANN + ".RequestBody"), ann("jakarta.validation.Valid")]},
                    {"name": "bindingResult", "type": SP + ".validation.BindingResult", "annotations": []},
                    {"name": "ucBuilder", "type": SP + ".web.util.UriComponentsBuilder", "annotations": []}]),
                 m("list", "list()", [ann(ANN + ".GetMapping", value=["/api/%s" % n["route"]])], [], [(parent, "findAll")]),
                 m("remove", "remove(int)", [ann(ANN + ".DeleteMapping", value=["/api/%s/{id}" % n["route"]])],
                   [{"name": "id", "type": "int", "annotations": []}], [(parent, "delete")]),
             ]},
            {"fqn": parent, "kind": "interface", "path": self.parent, "resolution": "full", "supertypes": [], "annotations": [],
             "methods": [m("findAll", "findAll()", [], []), m("delete", "delete(%s)" % ent, [], [{"name": "e", "type": ent, "annotations": []}])]},
            {"fqn": self.fq("store", n["repo"]), "kind": "interface", "path": self.repo, "resolution": "full", "annotations": [],
             "supertypes": [SP + ".data.repository.Repository", parent], "methods": []},
            {"fqn": self.fq("store.sql", "Sql" + n["parent"]), "kind": "class", "path": self.alt, "resolution": "full",
             "annotations": [ann(SP + ".context.annotation.Profile", value=[n["alt_profile"]])], "supertypes": [parent],
             "methods": [m("findAll", "findAll()", [], [])]},
            {"fqn": ent, "kind": "class", "path": self.entity, "resolution": "full", "supertypes": [], "annotations": [], "methods": []},
        ]


NAMES_A = {"ctrl": "CrateController", "dto": "CrateDto", "entity": "Crate", "parent": "CrateLedger", "repo": "CrateStore",
           "route": "crates", "add": "addCrate", "profile": "depot-orm", "alt_profile": "depot-sql"}
NAMES_B = {"ctrl": "LeafEndpoint", "dto": "LeafForm", "entity": "Leaf", "parent": "LeafBook", "repo": "LeafVault",
           "route": "leaves", "add": "plant", "profile": "garden-jpa", "alt_profile": "garden-jdbc"}


def run_world(base: str, names: dict[str, str]) -> int:
    ob = _load("obt_e2e", HERE / "outcome_board.test.py")
    w = World(base, names)
    types = w.types()
    eps = derive_entry_points({"types": types}, load_catalogs(HERMES.parent))
    by_member = {e["member"].split("(", 1)[0]: e["id"] for e in eps}
    corpus = {"schema": "rhoai3.scenario-corpus/v1", "scenarios": [
        {"id": "sc:list", "entry_point": by_member["list"], "method": "GET", "path": "/api/%s" % names["route"], "effects": []},
        {"id": "sc:remove", "entry_point": by_member["remove"], "method": "DELETE", "path": "/api/%s/1" % names["route"],
         "effects": [{"id": "eff:after-remove", "method": "GET", "path": "/api/%s/1" % names["route"]}]},
        {"id": "sc:add", "entry_point": by_member[names["add"]], "method": "POST", "path": "/api/%s" % names["route"], "effects": []},
    ]}
    items = [{"id": "err:ctrl-br", "source": "javac", "kind": "compile", "category": "mandatory", "path": w.ctrl, "line": 8,
              "rule_id": "compiler.err.doesnt.exist", "message": "package %s.validation does not exist" % SP}]
    wl = {"schema": "rhoai3.worklist/v1", "items": items, "clusters": W.cluster_items(items, {}, set()), "unlocatable": [],
          "not_counted": [], "measure": {"known": True, "tuple": [0, 1, 0]}}
    oracles: dict[str, list[str]] = {}
    for sc in corpus["scenarios"]:
        oracles.setdefault(sc["entry_point"], []).append(sc["id"])
    inventory = [{"entry_point_id": e["id"], "file": w.ctrl, "kind": e.get("kind") or "http"} for e in eps]
    fx = {"worklist": wl, "entry_points": inventory, "oracles": oracles, "references": {},
          "provenance": {"snapshot_kind": "synthetic", "scope_note": "planned units e2e", "construction": "planned_units_e2e.test",
                         "observed_migration_event": False}}
    run = ob.Run(fx=fx, publish=False)
    orig = L._allowed_paths

    def seam(root, node, worklist, owned=None):
        # TEST SEAM ONLY: the issue-side wiring workstream B is asked to implement
        c, paths = orig(root, node, worklist, owned)
        if c or not (node.get("planned_units") or node.get("requirements")):
            return c, paths
        from planner.outcome_store import Store
        rev = Store(Path(root)).current_revision() or {}
        # c == "": no open cluster grants this outcome anything now
        g = OG.planned_unit_grant(node, rev.get("requirements") or [], exists=lambda p: (Path(root) / p).exists(),
                                  cluster_open=False)
        return ("planned:%s:1" % node["outcome_id"], g["paths"]) if not g["refusal"] else ("", [])

    # the seam is no longer installed: outcome_lifecycle.issue grants planned units itself (workstream B)
    del seam
    try:
        root = run.root
        pins = json.loads((root / ".hermes/pins.json").read_text())
        pins["pins"]["quarkus_platform"] = {"java_release": 21}
        (root / ".hermes/pins.json").write_text(json.dumps(pins))
        for sub in ("catalogs", "schemas"):
            shutil.copytree(HERMES / "planning" / sub, root / ".hermes/planning" / sub, dirs_exist_ok=True)
        dec = S.full_decisions()
        # (the decided datasource is its own requirement-only unit; its checker is check-datasource-decision)
        dec["build_profiles"] = {"adr": "ADR-001", "active": [names["profile"]]}
        (root / "decisions.yaml").write_text(S.decisions_yaml(dec), encoding="utf-8")
        for rel, text in {**STUBS, **DEST_ONLY, **w.domain(), w.ctrl: w.spring_ctrl()}.items():
            run.edit(rel, text)
        for rel, text in {**STUBS, **w.domain(), w.ctrl: w.spring_ctrl()}.items():
            run.edit(".derived/frozen-input/" + rel, text)
        # the source's own configuration: where it serves (round 3)
        run.edit(".derived/frozen-input/src/main/resources/application.properties",
                 "server.port=9966\nserver.servlet.context-path=/%s-app/\n" % names["route"])
        run.edit("pom.xml", "<project><dependencies><dependency><groupId>io.quarkus</groupId>"
                            "<artifactId>quarkus-jdbc-postgresql</artifactId></dependency></dependencies></project>\n")
        run.edit("src/main/resources/application.properties", "quarkus.profile=%s\n" % names["alt_profile"])
        for rel in ("schema_sql", "seed_sql"):
            run.edit(dec["datasource"][rel], "-- %s\n" % rel)
        ds = dec["datasource"]
        # this run's own parity database, as the RHDH template assigns it (no
        # endpoint in the environment: analysis may proceed, nothing connects)
        run.edit("migration.yaml", "migration:\n  target: quarkus\nresources:\n  run: e2e-run\n  namespace: e2e\n"
                                   "  receipt_env: PARITY_RUN_RECEIPT\n  parity_database:\n    instance: %s\n    database: parity\n"
                                   "    port: 5432\n    server_secret: e2e-parity-postgres\n    workspace_secret: e2e-parity-db\n"
                                   "    jdbc_url_env: %s\n    username_env: %s\n    password_env: %s\n"
                                   % (ds["instance"], ds["jdbc_url_env"], ds["username_env"], ds["password_env"]))
        run.edit(".mvn/maven.config", "-Dquarkus.profile=%s\n" % names["alt_profile"])
        write_canonical(root / "evidence/planning/evidence-bundle.json",
                        {"schema": "rhoai3.evidence-bundle/v1", "structure": {"available": True, "mode": "full", "types": types},
                         "entry_points": eps})
        write_canonical(root / "verification/scenarios/corpus.json", corpus)
        ob.git(root, "add", "-A")
        ob.git(root, "commit", "-qm", "M1 evidence and the bootstrapped tree")

        # --- derive (production) and publish ---
        reqs = SR.for_root(root, oracles=L._oracles(root))["requirements"]
        byrule = {}
        for r in reqs:
            byrule.setdefault(r["rule"].split("/")[0], []).append(r)
        want = {"request-validation", "handler-parameter-binding", "annotation-retirement", "repository-architecture",
                "configuration-decision"}
        if not want <= {k for k, v in byrule.items() if any(x["status"] == "applicable" for x in v)}:
            return _fail("[%s] every planned-unit kind is derived applicable: %s" % (base, {k: [x["status"] for x in v] for k, v in byrule.items()}))
        loc = [r for r in byrule["handler-parameter-binding"] if "unit:location-null-arguments" in r["acceptance"]]
        if not loc:
            return _fail("[%s] the URI builder handler carries the Location obligation" % base)
        run.plan = ob.derive(fx, requirements=reqs)
        run.publish()
        run.release()
        rev = run.store.current_revision()
        acct = rev["requirement_ownership"]
        owner = {k: acct[byrule[k][0]["id"]] for k in want if byrule[k][0]["status"] == "applicable"}
        rep = [r for r in byrule["repository-architecture"] if r["status"] == "applicable"][0]
        cfg = [r for r in byrule["configuration-decision"] if r["subject"] == "build_profiles"][0]
        owner["repository-architecture"], owner["configuration-decision"] = acct[rep["id"]], acct[cfg["id"]]
        ctrl_owner = owner["request-validation"]
        if not (owner["handler-parameter-binding"] == owner["annotation-retirement"] == ctrl_owner and ctrl_owner.startswith("source:")):
            return _fail("[%s] the controller requirements join the controller's finding cluster: %s" % (base, owner))
        if not (owner["repository-architecture"].startswith("requirement:") and owner["configuration-decision"].startswith("requirement:")):
            return _fail("[%s] the repository and configuration units are requirement-only: %s" % (base, owner))
        nodes = {n["outcome_id"]: n for n in rev["nodes"]}

        def attempt(oid: str, edits: dict[str, str], attempt_no: str, *, runtime_ok=True, scenarios=(), drop=True):
            tid, rid, iss = run.issue(oid)
            ctx = run.ctx()
            if not iss["allowed_paths"]:
                raise AssertionError("%s was issued no scope" % oid)
            for rel, text in edits.items():
                run.edit(rel, text)
            L.check_write(ctx, task_id=tid, run_id=rid, rel_paths=sorted(edits))
            L.record_verdict(ctx, task_id=tid, run_id=rid, verdict="ACCEPTED", candidate=ctx.product_tree(), attempt=attempt_no)
            ob.git(root, "add", "-A")
            ob.git(root, "commit", "-qm", "%s attempt %s" % (oid, attempt_no), "--allow-empty")
            if drop:
                run.drop(*nodes[oid]["obligations"])
            run.worklist["runtime"] = {"package": {"ran": True, "rc": 0 if runtime_ok else 1},
                                       "boot": {"ran": True, "rc": 0 if runtime_ok else 1, "ready": runtime_ok}}
            run.save_worklist()
            # the scenarios this attempt claims are MEASURED: a PASS record bound to the candidate tree each
            # (requirement_checks accepts nothing else, v29 Owner)
            sdir = root / "verification" / "parity" / "scenarios"
            sdir.mkdir(parents=True, exist_ok=True)
            for f in sdir.glob("*.json"):
                f.unlink()
            for sid in scenarios:
                (sdir / ("%s.json" % sid.replace(":", "_"))).write_text(json.dumps(
                    {"schema": "rhoai3.scenario-parity/v1", "scenario": sid, "verdict": "PASS",
                     "binding": {"mode": "candidate", "candidate_sha256": ctx.product_tree()}}))
            out = L.accept_commit(ctx, task_id=tid, run_id=rid, attempt=attempt_no, commit=ob.git(root, "rev-parse", "HEAD"),
                                  measurement={"classes": ["build", "compile", "tests", "runtime", "parity"], "scenarios": list(scenarios)})
            meas = [r["doc"] for r in run.store.ledger("_measure")][-1]
            if out["outcome_accepted"]:
                L.check_complete(ctx, task_id=tid, run_id=rid, profile="implementer", audit_green=False)
                run.native.complete(tid)
            return out, iss, meas

        ds_req = [r for r in byrule["configuration-decision"] if r["subject"] == "datasource"][0]
        owner["datasource"] = acct[ds_req["id"]]
        ap = [r for r in byrule.get("application-path", []) if r["status"] == "applicable"]
        if [(r["facts"]["dest_key"], r["facts"]["dest_value"]) for r in ap] != [("quarkus.http.root-path", "/%s-app" % names["route"])]:
            return _fail("[%s] the source's context path is an owed application path: %s" % (base, byrule.get("application-path")))
        owner["application-path"] = acct[ap[0]["id"]]
        if owner["application-path"] != owner["datasource"]:
            return _fail("[%s] the application path joins the configuration owner of the same file: %s" % (base, owner))
        targets = {ctrl_owner, owner["repository-architecture"], owner["configuration-decision"], owner["datasource"]}
        props = {"quarkus.profile": names["alt_profile"]}

        def render() -> str:
            return "".join("%s=%s\n" % kv for kv in sorted(props.items()))

        def do_controller(oid: str) -> str:
            broken = (("inverted guard", w.dest_ctrl(guard="validator.validate(dto).isEmpty()"), "unit:handler-validation-guards"),
                      ("bare Location argument", w.dest_ctrl(arg="dto.getId()"), "unit:location-null-arguments"),
                      ("CrossOrigin kept", w.dest_ctrl(cross=True), "structure:annotation-absent:%s.CrossOrigin" % ANN))
            k = 0
            for label, text, chk in broken:
                k += 1
                out, iss, meas = attempt(oid, {w.ctrl: text}, str(k), scenarios=["sc:add"])
                if out["outcome_accepted"] or meas["check_status"].get(chk, {}).get("status") != "fail":
                    return "controller: %s must be refused by %s: %s" % (label, chk, meas.get("check_status"))
                if w.ctrl not in iss["allowed_paths"]:
                    return "the controller's scope is its cluster: %s" % iss["allowed_paths"]
            out, _iss, meas = attempt(oid, {w.ctrl: w.dest_ctrl()}, str(k + 1), scenarios=["sc:add"])
            return "" if out["outcome_accepted"] else "the faithful controller is accepted: %s" % meas.get("check_status")

        def do_repository(oid: str) -> str:
            out, iss, meas = attempt(oid, {w.impl: w.impl_src(stub=True)}, "1", scenarios=["sc:list", "sc:remove"], drop=False)
            if iss["cluster"] != "planned:%s:1" % oid or w.impl not in iss["allowed_paths"] or w.ctrl in iss["allowed_paths"]:
                return "the planned unit's bounded grant is its own planned paths: %s" % iss
            if out["outcome_accepted"] or meas["check_status"]["unit:fragment-behaviour-bodies"]["status"] != "fail":
                return "stub delegates are refused: %s" % meas["check_status"]
            out, iss, meas = attempt(oid, {w.impl: w.impl_src(stub=False)}, "2", scenarios=["sc:list"], drop=False)
            eff = "behavior:repository-effects:%s" % w.fq("store", names["parent"])
            if out["outcome_accepted"] or meas["check_status"][eff]["status"] != "unknown":
                return "a write never measured keeps the unit open: %s" % meas["check_status"]
            out, iss, meas = attempt(oid, {w.impl: w.impl_src(stub=False) + "// measured\n"}, "3", scenarios=["sc:list", "sc:remove"], drop=False)
            return "" if out["outcome_accepted"] else "the real delegate with its read and write scenarios is accepted: %s" % meas["check_status"]

        def do_profiles(oid: str) -> str:
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render()}, "1", drop=False)
            if out["outcome_accepted"] or meas["check_status"]["config:decided-keys"]["status"] != "fail":
                return "another profile than the decided one is refused: %s" % meas["check_status"]
            props["quarkus.profile"] = names["profile"]
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render(),
                                           ".mvn/maven.config": "-Dquarkus.profile=%s\n" % names["profile"]}, "2", drop=False)
            return "" if out["outcome_accepted"] else "the decided build profile is accepted: %s (%s)" % (meas["check_status"], iss["allowed_paths"])

        def do_datasource(oid: str) -> str:
            ds = dec["datasource"]
            props.update({"quarkus.datasource.db-kind": ds["db_kind"], "quarkus.datasource.jdbc.url": "${%s}" % ds["jdbc_url_env"],
                          "quarkus.datasource.username": "${%s}" % ds["username_env"], "quarkus.datasource.password": "literal-secret",
                          "quarkus.hibernate-orm.database.generation": ds["hibernate_generation"]})
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render()}, "1", drop=False)
            if out["outcome_accepted"] or meas["check_status"]["config:decided-keys"]["status"] != "fail":
                return "a literal credential is refused by check-datasource-decision: %s" % meas["check_status"]
            props["quarkus.datasource.password"] = "${%s}" % ds["password_env"]
            if owner["configuration-decision"] == owner["datasource"]:
                return ""
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render()}, "2", drop=False)
            if out["outcome_accepted"] or meas["check_status"]["config:application-path"]["status"] != "fail":
                return "the decided datasource without the source's context path is still refused: %s" % meas["check_status"]
            props["quarkus.http.root-path"] = "/%s-app/" % names["route"]
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render()}, "3", drop=False)
            return "" if out["outcome_accepted"] else "the decided datasource under the source's path is accepted: %s" % meas["check_status"]

        def do_both(oid: str) -> str:
            # the two decided-configuration requirements share one owner (the
            # properties file both render): each broken half refuses the whole
            return do_datasource(oid) or do_profiles_after(oid)

        def do_profiles_after(oid: str) -> str:
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render()}, "3", drop=False)
            if out["outcome_accepted"] or meas["check_status"]["config:decided-keys"]["status"] != "fail":
                return "the right datasource with another build profile is still refused: %s" % meas["check_status"]
            props["quarkus.profile"] = names["profile"]
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render(),
                                           ".mvn/maven.config": "-Dquarkus.profile=%s\n" % names["profile"]}, "4", drop=False)
            if out["outcome_accepted"] or meas["check_status"]["config:application-path"]["status"] != "fail":
                return "the destination not serving under the source's context path is refused: %s" % meas["check_status"]
            props["quarkus.http.root-path"] = "/%s-app/" % names["route"]
            out, iss, meas = attempt(oid, {"src/main/resources/application.properties": render()}, "5", drop=False)
            return "" if out["outcome_accepted"] else "both decisions rendered are accepted: %s" % meas["check_status"]

        scripted = {ctrl_owner: do_controller, owner["repository-architecture"]: do_repository}
        if owner["configuration-decision"] == owner["datasource"]:
            scripted[owner["datasource"]] = do_both
        else:
            scripted[owner["configuration-decision"]] = do_profiles
            scripted[owner["datasource"]] = do_datasource
        need: set[str] = set()
        frontier = list(targets)
        while frontier:
            x = frontier.pop()
            if x in need or x not in nodes:
                continue
            need.add(x)
            frontier.extend(nodes[x].get("parents") or [])
        for n in OG.topo_order(rev["nodes"]):
            oid = n["outcome_id"]
            if oid not in need or n["role"] != "repair":
                continue
            if oid not in scripted:
                return _fail("[%s] an unscripted prerequisite %s stands before the planned units" % (base, oid))
            err = scripted[oid](oid)
            if err:
                return _fail("[%s] %s" % (base, err))

        # --- continue: every repair outcome accepted, the account says so ---
        acc = L.progress_account(run.store, run.ctx().product_tree())
        done = {n["outcome_id"] for n in rev["nodes"] if (L._outcome(run.store, n["outcome_id"]) or {}).get("status") == "accepted"}
        if not targets <= done:
            return _fail("[%s] the three units are accepted: %s" % (base, sorted(targets - done)))
        if acc["accepted_historically"] < 3:
            return _fail("[%s] the account counts them: %s" % (base, acc))
    finally:
        L._allowed_paths = orig
        run.close()
    return 0


def main() -> int:
    if not shutil.which("javac"):
        print("SKIP planned_units_e2e: no javac (not run)")
        return 0
    for base, names in (("com.example.depot", NAMES_A), ("org.acme.garden", NAMES_B)):
        if run_world(base, names):
            return 1
    print("OK: planned units end to end (derive -> publish/release -> issue a bounded scope -> scripted candidate -> recomputed "
          "requirement checks -> accept -> complete): the controller unit refuses an inverted guard, a bare Location argument "
          "and a kept CrossOrigin and accepts the faithful migration; the requirement-only repository unit (issued through "
          "planned_unit_grant in outcome_lifecycle.issue) refuses stub bodies and an unmeasured write and accepts the real delegate with its "
          "scenarios; the requirement-only configuration unit refuses another profile and accepts the decided one; twice, renamed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
