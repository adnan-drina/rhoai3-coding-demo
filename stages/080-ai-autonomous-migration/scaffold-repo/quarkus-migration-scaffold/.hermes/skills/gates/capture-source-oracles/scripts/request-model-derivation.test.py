#!/usr/bin/env python3
"""request-model derivation selftest (M-1): a write the document's PATHS do not
bind is derived from the handler's own REQUEST MODEL, never left without an
oracle and never filled with invented values.

v29's initial plan kept twelve HTTP entry points with no captured oracle. For
eleven the OpenAPI document named no operation for the route (or named one
under path variables the route cannot supply) while the build GENERATES the
handler's @RequestBody type from that same document's components; the twelfth
was a read whose route carries a whole-segment wildcard. The fixture here has
the same SHAPES under its own names:

  Kind     a standalone entity whose model REQUIRES its readOnly identity
  Item     references Kind, owns a required readOnly collection, and its table
           requires a column (holder) the request model cannot carry
  Tag      a create whose handler builds no Location
  Account  a client-keyed create with no route that reads it back

and the renamed twin changes every package, type, member, route, schema,
property, table, column, seed value and the generator's naming convention
(suffix -> prefix). The decisions must be identical after the names are
erased; the bodies, ids and digests must change with the inputs.

Also: the whole-segment wildcard is filled (a mixed or ambiguous one stays a
gap), the read oracle of a wildcard route is captured at the filled path, the
qualification gate judges ``read_back_properties`` and
``creates_without_location``, and the planner keeps a write whose scenarios
cannot read back what it persisted UNRESOLVED with the reason.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DERIVE = HERE / "derive-source-scenarios.py"
QUALIFY = HERE / "qualify-source-captures.py"
CAPTURE_READS = HERE / "capture-source-oracles.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
from _oracle_common import normalize_body, retain_body, slug  # noqa: E402
from _scenarios import (QUALIFICATION, SCENARIO_ORACLES, WILDCARD_SEGMENT_FILL, corpus_digest, fill_route_wildcards,  # noqa: E402
                        load_corpus, request_of, route_matches, scenario_slug)
from planner import source_requirements  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, STRUCTURE, producer_receipt  # noqa: E402

CORPUS_P = Path("verification") / "scenarios" / "corpus.json"
BASE = "http://127.0.0.1:9966/ctx"
_SPRING = "org.springframework.web.bind.annotation."
_JPA = "javax.persistence."


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# the fixture, parameterized by every name it uses
# --------------------------------------------------------------------------
class Names:
    def __init__(self, **kw: str) -> None:
        self.__dict__.update(kw)

    def pairs(self) -> list[tuple[str, str]]:
        return sorted(self.__dict__.items())


# Every name is distinctive in both specimens, so erasing them cannot touch the
# harness's own words. Routes ARE the table names (the path variables resolve
# through them, as on the pilot).
PLAIN = Names(
    web="a.web", dto="a.dto", model="a.model", prefix="", suffix="Dto",
    Kind="Specie", Item="Critter", Tag="Plaque", Account="Patron", Holder="Keeper", item_lc="critter",
    kinds="species", items="critters", tags="plaques", accounts="patrons", holders="keepers",
    name="moniker", label="nickname", kindId="specieRef", kind="specie", notes="jottings", Note="Jotting", text="scribble",
    title="banner", handle="alias", secret="passcode", holder="keeper",
    label_col="nick_txt", label_var="nickTxt", kind_col="specie_ref", holder_col="keeper_ref", handle_col="alias_nm",
    secret_col="pass_txt", r_legacy="olden",
    v_one="vonex", v_two="vtwox", v_alpha="valphx", v_rex="rexish", v_max="maxish", v_root="rootish", v_newkey="neo.keyq",
    v_titleA="firstish", v_topic="topicish",
)
TWIN = Names(
    web="z.gateway", dto="z.wire", model="z.domain", prefix="Wire", suffix="",
    Kind="Grade", Item="Parcel", Tag="Badge", Account="Member", Holder="Ledger", item_lc="parcel",
    kinds="grades", items="parcels", tags="badges", accounts="members", holders="ledgers",
    name="caption", label="headline", kindId="gradeRef", kind="grade", notes="remarks", Note="Remark", text="bodytext",
    title="motto", handle="login", secret="phrase", holder="ledger",
    label_col="headline_txt", label_var="headlineTxt", kind_col="grade_ref", holder_col="ledger_ref", handle_col="login_nm",
    secret_col="phrase_txt", r_legacy="archive",
    v_one="unoq", v_two="dosq", v_alpha="omegq", v_rex="kipq", v_max="luxq", v_root="bossq", v_newkey="zed.keyz",
    v_titleA="goldq", v_topic="themeq",
)


def _api_docs(n: Names, *, account_key: str = "") -> str:
    key = account_key or n.v_newkey
    return (
        "openapi: 3.0.1\n"
        "info:\n  title: fixture\n  version: '1'\n"
        "paths:\n"
        # the only operation: the item create under a nested path whose
        # variable the controller's route cannot supply (v29's addPet shape)
        "  /%s/{%sId}/%s:\n" % (n.r_legacy, n.holder, n.items) +
        "    post:\n      operationId: add%s\n" % n.Item +
        "      requestBody:\n        content:\n          application/json:\n            schema:\n"
        "              $ref: '#/components/schemas/%sFields'\n" % n.Item +
        "      responses:\n        '201':\n          description: created\n"
        "components:\n  schemas:\n"
        "    %s:\n      type: object\n      properties:\n" % n.Kind +
        "        id:\n          type: integer\n          readOnly: true\n          example: 1\n"
        "        %s:\n          type: string\n          minLength: 1\n          example: %s\n" % (n.name, n.v_alpha) +
        "      required:\n        - id\n"
        "    %sFields:\n      type: object\n      properties:\n" % n.Item +
        "        %s:\n          type: string\n          pattern: '^[a-z]*$'\n          example: %s\n" % (n.label, n.v_rex) +
        "        %s:\n          type: integer\n          example: 1\n" % n.kindId +
        "      required:\n        - %s\n" % n.label +
        "    %s:\n      allOf:\n        - $ref: '#/components/schemas/%sFields'\n" % (n.Item, n.Item) +
        "        - type: object\n          properties:\n"
        "            id:\n              type: integer\n              readOnly: true\n              example: 1\n"
        "            %s:\n              $ref: '#/components/schemas/%s'\n" % (n.kind, n.Kind) +
        "            %s:\n              type: array\n              readOnly: true\n              items:\n"
        "                $ref: '#/components/schemas/%s'\n" % (n.notes, n.Note) +
        "          required:\n            - id\n            - %s\n            - %s\n" % (n.kind, n.notes) +
        "    %s:\n      type: object\n      properties:\n" % n.Note +
        "        id:\n          type: integer\n          readOnly: true\n          example: 1\n"
        "        %s:\n          type: string\n          example: %s\n" % (n.text, n.v_topic) +
        "    %s:\n      type: object\n      properties:\n" % n.Tag +
        "        id:\n          type: integer\n          readOnly: true\n          example: 1\n"
        "        %s:\n          type: string\n          minLength: 1\n          example: %s\n" % (n.title, n.v_titleA) +
        "      required:\n        - id\n        - %s\n" % n.title +
        "    %s:\n      type: object\n      properties:\n" % n.Account +
        "        %s:\n          type: string\n          minLength: 1\n          example: %s\n" % (n.handle, key) +
        "        %s:\n          type: string\n          minLength: 1\n          example: 1234\n" % n.secret +
        "      required:\n        - %s\n" % n.handle
    )


def _pom(n: Names, *, input_spec: str = "${project.basedir}/src/main/resources/api-docs.yml", package: str = "") -> str:
    naming = ("<modelNamePrefix>%s</modelNamePrefix>" % n.prefix if n.prefix else "") + \
             ("<modelNameSuffix>%s</modelNameSuffix>" % n.suffix if n.suffix else "")
    return ("<project><build><plugins><plugin><groupId>org.openapitools</groupId>"
            "<artifactId>openapi-generator-maven-plugin</artifactId><version>5.2.1</version>"
            "<executions><execution><goals><goal>generate</goal></goals><configuration>"
            "<inputSpec>%s</inputSpec><modelPackage>%s</modelPackage><generatorName>spring</generatorName>%s"
            "<generateApis>false</generateApis></configuration></execution></executions></plugin></plugins></build></project>"
            % (input_spec, package or n.dto, naming))


def _schema_sql(n: Names) -> str:
    return (
        "CREATE TABLE %s (\n  id INTEGER IDENTITY PRIMARY KEY,\n  %s VARCHAR(80)\n);\n" % (n.kinds, n.name) +
        "CREATE TABLE %s (\n  id INTEGER IDENTITY PRIMARY KEY\n);\n" % n.holders +
        "CREATE TABLE %s (\n  id INTEGER IDENTITY PRIMARY KEY,\n  %s VARCHAR(30),\n  %s INTEGER NOT NULL,\n  %s INTEGER NOT NULL\n);\n"
        % (n.items, n.label_col, n.kind_col, n.holder_col) +
        "ALTER TABLE %s ADD CONSTRAINT fk_a FOREIGN KEY (%s) REFERENCES %s (id);\n" % (n.items, n.kind_col, n.kinds) +
        "ALTER TABLE %s ADD CONSTRAINT fk_b FOREIGN KEY (%s) REFERENCES %s (id);\n" % (n.items, n.holder_col, n.holders) +
        "CREATE TABLE %s (\n  id INTEGER IDENTITY PRIMARY KEY,\n  %s VARCHAR(80)\n);\n" % (n.tags, n.title) +
        "CREATE TABLE %s (\n  %s VARCHAR(20) NOT NULL,\n  %s VARCHAR(20) NOT NULL,\n  PRIMARY KEY (%s)\n);\n"
        % (n.accounts, n.handle_col, n.secret_col, n.handle_col)
    )


def _seed_sql(n: Names) -> str:
    return (
        "INSERT INTO %s VALUES (1, '%s');\nINSERT INTO %s VALUES (2, '%s');\n" % (n.kinds, n.v_one, n.kinds, n.v_two) +
        "INSERT INTO %s VALUES (1);\n" % n.holders +
        "INSERT INTO %s VALUES (1, '%s', 1, 1);\nINSERT INTO %s VALUES (2, '%s', 2, 1);\n" % (n.items, n.v_rex, n.items, n.v_max) +
        "INSERT INTO %s VALUES (1, '%s');\n" % (n.tags, n.v_titleA) +
        "INSERT INTO %s VALUES ('%s', 'x');\n" % (n.accounts, n.v_root)
    )


def _ann(fqn: str, **values: Any) -> dict[str, Any]:
    return {"fqn": fqn, "values": {k: (v if isinstance(v, list) else [v]) for k, v in values.items()}}


def _field(name: str, type_: str, *anns: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "type": type_, "annotations": list(anns)}


def _ctl(n: Names, simple: str) -> str:
    return "%s.%sRestController" % (n.web, simple)


def _dto(n: Names, simple: str) -> str:
    return "%s.%s%s%s" % (n.dto, n.prefix, simple, n.suffix)


def _handler(n: Names, name: str, body_type: str, *, item: bool, location: bool) -> tuple[dict[str, Any], str]:
    params = ([{"name": "id", "type": "int", "annotations": [_ann(_SPRING + "PathVariable")]}] if item else []) + [
        {"name": "body", "type": body_type, "annotations": [_ann("javax.validation.Valid"), _ann(_SPRING + "RequestBody")]},
        {"name": "binding", "type": "org.springframework.validation.BindingResult", "annotations": []}]
    sig = "%s(%s)" % (name, ",".join(p["type"] for p in params))
    calls = [{"name": "save", "owner": "%s.Service" % n.web}]
    if location:
        calls.append({"name": "setLocation", "owner": "org.springframework.http.HttpHeaders"})
    return {"name": name, "signature": sig, "params": params, "calls": calls,
            "annotations": [_ann(_SPRING + "RequestMapping", method="PUT" if item else "POST")]}, sig


def _ep(n: Names, simple: str, sig: str, method: str, route: str) -> dict[str, Any]:
    t = _ctl(n, simple)
    return {"id": "ep:%s#%s:http" % (t, sig), "kind": "http", "type": t, "member": sig, "path": "src/main/java/x.java",
            "http_method": method, "http_path": route}


def _get(n: Names, simple: str, name: str, route: str) -> dict[str, Any]:
    return _ep(n, simple, "%s()" % name, "GET", route)


def build(td: Path, n: Names, *, pom: str | None = None, account_key: str = "") -> tuple[Path, dict[str, str]]:
    root = td / "dest"
    copy = td / "frozen"
    res = copy / "src" / "main" / "resources"
    (res / "db" / "hsqldb").mkdir(parents=True)
    (copy / "pom.xml").write_text(pom if pom is not None else _pom(n), encoding="utf-8")
    (res / "api-docs.yml").write_text(_api_docs(n, account_key=account_key), encoding="utf-8")
    (res / "db" / "hsqldb" / "populateDB.sql").write_text(_seed_sql(n), encoding="utf-8")
    (res / "db" / "hsqldb" / "initDB.sql").write_text(_schema_sql(n), encoding="utf-8")
    write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(copy), "source_digest": "fixture-source-digest"})
    types: list[dict[str, Any]] = []
    eps: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    for role, simple, route, item_rt, location in (("Kind", n.Kind, n.kinds, True, True), ("Item", n.Item, n.items, True, True),
                                                   ("Tag", n.Tag, n.tags, False, False), ("Account", n.Account, n.accounts, False, False)):
        body_type = _dto(n, simple)
        add, add_sig = _handler(n, "add%s" % simple, body_type, item=False, location=location)
        methods = [add]
        coll = "/api/%s" % route
        eps.append(_ep(n, simple, add_sig, "POST", coll))
        ids["create:" + role] = eps[-1]["id"]
        if simple != n.Account:
            eps.append(_get(n, simple, "list%s" % simple, coll))
        if item_rt:
            var = "{%sId}" % (simple[0].lower() + simple[1:])
            upd, upd_sig = _handler(n, "update%s" % simple, body_type, item=True, location=False)
            methods.append(upd)
            eps.append(_ep(n, simple, upd_sig, "PUT", coll + "/" + var))
            ids["update:" + role] = eps[-1]["id"]
            eps.append(_ep(n, simple, "get%s(int)" % simple, "GET", coll + "/" + var))
        types.append({"fqn": _ctl(n, simple), "annotations": [_ann(_SPRING + "RestController")], "methods": methods})
    # a search read whose route carries a whole-segment wildcard (v29's
    # getOwnersList shape): filled, and its variable resolved from the seed
    eps.append(_ep(n, n.Item, "find%s(java.lang.String)" % n.Item, "GET", "/api/%s/*/%s/{%s}" % (n.items, n.r_legacy, n.label_var)))
    ids["wildcard"] = eps[-1]["id"]
    base = "%s.Base" % n.model
    types += [
        {"fqn": base, "annotations": [_ann(_JPA + "MappedSuperclass")],
         "fields": [_field("id", "java.lang.Integer", _ann("Id"), _ann("GeneratedValue", strategy="IDENTITY"))]},
        {"fqn": "%s.%s" % (n.model, n.Kind), "annotations": [_ann(_JPA + "Entity"), _ann(_JPA + "Table", name=n.kinds)],
         "supertypes": [base], "fields": [_field(n.name, "java.lang.String", _ann("Column", name=n.name))]},
        {"fqn": "%s.%s" % (n.model, n.Holder), "annotations": [_ann(_JPA + "Entity"), _ann(_JPA + "Table", name=n.holders)],
         "supertypes": [base], "fields": []},
        {"fqn": "%s.%s" % (n.model, n.Item), "annotations": [_ann(_JPA + "Entity"), _ann(_JPA + "Table", name=n.items)],
         "supertypes": [base], "fields": [
             _field(n.label, "java.lang.String", _ann("Column", name=n.label_col)),
             _field(n.kind, "%s.%s" % (n.model, n.Kind), _ann("ManyToOne"), _ann("JoinColumn", name=n.kind_col)),
             _field(n.holder, "%s.%s" % (n.model, n.Holder), _ann("ManyToOne"), _ann("JoinColumn", name=n.holder_col))]},
        {"fqn": "%s.%s" % (n.model, n.Tag), "annotations": [_ann(_JPA + "Entity"), _ann(_JPA + "Table", name=n.tags)],
         "supertypes": [base], "fields": [_field(n.title, "java.lang.String")]},
        {"fqn": "%s.%s" % (n.model, n.Account), "annotations": [_ann(_JPA + "Entity"), _ann(_JPA + "Table", name=n.accounts)],
         "fields": [_field(n.handle, "java.lang.String", _ann("Id"), _ann("Column", name=n.handle_col)),
                    _field(n.secret, "java.lang.String", _ann("Column", name=n.secret_col))]},
    ]
    write_canonical(root / STRUCTURE, {"types": types})
    write_canonical(root / EVIDENCE_BUNDLE, {"schema": "rhoai3.evidence-bundle/v1", "entry_points": eps})
    return root, ids


def _derive(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(DERIVE), "--root", str(root)], text=True, capture_output=True)


def _normalize(text: str, n: Names) -> str:
    # the generated model's name follows the build's naming convention, which
    # the twin changes on purpose (suffix -> prefix): one token per model
    text = re.sub(r"modelNamePrefix='[^']*' modelNameSuffix='[^']*'", "<naming>", text)
    for key in ("Kind", "Item", "Tag", "Account"):
        text = text.replace("%s%s%s" % (n.prefix, getattr(n, key), n.suffix), "<model:%s>" % key)
    for _i, (key, value) in sorted(enumerate(n.pairs()), key=lambda kv: -len(kv[1][1])):
        if value and key not in ("prefix", "suffix"):
            text = text.replace(value, "<%s>" % key)
    return text


def _decisions(root: Path, n: Names) -> dict[str, Any]:
    corpus = load_json(root / CORPUS_P)
    rows = {}
    for sc in corpus["scenarios"]:
        body = json.loads((root / sc["body_file"]).read_text(encoding="utf-8")) if sc.get("body_file") else None
        row = {k: sc.get(k) for k in ("method", "path", "headers", "reset_before", "effects", "qualify", "effects_unobservable")}
        row["kind"] = sc["derived_from"]["kind"]
        row["body"] = body
        row["evidence"] = sc["derived_from"]["evidence"]
        rows[_normalize(sc["id"], n)] = json.loads(_normalize(json.dumps(row, sort_keys=True), n))
    return {"scenarios": rows, "gaps": sorted(_normalize(g, n) for g in corpus["gaps"]),
            "path_vars": json.loads(_normalize(json.dumps(corpus.get("path_vars") or {}, sort_keys=True), n))}


# --------------------------------------------------------------------------
# the cases
# --------------------------------------------------------------------------
def _derivation_case() -> int:
    n = PLAIN
    with tempfile.TemporaryDirectory(prefix="model-derive-") as td:
        root, ids = build(Path(td), n)
        p = _derive(root)
        if p.returncode != 0:
            return _fail("the fixture derives: %s%s" % (p.stdout, p.stderr))
        corpus = load_json(root / CORPUS_P)
        sc = {s["id"]: s for s in corpus["scenarios"]}

        def body(sid: str) -> Any:
            return json.loads((root / sc[sid]["body_file"]).read_text(encoding="utf-8"))

        K, I, T, A = n.kinds, n.items, n.tags, n.accounts
        want = {"sc:create-%s" % K, "sc:create-invalid-%s-%s" % (K, n.name), "sc:update-%s-1" % K,
                "sc:update-invalid-%s-1-%s" % (K, n.name),
                "sc:create-refused-%s" % I, "sc:create-invalid-%s-%s" % (I, n.label), "sc:update-%s-2" % I,
                "sc:update-invalid-%s-2-%s" % (I, n.label),
                "sc:create-%s" % T, "sc:create-invalid-%s-%s" % (T, n.title),
                "sc:create-%s" % A, "sc:create-invalid-%s-%s" % (A, n.handle), "sc:create-invalid-%s-%s" % (A, n.secret)}
        if set(sc) != want:
            return _fail("the request models derive exactly these scenarios: missing %s, extra %s\ngaps: %s"
                         % (sorted(want - set(sc)), sorted(set(sc) - want), corpus["gaps"]))
        # Kind: the model REQUIRES its readOnly identity -> one no seeded row holds
        k = sc["sc:create-%s" % K]
        if body(k["id"]) != {"id": 3, n.name: n.v_alpha}:
            return _fail("a required readOnly identity is the first above the seeded maximum, the rest the document's example: %s" % body(k["id"]))
        if k["qualify"] != {"intent": "positive", "expect_status": [201], "read_back_properties": [n.name], "location": "absolute-under-base",
                            "creates_one_entity": True, "identity_field": "id"}:
            return _fail("the create's contract: one new entity carrying what the model requires, Location naming it: %s" % k["qualify"])
        ev = k["derived_from"]["evidence"]
        if not any(e.startswith("build:pom.xml openapi-generator-maven-plugin") and "%s%s is generated from #/components/schemas/%s"
                   % (n.Kind, n.suffix, n.Kind) in e for e in ev) \
                or not any("seed:%s.id max 2 → id 3" % K in e for e in ev) \
                or not any(e.startswith("note:") and "no OpenAPI operation for POST /api/%s" % K in e for e in ev):
            return _fail("the binding evidence names the generator configuration, the seeded maximum and why no operation bound: %s" % ev)
        if "Origin" in k["headers"] or k.get("cors_policy"):
            return _fail("a model-bound write is same-origin, so the enabled mode can reuse it as its probe: %s" % k["headers"])
        # the update addresses the first seeded row the body CHANGES
        u = sc["sc:update-%s-1" % K]
        if u["path"] != "/api/%s/1" % K or body(u["id"]) != {"id": 1, n.name: n.v_alpha} \
                or u["qualify"] != {"intent": "positive", "expect_status": [200, 204], "after_contains_body": True,
                                    "read_back_properties": ["id", n.name], "before_lacks_body": True}:
            return _fail("the update writes the example over a seeded row it changes, asserting the row's identity too: %s %s" % (u["path"], u["qualify"]))
        ui = sc["sc:update-%s-2" % I]
        if ui["path"] != "/api/%s/2" % I or not any(
                "seed:%s#2: the first seeded row whose %s differs" % (I, n.label) in e for e in ui["derived_from"]["evidence"]):
            return _fail("row 1 already holds the example value, so the update addresses row 2 and says why: %s" % ui)
        # an OPTIONAL minLength string is still validated when present
        inv = sc["sc:create-invalid-%s-%s" % (K, n.name)]
        if body(inv["id"]) != {"id": 3, n.name: ""} or inv["qualify"] != {
                "intent": "negative", "expect_status": [400], "errors_header_names_field": n.name, "after_equals_before": True}:
            return _fail("the invalid body empties the constrained string and nothing else: %s" % inv)
        # Item: the reference resolves to the SEEDED row the example names
        r = sc["sc:create-refused-%s" % I]
        ib = body(r["id"])
        if ib != {"id": 3, n.label: n.v_rex, n.kindId: 1, n.kind: {"id": 1, n.name: n.v_one}, n.notes: []}:
            return _fail("a reference is the seeded row the example's identity names (not the example's other values), and a "
                         "required server-owned collection is sent empty: %s" % ib)
        if r["qualify"] != {"intent": "negative", "expect_status_class": "4xx", "after_equals_before": True} \
                or not any("schema:%s.%s NOT NULL with no default; structure:%s.%s maps it" % (I, n.holder_col, n.Item, n.holder) in e
                           for e in r["derived_from"]["evidence"]):
            return _fail("a body that cannot fill a NOT NULL column is a refused create, with the column and the field as evidence: %s" % r)
        if any(ids["create:Item"] in g for g in corpus["gaps"]):
            return _fail("the operation-binding gap of a model-bound write moves to the scenario's notes: %s" % corpus["gaps"])
        if not any(e.startswith("note:") and "path-variable sets differ" in e for e in r["derived_from"]["evidence"]):
            return _fail("the operation that did not bind is kept as a note: %s" % r["derived_from"]["evidence"])
        if body("sc:create-invalid-%s-%s" % (I, n.label)) != dict(ib, **{n.label: n.v_rex + "!"}):
            return _fail("a pattern violation is verified against the pattern: %s" % body("sc:create-invalid-%s-%s" % (I, n.label)))
        # Tag: the handler builds no Location
        t = sc["sc:create-%s" % T]
        if "location" in t["qualify"] or t["qualify"].get("creates_without_location") is not True or t["qualify"].get("creates_one_entity") is not True:
            return _fail("a handler that builds no Location is judged by the read-back alone, and the contract says so: %s" % t["qualify"])
        # Account: a client key; nothing reads the table back
        a = sc["sc:create-%s" % A]
        if body(a["id"]) != {n.handle: n.v_newkey, n.secret: "1234"} or a["effects"] != [] \
                or "no GET entry point reads /api/%s" % A not in str(a.get("effects_unobservable")) \
                or a["qualify"] != {"intent": "positive", "expect_status": [201]}:
            return _fail("an unobservable create keeps its response contract and SAYS the write is unverified (the example coerced to "
                         "its declared string type): %s %s" % (body(a["id"]), a))
        if not any(g.startswith("create-effect %s" % ids["create:Account"]) for g in corpus["gaps"]):
            return _fail("the unobservable effect is a recorded gap: %s" % corpus["gaps"])
        if any(sc["sc:create-invalid-%s-%s" % (A, f)].get("effects_unobservable") is None for f in (n.handle, n.secret)):
            return _fail("the invalid bodies of an unobservable write say so too")
        # the wildcard read: its variable resolved from the seed, no gap left
        if corpus["path_vars"].get(n.label_var) != n.v_rex or any(ids["wildcard"] in g for g in corpus["gaps"]):
            return _fail("a whole-segment wildcard read is a request: %s %s" % (corpus["path_vars"], corpus["gaps"]))
        try:
            load_corpus(root)
        except Exception as exc:  # noqa: BLE001
            return _fail("the derived corpus loads: %s" % exc)
        # the planner: the unobservable write stays UNRESOLVED, with the reason
        facts = {s["id"]: {"method": s["method"], "path": s["path"], "effects": s["effects"],
                           **({"effects_unobservable": s["effects_unobservable"]} if s.get("effects_unobservable") else {})}
                 for s in corpus["scenarios"]}
        oracles: dict[str, list[str]] = {}
        for s in corpus["scenarios"]:
            oracles.setdefault(s["entry_point"], []).append(s["id"])
        eps = load_json(root / EVIDENCE_BUNDLE)["entry_points"]
        doc = source_requirements.derive(types=[], entry_points=eps, catalog={}, decisions=None, oracles=oracles,
                                         structure_complete=False, scenario_facts=facts)
        bv = {r["subject"]: r for r in doc["requirements"] if str(r["rule"]).startswith("behavior-verification")}
        acc, kind = bv[ids["create:Account"]], bv[ids["create:Kind"]]
        if acc["status"] != "unresolved" or not any("declare no read-back of what the write persisted" in u and "/api/%s" % A in u
                                                     for u in acc["unknowns"]):
            return _fail("a write whose scenarios cannot read back what it persisted stays unresolved and says why: %s" % acc)
        if kind["status"] != "applicable" or bv[ids["create:Item"]]["status"] != "applicable":
            return _fail("a write with a read-back is covered: %s" % kind)
    return 0


def _twin_case() -> int:
    """The same shapes under every other name: identical decisions once the
    names are erased; different bodies and digests."""
    out = {}
    raw = {}
    for label, n in (("plain", PLAIN), ("twin", TWIN)):
        with tempfile.TemporaryDirectory(prefix="model-twin-") as td:
            root, _ids = build(Path(td), n)
            p = _derive(root)
            if p.returncode != 0:
                return _fail("%s derives: %s%s" % (label, p.stdout, p.stderr))
            out[label] = _decisions(root, n)
            raw[label] = (corpus_digest(load_json(root / CORPUS_P)),
                          sorted(json.dumps(json.loads(f.read_text())) for f in (root / "verification" / "scenarios" / "bodies").glob("*.json")))
    if out["plain"] != out["twin"]:
        a, b = out["plain"], out["twin"]
        diff = [k for k in sorted(set(a["scenarios"]) | set(b["scenarios"])) if a["scenarios"].get(k) != b["scenarios"].get(k)]
        return _fail("the decisions depend on the evidence, never on the names; differing: %s\n  gaps %s\n  vs   %s\n  %s\n  vs\n  %s"
                     % (diff, a["gaps"], b["gaps"], a["scenarios"].get(diff[0]) if diff else "", b["scenarios"].get(diff[0]) if diff else ""))
    if raw["plain"][0] == raw["twin"][0] or raw["plain"][1] == raw["twin"][1]:
        return _fail("the concrete requests and the corpus digest change with the inputs")
    return 0


def _binding_refusal_case() -> int:
    """The model binds only through the build's own generator configuration:
    another document, another package or a key the seed holds are reasons."""
    n = PLAIN
    cases = (
        ("inputSpec", _pom(n, input_spec="${project.basedir}/src/main/resources/other.yml"), "", "is not the OpenAPI document this derivation read"),
        ("modelPackage", _pom(n, package="a.elsewhere"), "", "is not in the generator's modelPackage 'a.elsewhere'"),
        ("no generator", "<project/>", "", "the frozen build declares no OpenAPI model generator"),
        ("seeded key", None, n.v_root, "is a key the seed already holds in %s.%s" % (n.accounts, n.handle_col)),
    )
    for label, pom, key, why in cases:
        with tempfile.TemporaryDirectory(prefix="model-refuse-") as td:
            root, ids = build(Path(td), n, pom=pom, account_key=key)
            p = _derive(root)
            if p.returncode != 0:
                return _fail("%s: a model that does not bind is a gap, not a refusal: %s" % (label, p.stderr))
            corpus = load_json(root / CORPUS_P)
            target = ids["create:Account"] if label == "seeded key" else ids["create:Kind"]
            gaps = [g for g in corpus["gaps"] if target in g]
            if not gaps or why not in gaps[0] or any(s["entry_point"] == target for s in corpus["scenarios"]):
                return _fail("%s: no scenario, and the gap names the missing fact: %s" % (label, gaps or corpus["gaps"]))
    return 0


def _wildcard_helper_case() -> int:
    got = fill_route_wildcards("/api/items/*/legacy/{label}", ["/api/items/{itemId}", "/api/items"])
    if got[0] != "/api/items/%s/legacy/{label}" % WILDCARD_SEGMENT_FILL or len(got[1]) != 1 or got[2]:
        return _fail("a whole-segment wildcard is filled with the named value: %s" % (got,))
    if not fill_route_wildcards("/api/items/v*/x")[2]:
        return _fail("a wildcard mixed into literal text constrains the value: a gap")
    clash = fill_route_wildcards("/api/items/*/x", ["/api/items/{id}/x"])
    if not clash[2] or "also matched by /api/items/{id}/x" not in clash[2]:
        return _fail("a filled route another route also matches could reach another handler: %s" % (clash,))
    if not route_matches("/a/**/z", "/a/b/c/z") or route_matches("/a/*/z", "/a/b/c/z") or not route_matches("/a/**", "/a"):
        return _fail("route_matches reads * as one segment and ** as any")
    if fill_route_wildcards("/plain/{id}") != ("/plain/{id}", [], ""):
        return _fail("a route without a wildcard is returned unchanged")
    return 0


class _Stub(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps({"path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # noqa: D102
        return


def _wildcard_read_oracle_case() -> int:
    """The disabled mode's read oracle of a wildcard route is captured at the
    filled path, with the filling on record."""
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d" % srv.server_address[1]
    try:
        with tempfile.TemporaryDirectory(prefix="model-wild-") as td:
            root, ids = build(Path(td), PLAIN)
            p = subprocess.run([sys.executable, str(CAPTURE_READS), "--root", str(root), "--base-url", url, "--any-status",
                                "--entry-point", ids["wildcard"], "--path-var", "%s=%s" % (PLAIN.label_var, PLAIN.v_rex)], text=True, capture_output=True)
            rec = load_json(root / "verification" / "source-oracles" / (slug(ids["wildcard"]) + ".json"))
            n = PLAIN
            if p.returncode != 0 or rec["status"] != "CAPTURED" \
                    or rec["oracle"]["path"] != "/api/%s/%s/%s/%s" % (n.items, WILDCARD_SEGMENT_FILL, n.r_legacy, n.v_rex) \
                    or not rec["oracle"].get("wildcards") \
                    or rec["oracle"].get("path_template") != "/api/%s/*/%s/{%s}" % (n.items, n.r_legacy, n.label_var):
                return _fail("the wildcard read is captured at the filled path and says how: %s %s" % (rec, p.stderr))
    finally:
        srv.shutdown()
    return 0


# --------------------------------------------------------------------------
# qualification of the new contract parameters
# --------------------------------------------------------------------------
def _retain(root: Path, sid: str, name: str, payload: Any) -> tuple[dict[str, Any], str]:
    raw = json.dumps(payload).encode("utf-8")
    sha = normalize_body(raw, "application/json")[1]
    return retain_body(root / SCENARIO_ORACLES / "bodies" / scenario_slug(sid), name, raw, sha), sha


def _capture(root: Path, sc: dict[str, Any], corpus_sha: str, status: int, headers: dict[str, Any], body: Any,
             before: dict[str, tuple[int, Any]], after: dict[str, tuple[int, Any]]) -> None:
    sid = str(sc["id"])
    ev, sha = _retain(root, sid, "response", body)
    rec: dict[str, Any] = {
        "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": sc["entry_point"],
        "evidence_bundle_sha256": digest(load_json(root / EVIDENCE_BUNDLE)), "corpus_sha256": corpus_sha,
        "source": {"base_url": BASE, "analysis_copy_digest": "fixture-source-digest"}, "status": "CAPTURED", "reason": "",
        "request": {"method": sc["method"], "path": sc["path"], "headers": dict(sc.get("headers") or {}),
                    "request_sha256": request_of(root, sc)["request_sha256"]},
        "response": {"status": status, "headers": headers, "body_kind": "json", "body_sha256": sha, "evidence": ev},
        "before": [], "effects": [],
    }
    for key, rows in (("before", before), ("effects", after)):
        for eff in sc.get("effects") or []:
            st, payload = rows[eff["id"]]
            ev2, sha2 = _retain(root, sid, "%s-%s" % ("before" if key == "before" else "after", scenario_slug(eff["id"])), payload)
            rec[key].append({"id": eff["id"], "method": "GET", "path": eff["path"], "status": st, "body_kind": "json", "body_sha256": sha2, "evidence": ev2})
    write_canonical(root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json"), rec)


def _qualification_case() -> int:
    n = PLAIN
    with tempfile.TemporaryDirectory(prefix="model-qualify-") as td:
        root, _ids = build(Path(td), n)
        if _derive(root).returncode != 0:
            return _fail("the fixture derives")
        corpus = load_corpus(root)
        csha = corpus_digest(corpus)
        sc = {s["id"]: s for s in corpus["scenarios"]}
        K, T, A = n.kinds, n.tags, n.accounts
        create_k, update_k = sc["sc:create-%s" % K], sc["sc:update-%s-1" % K]
        lst, one, all_ = "eff:%s-list-after-create" % K, "eff:%s-1-after-update" % K, "eff:%s-list-after-update" % K
        kinds = [{"id": 1, n.name: n.v_one}, {"id": 2, n.name: n.v_two}]
        new = {"id": 3, n.name: n.v_alpha}
        # the source answers the create with its new identity; the read-back
        # carries the property the model requires -- PASS
        _capture(root, create_k, csha, 201, {"Location": BASE + "/api/%s/3" % K}, new, {lst: (200, kinds)}, {lst: (200, kinds + [new])})
        # the Location-less create: identified by the read-back alone -- PASS
        tlst = "eff:%s-list-after-create" % T
        tags = [{"id": 1, n.title: n.v_titleA}]
        _capture(root, sc["sc:create-%s" % T], csha, 201, {"Location": None}, {"id": 2, n.title: n.v_titleA},
                 {tlst: (200, tags)}, {tlst: (200, tags + [{"id": 2, n.title: n.v_titleA}])})
        # the update read back carrying the row's identity and the value -- PASS
        _capture(root, update_k, csha, 204, {"Location": None}, "",
                 {one: (200, kinds[0]), all_: (200, kinds)},
                 {one: (200, {"id": 1, n.name: n.v_alpha}), all_: (200, [{"id": 1, n.name: n.v_alpha}, kinds[1]])})
        # the unobservable create: its response alone -- PASS
        _capture(root, sc["sc:create-%s" % A], csha, 201, {"Location": None}, {n.handle: n.v_newkey}, {}, {})
        p = subprocess.run([sys.executable, str(QUALIFY), "--root", str(root)], text=True, capture_output=True)
        q = load_json(root / QUALIFICATION)
        caps = {s: r["capability"] for s, r in q["scenarios"].items()}
        for sid in (create_k["id"], "sc:create-%s" % T, update_k["id"], "sc:create-%s" % A):
            if caps.get(sid) != "PASS":
                return _fail("%s qualifies on what its contract says: %s\n%s" % (sid, q["scenarios"].get(sid), p.stderr))
        tag_checks = {c["check"]: c for c in q["scenarios"]["sc:create-%s" % T]["checks"]}
        if "location" in tag_checks or "the contract asserts no Location" not in tag_checks["creates_one_entity"]["detail"]:
            return _fail("a Location-less create is judged without one, and says so: %s" % tag_checks)
        # the new entity does NOT carry the required property -- FAIL, named
        _capture(root, create_k, csha, 201, {"Location": BASE + "/api/%s/3" % K}, new,
                 {lst: (200, kinds)}, {lst: (200, kinds + [{"id": 3, n.name: n.v_max}])})
        # a no-op update: the row already held the body -- FAIL on before_lacks_body
        _capture(root, update_k, csha, 204, {"Location": None}, "",
                 {one: (200, {"id": 1, n.name: n.v_alpha}), all_: (200, kinds)},
                 {one: (200, {"id": 1, n.name: n.v_alpha}), all_: (200, kinds)})
        subprocess.run([sys.executable, str(QUALIFY), "--root", str(root)], text=True, capture_output=True)
        q = load_json(root / QUALIFICATION)
        ck = q["scenarios"][create_k["id"]]
        if ck["capability"] != "FAIL" or not any("does not carry the request body (differs in %s)" % n.name in f for f in ck["known_failures"]):
            return _fail("a new entity without the required property is a judged FAIL naming it: %s" % ck)
        uk = q["scenarios"][update_k["id"]]
        if uk["capability"] != "FAIL" or not any(f.startswith("before_lacks_body") for f in uk["known_failures"]):
            return _fail("an update over a row that already held the body proves no write: %s" % uk)
    return 0


def main() -> int:
    for case in (_wildcard_helper_case, _derivation_case, _twin_case, _binding_refusal_case, _wildcard_read_oracle_case,
                 _qualification_case):
        if case():
            return 1
    print("OK: request-model derivation (a write no OpenAPI operation binds is derived from the handler's @RequestBody model, "
          "bound to the document's component through the build's own generator configuration (inputSpec, modelPackage, "
          "prefix/suffix) and refused with the missing fact otherwise; bodies are the schema's examples with a required readOnly "
          "identity one no seeded row holds, required server-owned collections sent empty, references resolved to the seeded row "
          "the example names and client keys checked against the seed; a NOT NULL column the model cannot fill is a refused "
          "create; an optional or required constrained string earns one invalid body; an update addresses the first seeded row "
          "it changes and asserts the row's identity; a handler that builds no Location is judged by its read-back alone; a "
          "write nothing reads back keeps its response oracle, says the write is unverified and stays UNRESOLVED in the plan; a "
          "whole-segment wildcard is filled with one named value and captured there, a mixed or ambiguous one stays a gap; "
          "qualification judges only the read_back_properties the contract names; every decision is identical for a twin "
          "renamed in every package, type, member, route, schema, property, table, column, seed value and generator naming "
          "convention, while its requests and digests differ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
