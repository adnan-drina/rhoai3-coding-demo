#!/usr/bin/env python3
"""scenario-derivation selftest: the corpus is a producer output, not a signature.

The control: a frozen source whose OpenAPI document carries examples, whose
seed names row 1 and whose one controller carries a @CrossOrigin policy. The
derivation must produce exactly the create / create-invalid / update / delete
/ cors-actual / cors-preflight scenarios from those inputs and nothing for the
reads; a required property with no example is a gap and no scenario (never an
invented value); an entry point whose mapping declares no HTTP method answers
every one of them, so it derives ONE read scenario whose contract is the
source's own first response, while a handler consuming a request body, a
wildcard route and a mapping the structure model does not record stay gaps.
The loader must
accept the derived corpus, refuse it after any edit, refuse it bound to another
bundle and refuse a placeholder approver. The qualification gate must PASS a
capture that shows what the scenario says, FAIL one that does not (a relative
Location, a 400 without the errors header) and be INCONCLUSIVE without the
retained body; and the parity receipt must be INCONCLUSIVE for a derived
corpus nobody qualified.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DERIVE = HERE / "derive-source-scenarios.py"
QUALIFY = HERE / "qualify-source-captures.py"
RECEIPT = HERE / "compose-parity-receipt.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
from _oracle_common import normalize_body, retain_body  # noqa: E402
from _scenarios import CorpusError, DERIVE_RECEIPT, QUALIFICATION, SCENARIO_ORACLES, corpus_digest, load_corpus, request_of, scenario_slug, source_cors_policies  # noqa: E402
from planner.canonical import sha256_file  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, STRUCTURE, producer_receipt  # noqa: E402

CORPUS_P = Path("verification") / "scenarios" / "corpus.json"
BASE = "http://127.0.0.1:9966/petclinic"
CONTROLLER = "a.OwnerRestController"
EP = {
    "list": "ep:%s#getOwners():http" % CONTROLLER,
    "get": "ep:%s#getOwner(int):http" % CONTROLLER,
    "create": "ep:%s#addOwner(a.OwnerDto):http" % CONTROLLER,
    "update": "ep:%s#updateOwner(int,a.OwnerDto):http" % CONTROLLER,
    "delete": "ep:%s#deleteOwner(int):http" % CONTROLLER,
}
SEED_OWNER_1 = {"id": 1, "firstName": "George", "lastName": "Franklin", "address": "110 W. Liberty St.", "city": "Madison", "telephone": "6085551023"}
SEED_OWNER_2 = {"id": 2, "firstName": "Betty", "lastName": "Davis", "address": "638 Cardinal Ave.", "city": "Sun Prairie", "telephone": "6085551749"}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _api_docs(drop_telephone_example: bool = False, post_operation_id: str = "addOwner", list_schema: bool = True) -> str:
    tel_example = "" if drop_telephone_example else "          example: '6085551023'\n"
    listing = ("          content:\n            application/json:\n              schema:\n                type: array\n"
               "                items:\n                  $ref: '#/components/schemas/Owner'\n") if list_schema else ""
    return (
        "openapi: 3.0.1\n"
        "info:\n  title: Spring PetClinic\n  description: |\n    Sample application.\n  version: '1.0'\n"
        "servers:\n  - url: http://localhost:9966/petclinic/api\n"
        "paths:\n"
        "  /owners:\n"
        "    post:\n      operationId: " + post_operation_id + "\n      requestBody:\n        content:\n          application/json:\n"
        "            schema:\n              $ref: '#/components/schemas/OwnerFields'\n        required: true\n"
        "      responses:\n        201:\n          description: created\n"
        "    get:\n      operationId: listOwners\n      responses:\n        '200':\n          description: ok\n" + listing +
        "  /owners/{ownerId}:\n"
        "    parameters:\n      - name: ownerId\n        in: path\n        required: true\n        schema:\n          type: integer\n        example: 1\n"
        "    get:\n      operationId: getOwner\n      responses:\n        '200':\n          description: ok\n"
        "    put:\n      operationId: updateOwner\n      requestBody:\n        content:\n          application/json:\n"
        "            schema:\n              $ref: '#/components/schemas/OwnerFields'\n        required: true\n"
        "      responses:\n        '204':\n          description: updated\n"
        "    delete:\n      operationId: deleteOwner\n      responses:\n        '204':\n          description: deleted\n"
        "components:\n  schemas:\n"
        "    OwnerFields:\n      type: object\n      properties:\n"
        "        telephone:\n          type: string\n          minLength: 1\n          pattern: '^[0-9]*$'\n" + tel_example +
        "        firstName:\n          type: string\n          minLength: 1\n          pattern: '^[a-zA-Z]*$'\n          example: George\n"
        "        lastName:\n          type: string\n          example: Franklin\n"
        "        address:\n          type: string\n          example: 110 W. Liberty St.\n"
        "        city:\n          type: string\n          example: Madison\n"
        "      required:\n        - firstName\n        - lastName\n        - address\n        - city\n        - telephone\n"
        "    Owner:\n      allOf:\n        - $ref: '#/components/schemas/OwnerFields'\n"
        "        - type: object\n          properties:\n            id:\n              type: integer\n              readOnly: true\n              example: 1\n"
    )


def _entry(key: str, method: str, path: str, member: str) -> dict[str, Any]:
    return {"id": EP[key], "kind": "http", "type": CONTROLLER, "member": member, "path": "src/main/java/a/OwnerRestController.java",
            "http_method": method, "http_path": path}


def entity(simple: str, table: str = "", fields: list[dict[str, Any]] | None = None, supertypes: list[str] | None = None) -> dict[str, Any]:
    """A structure-model @Entity as M1 records one: the table from @Table(name)
    when given, and the erased field types the model really carries."""
    anns: list[dict[str, Any]] = [{"fqn": "javax.persistence.Entity", "values": {}}]
    if table:
        anns.append({"fqn": "javax.persistence.Table", "values": {"name": [table]}})
    return {"fqn": "a.model.%s" % simple, "annotations": anns, "fields": list(fields or []), "supertypes": list(supertypes or [])}


def rel(name: str, kind: str, values: dict[str, Any], type_: str = "java.util.Set", join_table: str = "") -> dict[str, Any]:
    anns: list[dict[str, Any]] = [{"fqn": "javax.persistence.%s" % kind, "values": values}]
    if join_table:
        anns.append({"fqn": "javax.persistence.JoinTable", "values": {"name": [join_table]}})
    return {"name": name, "type": type_, "annotations": anns}


def build_root(td: Path, *, drop_telephone_example: bool = False, servlet: bool = False, api_docs: str | None = None,
               extra_eps: list[dict[str, Any]] | None = None, post_operation_id: str = "addOwner", list_schema: bool = True,
               seed_sql: str = "", schema_sql: str = "", schema_name: str = "schema.sql",
               entities: list[dict[str, Any]] | None = None, no_structure: bool = False,
               extra_types: list[dict[str, Any]] | None = None, add_eps: list[dict[str, Any]] | None = None) -> Path:
    root = td / "dest"
    copy = td / "frozen"
    res = copy / "src" / "main" / "resources"
    (res / "db" / "hsqldb").mkdir(parents=True)
    (copy / "pom.xml").write_text("<project/>", encoding="utf-8")
    (res / "api-docs.yml").write_text(api_docs if api_docs is not None else _api_docs(drop_telephone_example, post_operation_id, list_schema), encoding="utf-8")
    (res / "db" / "hsqldb" / "populateDB.sql").write_text(
        "INSERT INTO owners VALUES (1, 'George', 'Franklin', '110 W. Liberty St.', 'Madison', '6085551023');\n"
        "INSERT INTO owners VALUES (2, 'Betty', 'Davis', '638 Cardinal Ave.', 'Sun Prairie', '6085551749');\n"
        "INSERT INTO types VALUES (1, 'cat');\n" + seed_sql, encoding="utf-8")
    (res / "db" / "hsqldb" / schema_name).write_text(
        "CREATE TABLE owners (\n  id INTEGER IDENTITY PRIMARY KEY,\n  first_name VARCHAR(30),\n  last_name VARCHAR(30),\n"
        "  address VARCHAR(255),\n  city VARCHAR(80),\n  telephone VARCHAR(20)\n);\n" + schema_sql, encoding="utf-8")
    write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(copy), "source_digest": "fixture-source-digest"})
    if not no_structure:
        write_canonical(root / STRUCTURE, {"types": [
            {"fqn": CONTROLLER, "annotations": [{"fqn": "org.springframework.web.bind.annotation.CrossOrigin", "values": {"exposedHeaders": ["errors, content-type"]}}]},
            {"fqn": "a.OwnerDto", "annotations": []}] + list(entities or []) + list(extra_types or [])})
    eps = [_entry("list", "GET", "/api/owners", "getOwners()"), _entry("get", "GET", "/api/owners/{ownerId}", "getOwner(int)"),
           _entry("create", "POST", "/api/owners", "addOwner(a.OwnerDto)"), _entry("update", "PUT", "/api/owners/{ownerId}", "updateOwner(int,a.OwnerDto)"),
           _entry("delete", "DELETE", "/api/owners/{ownerId}", "deleteOwner(int)")]
    if servlet:
        eps.append({"id": "ep:a.RedirectServlet#:http", "kind": "http", "type": "a.RedirectServlet", "member": "", "path": "src/main/java/a/RedirectServlet.java", "http_method": "", "http_path": "/"})
    if extra_eps is not None:
        eps = list(extra_eps)  # the caller's bundle, not the fixture controller's
    eps = eps + list(add_eps or [])
    write_canonical(root / EVIDENCE_BUNDLE, {"schema": "rhoai3.evidence-bundle/v1", "entry_points": eps})
    return root


REAL_EXCERPT = HERE / "fixtures" / "petclinic-api-docs.excerpt.yml"
REAL_CONTROLLER = "org.springframework.samples.petclinic.rest.OwnerRestController"
REAL_USER_CONTROLLER = "org.springframework.samples.petclinic.rest.UserRestController"
REAL_MEMBERS = {
    "list": "getOwners()", "get": "getOwner(int)",
    "create": "addOwner(org.springframework.samples.petclinic.dto.OwnerDto,org.springframework.validation.BindingResult,org.springframework.web.util.UriComponentsBuilder)",
    "update": "updateOwner(int,org.springframework.samples.petclinic.dto.OwnerDto,org.springframework.validation.BindingResult,org.springframework.web.util.UriComponentsBuilder)",
    "delete": "deleteOwner(int)",
}
REAL_USER_MEMBER = "addOwner(org.springframework.samples.petclinic.dto.UserDto,org.springframework.validation.BindingResult)"


def _real_excerpt_case() -> int:
    """The parser and the operation binding against the REAL document's shape:
    a verbatim excerpt of v9's api-docs.yml, whose paths (``/owner``) do not
    name the controllers' routes (``/api/owners``) -- the miss that produced
    six deletes and fifteen gaps on v9 before operationId binding existed."""
    with tempfile.TemporaryDirectory(prefix="derive-real-") as td:
        real_eps = [
            {"id": "ep:%s#%s:http" % (REAL_CONTROLLER, m), "kind": "http", "type": REAL_CONTROLLER, "member": m,
             "path": "src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java", "http_method": meth, "http_path": route}
            for m, meth, route in ((REAL_MEMBERS["list"], "GET", "/api/owners"), (REAL_MEMBERS["get"], "GET", "/api/owners/{ownerId}"),
                                   (REAL_MEMBERS["create"], "POST", "/api/owners"), (REAL_MEMBERS["update"], "PUT", "/api/owners/{ownerId}"),
                                   (REAL_MEMBERS["delete"], "DELETE", "/api/owners/{ownerId}"))
        ] + [{"id": "ep:%s#%s:http" % (REAL_USER_CONTROLLER, REAL_USER_MEMBER), "kind": "http", "type": REAL_USER_CONTROLLER, "member": REAL_USER_MEMBER,
              "path": "src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java", "http_method": "POST", "http_path": "/api/users"}]
        root = build_root(Path(td), api_docs=REAL_EXCERPT.read_text(encoding="utf-8"), extra_eps=real_eps)
        p = _derive(root)
        if p.returncode != 0:
            return _fail("the real excerpt must derive: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        corpus = load_json(root / CORPUS_P)
        sc = {str(s["id"]): s for s in corpus["scenarios"]}
        by_ep = {}
        for s in corpus["scenarios"]:
            by_ep.setdefault(s["entry_point"], []).append(s)
        create = [s for s in by_ep.get("ep:%s#%s:http" % (REAL_CONTROLLER, REAL_MEMBERS["create"]), []) if s["derived_from"]["kind"] == "create"]
        invalid = [s for s in by_ep.get("ep:%s#%s:http" % (REAL_CONTROLLER, REAL_MEMBERS["create"]), []) if s["derived_from"]["kind"] == "create-invalid"]
        update = by_ep.get("ep:%s#%s:http" % (REAL_CONTROLLER, REAL_MEMBERS["update"]), [])
        if len(create) != 1 or len(invalid) != 5 or len(update) != 1:
            return _fail("the real controller's create, five invalid creates (one per constrained property) and update bind by operationId: %s\ngaps: %s" % (sorted(sc), corpus["gaps"]))
        if ("openapi-path:/owner≠route:/api/owners; bound by operationId addOwner" not in create[0]["derived_from"]["evidence"]
                or "openapi-path:/owner/{ownerId}≠route:/api/owners/{ownerId}; bound by operationId updateOwner" not in update[0]["derived_from"]["evidence"]):
            return _fail("the binding evidence records the path discrepancy and the operationId: %s" % create[0]["derived_from"])
        if {s["id"] for s in invalid} != {"sc:create-invalid-owners-%s" % f for f in ("firstName", "lastName", "address", "city", "telephone")}:
            return _fail("one negative per constrained property of the real schema: %s" % sorted(s["id"] for s in invalid))
        if create[0]["qualify"]["identity_field"] != "id":
            return _fail("the identity comes from the real listOwners response schema: %s" % create[0]["qualify"])
        body = json.loads((root / create[0]["body_file"]).read_text())
        if body != {"firstName": "George", "lastName": "Franklin", "address": "110 W. Liberty St.", "city": "Madison", "telephone": "6085551023"}:
            return _fail("the create body is the real document's OwnerFields examples: %s" % body)
        if create[0]["path"] != "/api/owners" or update[0]["path"] != "/api/owners/1" or json.loads((root / update[0]["body_file"]).read_text()) != body:
            return _fail("concrete paths are the code's routes, bodies the document's: %s %s" % (create[0]["path"], update[0]["path"]))
        tel = next(s for s in invalid if s["id"] == "sc:create-invalid-owners-telephone")
        inv = json.loads((root / tel["body_file"]).read_text())
        changed = [k for k in body if inv.get(k) != body[k]]
        if changed != ["telephone"] or re.fullmatch(r"^[0-9]*$", inv["telephone"]) is not None or tel["qualify"] != {"intent": "negative", "expect_status": [400], "errors_header_names_field": "telephone", "after_equals_before": True}:
            return _fail("each invalid body breaks exactly its own property of the real schema: %s %s" % (inv, tel["qualify"]))
        # UserRestController#addOwner shares the method name and must NOT be
        # handed OwnerFields: its stem (user) matches neither the tag nor the schema
        users = [s for s in corpus["scenarios"] if s["path"] == "/api/users"]
        if users or not any("/api/users" in g for g in corpus["gaps"]):
            return _fail("a same-named method on another controller is a gap, not a body it does not own: %s / %s" % (users, corpus["gaps"]))
        if corpus["path_vars"].get("ownerId") != "1":
            return _fail("path_vars from the seed: %s" % corpus["path_vars"])
    return 0


def _derive(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(DERIVE), "--root", str(root)] + list(extra), text=True, capture_output=True)


def _derivation_case() -> tuple[int, Path | None, tempfile.TemporaryDirectory | None]:
    td = tempfile.TemporaryDirectory(prefix="derive-")
    root = build_root(Path(td.name))
    p = _derive(root)
    if p.returncode != 0 or not p.stdout.startswith("OK: derived"):
        return _fail("derivation must succeed: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr)), None, td
    corpus = load_json(root / CORPUS_P)
    receipt = load_json(root / DERIVE_RECEIPT)
    pols, why = source_cors_policies(root)
    if len(pols) != 1 or why:
        return _fail("fixture declares one policy: %s %s" % (pols, why)), None, td
    short = pols[0].split(":", 1)[1]
    want = {"sc:create-owners", "sc:create-invalid-owners-telephone", "sc:create-invalid-owners-firstName", "sc:update-owners-1", "sc:delete-owners-1",
            "sc:cors-actual-%s" % short, "sc:cors-preflight-%s" % short}
    got = {str(s["id"]) for s in corpus["scenarios"]}
    if got != want:
        return _fail("the derived ids are the rules over the write entry points, one negative per constrained property, nothing for the reads: %s" % sorted(got)), None, td
    if corpus.get("approved_by") is not None or corpus["derived_from"]["producer"] != "derive-source-scenarios.py":
        return _fail("a derived corpus names its producer, not a person: %s" % corpus.get("derived_from")), None, td
    if corpus["derived_from"]["evidence_bundle_sha256"] != digest(load_json(root / EVIDENCE_BUNDLE)) or not corpus["derived_from"]["openapi"]["sha256"]:
        return _fail("derived_from binds the bundle and names the OpenAPI input: %s" % corpus["derived_from"]), None, td
    sc = {str(s["id"]): s for s in corpus["scenarios"]}
    create_body = json.loads((root / sc["sc:create-owners"]["body_file"]).read_text())
    expected_body = {k: v for k, v in SEED_OWNER_1.items() if k != "id"}
    if create_body != expected_body:
        return _fail("the create body is the document's examples without id: %s" % create_body), None, td
    if sc["sc:create-owners"]["qualify"] != {"intent": "positive", "expect_status": [201], "location": "absolute-under-base", "after_contains_body": True,
                                            "creates_one_entity": True, "identity_field": "id"}:
        return _fail("the create scenario carries its identity-aware contract, with the identity derived from the collection GET's response schema: %s" % sc["sc:create-owners"].get("qualify")), None, td
    if not any("items(Owner).id" in e for e in sc["sc:create-owners"]["derived_from"]["evidence"]):
        return _fail("the identity field names its evidence: %s" % sc["sc:create-owners"]["derived_from"]), None, td
    if sc["sc:create-owners"]["headers"].get("Origin") is None or sc["sc:create-owners"].get("cors_policy") != pols[0]:
        return _fail("a create on a controller carrying a CORS policy sends Origin and names the policy: %s" % sc["sc:create-owners"]), None, td
    invalid = json.loads((root / sc["sc:create-invalid-owners-telephone"]["body_file"]).read_text())
    if re.fullmatch(r"^[0-9]*$", invalid["telephone"]) is not None:
        return _fail("the invalid body's telephone must violate its pattern: %r" % invalid["telephone"]), None, td
    if {k: v for k, v in invalid.items() if k != "telephone"} != {k: v for k, v in create_body.items() if k != "telephone"}:
        return _fail("only telephone differs in the invalid body: %s" % invalid), None, td
    if re.fullmatch(r"^[a-zA-Z]*$", invalid["firstName"]) is None:
        return _fail("every other constrained field stays valid: %s" % invalid), None, td
    if sc["sc:create-invalid-owners-telephone"]["qualify"] != {"intent": "negative", "expect_status": [400], "errors_header_names_field": "telephone", "after_equals_before": True}:
        return _fail("the invalid scenario is negative and names the rejected field: %s" % sc["sc:create-invalid-owners-telephone"]["qualify"]), None, td
    invalid_fn = json.loads((root / sc["sc:create-invalid-owners-firstName"]["body_file"]).read_text())
    if re.fullmatch(r"^[a-zA-Z]*$", invalid_fn["firstName"]) is not None or [k for k in create_body if invalid_fn[k] != create_body[k]] != ["firstName"]:
        return _fail("one negative scenario per constrained property, each violating exactly its own: %s" % invalid_fn), None, td
    update_body = json.loads((root / sc["sc:update-owners-1"]["body_file"]).read_text())
    if update_body != expected_body or sc["sc:update-owners-1"]["path"] != "/api/owners/1":
        return _fail("the update writes the examples over the seeded row (id is readOnly and not sent): %s %s" % (update_body, sc["sc:update-owners-1"]["path"])), None, td
    if [e["path"] for e in sc["sc:update-owners-1"]["effects"]] != ["/api/owners/1", "/api/owners"]:
        return _fail("the update reads back the item and the collection: %s" % sc["sc:update-owners-1"]["effects"]), None, td
    d = sc["sc:delete-owners-1"]
    if not d.get("body_absent") or d["qualify"] != {"intent": "positive", "expect_status": [200, 204], "after_effect_status": {"eff:owners-1-after-delete": 404}}:
        return _fail("the delete has no body and expects the row gone: %s" % d), None, td
    ca, cp = sc["sc:cors-actual-%s" % short], sc["sc:cors-preflight-%s" % short]
    if ca["method"] != "GET" or ca["path"] != "/api/owners" or ca["qualify"].get("cors_expose_headers") != ["content-type", "errors"] or ca["headers"].get("Origin") != "http://parity.invalid:4200":
        return _fail("the actual exchange is a GET on the collection with the policy's exposed headers: %s" % ca), None, td
    if cp["method"] != "OPTIONS" or cp["path"] != "/api/owners" or cp["headers"].get("Access-Control-Request-Method") != "POST" or cp.get("identity"):
        return _fail("the preflight is an OPTIONS on the create path without identity: %s" % cp), None, td
    if corpus["path_vars"] != {"ownerId": "1"}:
        return _fail("path_vars come from the seed: %s" % corpus["path_vars"]), None, td
    if corpus["gaps"] != []:
        return _fail("the complete fixture derives with no gap: %s" % corpus["gaps"]), None, td
    if receipt["status"] != "ok" or receipt["corpus_sha256"] != corpus_digest(corpus) or sorted(receipt["scenarios"]) != sorted(want):
        return _fail("the receipt binds the corpus digest and lists the scenarios: %s" % receipt), None, td
    if set(receipt["bodies"]) != {s["body_file"] for s in corpus["scenarios"] if s.get("body_file")} or set(receipt["requests"]) != want:
        return _fail("the receipt binds every body's bytes and every request digest: %s %s" % (sorted(receipt["bodies"]), sorted(receipt["requests"]))), None, td
    if not (root / "verification" / "scenarios" / "bodies" / "create-owners.json").read_text().endswith("\n"):
        return _fail("bodies are written with a trailing newline"), None, td
    # a second derivation is byte-identical: nothing in the corpus is a clock or a host
    p = _derive(root)
    if p.returncode != 0 or load_json(root / DERIVE_RECEIPT)["corpus_sha256"] != receipt["corpus_sha256"]:
        return _fail("the derivation is deterministic: %s %s" % (p.stdout, p.stderr)), None, td
    # every derived scenario passes the corpus rules and the provenance binding
    try:
        load_corpus(root)
    except CorpusError as exc:
        return _fail("the loader must accept the derived corpus: %s" % exc), None, td
    # ... and refuses it after ANY edit: an edit has no provenance
    edited = load_json(root / CORPUS_P)
    edited["scenarios"][0]["why"] = "edited by hand"
    write_canonical(root / CORPUS_P, edited)
    try:
        load_corpus(root)
        return _fail("a derived corpus edited after derivation must be refused"), None, td
    except CorpusError as exc:
        if "edited after derivation" not in str(exc) or "missing" in str(exc):
            return _fail("the refusal names the digest mismatch and never says 'missing': %s" % exc), None, td
    write_canonical(root / CORPUS_P, corpus)
    # ... and refuses a BODY edited after derivation, which the corpus
    # digest alone (binding filenames) accepted (architect review of
    # 708cfef9: body_only_edit_after_derivation)
    bf = root / sc["sc:create-invalid-owners-telephone"]["body_file"]
    kept_body = bf.read_bytes()
    edited_body = json.loads(kept_body.decode("utf-8"))
    edited_body["firstName"] = "Edited"
    bf.write_text(json.dumps(edited_body, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    try:
        load_corpus(root)
        return _fail("a body file edited after derivation must be refused"), None, td
    except CorpusError as exc:
        if "body/request edited after derivation" not in str(exc):
            return _fail("the refusal names the body/request binding: %s" % exc), None, td
    bf.write_bytes(kept_body)
    # ... and refuses a receipt bound to another bundle
    rebound = dict(receipt)
    rebound["evidence_bundle_sha256"] = "0" * 64
    write_canonical(root / DERIVE_RECEIPT, rebound)
    try:
        load_corpus(root)
        return _fail("a corpus derived against another bundle must be refused"), None, td
    except CorpusError as exc:
        if "bundle" not in str(exc):
            return _fail("the refusal names the bundle binding: %s" % exc), None, td
    write_canonical(root / DERIVE_RECEIPT, receipt)
    # a hand-authored corpus still loads, but a placeholder is not an approver
    signed = json.loads(json.dumps(corpus))
    signed.pop("derived_from")
    signed["approved_by"] = "TODO: x"
    write_canonical(root / CORPUS_P, signed)
    try:
        load_corpus(root)
        return _fail("approved_by 'TODO: x' must be refused"), None, td
    except CorpusError as exc:
        if "placeholder" not in str(exc):
            return _fail("the refusal names the placeholder: %s" % exc), None, td
    signed["approved_by"] = "operator:test"
    write_canonical(root / CORPUS_P, signed)
    try:
        load_corpus(root)
    except CorpusError as exc:
        return _fail("a hand-authored corpus with a real approver is the permitted exception: %s" % exc), None, td
    # the derivation does not overwrite a hand-authored corpus
    p = _derive(root)
    if p.returncode != 1 or "hand-authored" not in p.stderr or load_json(root / CORPUS_P).get("approved_by") != "operator:test":
        return _fail("a hand-authored corpus at the output path is refused, not clobbered: rc=%s %s" % (p.returncode, p.stderr)), None, td
    if load_json(root / DERIVE_RECEIPT)["status"] != "blocked":
        return _fail("the refusal is on the record in the derivation receipt"), None, td
    write_canonical(root / CORPUS_P, corpus)
    write_canonical(root / DERIVE_RECEIPT, receipt)
    return 0, root, td


def _gap_cases() -> int:
    with tempfile.TemporaryDirectory(prefix="derive-gaps-") as td:
        root = build_root(Path(td), drop_telephone_example=True, servlet=True)
        p = _derive(root)
        if p.returncode != 0:
            return _fail("gaps are recorded, not refusals: rc=%s %s" % (p.returncode, p.stderr))
        corpus = load_json(root / CORPUS_P)
        ids = {str(s["id"]) for s in corpus["scenarios"]}
        if "sc:create-owners" in ids or "sc:create-invalid-owners" in ids or "sc:update-owners-1" in ids:
            return _fail("a required property with no example yields no scenario, never an invented value: %s" % sorted(ids))
        if not any(g == "no example for OwnerFields.telephone" for g in corpus["gaps"]):
            return _fail("the gap names the schema and property: %s" % corpus["gaps"])
        if any(str(i).startswith("sc:read-") for i in ids):
            return _fail("a servlet the structure model does not record derives no read scenario: %s" % sorted(ids))
        if not any("ep:a.RedirectServlet#:http" in g and "no HTTP method" in g for g in corpus["gaps"]):
            return _fail("a servlet entry point with no method is a gap: %s" % corpus["gaps"])
        if "sc:delete-owners-1" not in ids:
            return _fail("the delete needs no example and is still derived: %s" % sorted(ids))
        bodies = root / "verification" / "scenarios" / "bodies"
        if bodies.is_dir() and any(p.name.startswith("create") for p in bodies.iterdir()):
            return _fail("no body is written for a scenario that is not emitted")
    with tempfile.TemporaryDirectory(prefix="derive-conflict-") as td:
        # a path that matches but whose operationId names another member
        # (architect review of 708cfef9: addVet bound to the addOwner
        # controller by path alone) is a typed gap, never a binding
        root = build_root(Path(td), post_operation_id="addVet")
        p = _derive(root)
        corpus = load_json(root / CORPUS_P)
        ids = {str(s["id"]) for s in corpus["scenarios"]}
        if p.returncode != 0 or any(i.startswith("sc:create-") for i in ids):
            return _fail("a conflicting operationId must not bind: rc=%s %s" % (p.returncode, sorted(ids)))
        if not any(g.startswith("conflicting binding: path /owners ↔ operationId addVet ≠ member addOwner") for g in corpus["gaps"]):
            return _fail("the conflict is a typed gap: %s" % corpus["gaps"])
    with tempfile.TemporaryDirectory(prefix="derive-refuse-") as td:
        root = build_root(Path(td))
        (Path(td) / "frozen" / "src" / "main" / "resources" / "api-docs.yml").unlink()
        p = _derive(root)
        if p.returncode != 1 or "REFUSE" not in p.stderr or "OpenAPI" not in p.stderr:
            return _fail("no OpenAPI document is a refusal: rc=%s %s" % (p.returncode, p.stderr))
        if load_json(root / DERIVE_RECEIPT)["status"] != "blocked" or (root / CORPUS_P).exists():
            return _fail("a refusal leaves a blocked receipt and no corpus")
    return 0


# --------------------------------------------------------------------------
# a mapping that declares no HTTP method
# --------------------------------------------------------------------------
_SPRING = "org.springframework.web.bind.annotation."


def _mapping_type(fqn: str, member: str, *, route: str = "/", ann: str = "RequestMapping",
                  values: dict[str, Any] | None = None, params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """A controller as M1's structure model records one: the handler, the
    mapping annotation with its VALUES, and the parameters with theirs."""
    return {"fqn": fqn, "annotations": [{"fqn": _SPRING + "RestController", "values": {}}],
            "methods": [{"name": member.split("(", 1)[0], "signature": member, "params": list(params or []),
                         "annotations": [{"fqn": _SPRING + ann, "values": {"value": [route]} if values is None else values}]}]}


def _mapping_ep(fqn: str, member: str, route: str) -> dict[str, Any]:
    """An entry point the bundle records with NO http_method, as M1 records a
    @RequestMapping that names none."""
    return {"id": "ep:%s#%s:http" % (fqn, member), "kind": "http", "type": fqn, "member": member,
            "path": "src/main/java/%s.java" % fqn.replace(".", "/"), "http_method": "", "http_path": route,
            "evidence": "method-annotation:" + _SPRING + "RequestMapping"}


def _norm(text: str, names: list[str]) -> str:
    """The specimen's own names erased, longest first, so two fixtures that
    differ only in naming produce the same text."""
    for i, n in sorted(enumerate(names), key=lambda kv: -len(kv[1])):
        if n:
            text = text.replace(n, "<%d>" % i)
    return text


def _read_decision(root: Path, names: list[str], eid: str) -> dict[str, Any]:
    """What the derivation DECIDED for one entry point, with the names erased:
    the read scenarios' shape and evidence, and the gaps naming it."""
    corpus = load_json(root / CORPUS_P)
    reads = [s for s in corpus["scenarios"] if str(s["id"]).startswith("sc:read-")]
    rows = []
    for sc in reads:
        row = {k: sc.get(k) for k in ("method", "headers", "identity", "body_absent", "reset_before", "effects", "normalization", "qualify")}
        row["kind"] = sc["derived_from"]["kind"]
        row["evidence"] = [_norm(e, names) for e in sc["derived_from"]["evidence"]]
        rows.append(row)
    return {"reads": rows, "gaps": sorted(_norm(g, names) for g in corpus["gaps"] if eid in g)}


def _methodless_decisions(fqn: str, member: str, route: str, wildcard: str,
                          ptype: str, pname: str) -> dict[str, Any]:
    """The three decisions for a method-less mapping under ONE set of names:
    the plain handler, the one that consumes a request body, and the one whose
    route carries a wildcard."""
    eid = "ep:%s#%s:http" % (fqn, member)
    names = [fqn, member, ptype, pname, wildcard]
    body_param = {"name": pname, "type": ptype, "annotations": [{"fqn": _SPRING + "RequestBody", "values": {}}]}
    out: dict[str, Any] = {}
    for key, types, eps in (
            ("plain", [_mapping_type(fqn, member, route=route)], [_mapping_ep(fqn, member, route)]),
            ("consumes_body", [_mapping_type(fqn, member, route=route, params=[body_param])], [_mapping_ep(fqn, member, route)]),
            ("wildcard", [_mapping_type(fqn, member, route=wildcard)], [_mapping_ep(fqn, member, wildcard)])):
        with tempfile.TemporaryDirectory(prefix="derive-methodless-") as td:
            root = build_root(Path(td), extra_types=types, add_eps=eps)
            p = _derive(root)
            if p.returncode != 0:
                raise AssertionError("a method-less mapping is derived or a recorded gap, never a refusal: %s" % p.stderr)
            out[key] = _read_decision(root, names, eid)
    return out


def _methodless_mapping_case() -> int:
    """Spring MVC: @RequestMapping WITHOUT method matches every method, so a
    GET is a request the evidence supports.

    Measured on v9 (2026-09-14): RootRestController#redirectToSwagger declares
    @RequestMapping(value = "/") and answers GET / with a 302 to the servlet
    context path. The derivation recorded a gap and derived nothing, so no
    scenario observed the redirect -- and a worker then replaced the SpEL
    context path on the destination with "", sending the redirect outside the
    destination's root path, a behavioural withdrawal nothing could see. A
    handler that consumes a request body answers no such GET, a wildcard route
    is still not a request, and none of these decisions depends on the
    specimen's names."""
    fqn, member, route = "a.RootRestController", "redirectToSwagger(javax.servlet.http.HttpServletResponse)", "/"
    eid = "ep:%s#%s:http" % (fqn, member)
    with tempfile.TemporaryDirectory(prefix="derive-methodless-") as td:
        root = build_root(Path(td), extra_types=[_mapping_type(fqn, member)], add_eps=[_mapping_ep(fqn, member, route)])
        p = _derive(root)
        if p.returncode != 0:
            return _fail("a method-less mapping derives, it does not refuse: rc=%s %s" % (p.returncode, p.stderr))
        corpus = load_json(root / CORPUS_P)
        reads = [s for s in corpus["scenarios"] if str(s["id"]).startswith("sc:read-")]
        if [str(s["id"]) for s in reads] != ["sc:read-root"]:
            return _fail("ONE read scenario, named for the path it requests: %s" % [str(s["id"]) for s in corpus["scenarios"]])
        sc = reads[0]
        if [sc["method"], sc["path"], sc["body_absent"], sc["reset_before"], sc["effects"], sc["headers"]] != ["GET", "/", True, False, [], {}]:
            return _fail("a derived read is a GET of the concrete path, with no body, no reset and no effects: %s" % sc)
        if sc["qualify"] != {"intent": "positive", "usable_first_response": True}:
            return _fail("neither 2xx nor 3xx is knowable a priori, so the contract judges evidence usability only: %s" % sc["qualify"])
        want = "structure:%s#%s @RequestMapping without method → GET (Spring: no method matches every method)" % (fqn, member)
        if sc["derived_from"]["kind"] != "read" or want not in sc["derived_from"]["evidence"]:
            return _fail("the evidence line names the mapping Spring reads: %s" % sc["derived_from"])
        if any(eid in g for g in corpus["gaps"]):
            return _fail("an entry point that derived a scenario is no longer a gap: %s" % corpus["gaps"])
        # the loader accepts it: a GET with no body is a complete request
        try:
            load_corpus(root)
        except CorpusError as exc:
            return _fail("the derived read scenario must load: %s" % exc)
    try:
        mine = _methodless_decisions(fqn, member, route, "/legacy/*", "a.OwnerDto", "payload")
    except AssertionError as exc:
        return _fail(str(exc))
    body_gaps = mine["consumes_body"]["gaps"]
    if mine["consumes_body"]["reads"] or len(body_gaps) != 1 or "consumes a request body" not in body_gaps[0] or "@RequestBody" not in body_gaps[0]:
        return _fail("a handler that consumes a body derives no GET, and the gap says why: %s" % mine["consumes_body"])
    wild_gaps = mine["wildcard"]["gaps"]
    if mine["wildcard"]["reads"] or len(wild_gaps) != 1 or "carries a wildcard and is not a request" not in wild_gaps[0]:
        return _fail("a wildcard route keeps the existing gap and derives nothing: %s" % mine["wildcard"])
    # the specimen-independence invariance check: different package, type,
    # member, route and parameter names, same decisions
    try:
        renamed = _methodless_decisions("z.gateway.PortalResource", "showPortal(javax.servlet.http.HttpServletResponse)",
                                        "/portal", "/archive/*", "z.gateway.PortalPayload", "incoming")
    except AssertionError as exc:
        return _fail(str(exc))
    if renamed != mine:
        return _fail("the decisions are derived from the evidence, not from the names:\n  %s\n  %s" % (mine, renamed))
    return 0


def _methodless_qualification_case() -> int:
    """The read contract judges EVIDENCE and records what it saw. A usable
    first response is a PASS whatever its class -- the source's redirect is as
    legitimate an answer as a page -- and a 5xx nothing named is INCONCLUSIVE
    with the failure on the record, never a PASS and never a FAIL."""
    fqn, member = "a.RootRestController", "redirectToSwagger(javax.servlet.http.HttpServletResponse)"
    for status, want_capability, want_class in ((302, "PASS", "3xx"), (200, "PASS", "2xx"), (503, "INCONCLUSIVE", "")):
        with tempfile.TemporaryDirectory(prefix="derive-methodless-q-") as td:
            root = build_root(Path(td), extra_types=[_mapping_type(fqn, member)], add_eps=[_mapping_ep(fqn, member, "/")])
            if _derive(root).returncode != 0:
                return _fail("the fixture must derive")
            corpus = load_corpus(root)
            sc = {str(s["id"]): s for s in corpus["scenarios"]}["sc:read-root"]
            headers = {"Location": BASE + "/swagger-ui/index.html" if status == 302 else None}
            _capture(root, sc, corpus_digest(corpus), status, headers, {"ok": True}, {}, {})
            p, doc = _qualify(root)
            if p.returncode != 0:
                return _fail("a recorded verdict exits 0: rc=%s %s" % (p.returncode, p.stderr))
            row = doc["scenarios"]["sc:read-root"]
            if row["capability"] != want_capability:
                return _fail("a %s first response qualifies %s, not %s: %s" % (status, want_capability, row["capability"], row["reason"]))
            check = next((c for c in row["checks"] if c["check"] == "usable_first_response"), None)
            if want_capability == "PASS":
                if row["evidence"]["status"] != "USABLE" or check is None or check.get("observed_status_class") != want_class:
                    return _fail("the observed status class is RECORDED, not expected: %s" % row["checks"])
            elif row["evidence"]["status"] != "UNUSABLE" or not any("%s" % status in f for f in row["known_failures"]):
                return _fail("a 5xx the contract does not name is unusable evidence with the failure recorded: %s" % row)
    return 0


PET_CONTROLLER = "a.PetRestController"
_PET_DOCS = (
    "openapi: 3.0.1\n"
    "info:\n  title: Pets\n  version: '1.0'\n"
    "paths:\n"
    "  /owner/{ownerId}/pet:\n"
    "    parameters:\n      - name: ownerId\n        in: path\n        required: true\n        schema:\n          type: integer\n        example: 1\n"
    "    post:\n      operationId: addPet\n      requestBody:\n        content:\n          application/json:\n"
    "            schema:\n              $ref: '#/components/schemas/PetFields'\n        required: true\n"
    "      responses:\n        201:\n          description: created\n"
    "  /pet/{petId}:\n"
    "    parameters:\n      - name: petId\n        in: path\n        required: true\n        schema:\n          type: integer\n        example: 1\n"
    "    put:\n      operationId: updatePet\n      requestBody:\n        content:\n          application/json:\n"
    "            schema:\n              $ref: '#/components/schemas/PetFields'\n        required: true\n"
    "      responses:\n        '204':\n          description: updated\n"
    "components:\n  schemas:\n"
    "    PetFields:\n      type: object\n      properties:\n"
    "        name:\n          type: string\n          minLength: 1\n          example: Leo\n"
    "      required:\n        - name\n"
)


def _pet_ep(method: str, route: str, member: str) -> dict[str, Any]:
    return {"id": "ep:%s#%s:http" % (PET_CONTROLLER, member), "kind": "http", "type": PET_CONTROLLER, "member": member,
            "path": "src/main/java/a/PetRestController.java", "http_method": method, "http_path": route}


def _path_variable_case() -> int:
    """An operationId match is not a binding unless the operation's path
    variables are resolvable through the route's.

    Measured on v9 (2026-09-14): ``addPet`` bound ``POST /owner/{ownerId}/pet``
    to the route ``POST /api/pets``, which carries no ``ownerId``, and the
    derived ``PetFields`` body went to a route that cannot express the
    operation's identity -- the source answered 400 and the qualification
    could not say what happened. The same document's ``updatePet``
    (``PUT /pet/{petId}`` ↔ ``PUT /api/pets/{petId}``) has the same variable
    set and must still bind."""
    with tempfile.TemporaryDirectory(prefix="derive-pathvars-") as td:
        eps = [_pet_ep("POST", "/api/pets", "addPet(a.PetDto)"), _pet_ep("PUT", "/api/pets/{petId}", "updatePet(int,a.PetDto)")]
        root = build_root(Path(td), api_docs=_PET_DOCS, extra_eps=eps,
                          seed_sql="INSERT INTO pets VALUES (1, 'Leo');\n",
                          schema_sql="CREATE TABLE pets (\n  id INTEGER IDENTITY PRIMARY KEY,\n  name VARCHAR(30)\n);\n")
        p = _derive(root)
        if p.returncode != 0:
            return _fail("a path-variable mismatch is a gap, not a refusal: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        corpus = load_json(root / CORPUS_P)
        ids = {str(s["id"]) for s in corpus["scenarios"]}
        if any(i.startswith("sc:create-") for i in ids):
            return _fail("no scenario, positive or invalid, is emitted for an unbound route: %s" % sorted(ids))
        want_gap = ("create ep:%s#addPet(a.PetDto):http: operationId addPet binds POST /owner/{ownerId}/pet (variables: ownerId) "
                    "to route /api/pets (variables: none); path-variable sets differ; not bound" % PET_CONTROLLER)
        if want_gap not in corpus["gaps"]:
            return _fail("the gap names both paths and both variable sets: %s" % corpus["gaps"])
        if any(g.startswith("create ") and "no OpenAPI operation" in g for g in corpus["gaps"]):
            return _fail("the typed gap replaces the generic one; it is not reported twice: %s" % corpus["gaps"])
        update = [s for s in corpus["scenarios"] if s["id"] == "sc:update-pets-1"]
        if len(update) != 1:
            return _fail("a matching variable set still binds: %s / %s" % (sorted(ids), corpus["gaps"]))
        if "openapi-path:/pet/{petId}≠route:/api/pets/{petId}; bound by operationId updatePet" not in update[0]["derived_from"]["evidence"]:
            return _fail("the binding evidence still records the path discrepancy: %s" % update[0]["derived_from"])
    return 0


def _foreign_key_delete_case() -> int:
    """A delete addresses a row the database will let go.

    v9 derived ``DELETE /api/specialties/1`` because 1 is the first seeded row;
    the source answered 400 ``DataIntegrityViolationException ...
    FK_VET_SPECIALTIES_SPECIALTIES`` because ``vet_specialties`` references
    every seeded specialty. The schema says so, so the derivation reads it."""
    seed = ("INSERT INTO owners VALUES (3, 'Eduardo', 'Rodriquez', '2693 Commerce St.', 'McFarland', '6085558763');\n"
            "INSERT INTO pets VALUES (1, 'Leo', 1);\n"
            "INSERT INTO pets VALUES (2, 'Basil', 2);\n"
            "INSERT INTO specialties VALUES (1, 'radiology');\n"
            "INSERT INTO specialties VALUES (2, 'surgery');\n"
            "INSERT INTO vet_specialties VALUES (2, 1);\n"
            "INSERT INTO vet_specialties VALUES (3, 2);\n")
    schema = ("CREATE TABLE pets (\n  id INTEGER IDENTITY PRIMARY KEY,\n  name VARCHAR(30),\n  owner_id INT NOT NULL,\n"
              "  FOREIGN KEY (owner_id) REFERENCES owners (id)\n);\n"
              "CREATE TABLE specialties (\n  id INTEGER IDENTITY PRIMARY KEY,\n  name VARCHAR(80)\n);\n"
              "CREATE TABLE vet_specialties (\n  vet_id INT NOT NULL,\n  specialty_id INT NOT NULL,\n"
              "  CONSTRAINT FK_VET_SPECIALTIES_SPECIALTIES FOREIGN KEY (specialty_id) REFERENCES specialties (id)\n);\n")
    with tempfile.TemporaryDirectory(prefix="derive-fk-") as td:
        eps = [_entry("delete", "DELETE", "/api/owners/{ownerId}", "deleteOwner(int)"),
               {"id": "ep:a.SpecialtyRestController#deleteSpecialty(int):http", "kind": "http", "type": "a.SpecialtyRestController",
                "member": "deleteSpecialty(int)", "path": "src/main/java/a/SpecialtyRestController.java",
                "http_method": "DELETE", "http_path": "/api/specialties/{specialtyId}"}]
        # the schema lives in the seed's own directory under petclinic's own
        # name: discovery is by content, never by a specimen's filename.
        # Neither entity removes what points at it, so the refusal is the
        # source's own and the negative scenario is derivable
        ents = [entity("Owner", "owners"), entity("Pet", "pets", [rel("owner", "ManyToOne", {}, "a.model.Owner")]),
                entity("Specialty", "specialties"), entity("Vet", "vets")]
        root = build_root(Path(td), extra_eps=eps, seed_sql=seed, schema_sql=schema, schema_name="initDB.sql", entities=ents)
        p = _derive(root)
        if p.returncode != 0:
            return _fail("a foreign key is evidence, not a refusal: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        corpus = load_json(root / CORPUS_P)
        sc = {str(s["id"]): s for s in corpus["scenarios"]}
        deletes = {i for i in sc if "delete" in i}
        if deletes != {"sc:delete-owners-3", "sc:delete-referenced-owners-1", "sc:delete-referenced-specialties-1"}:
            return _fail("the positive delete addresses the unreferenced row and every blocked resource gets one negative: %s\ngaps: %s" % (sorted(deletes), corpus["gaps"]))
        pos = sc["sc:delete-owners-3"]
        if pos["path"] != "/api/owners/3" or "seed:owners#3 unreferenced by pets.owner_id" not in pos["derived_from"]["evidence"]:
            return _fail("the choice and its evidence are recorded on the scenario: %s" % pos["derived_from"])
        if "schema:FOREIGN KEY pets.owner_id → owners.id" not in pos["derived_from"]["evidence"]:
            return _fail("the constraint that forced the choice is named: %s" % pos["derived_from"])
        if any("every seed row of owners is referenced" in g for g in corpus["gaps"]):
            return _fail("a table with a free row is not a gap: %s" % corpus["gaps"])
        want = ("delete ep:a.SpecialtyRestController#deleteSpecialty(int):http: every seed row of specialties is referenced "
                "(FK_VET_SPECIALTIES_SPECIALTIES/vet_specialties.specialty_id); no deletable row derivable")
        if want not in corpus["gaps"]:
            return _fail("an all-referenced table is a typed gap naming the constraint: %s" % corpus["gaps"])
        neg = sc["sc:delete-referenced-specialties-1"]
        if neg["qualify"] != {"intent": "negative", "expect_status_class": "4xx",
                              "after_effect_status": {"eff:specialties-1-after-refused-delete": 200}}:
            return _fail("the negative delete states exactly what is checked: %s" % neg["qualify"])
        if not neg.get("body_absent") or neg["path"] != "/api/specialties/1" or neg["method"] != "DELETE":
            return _fail("the refused delete is the same request against a referenced row: %s" % neg)
        if "FK_VET_SPECIALTIES_SPECIALTIES/vet_specialties.specialty_id" not in " ".join(neg["derived_from"]["evidence"]):
            return _fail("the negative names what references the row: %s" % neg["derived_from"])
        rec = load_json(root / DERIVE_RECEIPT)
        read = [i["path"] for i in rec["inputs"]["sql"]]
        if read != ["src/main/resources/db/hsqldb/populateDB.sql", "src/main/resources/db/hsqldb/initDB.sql"]:
            return _fail("the receipt records which SQL the derivation read: %s" % read)
    # ... and with no schema file beside the seed, the foreign keys are unknown
    # and the derivation says so rather than deriving a delete blind
    with tempfile.TemporaryDirectory(prefix="derive-noschema-") as td:
        root = build_root(Path(td))
        (Path(td) / "frozen" / "src" / "main" / "resources" / "db" / "hsqldb" / "schema.sql").unlink()
        if _derive(root).returncode != 0:
            return _fail("a missing schema file is a gap, not a refusal")
        gaps = load_json(root / CORPUS_P)["gaps"]
        if not any("no schema file declaring CREATE TABLE" in g for g in gaps):
            return _fail("a seed with no schema beside it records why its foreign keys are unknown: %s" % gaps)
    return 0


_REMOVAL_SEED = (
    "INSERT INTO pets VALUES (1, 'Leo', 1);\n"
    "INSERT INTO pets VALUES (2, 'Basil', 1);\n"
    "INSERT INTO pets VALUES (3, 'Rosy', 1);\n"
    "INSERT INTO pets VALUES (4, 'Jewel', 1);\n"
    "INSERT INTO pets VALUES (5, 'Iggy', 2);\n"
    "INSERT INTO vets VALUES (1, 'James');\n"
    "INSERT INTO vets VALUES (2, 'Helen');\n"
    "INSERT INTO specialties VALUES (1, 'radiology');\n"
    "INSERT INTO specialties VALUES (2, 'surgery');\n"
    "INSERT INTO vet_specialties VALUES (1, 1);\n"
    "INSERT INTO vet_specialties VALUES (2, 2);\n")


def _removal_schema(on_delete: str = "") -> str:
    return ("CREATE TABLE pets (\n  id INTEGER IDENTITY PRIMARY KEY,\n  name VARCHAR(30),\n  owner_id INT NOT NULL,\n"
            "  FOREIGN KEY (owner_id) REFERENCES owners (id)%s\n);\n" % on_delete +
            "CREATE TABLE vets (\n  id INTEGER IDENTITY PRIMARY KEY,\n  name VARCHAR(30)\n);\n"
            "CREATE TABLE specialties (\n  id INTEGER IDENTITY PRIMARY KEY,\n  name VARCHAR(80)\n);\n"
            "CREATE TABLE vet_specialties (\n  vet_id INT NOT NULL,\n  specialty_id INT NOT NULL,\n"
            "  CONSTRAINT FK_VS_VETS FOREIGN KEY (vet_id) REFERENCES vets (id),\n"
            "  CONSTRAINT FK_VS_SPECIALTIES FOREIGN KEY (specialty_id) REFERENCES specialties (id)\n);\n")


def _ep(type_simple: str, member: str, method: str, route: str) -> dict[str, Any]:
    return {"id": "ep:a.%s#%s:http" % (type_simple, member), "kind": "http", "type": "a.%s" % type_simple, "member": member,
            "path": "src/main/java/a/%s.java" % type_simple, "http_method": method, "http_path": route}


_REMOVAL_EPS = [
    _entry("delete", "DELETE", "/api/owners/{ownerId}", "deleteOwner(int)"),
    _ep("PetRestController", "getPet(int)", "GET", "/api/pets/{petId}"),
    _ep("VetRestController", "deleteVet(int)", "DELETE", "/api/vets/{vetId}"),
    _ep("SpecialtyRestController", "deleteSpecialty(int)", "DELETE", "/api/specialties/{specialtyId}"),
]


def _application_removal_case() -> int:
    """A schema foreign key does not say whether the SOURCE refuses the delete.

    Measured on destination v9 (2026-09-14): the derived negative
    ``sc:delete-referenced-*`` expected a refusal for owners, pets, types and
    vets, and the frozen source deleted all four (204). Only ``specialties``
    refused. The difference is in the application, not the schema:
    ``Owner.pets`` is ``@OneToMany(cascade = ALL)`` and ``Vet.specialties``
    owns the ``vet_specialties`` ``@JoinTable``, so the application removes the
    references itself, while ``Specialty`` is the inverse side and declares
    nothing. The structure model records exactly that, so the derivation reads
    it and derives by what the evidence supports: a cascading positive, a
    refusal, or -- when nothing decides -- neither, and a typed gap."""
    owner_pets = entity("Owner", "owners", [rel("pets", "OneToMany", {"cascade": ["ALL"], "mappedBy": ["owner"]})])
    pet = entity("Pet", "pets", [rel("owner", "ManyToOne", {}, "a.model.Owner")])
    vet_owning = entity("Vet", "vets", [rel("specialties", "ManyToMany", {"fetch": ["EAGER"]}, join_table="vet_specialties")])
    specialty_inverse = entity("Specialty", "specialties", [rel("vets", "ManyToMany", {"mappedBy": ["specialties"]})])

    # (a) cascade ALL on the parent's own field, and (b) the owning @ManyToMany
    with tempfile.TemporaryDirectory(prefix="derive-cascade-") as td:
        root = build_root(Path(td), extra_eps=_REMOVAL_EPS, seed_sql=_REMOVAL_SEED, schema_sql=_removal_schema(),
                          entities=[owner_pets, pet, vet_owning, specialty_inverse])
        p = _derive(root)
        if p.returncode != 0:
            return _fail("the relationship model is evidence, not a refusal: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        corpus = load_json(root / CORPUS_P)
        sc = {str(s["id"]): s for s in corpus["scenarios"]}
        deletes = sorted(i for i in sc if "delete" in i)
        if deletes != ["sc:delete-cascading-owners-1", "sc:delete-cascading-vets-1", "sc:delete-referenced-specialties-1"]:
            return _fail("cascade ALL and an owned join table derive a cascading positive; the inverse side keeps the refusal: %s\ngaps: %s"
                         % (deletes, corpus["gaps"]))
        casc = sc["sc:delete-cascading-owners-1"]
        if casc["path"] != "/api/owners/1" or not casc.get("body_absent") or not casc.get("reset_before") or casc["method"] != "DELETE":
            return _fail("the cascading delete is the same request against the referenced row: %s" % casc)
        if casc["derived_from"]["kind"] != "delete-cascading":
            return _fail("the cascading delete names its own rule: %s" % casc["derived_from"])
        # the children are read back one per referencing row, capped at three
        if [e["path"] for e in casc["effects"]] != ["/api/owners/1", "/api/pets/1", "/api/pets/2", "/api/pets/3"]:
            return _fail("the effects are the row and each referencing row a bound item route reads: %s" % casc["effects"])
        if casc["qualify"] != {"intent": "positive", "expect_status": [200, 204], "after_effect_status": {
                "eff:owners-1-after-cascading-delete": 404, "eff:pets-1-after-cascading-delete": 404,
                "eff:pets-2-after-cascading-delete": 404, "eff:pets-3-after-cascading-delete": 404}}:
            return _fail("the cascading delete states exactly what is checked: %s" % casc["qualify"])
        ev = casc["derived_from"]["evidence"]
        if "schema:FOREIGN KEY pets.owner_id → owners.id" not in ev:
            return _fail("the FK evidence is on the scenario: %s" % ev)
        if not any(e.startswith("structure:Owner.pets @OneToMany(cascade=ALL)") and "table pets" in e for e in ev):
            return _fail("the application-removal evidence names the annotation and the field: %s" % ev)
        if "structure:Owner @Table(name=owners)" not in ev or "structure:Pet @Table(name=pets)" not in ev:
            return _fail("how each entity was mapped to its table is evidence too: %s" % ev)
        if not any(e.startswith("note:4 rows of pets reference owners#1") and "first 3" in e for e in ev):
            return _fail("the cap on the read-back children is noted: %s" % ev)
        vets = sc["sc:delete-cascading-vets-1"]
        if [e["path"] for e in vets["effects"]] != ["/api/vets/1"]:
            return _fail("a join table has no item route, so only the deleted row is read back: %s" % vets["effects"])
        if not any("owns the vet_specialties join table" in e for e in vets["derived_from"]["evidence"]):
            return _fail("the owning @ManyToMany is the removal evidence: %s" % vets["derived_from"])
        if not any(e.startswith("note:") and "not observable through routes" in e for e in vets["derived_from"]["evidence"]):
            return _fail("a child nothing can read is said to be unobservable, not silently dropped: %s" % vets["derived_from"])
        neg = sc["sc:delete-referenced-specialties-1"]
        if neg["qualify"] != {"intent": "negative", "expect_status_class": "4xx",
                              "after_effect_status": {"eff:specialties-1-after-refused-delete": 200}}:
            return _fail("the inverse @ManyToMany side keeps the refusal contract: %s" % neg["qualify"])
        if not any("none declared" in e for e in neg["derived_from"]["evidence"]):
            return _fail("the negative records that the application declares no removal: %s" % neg["derived_from"])
        if "structure:Specialty @Table(name=specialties)" not in neg["derived_from"]["evidence"]:
            return _fail("the negative records the mapping it judged: %s" % neg["derived_from"])

    # (c) the schema's own ON DELETE CASCADE, with an application that declares
    # nothing: the reference still goes, so the scenario is still positive.
    # This Owner declares no @Table either, so its table comes from its name
    with tempfile.TemporaryDirectory(prefix="derive-ondelete-") as td:
        root = build_root(Path(td), extra_eps=_REMOVAL_EPS, seed_sql=_REMOVAL_SEED,
                          schema_sql=_removal_schema(" ON DELETE CASCADE"),
                          entities=[entity("Owner"), pet, vet_owning, specialty_inverse])
        if _derive(root).returncode != 0:
            return _fail("an ON DELETE CASCADE is evidence, not a refusal")
        corpus = load_json(root / CORPUS_P)
        sc = {str(s["id"]): s for s in corpus["scenarios"]}
        if "sc:delete-cascading-owners-1" not in sc or "sc:delete-referenced-owners-1" in sc:
            return _fail("ON DELETE CASCADE carries the children away: %s\ngaps: %s" % (sorted(sc), corpus["gaps"]))
        ev = sc["sc:delete-cascading-owners-1"]["derived_from"]["evidence"]
        if not any("ON DELETE CASCADE" in e and e.startswith("schema:FOREIGN KEY pets.owner_id") for e in ev):
            return _fail("the constraint's own rule is the removal evidence: %s" % ev)

    # an entity with no @Table is mapped by its own name, and says so
    with tempfile.TemporaryDirectory(prefix="derive-nametable-") as td:
        root = build_root(Path(td), extra_eps=_REMOVAL_EPS, seed_sql=_REMOVAL_SEED, schema_sql=_removal_schema(),
                          entities=[entity("Owner", "", [rel("pets", "OneToMany", {"orphanRemoval": ["true"]})]),
                                    entity("Pet", "", [rel("owner", "ManyToOne", {}, "a.model.Owner")])])
        if _derive(root).returncode != 0:
            return _fail("an entity without @Table is a mapping, not a refusal")
        sc = {str(s["id"]): s for s in load_json(root / CORPUS_P)["scenarios"]}
        if "sc:delete-cascading-owners-1" not in sc:
            return _fail("orphanRemoval removes the reference just as cascade REMOVE does: %s" % sorted(sc))
        ev = sc["sc:delete-cascading-owners-1"]["derived_from"]["evidence"]
        if "structure:Owner → owners (entity name; no @Table)" not in ev or "structure:Pet → pets (entity name; no @Table)" not in ev:
            return _fail("the name-derived mapping is recorded as such: %s" % ev)
        if not any("orphanRemoval=true" in e for e in ev):
            return _fail("orphanRemoval is named as the removal evidence: %s" % ev)

    # no structure model: neither scenario, and a typed gap saying why
    with tempfile.TemporaryDirectory(prefix="derive-nostructure-") as td:
        root = build_root(Path(td), extra_eps=_REMOVAL_EPS, seed_sql=_REMOVAL_SEED, schema_sql=_removal_schema(), no_structure=True)
        if _derive(root).returncode != 0:
            return _fail("a missing structure model is a gap, not a refusal")
        corpus = load_json(root / CORPUS_P)
        ids = {str(s["id"]) for s in corpus["scenarios"]}
        if any(i.startswith("sc:delete-referenced-") or i.startswith("sc:delete-cascading-") for i in ids):
            return _fail("an expectation nobody can derive is not an oracle: %s" % sorted(ids))
        want = ("delete-referenced ep:a.OwnerRestController#deleteOwner(int):http: whether the application removes pets.owner_id "
                "references is not derivable (no structure model at evidence/structure/structure.json, so the application's own "
                "relationships are unknown)")
        if want not in corpus["gaps"]:
            return _fail("the gap names the reference and why it is not derivable: %s" % corpus["gaps"])
        if not any("vet_specialties.specialty_id references is not derivable" in g for g in corpus["gaps"]):
            return _fail("every undecidable reference gets its own gap: %s" % corpus["gaps"])
    return 0


def _retain(root: Path, sid: str, name: str, payload: Any) -> tuple[dict[str, Any], str]:
    raw = json.dumps(payload).encode("utf-8")
    sha = normalize_body(raw, "application/json")[1]
    return retain_body(root / SCENARIO_ORACLES / "bodies" / scenario_slug(sid), name, raw, sha), sha


def _capture(root: Path, sc: dict[str, Any], corpus_sha: str, status: int, headers: dict[str, Any], body: Any,
             before: dict[str, tuple[int, Any]], after: dict[str, tuple[int, Any]], request_sha: str | None = None,
             effects_identity: dict[str, Any] | None = None) -> Path:
    sid = str(sc["id"])
    ev, sha = _retain(root, sid, "response", body)
    rec: dict[str, Any] = {
        "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": sc["entry_point"],
        "evidence_bundle_sha256": digest(load_json(root / EVIDENCE_BUNDLE)), "corpus_sha256": corpus_sha,
        "source": {"base_url": BASE, "analysis_copy_digest": "fixture-source-digest"}, "status": "CAPTURED", "reason": "",
        "request": {"method": sc["method"], "path": sc["path"], "headers": dict(sc.get("headers") or {}),
                    "request_sha256": request_sha if request_sha is not None else request_of(root, sc)["request_sha256"]},
        "response": {"status": status, "headers": headers, "body_kind": "json", "body_sha256": sha, "evidence": ev},
        "before": [], "effects": [],
    }
    if effects_identity is not None:
        # whom the producer took the read-backs as, recorded by NAME the way
        # capture-source-scenarios.py records it
        rec["effects_identity"] = dict(effects_identity)
    for key, rows in (("before", before), ("effects", after)):
        for eff in sc.get("effects") or []:
            st, payload = rows[eff["id"]]
            ev, sha = _retain(root, sid, "%s-%s" % ("before" if key == "before" else "after", scenario_slug(eff["id"])), payload)
            rec[key].append({"id": eff["id"], "method": "GET", "path": eff["path"], "status": st, "body_kind": "json", "body_sha256": sha, "evidence": ev})
    out = root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json")
    write_canonical(out, rec)
    return out


def _effects_identity_qualification_case() -> int:
    """What a REFUSED write left behind, judged.

    Measured on destination v9 (2026-09-15): 15 negative authorization
    scenarios qualified INCONCLUSIVE with ``before eff:... answered 401, not
    2xx; its body cannot stand for the collection``. The read-backs carried
    the refusing request's own identity, so the one thing those scenarios
    exist to show -- the state did not change -- could not be read off the
    evidence at all. With the read-backs taken as the identity the policy
    ACCEPTS (``effects_identity``), the predicate is judgeable both ways: PASS
    when the state is unchanged, FAIL when the refused write changed it
    anyway. A capture that took them as somebody else is UNUSABLE evidence
    naming the identity, and a scenario that declares none keeps exactly the
    answer it had."""
    accepted = {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": "PARITY_ADMIN"}
    eff = {"id": "eff:owners-after-denied-delete", "method": "GET", "path": "/api/owners"}
    seeded = [SEED_OWNER_1, SEED_OWNER_2]
    refusal = ({"WWW-Authenticate": 'Basic realm="fixture"', "Location": None}, {"error": "unauthorized"})

    def corpus_with(effects_identity: dict[str, Any] | None) -> dict[str, Any]:
        sc: dict[str, Any] = {
            "id": "sc:auth-anonymous-delete-owners-1", "entry_point": EP["delete"], "method": "DELETE",
            "path": "/api/owners/1", "headers": {}, "identity": {"kind": "none"}, "body_absent": True,
            "reset_before": True, "effects": [dict(eff)], "normalization": [],
            "qualify": {"intent": "negative", "expect_status_class": "4xx", "after_equals_before": True}}
        if effects_identity is not None:
            sc["effects_identity"] = dict(effects_identity)
        return {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                "initial_state": {"reset": "restart the source", "dataset": "two owners"},
                "path_vars": {"ownerId": "1"}, "scenarios": [sc]}

    with tempfile.TemporaryDirectory(prefix="qualify-effects-identity-") as td:
        root = build_root(Path(td))
        declared = corpus_with({"kind": "basic", "credential_ref": "PARITY_ADMIN"})
        write_canonical(root / CORPUS_P, declared)
        sc = declared["scenarios"][0]
        sha = corpus_digest(load_json(root / CORPUS_P))

        # (a) the state the refusal left, read back as the accepted identity
        _capture(root, sc, sha, 401, refusal[0], refusal[1], {eff["id"]: (200, seeded)}, {eff["id"]: (200, seeded)},
                 effects_identity=accepted)
        p, q = _qualify(root)
        r = q["scenarios"][sc["id"]]
        if p.returncode != 0 or r["capability"] != "PASS" or r["evidence"] != {"status": "USABLE", "reasons": []}:
            return _fail("a refusal whose accepted-identity read-backs are unchanged is a PASS, not an INCONCLUSIVE: %s" % r)
        if not any(c["check"] == "after_equals_before" and c["ok"] is True for c in r["checks"]):
            return _fail("after_equals_before is the predicate that was judged: %s" % r["checks"])

        # (b) ... and a refused write that nevertheless changed the state FAILs
        _capture(root, sc, sha, 401, refusal[0], refusal[1], {eff["id"]: (200, seeded)},
                 {eff["id"]: (200, [SEED_OWNER_2])}, effects_identity=accepted)
        p, q = _qualify(root)
        r = q["scenarios"][sc["id"]]
        if r["capability"] != "FAIL" or not any(c["check"] == "after_equals_before" and c["ok"] is False for c in r["checks"]):
            return _fail("a 401 that deleted the row anyway is a judged FAIL: %s" % r)

        # (c) a capture that took the read-backs as the refused caller is
        # evidence about another question, and the reason names the identity
        # by reference rather than leaving "answered 401" to be interpreted
        _capture(root, sc, sha, 401, refusal[0], refusal[1], {eff["id"]: (401, refusal[1])}, {eff["id"]: (401, refusal[1])})
        p, q = _qualify(root)
        r = q["scenarios"][sc["id"]]
        if (r["capability"] != "INCONCLUSIVE" or r["evidence"]["status"] != "UNUSABLE"
                or "credential_ref PARITY_ADMIN" not in r["reason"] or "the request's own identity" not in r["reason"]):
            return _fail("read-backs taken as somebody else are unusable evidence naming both identities: %s" % r)
        if "PARITY" not in json.dumps(q) or "password" in json.dumps(q).lower():
            return _fail("the identity travels by reference and nothing else does: %s" % r["reason"])

        # (d) a scenario that declares no effects identity keeps the answer it
        # had: the read-backs are the request's own, and 401s cannot stand for
        # the collection
        plain = corpus_with(None)
        write_canonical(root / CORPUS_P, plain)
        sha = corpus_digest(load_json(root / CORPUS_P))
        _capture(root, plain["scenarios"][0], sha, 401, refusal[0], refusal[1],
                 {eff["id"]: (401, refusal[1])}, {eff["id"]: (401, refusal[1])})
        p, q = _qualify(root)
        r = q["scenarios"][sc["id"]]
        if r["capability"] != "INCONCLUSIVE" or "not 2xx" not in r["reason"]:
            return _fail("with no effects identity declared the v9 answer stands unchanged: %s" % r)

        # ... and a corpus naming an effects identity for a scenario with no
        # read-backs to take is refused outright
        empty = corpus_with({"kind": "basic", "credential_ref": "PARITY_ADMIN"})
        empty["scenarios"][0]["effects"] = []
        write_canonical(root / CORPUS_P, empty)
        try:
            load_corpus(root)
            return _fail("an effects identity for read-backs nobody takes must be refused")
        except CorpusError as exc:
            if "read-backs nobody takes" not in str(exc):
                return _fail("the refusal says what is wrong: %s" % exc)
    return 0


def _qualify(root: Path) -> tuple[subprocess.CompletedProcess, dict[str, Any]]:
    p = subprocess.run([sys.executable, str(QUALIFY), "--root", str(root)], text=True, capture_output=True)
    return p, load_json(root / QUALIFICATION)


def _qualification_case(root: Path) -> int:
    corpus = load_corpus(root)
    corpus_sha = corpus_digest(corpus)
    sc = {str(s["id"]): s for s in corpus["scenarios"]}
    short = str(corpus["cors_policies"][0]["id"]).split(":", 1)[1]
    origin = sc["sc:cors-actual-%s" % short]["headers"]["Origin"]
    create_body = json.loads((root / sc["sc:create-owners"]["body_file"]).read_text())
    created = dict(create_body, id=11)
    seeded = [SEED_OWNER_1, SEED_OWNER_2]
    cors = {"Access-Control-Allow-Origin": origin, "Access-Control-Expose-Headers": "errors, content-type", "Access-Control-Allow-Credentials": None}
    good_create = dict(cors, Location=BASE + "/api/owners/11", errors=None)
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    invalid_hdrs = dict(cors, Location=None, errors='[{"fieldName":"telephone","fieldValue":"6085551023!","errorMessage":"numeric value out of bounds"}]')
    inv_tel, inv_fn = sc["sc:create-invalid-owners-telephone"], sc["sc:create-invalid-owners-firstName"]
    eff_tel, eff_fn = "eff:owners-list-after-invalid-create-telephone", "eff:owners-list-after-invalid-create-firstName"
    _capture(root, inv_tel, corpus_sha, 400, invalid_hdrs, {"error": "bad request"}, {eff_tel: (200, seeded)}, {eff_tel: (200, seeded)})
    fn_hdrs = dict(invalid_hdrs, errors='[{"fieldName":"firstName","fieldValue":"George!","errorMessage":"must match"}]')
    _capture(root, inv_fn, corpus_sha, 400, fn_hdrs, {"error": "bad request"}, {eff_fn: (200, seeded)}, {eff_fn: (200, seeded)})
    update_body = json.loads((root / sc["sc:update-owners-1"]["body_file"]).read_text())
    updated = dict(update_body, id=1)
    _capture(root, sc["sc:update-owners-1"], corpus_sha, 204, {"Location": None}, "",
             {"eff:owners-1-after-update": (200, SEED_OWNER_1), "eff:owners-list-after-update": (200, seeded)},
             {"eff:owners-1-after-update": (200, updated), "eff:owners-list-after-update": (200, [updated, SEED_OWNER_2])})
    _capture(root, sc["sc:delete-owners-1"], corpus_sha, 204, {"Location": None}, "",
             {"eff:owners-1-after-delete": (200, SEED_OWNER_1)}, {"eff:owners-1-after-delete": (404, {"error": "not found"})})
    _capture(root, sc["sc:cors-actual-%s" % short], corpus_sha, 200, dict(cors, Location=None), seeded, {}, {})
    _capture(root, sc["sc:cors-preflight-%s" % short], corpus_sha, 200,
             {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE", "Access-Control-Allow-Headers": "content-type",
              "Access-Control-Max-Age": "1800", "Location": None}, "", {}, {})
    p, q = _qualify(root)
    verdicts = {sid: r["capability"] for sid, r in q["scenarios"].items()}
    if p.returncode != 0 or q["verdict"] != "PASS" or set(verdicts.values()) != {"PASS"} or q["corpus_sha256"] != corpus_sha:
        return _fail("captures that show what every scenario says are PASS: rc=%s %s %s%s" % (p.returncode, verdicts, p.stdout, p.stderr))
    rec = q["scenarios"]["sc:create-owners"]
    checks = {c["check"]: c for c in rec["checks"]}
    if set(checks) != {"expect_status", "location", "after_contains_body", "creates_one_entity"} or not all(c["ok"] is True for c in checks.values()):
        return _fail("the create's checks are exactly its contract: %s" % checks)
    cap_p = root / SCENARIO_ORACLES / (scenario_slug("sc:create-owners") + ".json")
    if (rec["evidence"] != {"status": "USABLE", "reasons": []} or rec["intent"] != "positive" or rec["known_failures"] != []
            or rec["capture_sha256"] != hashlib.sha256(cap_p.read_bytes()).hexdigest() or rec["request_sha256"] != request_of(root, sc["sc:create-owners"])["request_sha256"]
            or rec["corpus_sha256"] != corpus_sha or rec["evidence_bundle_sha256"] != digest(load_json(root / EVIDENCE_BUNDLE))):
        return _fail("a record carries both results and is bound to the exact capture: %s" % {k: rec[k] for k in ("evidence", "intent", "known_failures", "capture_sha256", "request_sha256")})
    if q["scenarios"]["sc:create-invalid-owners-telephone"]["intent"] != "negative" or q["scenarios"]["sc:create-invalid-owners-firstName"]["intent"] != "negative":
        return _fail("negative scenarios are recorded as negative")
    # a relative Location is not the source's absolute form under its base
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, dict(good_create, Location="/petclinic/api/owners/11"), created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    # a recorded FAIL is a source fact, not a refusal: the gate exits 0 and
    # still names the scenario on stderr
    if p.returncode != 0 or r["verdict"] != "FAIL" or not any(c["check"] == "location" and c["ok"] is False for c in r["checks"]) or "sc:create-owners" not in p.stderr:
        return _fail("a relative Location FAILs and names location: rc=%s %s %s" % (p.returncode, r, p.stderr))
    if "OK: qualification FAIL" not in p.stdout:
        return _fail("the verdict line still prints on a recorded FAIL: %s" % p.stdout)
    # a Location on another origin is not under the base either
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, dict(good_create, Location="http://elsewhere:8080/petclinic/api/owners/11"), created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["verdict"] != "FAIL":
        return _fail("a Location on another origin FAILs")
    # a created owner that is NOT in the list afterwards is a create that did not create
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded)})
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    # the example body IS seed owner 1, so "present afterwards" holds trivially;
    # "one more than before" is what catches a create that created nothing
    if r["capability"] != "FAIL" or r["evidence"]["status"] != "USABLE" or not any(c["check"] == "creates_one_entity" and c["ok"] is False for c in r["checks"]):
        return _fail("a 201 whose read-back gained no new entity FAILs: %s" % r)
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    # the 400 without the errors header the source exposes
    _capture(root, inv_tel, corpus_sha, 400, dict(invalid_hdrs, errors=None), {"error": "bad request"}, {eff_tel: (200, seeded)}, {eff_tel: (200, seeded)})
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-invalid-owners-telephone"]
    if r["capability"] != "FAIL" or not any(c["check"] == "errors_header_names_field" and c["ok"] is False for c in r["checks"]):
        return _fail("a 400 without the errors header FAILs: %s" % r)
    # ... a 400 whose parsed errors name another field: the rejection is not this scenario's
    _capture(root, inv_tel, corpus_sha, 400, fn_hdrs, {"error": "bad request"}, {eff_tel: (200, seeded)}, {eff_tel: (200, seeded)})
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-invalid-owners-telephone"]["capability"] != "FAIL":
        return _fail("a firstName rejection is not telephone coverage: %s" % q["scenarios"]["sc:create-invalid-owners-telephone"])
    # ... and a 400 that nevertheless changed the list
    _capture(root, inv_tel, corpus_sha, 400, invalid_hdrs, {"error": "bad request"}, {eff_tel: (200, seeded)}, {eff_tel: (200, seeded + [created])})
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-invalid-owners-telephone"]["capability"] != "FAIL":
        return _fail("a rejected create that changed the list FAILs")
    # invalid_non_json_error_and_unretained_500_readbacks: a non-JSON errors
    # header and 500 read-backs with no retained body are UNUSABLE evidence,
    # never a PASS on a substring
    _capture(root, inv_tel, corpus_sha, 400, dict(invalid_hdrs, errors="telephone"), {"error": "bad request"}, {eff_tel: (500, {"error": "boom"})}, {eff_tel: (500, {"error": "boom"})})
    cap_p = root / SCENARIO_ORACLES / (scenario_slug("sc:create-invalid-owners-telephone") + ".json")
    cap = load_json(cap_p)
    for row in cap["before"] + cap["effects"]:
        row.pop("evidence", None)
    write_canonical(cap_p, cap)
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-invalid-owners-telephone"]
    if r["capability"] != "INCONCLUSIVE" or r["evidence"]["status"] != "UNUSABLE" or "errors header not parseable" not in r["reason"] or "not 2xx" not in r["reason"]:
        return _fail("invalid_non_json_error_and_unretained_500_readbacks is INCONCLUSIVE naming both: %s" % r)
    _capture(root, inv_tel, corpus_sha, 400, invalid_hdrs, {"error": "bad request"}, {eff_tel: (200, seeded)}, {eff_tel: (200, seeded)})
    # duplicate_existing_id_and_wrong_location: a duplicate of a seeded row
    # (same identity) and a Location pointing at 999 passed a count; the
    # identity-aware predicate FAILs naming each broken condition
    cap_p = root / SCENARIO_ORACLES / (scenario_slug("sc:create-owners") + ".json")
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, dict(good_create, Location=BASE + "/api/owners/999"), created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [dict(SEED_OWNER_1)])})
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    if (r["capability"] != "FAIL" or r["evidence"]["status"] != "USABLE" or "expected exactly one" not in r["reason"]
            or "duplicated" not in r["reason"] or "999" not in r["reason"]):
        return _fail("duplicate_existing_id_and_wrong_location FAILs naming the new-identity, prior-entity and Location conditions: %s" % r)
    # failed_status_plus_unbound_after_body: a 500 beside an unbound read-back
    # is INCONCLUSIVE (unusable evidence), with the 500 on the record
    _capture(root, sc["sc:create-owners"], corpus_sha, 500, good_create, {"error": "boom"},
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    cap = load_json(cap_p)
    cap["effects"][0].pop("evidence")
    write_canonical(cap_p, cap)
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    if r["capability"] != "INCONCLUSIVE" or r["evidence"]["status"] != "UNUSABLE" or not any("status 500" in f for f in r["known_failures"]):
        return _fail("failed_status_plus_unbound_after_body is INCONCLUSIVE with the 500 recorded: %s" % r)
    # foreign_capture_identity_and_request: a capture answering another
    # request is not this scenario's capture
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])}, request_sha="f" * 64)
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    if r["capability"] != "INCONCLUSIVE" or "not this scenario's capture" not in r["reason"]:
        return _fail("foreign_capture_identity_and_request is INCONCLUSIVE: %s" % r)
    # a missing retained body cannot be checked
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    cap = load_json(cap_p)
    Path(cap["effects"][0]["evidence"]["body_file"]).unlink()
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    if r["capability"] != "INCONCLUSIVE" or r["evidence"]["status"] != "UNUSABLE" or not any(c["check"] == "after_contains_body" and c["ok"] is None and "absent" in c["detail"] for c in r["checks"]):
        return _fail("a missing retained body is INCONCLUSIVE with the reason: %s" % r)
    # a retained body whose bytes are not the recorded digest is not evidence
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    cap = load_json(cap_p)
    Path(cap["effects"][0]["evidence"]["body_file"]).write_bytes(json.dumps(seeded + [created, {"id": 12}]).encode())
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["capability"] != "INCONCLUSIVE" or "digest" not in q["scenarios"]["sc:create-owners"]["reason"]:
        return _fail("a retained body that does not match its digest is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    # a row retained without digests is bytes of unknown origin
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    cap = load_json(cap_p)
    cap["effects"][0]["evidence"].pop("raw_body_sha256")
    write_canonical(cap_p, cap)
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["capability"] != "INCONCLUSIVE" or "not digest-bound" not in q["scenarios"]["sc:create-owners"]["reason"]:
        return _fail("a retained body without its digests is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    # no capture at all, and a capture of another corpus
    cap_p.unlink()
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["capability"] != "INCONCLUSIVE" or q["scenarios"]["sc:create-owners"]["reason"] != "no capture":
        return _fail("no capture is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    _capture(root, sc["sc:create-owners"], "1" * 64, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["capability"] != "INCONCLUSIVE" or "corpus" not in q["scenarios"]["sc:create-owners"]["reason"]:
        return _fail("a capture bound to another corpus is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    # identity_field null: the gate refuses to judge a create by count
    with tempfile.TemporaryDirectory(prefix="derive-noid-") as td2:
        root2 = build_root(Path(td2), list_schema=False)
        _derive(root2)
        corpus2 = load_corpus(root2)
        sc2 = {str(s["id"]): s for s in corpus2["scenarios"]}
        if sc2["sc:create-owners"]["qualify"]["identity_field"] is not None:
            return _fail("no response schema on the collection GET means identity_field null: %s" % sc2["sc:create-owners"]["qualify"])
        corpus2_sha = corpus_digest(corpus2)
        _capture(root2, sc2["sc:create-owners"], corpus2_sha, 201, good_create, created,
                 {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
        p2, q2 = _qualify(root2)
        r2 = q2["scenarios"]["sc:create-owners"]
        if r2["capability"] != "INCONCLUSIVE" or "collection identity not derivable" not in r2["reason"]:
            return _fail("a create without a derivable identity is INCONCLUSIVE, never counted: %s" % r2)
        # ... and it is the PREDICATE that is unanswerable, not the evidence:
        # every other check was judged and passed
        if (r2["evidence"] != {"status": "USABLE", "reasons": []} or r2["known_failures"] != []
                or [u.split(":")[0] for u in r2["unjudged"]] != ["creates_one_entity"]
                or not all(c["ok"] is True for c in r2["checks"] if c["check"] != "creates_one_entity")):
            return _fail("all judged and passing beside one unjudgeable predicate is INCONCLUSIVE, with sound evidence: %s" % r2)
        if p2.returncode != 0:
            return _fail("a recorded INCONCLUSIVE is a verdict, not a refusal: rc=%s %s" % (p2.returncode, p2.stderr))
        # the v9 shape: the source answered 400 to a create, the errors header
        # parses, and the collection's identity_field is null. The 400 is
        # USABLE evidence and the expect_status miss is a JUDGED failure, so
        # the verdict is FAIL -- the unanswerable create predicate beside it
        # does not turn an answered mismatch back into a question
        _capture(root2, sc2["sc:create-owners"], corpus2_sha, 400,
                 dict(cors, Location=None, errors='[{"fieldName":"id","fieldValue":"null","errorMessage":"must not be null"}]'),
                 {"error": "bad request"}, {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded)})
        p2, q2 = _qualify(root2)
        r2 = q2["scenarios"]["sc:create-owners"]
        if r2["capability"] != "FAIL" or r2["evidence"]["status"] != "USABLE":
            return _fail("a 400 with a well-formed errors header is usable evidence and its expect_status miss is FAIL: %s" % r2)
        if (not any("expect_status" in f and "status 400" in f for f in r2["known_failures"])
                or not any(c["check"] == "creates_one_entity" and c["ok"] is None for c in r2["checks"])):
            return _fail("the judged failure and the unjudgeable predicate are both on the record: %s" % r2)
        if p2.returncode != 0 or "OK: qualification FAIL" not in p2.stdout:
            return _fail("a recorded FAIL exits 0 and prints its verdict: rc=%s %s%s" % (p2.returncode, p2.stdout, p2.stderr))
        # a refusal to JUDGE is different: with the corpus naming requests and
        # not one capture on disk, no qualification document is written
        for stale in (root2 / SCENARIO_ORACLES).glob("sc*.json"):
            stale.unlink()
        p2 = subprocess.run([sys.executable, str(QUALIFY), "--root", str(root2)], text=True, capture_output=True)
        if p2.returncode != 1 or "REFUSE" not in p2.stderr or "no capture" not in p2.stderr:
            return _fail("no capture at all is a refusal to judge: rc=%s %s%s" % (p2.returncode, p2.stdout, p2.stderr))
    # a scenario without a contract cannot be qualified
    bare = json.loads(json.dumps(corpus))
    for s in bare["scenarios"]:
        s.pop("qualify", None)
    write_canonical(root / CORPUS_P, bare)
    rec = load_json(root / DERIVE_RECEIPT)
    rec["corpus_sha256"] = corpus_digest(bare)
    write_canonical(root / DERIVE_RECEIPT, rec)
    p, q = _qualify(root)
    if p.returncode != 0 or any(r["capability"] != "INCONCLUSIVE" or "no qualification contract" not in r["reason"] for r in q["scenarios"].values()):
        return _fail("a scenario without a qualify block is INCONCLUSIVE and recorded, not refused: rc=%s %s" % (p.returncode, q["scenarios"]))
    return 0


def _receipt_case() -> int:
    """The parity receipt is INCONCLUSIVE for a derived corpus nobody qualified,
    and for a scenario whose qualification is not PASS."""
    with tempfile.TemporaryDirectory(prefix="receipt-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        specimens.prepare_loop(root)
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("fixture not admitted: %s" % rec["reasons"][:3])
        ep = sorted(str(e["id"]) for e in load_json(root / EVIDENCE_BUNDLE)["entry_points"])[0]
        corpus = {"schema": "rhoai3.scenario-corpus/v1",
                  "derived_from": {"producer": "derive-source-scenarios.py", "evidence_bundle_sha256": digest(load_json(root / EVIDENCE_BUNDLE))},
                  "initial_state": {}, "path_vars": {}, "cors_policies": [], "gaps": [],
                  "scenarios": [{"id": "sc:read-x", "entry_point": ep, "method": "GET", "path": "/api/x", "body_absent": True, "reset_before": False,
                                 "effects": [], "normalization": [], "qualify": {"expect_status": [200]}}]}
        write_canonical(root / CORPUS_P, corpus)
        write_canonical(root / DERIVE_RECEIPT, {"schema": "rhoai3.scenario-derivation/v1", "producer": "derive-source-scenarios.py", "status": "ok",
                                                "evidence_bundle_sha256": digest(load_json(root / EVIDENCE_BUNDLE)), "corpus_sha256": corpus_digest(corpus),
                                                "bodies": {}, "requests": {"sc:read-x": request_of(root, corpus["scenarios"][0])["request_sha256"]}})
        corpus_sha = corpus_digest(load_json(root / CORPUS_P))
        receipt_digest = load_json(root / "evidence/planning/admission-receipt.json")["receipt_digest"]
        write_canonical(root / "verification" / "parity" / "scenarios" / (scenario_slug("sc:read-x") + ".json"),
                        {"scenario": "sc:read-x", "entry_point": ep, "receipt_sha256": receipt_digest, "corpus_sha256": corpus_sha, "verdict": "PASS", "reason": ""})
        # every other entry point has a passed read parity record, so the
        # receipt as a whole is judged by the scenario under test
        from _oracle_common import PARITY, slug
        for other in sorted(str(e["id"]) for e in load_json(root / EVIDENCE_BUNDLE)["entry_points"]):
            if other != ep:
                write_canonical(root / PARITY / (slug(other) + ".json"), {"entry_point": other, "receipt_sha256": receipt_digest, "verdict": "PASS", "reason": "fixture"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "captures not qualified" not in row["reason"] or not doc["qualification"]["derived_corpus"]:
            return _fail("a derived corpus with no qualification is INCONCLUSIVE: %s %s" % (row, doc.get("qualification")))
        # a qualification that is INCONCLUSIVE (no capture, evidence not
        # digest-bound): the entry point cannot be judged
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"capability": "INCONCLUSIVE", "intent": "positive", "reason": "no capture"}}, "verdict": "INCONCLUSIVE"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if (row["verdict"] != "INCONCLUSIVE" or "capture not qualified: sc:read-x INCONCLUSIVE" not in row["reason"]
                or doc["coverage_gaps"] != [{"scenario": "sc:read-x", "entry_point": ep, "kind": "inconclusive-qualification", "intent": "positive",
                                            "reason": "capture not qualified: no capture"}]):
            return _fail("a scenario qualified INCONCLUSIVE makes its entry point INCONCLUSIVE and is an uncovered capability: %s %s" % (row, doc["coverage_gaps"]))
        # a POSITIVE scenario whose capability FAILED is a source-side fixture
        # failure: no parity credit, the entry point INCONCLUSIVE, and a
        # coverage gap of kind fixture-failed on the receipt
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"capability": "FAIL", "intent": "positive", "reason": "expect_status: status 500"}}, "verdict": "FAIL"})
        p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if p.returncode != 1 or row["verdict"] != "INCONCLUSIVE" or "source fixture failed qualification: sc:read-x" not in row["reason"]:
            return _fail("a positive FAIL qualification is a fixture failure, INCONCLUSIVE for its entry point: %s %s%s" % (row, p.stdout, p.stderr))
        if doc["coverage_gaps"] != [{"scenario": "sc:read-x", "entry_point": ep, "kind": "fixture-failed", "intent": "positive",
                                     "reason": "source fixture failed qualification: expect_status: status 500"}] or "coverage gap sc:read-x" not in p.stdout:
            return _fail("the fixture failure is a coverage gap on the receipt, printed: %s %s" % (doc["coverage_gaps"], p.stdout))
        # a NEGATIVE scenario whose capability PASSED compares parity normally
        # and counts as negative coverage only
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"capability": "PASS", "intent": "negative", "reason": ""}}, "verdict": "PASS"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "PASS" or row["coverage"] != {"positive": [], "negative": ["sc:read-x"]} or doc["coverage_gaps"]:
            return _fail("a negative PASS is negative coverage only: %s" % row)
        # a qualification bound to another capture is stale
        cap_p = root / SCENARIO_ORACLES / (scenario_slug("sc:read-x") + ".json")
        write_canonical(cap_p, {"schema": "rhoai3.source-scenario/v1", "scenario": "sc:read-x", "status": "CAPTURED"})
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"capability": "PASS", "intent": "positive", "reason": "", "capture_sha256": "0" * 64}}, "verdict": "PASS"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "requalify after recapture" not in row["reason"] or [g["kind"] for g in doc["coverage_gaps"]] != ["stale-qualification"]:
            return _fail("a qualification whose capture changed is stale: %s %s" % (row, doc["coverage_gaps"]))
        cap_p.unlink()
        # a qualification with no record for the scenario
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha, "scenarios": {}, "verdict": "INCONCLUSIVE"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        row = next(r for r in load_json(root / "verification" / "parity" / "receipt.json")["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "has no qualification record" not in row["reason"]:
            return _fail("a scenario with no qualification record is INCONCLUSIVE: %s" % row)
        # ... and PASS once qualified
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"capability": "PASS", "intent": "positive", "reason": ""}}, "verdict": "PASS"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        row = next(r for r in load_json(root / "verification" / "parity" / "receipt.json")["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "PASS":
            return _fail("a qualified, passed scenario passes its entry point: %s" % row)
        # a hand-authored corpus without a qualification file keeps today's behaviour
        (root / QUALIFICATION).unlink()
        signed = json.loads(json.dumps(corpus))
        signed.pop("derived_from")
        signed["approved_by"] = "operator:test"
        write_canonical(root / CORPUS_P, signed)
        signed_sha = corpus_digest(load_json(root / CORPUS_P))
        write_canonical(root / "verification" / "parity" / "scenarios" / (scenario_slug("sc:read-x") + ".json"),
                        {"scenario": "sc:read-x", "entry_point": ep, "receipt_sha256": receipt_digest, "corpus_sha256": signed_sha, "verdict": "PASS", "reason": ""})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        row = next(r for r in load_json(root / "verification" / "parity" / "receipt.json")["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "PASS":
            return _fail("an Operator-authored corpus without qualification keeps its behaviour: %s" % row)
    return 0


_AUTHZ = "org.springframework.security.access.prepost.PreAuthorize"
_ROLES_ALLOWED = "javax.annotation.security.RolesAllowed"


def _authz_fixture(td: Path, name: str, pkg: str, ctrl: str, read: str, write: str,
                   role_a: str, role_b: str) -> tuple[Path, dict[str, str]]:
    """A controller guarded by a type-level policy with one member overriding
    it -- two policies -- recorded the way M1's structure model records one."""
    root = td / name
    fqn = "%s.%s" % (pkg, ctrl)
    types = [{"fqn": fqn,
              "annotations": [{"fqn": _AUTHZ, "values": {"value": "hasRole('%s')" % role_a}}],
              "methods": [{"name": read, "signature": "%s()" % read, "annotations": []},
                          {"name": write, "signature": "%s(int)" % write,
                           "annotations": [{"fqn": _AUTHZ, "values": {"value": "hasRole('%s')" % role_b}}]}]}]
    eps = {"read": "ep:%s#%s():http" % (fqn, read), "write": "ep:%s#%s(int):http" % (fqn, write)}
    write_canonical(root / STRUCTURE, {"types": types})
    write_canonical(root / EVIDENCE_BUNDLE, {"schema": "rhoai3.evidence-bundle/v1", "entry_points": [
        {"id": eps["read"], "kind": "http", "type": fqn, "member": "%s()" % read, "http_method": "GET", "http_path": "/api/x"},
        {"id": eps["write"], "kind": "http", "type": fqn, "member": "%s(int)" % write, "http_method": "DELETE", "http_path": "/api/x/{id}"}]})
    return root, eps


def _authorization_policy_case() -> int:
    """The source's authorization policies, read from the model and keyed by
    what they SAY.

    ADR-014 keeps the enabled mode's authorization semantics, and the
    enabled-mode corpus (allowed identity / anonymous / invalid credentials /
    authenticated without the role) is derived per POLICY. Deriving it needs
    the distinct policies and the entry points each one guards, named from
    M1's model rather than from a specimen's controller text -- so the helper
    is tested on two policies, on the same two under another package, type,
    member and annotation spelling, and on the absence of the model, which is
    a reason and never an empty answer."""
    from _scenarios import source_authorization_policies, source_authorization_policy_map

    with tempfile.TemporaryDirectory(prefix="authz-") as td:
        t = Path(td)
        root, eps = _authz_fixture(t, "one", "a", "OwnerRestController", "getOwners", "deleteOwner",
                                   "ROLE_OWNER_ADMIN", "ROLE_VET_ADMIN")
        policies, why = source_authorization_policy_map(root)
        if why or len(policies) != 2:
            return _fail("a type policy with one member override is two policies: %s %s" % (sorted(policies), why))
        by_ep = {e: row["expression"] for row in policies.values() for e in row["entry_points"]}
        if by_ep != {eps["read"]: "hasRole('ROLE_OWNER_ADMIN')", eps["write"]: "hasRole('ROLE_VET_ADMIN')"}:
            return _fail("each entry point maps to the policy that guards it, the member's own overriding its type's: %s" % by_ep)
        if sorted(source_authorization_policies(root)[0]) != sorted(policies):
            return _fail("the id list and the map must name the same policies")

        # the same two policies under entirely different names
        renamed, reps = _authz_fixture(t, "two", "z.legacy.web", "CustodianEndpoint", "listAll", "removeOne",
                                       "ROLE_OWNER_ADMIN", "ROLE_VET_ADMIN")
        rpolicies, rwhy = source_authorization_policy_map(renamed)
        if rwhy or sorted(rpolicies) != sorted(policies):
            return _fail("a renamed specimen states the same policies: %s vs %s" % (sorted(rpolicies), sorted(policies)))
        rby_ep = {e: row["expression"] for row in rpolicies.values() for e in row["entry_points"]}
        if set(rby_ep) & set(by_ep) or sorted(rby_ep.values()) != sorted(by_ep.values()):
            return _fail("the entry points are the renamed ones and the expressions are the same: %s" % rby_ep)

        # a role SET is a set: two spellings of one policy are one policy
        order = t / "order"
        write_canonical(order / STRUCTURE, {"types": [
            {"fqn": "a.First", "annotations": [{"fqn": _ROLES_ALLOWED, "values": {"value": ["ROLE_A", "ROLE_B"]}}],
             "methods": [{"name": "one", "signature": "one()", "annotations": []}]},
            {"fqn": "a.Second", "annotations": [{"fqn": _ROLES_ALLOWED, "values": {"value": ["ROLE_B", "ROLE_A"]}}],
             "methods": [{"name": "two", "signature": "two()", "annotations": []}]}]})
        write_canonical(order / EVIDENCE_BUNDLE, {"schema": "rhoai3.evidence-bundle/v1", "entry_points": [
            {"id": "ep:a.First#one():http", "kind": "http", "type": "a.First", "member": "one()"},
            {"id": "ep:a.Second#two():http", "kind": "http", "type": "a.Second", "member": "two()"}]})
        opolicies, owhy = source_authorization_policy_map(order)
        if owhy or len(opolicies) != 1 or len(list(opolicies.values())[0]["entry_points"]) != 2:
            return _fail("the same roles in another order are one policy guarding both: %s %s" % (opolicies, owhy))

        # absence is a reason: "no policies" and "not read" must not look alike
        (root / STRUCTURE).unlink()
        gone, gone_why = source_authorization_policy_map(root)
        if gone or "unknown" not in gone_why:
            return _fail("a missing structure model is a reason, not an empty policy set: %r" % gone_why)
        (renamed / EVIDENCE_BUNDLE).unlink()
        gone, gone_why = source_authorization_policy_map(renamed)
        if gone or "unknown" not in gone_why:
            return _fail("a missing evidence bundle is a reason: which entry points the policies guard is unknown: %r" % gone_why)
    return 0


# --------------------------------------------------------------------------
# the enabled security mode (ADR-014)
# --------------------------------------------------------------------------
ENABLED_CORPUS_P = Path("verification") / "scenarios-enabled" / "corpus.json"
ENABLED_RECEIPT_P = Path("verification") / "scenarios-enabled" / "_derive.json"
# what the disabled derivation produced before the enabled mode existed, file
# by file. The enabled corpus is a NEW artifact beside it; a byte of the other
# mode's output moving would mean the modes are not separate after all
DISABLED_OUTPUT_SHA256 = {
    "verification/scenarios/bodies/create-invalid-owners-firstName.json": "d59f3e0e22e15c1776b2df76ea900b5cc4abaa89e9a21938271ba2ef4e98bb23",
    "verification/scenarios/bodies/create-invalid-owners-telephone.json": "e1a3fbb3bf89929d9ea0bc6944b47ded3f844473d1e8fa7892884e141e030037",
    "verification/scenarios/bodies/create-owners.json": "af31ffdcc5159780b66903b1754109c340d18375a3c5bacac8c66f533eea7516",
    "verification/scenarios/bodies/update-owners-1.json": "af31ffdcc5159780b66903b1754109c340d18375a3c5bacac8c66f533eea7516",
    "verification/scenarios/corpus.json": "d8401ac17ba4d37ada324158b033161d604ee5bc6665283e49ea4d53978f5312",
}


class Names:
    """Every name a specimen chooses. Two instances of this class are the
    same source under different names, and the derivation must decide the
    same things about both."""

    def __init__(self, pkg: str, controller: str, read_type: str, roles_type: str, resource: str, var: str,
                 field: str, example: str, create: str, delete: str, other: str, read: str, read_route: str,
                 roles: tuple[str, str, str], role_fields: tuple[str, str, str], user_table: str, role_table: str,
                 user_col: str, role_col: str, who_all: str, who_one: str, cred_all: str, cred_one: str, cred_bad: str,
                 get_one: str, get_gap: str, gap_var: str, unguarded: str) -> None:
        self.pkg, self.controller, self.read_type, self.roles_type = pkg, controller, read_type, roles_type
        self.resource, self.var, self.field, self.example = resource, var, field, example
        self.create, self.delete, self.other, self.read, self.read_route = create, delete, other, read, read_route
        self.roles, self.role_fields = roles, role_fields
        self.user_table, self.role_table, self.user_col, self.role_col = user_table, role_table, user_col, role_col
        self.who_all, self.who_one = who_all, who_one
        self.cred_all, self.cred_one, self.cred_bad = cred_all, cred_one, cred_bad
        # a guarded GET the disabled corpus derives no scenario for (reads are
        # captured outside it), and a second one whose path variable nothing
        # resolves -- the first must be probed, the second must stay a gap
        self.get_one, self.get_gap, self.gap_var = get_one, get_gap, gap_var
        # a GET NO annotation guards: unprobed until the Operator declares
        # what the source's enabled configuration requires of every request
        self.unguarded = unguarded

    @property
    def ctrl_fqn(self) -> str:
        return "%s.%s" % (self.pkg, self.controller)

    @property
    def read_fqn(self) -> str:
        return "%s.%s" % (self.pkg, self.read_type)

    @property
    def user_entity(self) -> str:
        return self.user_table.rstrip("s").capitalize()

    @property
    def role_entity(self) -> str:
        return self.role_table.rstrip("s").capitalize()

    @property
    def route(self) -> str:
        return "/api/%s" % self.resource

    def every(self) -> list[str]:
        """The strings a comparison must erase, longest first."""
        return [self.ctrl_fqn, self.read_fqn, "%s.%s" % (self.pkg, self.roles_type), self.pkg, self.controller,
                self.read_type, self.roles_type, self.resource, self.var, self.field, self.example, self.create,
                self.delete, self.other, self.read, self.read_route, self.user_table, self.role_table, self.user_col,
                self.role_col, self.who_all, self.who_one, self.cred_all, self.cred_one, self.cred_bad,
                self.read_route.strip("/"), self.user_entity, self.role_entity, self.get_one, self.get_gap,
                self.gap_var, self.unguarded, *self.roles, *self.role_fields]


PLAIN = Names(pkg="a.rest", controller="OwnerRestController", read_type="RootRestController", roles_type="Roles",
              resource="owners", var="ownerId", field="lastName", example="Franklin", create="addOwner",
              delete="deleteOwner", other="statusOfOwner", read="redirectToDocs", read_route="/docs",
              roles=("ROLE_OWNER_ADMIN", "ROLE_VET_ADMIN", "ROLE_ADMIN"),
              role_fields=("OWNER_ADMIN", "VET_ADMIN", "ADMIN"),
              user_table="users", role_table="roles", user_col="username", role_col="role",
              who_all="admin", who_one="helper", cred_all="PARITY_ADMIN", cred_one="PARITY_HELPER", cred_bad="PARITY_WRONG",
              get_one="getOwner", get_gap="getOwnerVisits", gap_var="visitId", unguarded="listOwners")

RENAMED = Names(pkg="z.legacy.web", controller="CustodianEndpoint", read_type="LandingEndpoint", roles_type="Grants",
                resource="widgets", var="widgetId", field="label", example="Zeta", create="registerWidget",
                delete="removeWidget", other="pingWidget", read="landing", read_route="/home",
                roles=("GRANT_KEEPER", "GRANT_WATCHER", "GRANT_BOSS"),
                role_fields=("KEEPER", "WATCHER", "BOSS"),
                user_table="principals", role_table="grants", user_col="login", role_col="grant_name",
                who_all="keeper", who_one="reader", cred_all="FIXTURE_KEEPER", cred_one="FIXTURE_READER", cred_bad="FIXTURE_BAD",
                get_one="fetchWidget", get_gap="fetchWidgetSlots", gap_var="slotId", unguarded="allWidgets")

_PRE_AUTHORIZE = "org.springframework.security.access.prepost.PreAuthorize"


def _authz_api_docs(n: Names) -> str:
    fields, entity = "%sFields" % n.controller, "%sEntity" % n.controller
    return (
        "openapi: 3.0.1\n"
        "info:\n  title: fixture\n  version: '1.0'\n"
        "paths:\n"
        "  %s:\n" % n.route +
        "    post:\n      operationId: %s\n      requestBody:\n        content:\n          application/json:\n" % n.create +
        "            schema:\n              $ref: '#/components/schemas/%s'\n        required: true\n" % fields +
        "      responses:\n        201:\n          description: created\n"
        "    get:\n      operationId: list%s\n      responses:\n        '200':\n          description: ok\n" % n.controller +
        "          content:\n            application/json:\n              schema:\n                type: array\n"
        "                items:\n                  $ref: '#/components/schemas/%s'\n" % entity +
        "  %s/{%s}:\n" % (n.route, n.var) +
        "    parameters:\n      - name: %s\n        in: path\n        required: true\n        schema:\n          type: integer\n        example: 1\n" % n.var +
        "    delete:\n      operationId: %s\n      responses:\n        '204':\n          description: deleted\n" % n.delete +
        "components:\n  schemas:\n"
        "    %s:\n      type: object\n      properties:\n" % fields +
        "        %s:\n          type: string\n          minLength: 1\n          pattern: '^[a-zA-Z]*$'\n          example: %s\n" % (n.field, n.example) +
        "      required:\n        - %s\n" % n.field +
        "    %s:\n      allOf:\n        - $ref: '#/components/schemas/%s'\n" % (entity, fields) +
        "        - type: object\n          properties:\n            id:\n              type: integer\n              readOnly: true\n              example: 1\n"
    )


def _authz_security(n: Names, *, identities: list[str] | None = None, invalid: bool = True) -> dict[str, Any]:
    """A ``decisions.yaml`` security section for this specimen's own names.

    The Operator's declaration, in the file an ADR backs: the source's switch
    by KEY, and each seeded identity by the NAME of the variable holding its
    credential. No credential is in it, and the harness reads no account."""
    who = [n.who_all, n.who_one] if identities is None else identities
    refs = {n.who_all: n.cred_all, n.who_one: n.cred_one}
    sec: dict[str, Any] = {
        "adr": "ADR-003",
        "switch": {"key": "%s.security.enable" % n.pkg, "disabled_value": "false", "enabled_value": "true"},
        "identities": [{"name": w, "credential_ref": refs[w]} for w in who],
    }
    if invalid:
        sec["invalid_credential_ref"] = n.cred_bad
    return sec


def _security_yaml(sec: dict[str, Any]) -> str:
    """The security block, with every scalar quoted.

    The switch's settings are STRINGS the source reads off a property -- a
    specimen whose off setting is spelled ``false`` must not reach the loader
    as a boolean, which is what an unquoted scalar becomes on the way back."""
    lines = ["security:", "  adr: %s" % json.dumps(sec["adr"]), "  switch:"]
    lines += ["    %s: %s" % (k, json.dumps(str(v))) for k, v in sorted(sec["switch"].items())]
    lines.append("  identities:%s" % ("" if sec["identities"] else " []"))
    for row in sec["identities"]:
        lines.append("    - name: %s" % json.dumps(row["name"]))
        lines.append("      credential_ref: %s" % json.dumps(row["credential_ref"]))
        if row.get("roles"):
            lines.append("      roles:")
            lines += ["        - %s" % json.dumps(r) for r in row["roles"]]
    if sec.get("invalid_credential_ref") is not None:
        lines.append("  invalid_credential_ref: %s" % json.dumps(str(sec["invalid_credential_ref"])))
    if sec.get("request_policy"):
        lines.append("  request_policy: %s" % json.dumps(str(sec["request_policy"])))
    if sec.get("fixtures"):
        lines.append("  fixtures:")
    for fx in (sec.get("fixtures") or []):
        lines.append("    - name: %s" % json.dumps(fx["name"]))
        lines.append("      scenarios: %s" % json.dumps(fx["scenarios"]))
        lines.append("      dataset_config_key: %s" % json.dumps(fx["dataset_config_key"]))
        if fx.get("intent"):
            lines.append("      intent: %s" % json.dumps(fx["intent"]))
        lines.append("      statements:")
        lines += ["        - %s" % json.dumps(s) for s in fx["statements"]]
    return "\n".join(lines) + "\n"


def _write_decisions(root: Path, security: dict[str, Any] | None) -> None:
    import shutil
    # the loader validates against the schemas that ship with the workspace,
    # so the fixture carries them the way a real destination does
    shutil.copytree(HERE.parents[3] / "planning", root / ".hermes" / "planning", dirs_exist_ok=True)
    text = specimens.decisions_yaml(specimens.full_decisions())
    if security is not None:
        text += _security_yaml(security)
    (root / "decisions.yaml").write_text(text, encoding="utf-8")


_COMPONENT = "org.springframework.stereotype.Component"


def _authz_constant_fields(n: Names, constants: str) -> list[dict[str, Any]]:
    """The constants type's field rows as the sealed model carries them: with
    their values, or -- for a model sealed before the extractor recorded
    initializers -- with the field's name and type and nothing else."""
    rows: list[dict[str, Any]] = [{"name": field, "type": "java.lang.String"} for field in n.role_fields]
    if constants == "sealed":
        rows[0]["constant"] = n.roles[0]
        rows[1]["constant"] = n.roles[1]
        rows[2]["value"] = '"%s"' % n.roles[2]
    return rows


def _roles_java(copy: Path, n: Names) -> None:
    """The constants type as the frozen source declares it: a component whose
    final String fields carry the role names.

    A structure model sealed before the extractor recorded field initializers
    has the fields and not the values, and this tree is the only thing left
    that can answer (destination v9, 2026-09-15)."""
    d = copy / "src" / "main" / "java" / Path(*n.pkg.split("."))
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.java" % n.roles_type)).write_text(
        "package %s;\n" % n.pkg
        + "import %s;\n" % _COMPONENT
        + "@Component\npublic class %s {\n" % n.roles_type
        + "".join('    public final String %s = "%s";\n' % (field, role)
                  for field, role in zip(n.role_fields, n.roles))
        + "}\n", encoding="utf-8")


def _authz_root(td: Path, name: str, n: Names, *, holdings: dict[str, list[str]] | None = None,
                unsupported: bool = True, map_identity: bool = True,
                security: dict[str, Any] | None = None, decisions: bool = False,
                constants: str = "sealed", enabled_column: bool = False, cors: bool = False) -> Path:
    """A frozen source with an authorization policy on a write, another on a
    method-less read, a constants type the expressions refer to, and a seeded
    identity store the structure model maps.

    ``holdings`` is what the SEED says each identity holds (default: one
    identity with every role, one with a single role). ``constants`` says
    where the role NAMES are to be found: in the sealed structure model
    (``sealed``), only in the frozen source's own tree (``frozen``: the shape
    of a run sealed before the extractor recorded initializers), or nowhere
    (``none``)."""
    root, copy = td / name / "dest", td / name / "frozen"
    res = copy / "src" / "main" / "resources"
    (res / "db" / "hsqldb").mkdir(parents=True)
    (copy / "pom.xml").write_text("<project/>", encoding="utf-8")
    (res / "api-docs.yml").write_text(_authz_api_docs(n), encoding="utf-8")
    held = holdings if holdings is not None else {n.who_all: list(n.roles), n.who_one: [n.roles[1]]}
    rows = []
    i = 0
    for who in sorted(held):
        for role in held[who]:
            i += 1
            rows.append("INSERT INTO %s VALUES (%d, '%s', '%s');\n" % (n.role_table, i, who, role))
    (res / "db" / "hsqldb" / "populateDB.sql").write_text(
        "INSERT INTO %s VALUES (1, '%s');\n" % (n.resource, n.example)
        + "INSERT INTO %s VALUES (2, 'Other');\n" % n.resource
        + "".join("INSERT INTO %s VALUES ('%s', 'secret'%s);\n" % (n.user_table, who, ", true" if enabled_column else "")
                  for who in sorted(held))
        + "".join(rows), encoding="utf-8")
    (res / "db" / "hsqldb" / "initDB.sql").write_text(
        "CREATE TABLE %s (\n  id INTEGER IDENTITY PRIMARY KEY,\n  %s VARCHAR(30)\n);\n" % (n.resource, _snake_col(n.field))
        + "CREATE TABLE %s (\n  %s VARCHAR(20) PRIMARY KEY,\n  password VARCHAR(20)%s\n);\n"
        % (n.user_table, n.user_col, ",\n  enabled BOOLEAN NOT NULL" if enabled_column else "")
        + "CREATE TABLE %s (\n  id INTEGER IDENTITY PRIMARY KEY,\n  %s VARCHAR(20) NOT NULL,\n  %s VARCHAR(30) NOT NULL,\n"
          "  FOREIGN KEY (%s) REFERENCES %s (%s)\n);\n" % (n.role_table, n.user_col, n.role_col, n.user_col, n.user_table, n.user_col),
        encoding="utf-8")
    write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(copy), "source_digest": "fixture-source-digest"})
    write_pol = {"fqn": _PRE_AUTHORIZE, "values": {"value": "hasRole(@%s.%s)" % (n.roles_type.lower(), n.role_fields[0])}}
    read_pol = {"fqn": _PRE_AUTHORIZE, "values": {"value": "hasAnyRole(@%s.%s, #%s.%s)"
                                                  % (n.roles_type.lower(), n.role_fields[1], n.roles_type.lower(), n.role_fields[2])}}
    methods = [
        {"name": n.create, "signature": "%s(%s.%sDto)" % (n.create, n.pkg, n.controller), "annotations": [dict(write_pol)]},
        {"name": n.delete, "signature": "%s(int)" % n.delete, "annotations": [dict(write_pol)]},
        # the two guarded READS: the disabled corpus derives no scenario for
        # either (an idempotent read is captured outside it), so the enabled
        # mode has to derive its own request -- which it can do for the first
        # (the seed resolved its path variable) and not for the second
        {"name": n.get_one, "signature": "%s(int)" % n.get_one, "annotations": [dict(read_pol)]},
        {"name": n.get_gap, "signature": "%s(int)" % n.get_gap, "annotations": [dict(read_pol)]},
        # the UNANNOTATED read: no policy names it, so the annotations alone
        # say nothing about it -- which is the whole question
        # security.request_policy answers
        {"name": n.unguarded, "signature": "%s()" % n.unguarded, "annotations": []},
    ]
    if unsupported:
        methods.append({"name": n.other, "signature": "%s()" % n.other,
                        "annotations": [{"fqn": _PRE_AUTHORIZE, "values": {"value": "isAuthenticated()"}}]})
    types = [
        {"fqn": n.ctrl_fqn, "methods": methods,
         "annotations": ([{"fqn": "org.springframework.web.bind.annotation.CrossOrigin",
                           "values": {"exposedHeaders": ["errors"]}}] if cors else [])},
        {"fqn": n.read_fqn, "annotations": [],
         "methods": [{"name": n.read, "signature": "%s()" % n.read, "params": [],
                      "annotations": [{"fqn": "org.springframework.web.bind.annotation.RequestMapping", "values": {"value": [n.read_route]}},
                                      dict(read_pol)]}]},
        # the constants the expressions refer to. The type is a COMPONENT --
        # that stereotype is what makes @roles a name for it -- and M1 records
        # each field's value in two spellings, so neither is the only one read
        {"fqn": "%s.%s" % (n.pkg, n.roles_type), "annotations": [{"fqn": _COMPONENT, "values": {}}],
         "fields": _authz_constant_fields(n, constants)},
    ]
    if constants == "frozen":
        _roles_java(copy, n)
    if map_identity:
        # the JPA identity mapping: without it the seeded tables are two
        # tables that happen to carry matching strings
        types += [entity(n.user_entity, n.user_table), entity(n.role_entity, n.role_table)]
    write_canonical(root / STRUCTURE, {"types": types})
    write_canonical(root / EVIDENCE_BUNDLE, {"schema": "rhoai3.evidence-bundle/v1", "entry_points": [
        {"id": "ep:%s#%s:http" % (n.ctrl_fqn, methods[0]["signature"]), "kind": "http", "type": n.ctrl_fqn,
         "member": methods[0]["signature"], "http_method": "POST", "http_path": n.route},
        {"id": "ep:%s#%s:http" % (n.ctrl_fqn, methods[1]["signature"]), "kind": "http", "type": n.ctrl_fqn,
         "member": methods[1]["signature"], "http_method": "DELETE", "http_path": "%s/{%s}" % (n.route, n.var)},
        {"id": "ep:%s#%s():http" % (n.read_fqn, n.read), "kind": "http", "type": n.read_fqn, "member": "%s()" % n.read,
         "http_method": "", "http_path": n.read_route},
        {"id": "ep:%s#%s:http" % (n.ctrl_fqn, methods[2]["signature"]), "kind": "http", "type": n.ctrl_fqn,
         "member": methods[2]["signature"], "http_method": "GET", "http_path": "%s/{%s}" % (n.route, n.var)},
        {"id": "ep:%s#%s:http" % (n.ctrl_fqn, methods[3]["signature"]), "kind": "http", "type": n.ctrl_fqn,
         "member": methods[3]["signature"], "http_method": "GET", "http_path": "%s/{%s}" % (n.route, n.gap_var)},
        # the unannotated route the pilot specimen's root redirect is: no
        # policy names it, and its concrete URL is the root path itself
        {"id": "ep:%s#%s:http" % (n.ctrl_fqn, methods[4]["signature"]), "kind": "http", "type": n.ctrl_fqn,
         "member": methods[4]["signature"], "http_method": "GET", "http_path": "/"},
    ]})
    if decisions or security is not None:
        _write_decisions(root, security if security is not None else _authz_security(n))
    return root


def _snake_col(field: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", field).lower()


def _derive_enabled_fixture(root: Path, n: Names, *, identities: list[str] | None = None,
                            roles: list[str] | None = None) -> subprocess.CompletedProcess:
    args: list[str] = []
    for item in (identities if identities is not None else
                 ["%s=%s" % (n.who_all, n.cred_all), "%s=%s" % (n.who_one, n.cred_one), "invalid=%s" % n.cred_bad]):
        args += ["--identity", item]
    for item in (roles or []):
        args += ["--identity-roles", item]
    return _derive(root, "--security-mode", "enabled", *args)


def _rename_map(other: Names, plain: Names) -> list[tuple[str, str]]:
    """Every name of one specimen mapped back to the other's, longest first.

    The comparison runs the renamed corpus through this map: if the
    derivation decided the same things, what comes out is the first corpus,
    character for character. Erasing the names instead would erase the
    harness's own words too (a specimen that calls a column ``role`` shares
    the word with every sentence about roles), and a comparison that erases
    the vocabulary cannot see a decision change."""
    pairs = [(a, b) for a, b in zip(other.every(), plain.every()) if a and b and a != b]
    return sorted(dict.fromkeys(pairs), key=lambda kv: -len(kv[0]))


def _enabled_decisions(root: Path, rename: list[tuple[str, str]] | None = None,
                       corpus_p: Path = ENABLED_CORPUS_P) -> dict[str, Any]:
    """What the enabled derivation DECIDED: the scenarios it derived and the
    gaps it recorded, with ``rename`` applied, policy ids read as the
    expressions they digest and digests erased (two specimens spell the same
    body differently, and its digest is not a decision)."""
    corpus = load_json(root / corpus_p)

    def sub(text: str) -> str:
        for a, b in (rename or []):
            text = text.replace(a, b)
        return text

    policy_names = {str(row["id"]): "<policy %s>" % sub(str(row["expression"]))
                    for row in corpus.get("authorization_policies") or []}

    def norm(value: Any) -> Any:
        text = sub(json.dumps(value, sort_keys=True))
        for pid, label in policy_names.items():
            text = text.replace(pid, label)
        return json.loads(re.sub(r"\b[0-9a-f]{12,64}\b", "<sha>", text))

    rows = []
    for sc in corpus["scenarios"]:
        rows.append(norm({
            "id": sc["id"], "kind": sc["derived_from"]["kind"], "method": sc["method"], "path": sc["path"],
            "identity": sc["identity"], "effects_identity": sc.get("effects_identity"), "reset_before": sc["reset_before"],
            "effects": [e["id"] for e in sc["effects"]],
            "body": "present" if sc.get("body_file") else "absent",
            "asserted_headers": sc.get("asserted_headers"),
            "qualify": sc["qualify"], "evidence": sc["derived_from"]["evidence"], "why": sc["why"],
        }))
    # sorted by the RENAMED names: which identity sorts first is a fact about
    # the names, not a decision about the source
    rows.sort(key=lambda r: str(r["id"]))
    identities = sorted(norm(corpus["identities"]), key=lambda i: str(i["name"]))
    return {"scenarios": rows, "gaps": sorted(norm(corpus["gaps"])), "identities": identities,
            "policies": sorted(policy_names.values())}


def _enabled_mode_case() -> int:
    """ADR-014's four probes per policy, over a request the disabled corpus
    already states.

    The enabled mode is a different behaviour of the same source: the request
    must be the SAME one, or a difference in the answer is not the security
    switch. So nothing is derived a second time -- the disabled corpus's
    scenario is reused by id and body digest, and only the identity changes.
    What the Operator did not declare is not invented: the identity that lacks
    the role is the blocker ADR-014 names, and an expression this grammar
    cannot read derives nothing at all."""
    with tempfile.TemporaryDirectory(prefix="derive-enabled-") as td:
        n = PLAIN
        root = _authz_root(Path(td), "one", n)
        base = _derive(root)
        if base.returncode != 0:
            return _fail("the disabled corpus derives first: rc=%s %s" % (base.returncode, base.stderr))
        base_corpus = load_json(root / CORPUS_P)
        base_sha = corpus_digest(base_corpus)
        p = _derive_enabled_fixture(root, n)
        if p.returncode != 0 or "enabled-mode scenario" not in p.stdout:
            return _fail("the enabled corpus derives: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        if not (root / ENABLED_CORPUS_P).is_file() or corpus_digest(load_json(root / CORPUS_P)) != base_sha:
            return _fail("the enabled corpus is a separate artifact and the disabled one is untouched")
        corpus = load_json(root / ENABLED_CORPUS_P)
        ids = [str(s["id"]) for s in corpus["scenarios"]]
        want = sorted("sc:auth-%s-%s" % (kind, slug)
                      for slug in ("create-owners", "delete-owners-1") for kind in ("allowed", "anonymous", "invalid", "norole"))
        want += sorted("sc:auth-%s-%s" % (kind, slug)
                       for slug in ("read-docs", "read-api-%s-1" % n.resource) for kind in ("allowed", "anonymous", "invalid"))
        if ids != sorted(want):
            return _fail("four probes per policy and entry point, and no norole where nobody lacks the role: %s" % ids)
        sc = {str(s["id"]): s for s in corpus["scenarios"]}
        # a guarded READ the disabled corpus states nothing about: its request
        # is derived here, in the shape a read has, from the entry point's own
        # method and route and the path variable that corpus already resolved
        read = sc["sc:auth-allowed-read-api-%s-1" % n.resource]
        if (read["method"], read["path"], read["headers"], read["body_absent"], read["effects"], read["reset_before"],
                read["base_source"], read["base_scenario"], read["base_route"], read["qualify"]) != (
                "GET", "%s/1" % n.route, {}, True, [], False, "derived-read", "", "%s/{%s}" % (n.route, n.var),
                {"intent": "positive", "usable_first_response": True}):
            return _fail("a guarded read gets a derived base: GET, no body, no effect, no reset, usable first response: %s" % read)
        ev = read["derived_from"]["evidence"]
        if (not any(e.startswith("bundle:ep:") and "GET %s/{%s}" % (n.route, n.var) in e for e in ev)
                or not any(e.startswith("corpus:") and "path variable {%s} = 1" % n.var in e for e in ev)
                or any(e.startswith("corpus:sc:") for e in ev)):
            return _fail("the derived read names the entry point it came from and the path value it took, and cites no scenario: %s" % ev)
        if sc["sc:auth-anonymous-read-api-%s-1" % n.resource]["qualify"] != {"intent": "negative", "expect_status_class": "4xx"}:
            return _fail("a refused read expects a 4xx and holds nothing still: %s" % sc["sc:auth-anonymous-read-api-%s-1" % n.resource]["qualify"])
        # ... and the read whose path variable nothing resolves stays the gap
        # it was: a concrete URL is never invented to reach a probe
        if not any(g.startswith("auth-base ") and "{%s}" % n.gap_var in g for g in corpus["gaps"]):
            return _fail("an unresolvable route keeps the auth-base gap: %s" % corpus["gaps"])
        if any("%s-1" % n.gap_var in str(s["path"]) or "{" in str(s["path"]) for s in corpus["scenarios"]):
            return _fail("no scenario carries a route pattern or an invented path value")
        # the request is the base scenario's, to the byte
        create = base_corpus["scenarios"][[str(s["id"]) for s in base_corpus["scenarios"]].index("sc:create-owners")]
        for kind in ("allowed", "anonymous", "invalid", "norole"):
            probe = sc["sc:auth-%s-create-owners" % kind]
            if (probe["method"], probe["path"], probe["headers"], probe.get("body_file"), probe["effects"], probe["reset_before"]) != (
                    create["method"], create["path"], create["headers"], create.get("body_file"), create["effects"], create["reset_before"]):
                return _fail("%s reuses the base request unchanged: %s" % (kind, probe))
            if probe["base_scenario"] != "sc:create-owners" or probe["base_body_sha256"] != sha256_file(root / create["body_file"]):
                return _fail("the probe is bound to the base scenario by id and body digest: %s" % probe)
        # who each probe runs as, and what it expects
        if (sc["sc:auth-allowed-create-owners"]["identity"] != {"kind": "basic", "credential_ref": n.cred_all}
                or sc["sc:auth-norole-create-owners"]["identity"] != {"kind": "basic", "credential_ref": n.cred_one}
                or sc["sc:auth-anonymous-create-owners"]["identity"] != {"kind": "none"}
                or sc["sc:auth-invalid-create-owners"]["identity"] != {"kind": "basic", "credential_ref": n.cred_bad}):
            return _fail("the allowed identity holds the role, the norole one does not, anonymous carries nothing and invalid carries the "
                         "reference declared invalid: %s" % {k: v["identity"] for k, v in sc.items()})
        if sc["sc:auth-allowed-read-docs"]["identity"]["credential_ref"] != n.cred_one:
            return _fail("the least-privileged identity the policy accepts is the one that proves it: %s" % sc["sc:auth-allowed-read-docs"]["identity"])
        if sc["sc:auth-allowed-create-owners"]["qualify"] != {
                "intent": "positive", "usable_first_response": True, "after_contains_body": True,
                "creates_one_entity": True, "identity_field": "id"}:
            return _fail("the allowed probe expects no status -- the source's own answer is recorded -- and keeps the base's effect "
                         "assertions: %s" % sc["sc:auth-allowed-create-owners"]["qualify"])
        if sc["sc:auth-allowed-delete-owners-1"]["qualify"] != {
                "intent": "positive", "usable_first_response": True,
                "after_effect_status": {"eff:owners-1-after-delete": 404}}:
            return _fail("the allowed delete keeps the base's after-effect assertion: %s" % sc["sc:auth-allowed-delete-owners-1"]["qualify"])
        for kind in ("anonymous", "invalid", "norole"):
            if sc["sc:auth-%s-create-owners" % kind]["qualify"] != {
                    "intent": "negative", "expect_status_class": "4xx", "after_equals_before": True}:
                return _fail("a refused write is any 4xx with the base's read-backs unchanged: %s" % sc["sc:auth-%s-create-owners" % kind]["qualify"])
        if sc["sc:auth-anonymous-read-docs"]["qualify"] != {"intent": "negative", "expect_status_class": "4xx"}:
            return _fail("a refused read has no after-effects to hold still: %s" % sc["sc:auth-anonymous-read-docs"]["qualify"])
        # the challenge is asserted where a challenge is what the source sends
        if ([k for k in sorted(sc) if sc[k].get("asserted_headers")]
                != sorted("sc:auth-%s-%s" % (kind, slug) for kind in ("anonymous", "invalid")
                          for slug in ("create-owners", "delete-owners-1", "read-docs", "read-api-%s-1" % n.resource))
                or sc["sc:auth-anonymous-read-docs"]["asserted_headers"] != ["WWW-Authenticate"]):
            return _fail("the unauthenticated probes assert the challenge header and the others do not: %s"
                         % {k: v.get("asserted_headers") for k, v in sc.items()})
        # what every scenario STATES about where it came from
        ev = sc["sc:auth-norole-delete-owners-1"]["derived_from"]["evidence"]
        policy = sc["sc:auth-norole-delete-owners-1"]["authorization_policy"]
        if not (any(e.startswith("policy:%s @PreAuthorize(hasRole(@roles.OWNER_ADMIN))" % policy) for e in ev)
                and "policy:%s accepts %s" % (policy, n.roles[0]) in ev
                and any(e.startswith("identity:%s holds %s, credential_ref %s" % (n.who_one, n.roles[1], n.cred_one)) for e in ev)
                and any(e.startswith("corpus:sc:delete-owners-1 reused") for e in ev)):
            return _fail("every scenario names the policy, its expression, what the identity holds and the credential REFERENCE: %s" % ev)
        blob = json.dumps(corpus) + json.dumps(load_json(root / ENABLED_RECEIPT_P))
        if "secret" in blob or "Basic " in blob or "Authorization" in blob:
            return _fail("a credential (or a header built from one) reached the evidence")
        # the gaps: an unreadable expression, and ADR-014's blocker
        gaps = corpus["gaps"]
        read_policy = sc["sc:auth-allowed-read-docs"]["authorization_policy"]
        if not any(g.startswith("auth-policy isAuthenticated(): not in the supported grammar") for g in gaps):
            return _fail("an expression outside the grammar is a typed gap and no scenario: %s" % gaps)
        if "auth-norole %s: no declared identity lacks %s, %s; the seed provides none" % (read_policy, n.roles[2], n.roles[1]) not in gaps:
            return _fail("no identity lacking the role is the blocker ADR-014 names, never an invented account: %s" % gaps)
        # whose view the denied-write read-backs are: the identity the policy
        # ACCEPTS, not the caller it refused. The refused caller's own probes
        # answer 401, and a 401 says nothing about what the write did (v9,
        # 2026-09-14: 15 negative scenarios INCONCLUSIVE on after_equals_before)
        for kind in ("anonymous", "invalid", "norole"):
            probe = sc["sc:auth-%s-create-owners" % kind]
            if probe.get("effects_identity") != {"kind": "basic", "credential_ref": n.cred_all}:
                return _fail("a refused write reads its state back as the identity the policy accepts: %s"
                             % probe.get("effects_identity"))
            if not any(e.startswith("effects-identity:%s holds " % n.who_all) and "credential_ref %s" % n.cred_all in e
                       and "read-backs are taken as this identity" in e for e in probe["derived_from"]["evidence"]):
                return _fail("the scenario says the read-backs are taken as that identity, and names it by reference: %s"
                             % probe["derived_from"]["evidence"])
        if sc["sc:auth-allowed-create-owners"].get("effects_identity") is not None:
            return _fail("the allowed probe is already the accepted identity and names no second one")
        if sc["sc:auth-anonymous-read-docs"].get("effects_identity") is not None:
            return _fail("a probe that declares no effect names no identity to take them as")
        if any(g.startswith("auth-effects") for g in gaps):
            return _fail("with a declared identity the policy accepts, a refused write's state IS observable: %s" % gaps)
        # the receipt binds the mode, the identities and the corpus it reused
        receipt = load_json(root / ENABLED_RECEIPT_P)
        if (receipt["security_mode"] != "enabled" or receipt["base_corpus"] != {"path": CORPUS_P.as_posix(), "sha256": base_sha}
                or receipt["invalid_credential_ref"] != n.cred_bad
                or [i["credential_ref"] for i in receipt["identities"]] != [n.cred_all, n.cred_one]
                or sorted(receipt["requests"]) != sorted(ids)):
            return _fail("the receipt records the mode, the identities by reference and the base corpus it reused: %s" % receipt)
        if corpus.get("security_mode") != "enabled":
            return _fail("the corpus says which mode it is for")
        try:
            loaded = load_corpus(root, "enabled")
        except CorpusError as exc:
            return _fail("the loader accepts the enabled corpus it derived: %s" % exc)
        if len(loaded["scenarios"]) != len(ids):
            return _fail("the loader reads every derived scenario")
        # and refuses to read it as the other mode's
        (root / CORPUS_P).write_bytes((root / ENABLED_CORPUS_P).read_bytes())
        try:
            load_corpus(root)
            return _fail("a corpus of another mode must not load as this one")
        except CorpusError as exc:
            if "security_mode" not in str(exc):
                return _fail("the refusal names the mode: %s" % exc)
    return 0


def _enabled_constants_case() -> int:
    """Where a role NAME comes from when the expression carries only a
    reference.

    Measured on destination v9 (2026-09-15): the frozen source spells its
    roles in a ``@Component`` constants type and every ``@PreAuthorize`` says
    ``hasRole(@roles.VET_ADMIN)``. The sealed structure model recorded the
    type and its fields with name and type only, so the enabled derivation
    produced 0 scenarios and 4 ``not in the supported grammar`` gaps. The
    extractor now records the initializer; a model sealed before it did is
    answered from the frozen tree itself, through the dest-model extractor,
    and the receipt says so. With neither, the typed gap is exactly what it
    was -- an unreadable expression derives nothing."""
    with tempfile.TemporaryDirectory(prefix="derive-constants-") as td:
        n = PLAIN
        ids: dict[str, list[str]] = {}
        for where in ("sealed", "frozen"):
            root = _authz_root(Path(td), where, n, constants=where)
            if _derive(root).returncode != 0:
                return _fail("%s: the disabled corpus derives first" % where)
            p = _derive_enabled_fixture(root, n)
            if p.returncode != 0:
                return _fail("%s: the enabled corpus derives: %s%s" % (where, p.stdout, p.stderr))
            corpus = load_json(root / ENABLED_CORPUS_P)
            receipt = load_json(root / ENABLED_RECEIPT_P)
            ids[where] = [str(s["id"]) for s in corpus["scenarios"]]
            if any(g.startswith("auth-policy hasRole") or g.startswith("auth-policy hasAnyRole") for g in corpus["gaps"]):
                return _fail("%s: a resolvable constant leaves no grammar gap: %s" % (where, corpus["gaps"]))
            if [row["roles"] for row in corpus["authorization_policies"] if row["expression"].startswith("hasRole")] != [[n.roles[0]]]:
                return _fail("%s: the policy accepts the role the constant names: %s" % (where, corpus["authorization_policies"]))
            label = "sealed structure" if where == "sealed" else "frozen-source model"
            want = ('structure:%s @Component → bean %s; %s.%s = "%s" (constant from %s)'
                    % (n.roles_type, n.roles_type.lower(), n.roles_type, n.role_fields[0], n.roles[0], label))
            for sc in corpus["scenarios"]:
                if sc["id"].endswith("-create-%s" % n.resource) and want not in sc["derived_from"]["evidence"]:
                    return _fail("%s: every scenario says how the role name was resolved: %s" % (where, sc["derived_from"]["evidence"]))
            record = (receipt.get("inputs") or {}).get("constants")
            if where == "sealed":
                # nothing else was read: the sealed model answered
                if record is not None:
                    return _fail("a sealed model that carries the constants is not supplemented: %s" % record)
                continue
            references = sorted("@%s.%s" % (n.roles_type.lower(), f) for f in n.role_fields[:2]) + [
                "#%s.%s" % (n.roles_type.lower(), n.role_fields[2])]
            if (not record or record.get("tool") != "jdk-dest-model" or record.get("status") != "ok"
                    or record.get("source_root") != "src/main/java" or record.get("resolution") != "partial"
                    or len(str(record.get("source_digest") or "")) != 64 or len(str(record.get("model_sha256") or "")) != 64
                    or sorted(record.get("resolved") or []) != sorted(references)):
                return _fail("the receipt records the run that resolved them: %s" % record)
        if ids["sealed"] != ids["frozen"]:
            return _fail("where the constant was read makes no difference to what is derived: %s vs %s" % (ids["frozen"], ids["sealed"]))

        # (c) neither model carries it: the typed gap, unchanged
        root = _authz_root(Path(td), "unresolved", n, constants="none")
        _derive(root)
        p = _derive_enabled_fixture(root, n)
        if p.returncode != 0:
            return _fail("an unreadable expression is a gap, not a refusal: %s%s" % (p.stdout, p.stderr))
        corpus = load_json(root / ENABLED_CORPUS_P)
        want = ("auth-policy hasRole(@%s.%s): not in the supported grammar (the constant @%s.%s resolves to no string field "
                "of a type the structure model records)" % (n.roles_type.lower(), n.role_fields[0],
                                                            n.roles_type.lower(), n.role_fields[0]))
        if not any(g.startswith(want) for g in corpus["gaps"]):
            return _fail("an unresolvable constant is the typed gap it was: %s" % corpus["gaps"])
        if corpus["scenarios"]:
            return _fail("an expression nobody read derives nothing: %s" % [s["id"] for s in corpus["scenarios"]])
        if not any(g.startswith("auth-constants: the frozen source's own model could not be produced") for g in corpus["gaps"]):
            return _fail("the attempt to read the frozen source is recorded when it cannot be made: %s" % corpus["gaps"])
    return 0


def _enabled_rename_case() -> int:
    """The same source under other names decides the same things: packages,
    types, members, routes, role names, constant fields, identity tables,
    seeded identities and credential references all differ, and mapping the
    names back gives the same corpus."""
    with tempfile.TemporaryDirectory(prefix="derive-enabled-rename-") as td:
        # under both readings of the constants: the value M1 sealed, and the
        # value read back out of the frozen tree for a model that predates it
        for constants in ("sealed", "frozen"):
            out = []
            for name, n, rename in (("plain", PLAIN, None), ("renamed", RENAMED, _rename_map(RENAMED, PLAIN))):
                root = _authz_root(Path(td), "%s-%s" % (name, constants), n, constants=constants)
                if _derive(root).returncode != 0:
                    return _fail("%s: the disabled corpus derives" % name)
                p = _derive_enabled_fixture(root, n)
                if p.returncode != 0:
                    return _fail("%s: the enabled corpus derives: %s" % (name, p.stderr))
                out.append(_enabled_decisions(root, rename))
            if out[0] != out[1]:
                first = json.dumps(out[0], indent=1, sort_keys=True).splitlines()
                second = json.dumps(out[1], indent=1, sort_keys=True).splitlines()
                diff = [(a, b) for a, b in zip(first, second) if a != b][:6]
                return _fail("a renamed specimen decides the same things (constants %s): %s" % (constants, diff))
    return 0


def _enabled_identity_case() -> int:
    """Where the roles come from, and what happens when they are not there.

    The Operator declares which credential reference authenticates as which
    seeded identity; the SEED says what that identity holds wherever the
    structure model maps the identity store, and a declaration the seed
    contradicts is a gap with the evidence used. With no identity store to
    read, the declaration stands on its own; with neither, the identity is
    used for no probe. An undeclared invalid credential derives no
    invalid-credential probe, and no identity at all leaves the anonymous
    probe -- which needs none -- and blockers for the rest."""
    with tempfile.TemporaryDirectory(prefix="derive-enabled-roles-") as td:
        n = PLAIN
        # (a) the seed contradicts the declaration
        root = _authz_root(Path(td), "seeded", n)
        _derive(root)
        p = _derive_enabled_fixture(root, n, roles=["%s=%s" % (n.who_one, n.roles[0])])
        if p.returncode != 0:
            return _fail("a contradicted declaration is a gap, not a refusal: %s" % p.stderr)
        corpus = load_json(root / ENABLED_CORPUS_P)
        if not any(g.startswith("auth-identity %s: the Operator declares %s and the seed gives %s" % (n.who_one, n.roles[0], n.roles[1]))
                   and "the seed is the evidence and is used" in g for g in corpus["gaps"]):
            return _fail("a declaration the seed contradicts is a typed gap: %s" % corpus["gaps"])
        if [i for i in corpus["identities"] if i["name"] == n.who_one][0]["roles"] != [n.roles[1]]:
            return _fail("the seed is what is used: %s" % corpus["identities"])
        # (b) no identity store in the model: the declaration stands alone
        root = _authz_root(Path(td), "unmapped", n, map_identity=False)
        _derive(root)
        p = _derive_enabled_fixture(root, n, roles=["%s=%s,%s,%s" % (n.who_all, *n.roles), "%s=%s" % (n.who_one, n.roles[1])])
        if p.returncode != 0:
            return _fail("declared roles alone still derive: %s" % p.stderr)
        corpus = load_json(root / ENABLED_CORPUS_P)
        if ([i["roles_source"] for i in corpus["identities"]] != ["declared", "declared"]
                or not any("sc:auth-norole-" in str(s["id"]) for s in corpus["scenarios"])):
            return _fail("with no identity store the Operator's declaration is what there is: %s" % corpus["identities"])
        # (c) an identity with no roles from either source is used for nothing
        p = _derive_enabled_fixture(root, n)
        corpus = load_json(root / ENABLED_CORPUS_P)
        if not any(g.startswith("auth-roles %s:" % n.who_all) for g in corpus["gaps"]) or [s for s in corpus["scenarios"] if s["identity"].get("credential_ref") == n.cred_all]:
            return _fail("an identity whose roles nobody knows proves nothing: %s" % corpus["gaps"])
        # (d) no invalid credential, and no identity at all
        root = _authz_root(Path(td), "bare", n)
        _derive(root)
        p = _derive_enabled_fixture(root, n, identities=["%s=%s" % (n.who_all, n.cred_all)])
        corpus = load_json(root / ENABLED_CORPUS_P)
        kinds = sorted({str(s["derived_from"]["kind"]) for s in corpus["scenarios"]})
        if (kinds != ["auth-allowed", "auth-anonymous"]
                or not any(g.startswith("auth-invalid ") for g in corpus["gaps"])
                or not any(g.startswith("auth-norole ") for g in corpus["gaps"])):
            return _fail("an undeclared invalid credential, and one identity that holds every role, are gaps and no probes: %s %s"
                         % (kinds, corpus["gaps"]))
        # ... and with NO identity declared at all -- here through a decided
        # security section that names the switch and nobody, which is the shape
        # a specimen has before its seeded identities are read off the seed
        root = _authz_root(Path(td), "nobody", n, security=_authz_security(n, identities=[], invalid=False))
        _derive(root)
        p = _derive_enabled_fixture(root, n, identities=[])
        if p.returncode != 0:
            return _fail("a decided section that declares nobody still derives what it can: %s%s" % (p.stdout, p.stderr))
        corpus = load_json(root / ENABLED_CORPUS_P)
        kinds = sorted({str(s["derived_from"]["kind"]) for s in corpus["scenarios"]})
        if kinds != ["auth-anonymous"] or not any(g.startswith("auth-allowed ") for g in corpus["gaps"]):
            return _fail("with no identity declared only the anonymous probe is derivable: %s %s" % (kinds, corpus["gaps"]))
        # ... and with nobody to read the state back as, the auth-effects gap
        # is what stands: a refused write's read-backs are the refused
        # caller's own 401s, so no after_equals_before is stated at all --
        # a predicate nothing could settle is not a contract
        writes = [s for s in corpus["scenarios"] if s.get("effects")]
        if not writes:
            return _fail("the fixture must carry a refused write for this control")
        if any(s.get("effects_identity") is not None or "after_equals_before" in s["qualify"] for s in writes):
            return _fail("with no accepted identity nothing reads the state back, and nothing claims it is unchanged: %s"
                         % [(s["id"], s.get("effects_identity"), s["qualify"]) for s in writes])
        if not any(g.startswith("auth-effects ") and "no declared identity holds" in g and "not observable" in g
                   for g in corpus["gaps"]):
            return _fail("the unobservable state of a refused write is the gap ADR-014 asks for: %s" % corpus["gaps"])
        # a malformed declaration is usage, and the disabled mode takes none
        if _derive(root, "--security-mode", "enabled", "--identity", "no-equals-sign").returncode != 2:
            return _fail("NAME=CREDENTIAL_REF is the shape, and anything else is usage")
        if _derive(root, "--identity", "%s=%s" % (n.who_all, n.cred_all)).returncode != 2:
            return _fail("the disabled mode sends no credential and refuses an identity")
    return 0


def _enabled_regression_case() -> int:
    """The other mode's output does not move. The enabled corpus is a new
    artifact beside the disabled one; every byte the disabled derivation wrote
    before the enabled mode existed is still what it writes."""
    with tempfile.TemporaryDirectory(prefix="derive-regression-") as td:
        root = build_root(Path(td))
        p = _derive(root)
        if p.returncode != 0:
            return _fail("the control fixture derives: %s" % p.stderr)
        got = {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
               for f in sorted((root / "verification").rglob("*")) if f.is_file() and f.name != "_derive.json"}
        if got != DISABLED_OUTPUT_SHA256:
            return _fail("the disabled derivation writes exactly what it wrote before the enabled mode existed:\n  now: %s\n  was: %s"
                         % (json.dumps(got, indent=1, sort_keys=True), json.dumps(DISABLED_OUTPUT_SHA256, indent=1, sort_keys=True)))
    return 0


def _authorization_grammar_case() -> int:
    """Which roles a policy accepts, read from its expression and the source's
    own constants -- and the refusal to read one it does not know.

    A constant reference carries no role name: the name is in the structure
    model's field values, and resolving it there is what keeps this
    specimen-agnostic. An expression outside the grammar returns a REASON, so
    the derivation records a gap instead of deriving a probe against a policy
    nobody read."""
    from _scenarios import (SEALED_STRUCTURE, authorization_roles, resolve_role_constant, role_constants_from_model,
                            role_matches, source_role_constants)

    with tempfile.TemporaryDirectory(prefix="authz-grammar-") as td:
        n = PLAIN
        root = _authz_root(Path(td), "one", n)
        constants, why = source_role_constants(root)
        want_fields = dict(zip(n.role_fields, n.roles))
        by_type = (constants.get("by_type") or {}).get(n.roles_type.lower()) or {}
        by_bean = (constants.get("by_bean") or {}).get(n.roles_type[0].lower() + n.roles_type[1:]) or {}
        if why or by_type.get("fields") != want_fields or by_bean.get("fields") != want_fields:
            return _fail("the constants come from the model's own field values (both spellings), indexed by type and by bean "
                         "name: %s %s" % (constants, why))
        if set(by_type.get("sources", {}).values()) != {SEALED_STRUCTURE}:
            return _fail("a sealed model's constants say they came from it: %s" % by_type.get("sources"))
        # what the scenario has to be able to SAY: which type, which
        # stereotype made it a bean, the field, its value and which model
        # carried it
        value, gap, evidence = resolve_role_constant("@%s.%s" % (n.roles_type.lower(), n.role_fields[1]), constants)
        if gap or value != n.roles[1] or evidence != ('structure:%s @Component → bean %s; %s.%s = "%s" (constant from %s)'
                                                      % (n.roles_type, n.roles_type.lower(), n.roles_type, n.role_fields[1],
                                                         n.roles[1], SEALED_STRUCTURE)):
            return _fail("a resolved constant names its type, its stereotype, the bean, the field and where the value came "
                         "from: %r %s" % (evidence, gap))
        # a bean reference is not a type reference: `@roles` is a name a
        # component stereotype gives, and a class that merely lower-cases to
        # it is not a bean
        noncomponent = role_constants_from_model({"types": [
            {"fqn": "%s.%s" % (n.pkg, n.roles_type), "annotations": [],
             "fields": [{"name": n.role_fields[0], "type": "java.lang.String", "constant": n.roles[0]}]}]})
        got, gap = authorization_roles("PreAuthorize", "hasRole(@%s.%s)" % (n.roles_type.lower(), n.role_fields[0]), noncomponent)
        if got or "component-stereotyped" not in gap:
            return _fail("a bean reference to a type no stereotype makes a bean is a gap that says so: %s %s" % (got, gap))
        got, gap = authorization_roles("PreAuthorize", "hasRole(%s.%s)" % (n.roles_type, n.role_fields[0]), noncomponent)
        if gap or got != [n.roles[0]]:
            return _fail("a TYPE reference needs no stereotype: %s %s" % (got, gap))
        # and a stereotype that NAMES the bean replaces the default name
        named = role_constants_from_model({"types": [
            {"fqn": "%s.%s" % (n.pkg, n.roles_type), "annotations": [{"fqn": _COMPONENT, "values": {"value": ["theRoles"]}}],
             "fields": [{"name": n.role_fields[0], "type": "java.lang.String", "constant": n.roles[0]}]}]})
        got, gap = authorization_roles("PreAuthorize", "hasRole(@theRoles.%s)" % n.role_fields[0], named)
        if gap or got != [n.roles[0]]:
            return _fail("the bean name a stereotype states is the one that resolves: %s %s" % (got, gap))
        got, gap = authorization_roles("PreAuthorize", "hasRole(@%s.%s)" % (n.roles_type.lower(), n.role_fields[0]), named)
        if got or "component-stereotyped" not in gap:
            return _fail("a stereotype that names the bean registers no other name: %s %s" % (got, gap))
        cases = [
            ("PreAuthorize", "hasRole('%s')" % n.roles[0], [n.roles[0]]),
            ("PreAuthorize", "hasRole(@%s.%s)" % (n.roles_type.lower(), n.role_fields[0]), [n.roles[0]]),
            ("PreAuthorize", "hasRole(#%s.%s)" % (n.roles_type.lower(), n.role_fields[1]), [n.roles[1]]),
            ("PreAuthorize", "hasAnyRole(@%s.%s, @%s.%s)" % (n.roles_type.lower(), n.role_fields[1], n.roles_type.lower(), n.role_fields[2]),
             sorted([n.roles[1], n.roles[2]])),
            ("RolesAllowed", "%s, %s" % (n.roles[0], n.roles[1]), sorted([n.roles[0], n.roles[1]])),
            ("Secured", n.roles[2], [n.roles[2]]),
        ]
        for annotation, expression, want in cases:
            got, gap = authorization_roles(annotation, expression, constants)
            if gap or got != want:
                return _fail("%s(%s) accepts %s: got %s %s" % (annotation, expression, want, got, gap))
        for expression in ("isAuthenticated()", "permitAll()", "hasAuthority('%s')" % n.roles[0],
                           "hasRole('%s') or hasRole('%s')" % (n.roles[0], n.roles[1]),
                           "@securityMode.disabled() OR hasRole('%s')" % n.roles[0],
                           "hasRole(#lookup.of(1))", "hasRole(@nosuch.%s)" % n.role_fields[0], ""):
            got, gap = authorization_roles("PreAuthorize", expression, constants)
            if got or not gap:
                return _fail("%r is outside the grammar and says why: %s %s" % (expression, got, gap))
        # a platform that prefixes authorities makes the two spellings one role
        if not role_matches("ROLE_X", "X") or not role_matches("X", "ROLE_X") or role_matches("X", "Y"):
            return _fail("ROLE_X and X are the same role; X and Y are not")
    return 0


def _enabled_decided_case() -> int:
    """Who the enabled mode authenticates as comes from decisions.yaml.

    An identity typed at a shell is not a decision anyone can review: it binds
    to no ADR, is not in the tree the run is reproduced from, and nothing
    downstream can say where it came from. ADR-014 puts it in the Operator's
    own file instead -- by REFERENCE -- and the derivation reads it there by
    default. The controls: the decided run derives exactly what the same
    identities on the command line derive, it says which file they came from,
    it carries the specimen's own switch forward for the capture, and a
    workspace whose file declares no security section derives NOTHING and
    records why -- the blocker ADR-014 asks for, not an anonymous corpus
    wearing the enabled mode's name, and not silence."""
    with tempfile.TemporaryDirectory(prefix="derive-decided-") as td:
        n = PLAIN
        # the same fixture twice: identities on the command line, identities in
        # the decided file. Only the provenance may differ.
        typed = _authz_root(Path(td), "typed", n)
        _derive(typed)
        if _derive_enabled_fixture(typed, n).returncode != 0:
            return _fail("the command-line form still derives")
        decided = _authz_root(Path(td), "decided", n, decisions=True)
        _derive(decided)
        p = _derive(decided, "--security-mode", "enabled")
        if p.returncode != 0 or "enabled-mode scenario" not in p.stdout:
            return _fail("--security-mode enabled with no --identity reads the decided identities: rc=%s %s%s"
                         % (p.returncode, p.stdout, p.stderr))
        a, b = load_json(typed / ENABLED_CORPUS_P), load_json(decided / ENABLED_CORPUS_P)
        if [s["id"] for s in a["scenarios"]] != [s["id"] for s in b["scenarios"]] or a["gaps"] != b["gaps"]:
            return _fail("the decided identities derive what the typed ones derive: %s vs %s"
                         % ([s["id"] for s in b["scenarios"]], [s["id"] for s in a["scenarios"]]))
        if (b["identities_from"] != "decisions.yaml" or a["identities_from"] != "--identity"
                or b["invalid_credential_ref"] != n.cred_bad):
            return _fail("each corpus says where its identities came from: %s %s" % (b.get("identities_from"), a.get("identities_from")))
        if b["security_switch"] != {"key": "%s.security.enable" % n.pkg, "disabled_value": "false", "enabled_value": "true"}:
            return _fail("the decided switch travels with the corpus, so the capture starts the source the way it was derived for: %s"
                         % b.get("security_switch"))
        if "secret" in json.dumps(b) or "Basic " in json.dumps(b):
            return _fail("only references travel")
        # explicitly asking for both is a usage error, not a silent precedence
        p = _derive(decided, "--security-mode", "enabled", "--from-decisions", "--identity", "%s=%s" % (n.who_all, n.cred_all))
        if p.returncode != 2 or "--from-decisions" not in p.stderr:
            return _fail("--from-decisions and --identity together must refuse: rc=%s %s" % (p.returncode, p.stderr[-200:]))

        # no security section: nothing is derived, and the receipt says so
        bare = _authz_root(Path(td), "undecided", n, security=None)
        _derive(bare)
        _write_decisions(bare, None)
        p = _derive(bare, "--security-mode", "enabled")
        receipt = load_json(bare / ENABLED_RECEIPT_P)
        if p.returncode != 0 or (bare / ENABLED_CORPUS_P).exists():
            return _fail("an undeclared security section derives no corpus and is not red: rc=%s" % p.returncode)
        if (receipt.get("status") != "idle" or "no security section" not in str(receipt.get("reason"))
                or receipt.get("security_mode") != "enabled"):
            return _fail("the receipt records the blocker ADR-014 asks for: %s" % {k: receipt.get(k) for k in ("status", "reason")})
        # a section declared in a shape the loader refuses is named, not read
        _write_decisions(bare, dict(_authz_security(n), invalid_credential_ref="an-account:its-password"))
        p = _derive(bare, "--security-mode", "enabled")
        receipt = load_json(bare / ENABLED_RECEIPT_P)
        if p.returncode != 0 or receipt.get("status") != "idle" or "invalid_credential_ref" not in str(receipt.get("reason")):
            return _fail("a credential written where its NAME belongs is refused and named: %s" % receipt.get("reason"))
        if "its-password" in json.dumps(receipt):
            return _fail("the refusal names the field, never what it holds")
    return 0


# ---------------------------------------------------------------------------
# what the source's enabled configuration requires of a request no annotation
# names (ADR-014), and a separately recorded variant of the source baseline
# ---------------------------------------------------------------------------
VARIANT = "identity-disabled"
VARIANT_CORPUS_P = Path("verification") / ("scenarios-enabled-%s" % VARIANT) / "corpus.json"
VARIANT_RECEIPT_P = Path("verification") / ("scenarios-enabled-%s" % VARIANT) / "_derive.json"


def _fixture_decl(n: Names) -> dict[str, Any]:
    """The Operator's declaration of one variant of the source baseline: its
    name, the statements it applies after the declared dataset, the class of
    scenario it is recorded for, and the KEY the source reads its dataset
    location from. Every value is the SPECIMEN's -- the statements name its
    own table and column, the key its own framework's property."""
    return {"name": VARIANT, "intent": "refuse", "scenarios": "auth-allowed",
            "dataset_config_key": "%s.sql.init.data-locations" % n.pkg,
            "statements": ["UPDATE %s SET enabled = false WHERE %s = '%s'" % (n.user_table, n.user_col, n.who_all)]}


def _enabled_request_policy_case() -> int:
    """An unannotated route is guarded too, when the source says every
    request must be authenticated.

    ADR-014's enabled mode asks what the source does with each of its
    requests, and the annotations answer for only some of them: the pilot
    specimen configures ``anyRequest().authenticated()``, so its root redirect
    -- which carries no @PreAuthorize at all -- is still refused without an
    identity, and a derivation that walks only the annotations leaves it
    unprobed. Unprobed reads at M4 as "nothing to prove". So the Operator
    declares what the configuration requires, in the one file an ADR backs,
    and the derivation probes every entry point it has a request for: an
    identity the policy accepts, nobody, and the credential declared invalid.
    There is no fourth probe -- no identity authenticates and still fails a
    policy whose whole requirement is authentication -- and an entry point an
    explicit policy already guards keeps that policy, because a role is more
    than a login."""
    with tempfile.TemporaryDirectory(prefix="derive-reqpolicy-") as td:
        n = PLAIN
        declared = _authz_security(n)
        declared["request_policy"] = "authenticated"
        root = _authz_root(Path(td), "declared", n, security=declared)
        if _derive(root).returncode != 0:
            return _fail("the disabled corpus derives first")
        p = _derive(root, "--security-mode", "enabled")
        if p.returncode != 0:
            return _fail("the enabled corpus derives with a declared request policy: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        corpus = load_json(root / ENABLED_CORPUS_P)
        sc = {str(s["id"]): s for s in corpus["scenarios"]}
        # the root path names no segment, so the derived read is sc:read-root
        # -- the id the pilot specimen's own root redirect takes
        slug = "read-root"
        want = ["sc:auth-%s-%s" % (kind, slug) for kind in ("allowed", "anonymous", "invalid")]
        missing = [i for i in want if i not in sc]
        if missing:
            return _fail("the unannotated GET gets the allowed, anonymous and invalid probes: %s missing from %s"
                         % (missing, sorted(sc)))
        if "sc:auth-norole-%s" % slug in sc:
            return _fail("authentication is the whole policy, so there is no identity that authenticates and fails it")
        implicit = sc[want[0]]["authorization_policy"]
        if any(sc[i]["authorization_policy"] != implicit for i in want):
            return _fail("the three probes are of one policy: %s" % [sc[i]["authorization_policy"] for i in want])
        # the request is the read this producer derived, and it says so
        if (sc[want[0]]["method"], sc[want[0]]["path"], sc[want[0]]["base_source"], sc[want[0]]["base_route"]) != (
                "GET", "/", "derived-read", "/"):
            return _fail("the probe is the entry point's own GET of its own route: %s" % sc[want[0]])
        if sc[want[0]]["identity"] != {"kind": "basic", "credential_ref": n.cred_one}:
            return _fail("any declared identity satisfies it, and the least privileged proves it: %s" % sc[want[0]]["identity"])
        if sc[want[1]]["identity"] != {"kind": "none"} or sc[want[2]]["identity"] != {"kind": "basic", "credential_ref": n.cred_bad}:
            return _fail("anonymous carries nothing and invalid carries the reference declared invalid: %s %s"
                         % (sc[want[1]]["identity"], sc[want[2]]["identity"]))
        if sc[want[1]]["qualify"] != {"intent": "negative", "expect_status_class": "4xx"}:
            return _fail("a refused read expects a 4xx: %s" % sc[want[1]]["qualify"])
        # every scenario says the DECLARATION it came from, not an annotation
        for i in want:
            ev = sc[i]["derived_from"]["evidence"]
            if not any("decisions.security.request_policy authenticated → every request" in e for e in ev):
                return _fail("the evidence names the decision and what it covers: %s" % ev)
            if any("@PreAuthorize" in e for e in ev):
                return _fail("a policy nobody annotated must not be reported as an annotation: %s" % ev)
        if corpus.get("request_policy") != "authenticated":
            return _fail("the corpus records what the source's configuration requires: %s" % corpus.get("request_policy"))
        row = [r for r in corpus["authorization_policies"] if r["id"] == implicit]
        if not row or row[0]["declared_by"] != "decisions.security.request_policy" or row[0]["roles"] != []:
            return _fail("the implicit policy names the decision that declared it and accepts no role: %s" % row)
        # the annotated entry points keep the policies they had -- and their
        # fourth probe with them
        if not any(str(s["id"]).startswith("sc:auth-norole-") for s in corpus["scenarios"]):
            return _fail("an entry point an explicit policy guards keeps that policy and its no-role probe")
        for s in corpus["scenarios"]:
            if s["authorization_policy"] == implicit and s["entry_point"] in {
                    e for r in corpus["authorization_policies"] if r["id"] != implicit for e in r["entry_points"]}:
                return _fail("an entry point an explicit policy guards is not also probed by the request policy: %s" % s["id"])

        # ... and with nothing declared, the same tree derives none of them
        plain_root = _authz_root(Path(td), "undeclared", n, security=_authz_security(n))
        _derive(plain_root)
        if _derive(plain_root, "--security-mode", "enabled").returncode != 0:
            return _fail("the control tree derives")
        plain = load_json(plain_root / ENABLED_CORPUS_P)
        if any(str(s["id"]).endswith(slug) for s in plain["scenarios"]):
            return _fail("without the declared request policy the unannotated GET is not probed: %s"
                         % [s["id"] for s in plain["scenarios"]])
        if plain.get("request_policy") or "request_policy" not in str(plain and load_json(plain_root / ENABLED_RECEIPT_P).get("request_policy_note")):
            return _fail("a tree that declares none says so rather than staying silent: %s"
                         % load_json(plain_root / ENABLED_RECEIPT_P).get("request_policy_note"))

        # ... and the same specimen under other names decides the same things
        other = RENAMED
        other_declared = _authz_security(other)
        other_declared["request_policy"] = "authenticated"
        other_root = _authz_root(Path(td), "renamed", other, security=other_declared)
        _derive(other_root)
        if _derive(other_root, "--security-mode", "enabled").returncode != 0:
            return _fail("the renamed specimen derives")
        if _enabled_decisions(other_root, _rename_map(other, n)) != _enabled_decisions(root):
            a, b = _enabled_decisions(other_root, _rename_map(other, n)), _enabled_decisions(root)
            first = [(x, y) for x, y in zip(json.dumps(a, indent=1).splitlines(), json.dumps(b, indent=1).splitlines()) if x != y][:4]
            return _fail("the request policy decides the same things under another naming: %s" % first)
    return 0


def _enabled_variant_case() -> int:
    """A separately recorded variant of the source baseline.

    The seed ENABLES its identities, so no capture taken against the declared
    dataset can show what the source answers once one of them is disabled --
    and editing the dataset every other capture is taken against is not the
    answer. ADR-014's answer is a variant: the declared dataset plus the
    Operator's own statements, derived into its own corpus over the same
    requests, so the only difference between a baseline scenario and its
    variant is the database state. What it expects is what the Operator
    declared -- a refusal here -- and the statements travel verbatim, because
    a run nobody can re-apply them from is not reproducible."""
    with tempfile.TemporaryDirectory(prefix="derive-variant-") as td:
        n = PLAIN
        declared = _authz_security(n)
        declared["fixtures"] = [_fixture_decl(n)]
        root = _authz_root(Path(td), "declared", n, security=declared)
        _derive(root)
        if _derive(root, "--security-mode", "enabled").returncode != 0:
            return _fail("the enabled corpus is what a variant of it varies")
        base = load_json(root / ENABLED_CORPUS_P)
        p = _derive(root, "--security-mode", "enabled", "--fixture-variant", VARIANT)
        if p.returncode != 0 or "fixture variant %s" % VARIANT not in p.stdout:
            return _fail("the variant derives: rc=%s %s%s" % (p.returncode, p.stdout, p.stderr))
        corpus = load_json(root / VARIANT_CORPUS_P)
        allowed = sorted(str(s["id"]) for s in base["scenarios"] if s["derived_from"]["kind"] == "auth-allowed")
        want = sorted("sc:fixture-%s-%s" % (VARIANT, sid.split(":", 1)[-1]) for sid in allowed)
        if sorted(str(s["id"]) for s in corpus["scenarios"]) != want or not want:
            return _fail("one variant scenario per scenario of the declared class: %s vs %s"
                         % (sorted(str(s["id"]) for s in corpus["scenarios"]), want))
        by_id = {str(s["id"]): s for s in base["scenarios"]}
        for s in corpus["scenarios"]:
            src = by_id[s["base_scenario"]]
            if (s["method"], s["path"], s["headers"], s["identity"], s.get("body_file"), s.get("body_absent")) != (
                    src["method"], src["path"], src["headers"], src["identity"], src.get("body_file"), src.get("body_absent")):
                return _fail("the request is the base scenario's, to the byte: %s" % s["id"])
            if s["qualify"] != {"intent": "negative", "expect_status_class": "4xx"}:
                return _fail("a variant the Operator declares a refusal for expects a 4xx: %s %s" % (s["id"], s["qualify"]))
            if s["asserted_headers"] != ["WWW-Authenticate"] or s["effects"] != [] or s.get("effects_identity"):
                return _fail("a refusal asserts the challenge, and with no second identity holding what the refused one "
                             "holds it carries no read-back: %s" % s)
            if s["method"] != "GET" and (
                    "missing effects identity" not in str(s.get("effects_unobservable"))
                    or "credential_ref %s" % n.cred_all not in str(s.get("effects_unobservable"))):
                return _fail("a refused write with nobody to read its state back says so and names the refused identity: %s"
                             % s.get("effects_unobservable"))
            if s["method"] != "GET" and ("REVERT_NOT_COMPUTABLE" not in str(s.get("effects_unobservable"))
                                         or "%s.enabled" % n.user_table not in str(s.get("effects_unobservable"))):
                return _fail("... and why no revert could be computed either (the dataset defines no value of the varied "
                             "column): %s" % s.get("effects_unobservable"))
            if s["method"] == "GET" and "effects_unobservable" in s:
                return _fail("a refused read proves itself by its answer and needs no read-back: %s" % s["id"])
            if s["security_variant"] != VARIANT or s["security_mode"] != "enabled":
                return _fail("every scenario says which state it is of: %s" % s)
            if s["reset_before"] is not True:
                return _fail("a variant scenario is defined by its dataset state and always starts from it: %s" % s["id"])
            ev = s["derived_from"]["evidence"]
            if not any(e == "fixture:%s statement: %s" % (VARIANT, _fixture_decl(n)["statements"][0]) for e in ev):
                return _fail("the statements are recorded verbatim: %s" % ev)
            if not any("dataset_config_key" in str(corpus["fixture"]) and _fixture_decl(n)["dataset_config_key"] in e for e in ev):
                return _fail("the scenario names the key the dataset location is passed through: %s" % ev)
        fixture = corpus["fixture"]
        if (fixture["statements"] != _fixture_decl(n)["statements"] or fixture["intent"] != "refuse"
                or fixture["dataset_config_key"] != _fixture_decl(n)["dataset_config_key"]
                or not fixture["dataset"]["path"].endswith("populateDB.sql") or len(fixture["dataset"]["sha256"]) != 64):
            return _fail("the corpus states the fixture it is of and the declared dataset it is applied after: %s" % fixture)
        if corpus["security_variant"] != VARIANT or corpus["security_mode"] != "enabled":
            return _fail("the corpus says which state it is of: %s" % {k: corpus.get(k) for k in ("security_mode", "security_variant")})
        try:
            loaded = load_corpus(root, "enabled", VARIANT)
        except CorpusError as exc:
            return _fail("the loader accepts the variant corpus it derived: %s" % exc)
        if len(loaded["scenarios"]) != len(want):
            return _fail("the loader reads every variant scenario")
        try:
            load_corpus(root, "enabled")
            probe = load_json(root / ENABLED_CORPUS_P)
        except CorpusError as exc:
            return _fail("the baseline corpus still loads as itself: %s" % exc)
        if probe["scenarios"] == corpus["scenarios"]:
            return _fail("the variant is a separate artifact")
        # a variant nobody declared is never derived
        bad = _derive(root, "--security-mode", "enabled", "--fixture-variant", "no-such-fixture")
        if bad.returncode == 0 or "no security fixture named" not in bad.stderr:
            return _fail("an undeclared variant refuses and names what IS declared: rc=%s %s" % (bad.returncode, bad.stderr))
        # ... and a variant of the mode whose paths carry no suffix is refused
        # before it can write over the baseline's own directory
        clash = _derive(root, "--fixture-variant", VARIANT)
        if clash.returncode != 2 or "variant of a named mode" not in clash.stderr:
            return _fail("a variant of the default mode is a usage error: rc=%s %s" % (clash.returncode, clash.stderr))

        # ... and the same specimen under other names decides the same things
        other = RENAMED
        other_declared = _authz_security(other)
        other_declared["fixtures"] = [_fixture_decl(other)]
        other_root = _authz_root(Path(td), "renamed", other, security=other_declared)
        _derive(other_root)
        _derive(other_root, "--security-mode", "enabled")
        if _derive(other_root, "--security-mode", "enabled", "--fixture-variant", VARIANT).returncode != 0:
            return _fail("the renamed specimen derives its variant")
        rename = _rename_map(other, n)
        if _enabled_decisions(other_root, rename, VARIANT_CORPUS_P) != _enabled_decisions(root, None, VARIANT_CORPUS_P):
            a = _enabled_decisions(other_root, rename, VARIANT_CORPUS_P)
            b = _enabled_decisions(root, None, VARIANT_CORPUS_P)
            first = [(x, y) for x, y in zip(json.dumps(a, indent=1).splitlines(), json.dumps(b, indent=1).splitlines()) if x != y][:4]
            return _fail("the variant decides the same things under another naming: %s" % first)
    return 0


def _load_deriver() -> Any:
    import importlib.util
    spec = importlib.util.spec_from_file_location("derive_source_scenarios_under_test", DERIVE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _variant_effects_rule_case() -> int:
    """The rule itself, on synthetic base scenarios: a refused PUT and a
    refused DELETE carry the base read REQUESTS as state-unchanged read-backs,
    taken as a declared identity that is neither the refused one nor the one
    declared invalid; no such identity leaves the write without read-backs
    and a named reason; a variant with no refusal declared is untouched."""
    mod = _load_deriver()
    fixture = {"name": "acct-off", "intent": "refuse", "scenarios": "auth-allowed", "dataset_config_key": "k",
               "statements": ["UPDATE principals SET active = 0"]}
    dataset = {"path": "db/seed.sql", "sha256": "0" * 64}
    ids = [{"name": "boss", "credential_ref": "REF_BOSS", "roles": ["G_A", "G_B"]},
           {"name": "twin", "credential_ref": "REF_TWIN", "roles": ["G_A", "G_B", "G_C"]},
           {"name": "small", "credential_ref": "REF_SMALL", "roles": ["G_A"]},
           {"name": "bogus", "credential_ref": "REF_BAD", "roles": ["G_A", "G_B"]}]
    reads = [{"id": "eff:thing-9-after-update", "method": "GET", "path": "/api/things/9"},
             {"id": "eff:things-after-update", "method": "GET", "path": "/api/things"}]
    with tempfile.TemporaryDirectory(prefix="variant-rule-") as td:
        root = Path(td)
        for method in ("PUT", "DELETE"):
            base = {"id": "sc:auth-allowed-%s-things-9" % method.lower(), "entry_point": "ep:x", "method": method,
                    "path": "/api/things/9", "headers": {}, "identity": {"kind": "basic", "credential_ref": "REF_BOSS"},
                    "body_absent": True, "reset_before": True, "effects": [dict(e) for e in reads],
                    "security_mode": "enabled", "derived_from": {"kind": "auth-allowed"},
                    "qualify": {"intent": "positive", "after_effect_status": {reads[0]["id"]: 404}}}
            gaps: list[str] = []
            sc = mod._variant_scenario(root, "acct-off", fixture, base, "f" * 64, "c.json", dataset, ids, "REF_BAD", gaps)
            if [(e["id"], e["method"], e["path"], e["role"]) for e in sc["effects"]] != [
                    (e["id"], "GET", e["path"], "unchanged_under_refusal") for e in reads]:
                return _fail("a refused %s carries the base read requests as state-unchanged read-backs: %s" % (method, sc["effects"]))
            if any(set(e) != {"id", "method", "path", "role"} for e in sc["effects"]):
                return _fail("only the read REQUEST travels, never an expectation: %s" % sc["effects"])
            # the refused identity (REF_BOSS) and the invalid one (REF_BAD)
            # are excluded; REF_SMALL lacks G_B; REF_TWIN holds all of it
            if sc.get("effects_identity") != {"kind": "basic", "credential_ref": "REF_TWIN"}:
                return _fail("the read-backs are taken as a declared identity that is neither refused nor invalid and holds "
                             "what the refused one holds: %s" % sc.get("effects_identity"))
            if sc["qualify"] != {"intent": "negative", "expect_status_class": "4xx", "after_equals_before": True,
                                 "db_unchanged": True}:
                return _fail("the contract is a refusal whose database and read-backs are unchanged, and nothing of the "
                             "base's: %s" % sc["qualify"])
            if sc.get("effects_db_scope") != {"tables": [], "why": "no database scope was derived"}:
                return _fail("a scenario given no scope says so: %s" % sc.get("effects_db_scope"))
            if sc["identity"] != base["identity"] or gaps or "effects_unobservable" in sc:
                return _fail("the request is untouched and nothing is missing: %s %s" % (sc["identity"], gaps))
            if not any(e.startswith("effects-identity:twin ") for e in sc["derived_from"]["evidence"]):
                return _fail("the evidence names whose read-backs they are: %s" % sc["derived_from"]["evidence"])
            # nobody else declared -> no read-back, a named reason and a gap
            gaps = []
            lone = mod._variant_scenario(root, "acct-off", fixture, base, "f" * 64, "c.json", dataset,
                                         [ids[0], ids[2], ids[3]], "REF_BAD", gaps)
            why = str(lone.get("effects_unobservable") or "")
            if (lone["effects"] or lone.get("effects_identity") or "after_equals_before" in lone["qualify"]
                    or "missing effects identity" not in why or "credential_ref REF_BOSS" not in why or "G_A, G_B" not in why):
                return _fail("with no identity to read the state as, the write carries no read-back and names what is "
                             "missing: %s %s" % (lone["effects"], why))
            if len(gaps) != 1 or base["id"] not in gaps[0]:
                return _fail("the corpus records the missing identity as a gap: %s" % gaps)
            # no second identity, but a computable revert: REVERT-THEN-READ as
            # the request's own identity, judged against the baseline reads
            plan = {"schema": "rhoai3.variant-revert/v1", "strategy": "revert_then_read", "engine": "postgresql",
                    "rows": [], "statements": ["UPDATE \"principals\" SET \"active\" = 1 WHERE \"login\" = 'boss'"]}
            gaps = []
            rtr = mod._variant_scenario(root, "acct-off", fixture, base, "f" * 64, "c.json", dataset,
                                        [ids[0], ids[2], ids[3]], "REF_BAD", gaps, plan, "")
            if (rtr.get("effects_reader") != {"strategy": "revert_then_read", "name": "boss", "credential_ref": "REF_BOSS"}
                    or rtr.get("effects_identity") != {"kind": "basic", "credential_ref": "REF_BOSS"}
                    or [e["role"] for e in rtr["effects"]] != ["unchanged_under_refusal"] * 2
                    or rtr["qualify"] != {"intent": "negative", "expect_status_class": "4xx", "before_reads_usable": True,
                                          "after_equals_before": True, "db_unchanged": True}
                    or gaps or "effects_unobservable" in rtr):
                return _fail("with no other identity and a computable revert the reads are revert-then-read as the "
                             "request's own identity: %s %s %s" % (rtr.get("effects_reader"), rtr["qualify"], gaps))
            if not any("revert_then_read" in e and plan["statements"][0] in e for e in rtr["derived_from"]["evidence"]):
                return _fail("the evidence names the strategy and the revert it runs: %s" % rtr["derived_from"]["evidence"])
            # ... a declared second identity still wins over the revert
            both = mod._variant_scenario(root, "acct-off", fixture, base, "f" * 64, "c.json", dataset, ids, "REF_BAD", [],
                                         plan, "")
            if (both.get("effects_reader") or {}).get("strategy") != "second_identity":
                return _fail("a specimen that declares a second identity keeps that strategy: %s" % both.get("effects_reader"))
            # ... and with neither, both reasons are named
            gaps = []
            none = mod._variant_scenario(root, "acct-off", fixture, base, "f" * 64, "c.json", dataset,
                                         [ids[0]], "REF_BAD", gaps, None, "REVERT_NOT_COMPUTABLE: 'x' is not an UPDATE")
            why = str(none.get("effects_unobservable") or "")
            if none["effects"] or "missing effects identity" not in why or "REVERT_NOT_COMPUTABLE" not in why or len(gaps) != 1:
                return _fail("with neither strategy the write names both reasons: %s %s" % (why, gaps))
            # a variant that declares no refusal is what it always was
            gaps = []
            plain = mod._variant_scenario(root, "acct-off", dict(fixture, intent=""), base, "f" * 64, "c.json", dataset,
                                          ids, "REF_BAD", gaps)
            if (plain["effects"] or "effects_identity" in plain or "effects_unobservable" in plain or gaps
                    or plain["qualify"] != {"intent": "positive", "usable_first_response": True}):
                return _fail("an allow-intent variant is unaffected: %s" % plain)
        # a refused READ needs no read-back at all
        read = {"id": "sc:auth-allowed-read-things", "entry_point": "ep:y", "method": "GET", "path": "/api/things",
                "headers": {}, "identity": {"kind": "basic", "credential_ref": "REF_BOSS"}, "body_absent": True,
                "reset_before": False, "effects": [], "security_mode": "enabled"}
        sc = mod._variant_scenario(root, "acct-off", fixture, read, "f" * 64, "c.json", dataset, ids, "REF_BAD", [])
        if sc["effects"] or "effects_identity" in sc or "effects_unobservable" in sc:
            return _fail("a refused read is proved by its answer: %s" % sc)
    return 0


def _enabled_variant_effects_case() -> int:
    """End to end: with a second declared identity that holds everything the
    refused one holds, the derived variant's refused writes carry read-backs
    taken as that identity, the loader accepts the corpus, the receipt says
    which writes carry them and under which derivation, a corpus derived under
    the older promise is refused by name -- and a renamed specimen decides
    the same things."""
    with tempfile.TemporaryDirectory(prefix="derive-variant-effects-") as td:
        outcomes = []
        for n, label in ((PLAIN, "plain"), (RENAMED, "renamed")):
            declared = _authz_security(n)
            declared["fixtures"] = [_fixture_decl(n)]
            root = _authz_root(Path(td), label, n, security=declared,
                               holdings={n.who_all: list(n.roles), n.who_one: list(n.roles)})
            _derive(root)
            if _derive(root, "--security-mode", "enabled").returncode != 0:
                return _fail("the enabled corpus derives (%s)" % label)
            base = load_json(root / ENABLED_CORPUS_P)
            p = _derive(root, "--security-mode", "enabled", "--fixture-variant", VARIANT)
            if p.returncode != 0:
                return _fail("the variant derives (%s): %s%s" % (label, p.stdout, p.stderr))
            corpus = load_json(root / VARIANT_CORPUS_P)
            by_id = {str(s["id"]): s for s in base["scenarios"]}
            writes = [s for s in corpus["scenarios"] if s["method"] not in ("GET", "HEAD", "OPTIONS")]
            if {s["method"] for s in writes} != {"POST", "DELETE"}:
                return _fail("the fixture refuses a create and a delete: %s" % sorted(s["id"] for s in writes))
            for s in writes:
                src = by_id[s["base_scenario"]]
                if [e["id"] for e in s["effects"]] != [e["id"] for e in src["effects"]] or not s["effects"]:
                    return _fail("the refused write reads back what its base reads back: %s" % s["id"])
                if {e["role"] for e in s["effects"]} != {"unchanged_under_refusal"}:
                    return _fail("each read-back says what it proves: %s" % s["effects"])
                who = s.get("effects_identity") or {}
                if (who != {"kind": "basic", "credential_ref": n.cred_one} or who == s["identity"]
                        or who.get("credential_ref") == n.cred_bad):
                    return _fail("the read-backs are taken as the OTHER declared identity, never the refused or the invalid "
                                 "one: %s vs %s" % (who, s["identity"]))
                if (s.get("effects_reader") or {}).get("strategy") != "second_identity":
                    return _fail("the reader row records its strategy: %s" % s.get("effects_reader"))
                scope = s.get("effects_db_scope") or {}
                if n.resource not in (scope.get("tables") or []) or not scope.get("rule") or s["qualify"].get("db_unchanged") is not True:
                    return _fail("the no-effect claim is a database claim over a derived, recorded scope: %s %s"
                                 % (scope, s["qualify"]))
                if s["qualify"].get("after_equals_before") is not True or "effects_unobservable" in s:
                    return _fail("the refused write must leave its read-backs unchanged: %s" % s["qualify"])
            try:
                load_corpus(root, "enabled", VARIANT)
            except CorpusError as exc:
                return _fail("the loader accepts the variant corpus with read-backs: %s" % exc)
            receipt = load_json(root / VARIANT_RECEIPT_P)
            if (receipt.get("variant_derivation") != corpus["derived_from"].get("variant_derivation")
                    or not str(receipt.get("variant_derivation") or "").endswith("/v4")
                    or sorted(receipt.get("effects") or {}) != sorted(s["id"] for s in writes)
                    or any(r.get("identity") != {"kind": "basic", "credential_ref": n.cred_one}
                           for r in (receipt.get("effects") or {}).values())):
                return _fail("the receipt names the derivation and which writes carry read-backs as whom: %s"
                             % {k: receipt.get(k) for k in ("variant_derivation", "effects")})
            if receipt.get("corpus_sha256") != corpus_digest(corpus):
                return _fail("the receipt binds the corpus it wrote")
            outcomes.append((root, n))
        (root, n), (other_root, other) = outcomes
        rename = _rename_map(other, n)
        a = _enabled_decisions(other_root, rename, VARIANT_CORPUS_P)
        b = _enabled_decisions(root, None, VARIANT_CORPUS_P)
        if a != b:
            first = [(x, y) for x, y in zip(json.dumps(a, indent=1).splitlines(), json.dumps(b, indent=1).splitlines()) if x != y][:4]
            return _fail("the read-back decision is the same under another naming: %s" % first)
        # a variant corpus derived under the older promise (no version) is
        # derived again, never mixed with captures that assume the newer one
        old = load_json(root / VARIANT_CORPUS_P)
        old["derived_from"].pop("variant_derivation")
        write_canonical(root / VARIANT_CORPUS_P, old)
        try:
            load_corpus(root, "enabled", VARIANT)
            return _fail("a variant corpus from the older derivation must not load")
        except CorpusError as exc:
            if "derive the variant again" not in str(exc) or "missing" in str(exc):
                return _fail("the refusal says to derive again (and is not read as an absent corpus): %s" % exc)
        # ... and one derived under v2 (reads that declared no reset) too
        old["derived_from"]["variant_derivation"] = "rhoai3.fixture-variant-derivation/v2"
        write_canonical(root / VARIANT_CORPUS_P, old)
        try:
            load_corpus(root, "enabled", VARIANT)
            return _fail("a v2 variant corpus must not load under v3")
        except CorpusError as exc:
            if "/v2" not in str(exc) or "/v4" not in str(exc) or "derive the variant again" not in str(exc):
                return _fail("the v2 refusal names both derivations: %s" % exc)
        # ... while the baseline corpus of the mode is not versioned by it
        try:
            load_corpus(root, "enabled")
        except CorpusError as exc:
            return _fail("the mode's baseline corpus is not a variant: %s" % exc)
    return 0


def _enabled_variant_revert_case() -> int:
    """REVERT-THEN-READ end to end: the seed defines the varied column, no
    second identity holds what the refused one holds, so the refused writes
    read their state as the request's own identity on the baseline and after
    the computed revert. The corpus carries the revert the reset executes,
    the statements are the specimen's own column restored to the seeded
    value, the loader accepts it, the receipt names the strategy -- and the
    renamed specimen decides the same things."""
    with tempfile.TemporaryDirectory(prefix="derive-variant-revert-") as td:
        outcomes = []
        for n, label in ((PLAIN, "plain"), (RENAMED, "renamed")):
            declared = _authz_security(n)
            declared["fixtures"] = [_fixture_decl(n)]
            root = _authz_root(Path(td), label, n, security=declared, enabled_column=True)
            _derive(root)
            if _derive(root, "--security-mode", "enabled").returncode != 0:
                return _fail("the enabled corpus derives (%s)" % label)
            p = _derive(root, "--security-mode", "enabled", "--fixture-variant", VARIANT)
            if p.returncode != 0:
                return _fail("the variant derives (%s): %s%s" % (label, p.stdout, p.stderr))
            corpus = load_json(root / VARIANT_CORPUS_P)
            revert = corpus["fixture"].get("revert") or {}
            want = 'UPDATE "%s" SET "enabled" = true WHERE "%s" = \'%s\'' % (n.user_table, n.user_col, n.who_all)
            if revert.get("statements") != [want] or revert.get("strategy") != "revert_then_read":
                return _fail("the revert restores the varied column to the seeded value: %s" % revert)
            row = revert["rows"][0]
            if (row["variant_value"], row["baseline_value"], row["rows"], row["table_rows"]) != ("false", "true", 1, 2):
                return _fail("the revert knows what it must find and leave: %s" % row)
            writes = [s for s in corpus["scenarios"] if s["method"] not in ("GET", "HEAD", "OPTIONS")]
            if not writes:
                return _fail("the fixture refuses writes")
            for s in writes:
                if (s.get("effects_reader") != {"strategy": "revert_then_read", "name": n.who_all, "credential_ref": n.cred_all}
                        or s.get("effects_identity") != s["identity"] or not s["effects"]
                        or s["qualify"].get("before_reads_usable") is not True
                        or s["qualify"].get("after_equals_before") is not True):
                    return _fail("a refused write reads its state revert-then-read as its own identity: %s %s"
                                 % (s.get("effects_reader"), s["qualify"]))
            try:
                load_corpus(root, "enabled", VARIANT)
            except CorpusError as exc:
                return _fail("the loader accepts the revert-then-read corpus: %s" % exc)
            receipt = load_json(root / VARIANT_RECEIPT_P)
            if {r.get("strategy") for r in (receipt.get("effects") or {}).values()} != {"revert_then_read"}:
                return _fail("the receipt names the strategy per write: %s" % receipt.get("effects"))
            if receipt["fixture"].get("revert") != revert:
                return _fail("the receipt carries the revert the corpus binds")
            outcomes.append((root, n))
        (root, n), (other_root, other) = outcomes
        a = _enabled_decisions(other_root, _rename_map(other, n), VARIANT_CORPUS_P)
        b = _enabled_decisions(root, None, VARIANT_CORPUS_P)
        if a != b:
            first = [(x, y) for x, y in zip(json.dumps(a, indent=1).splitlines(), json.dumps(b, indent=1).splitlines()) if x != y][:4]
            return _fail("revert-then-read is decided the same under another naming: %s" % first)
        ra = json.dumps(load_json(other_root / VARIANT_CORPUS_P)["fixture"]["revert"]["rows"], sort_keys=True)
        for x, y in _rename_map(other, n):
            ra = ra.replace(x, y)
        rb = json.dumps(load_json(root / VARIANT_CORPUS_P)["fixture"]["revert"]["rows"], sort_keys=True)
        if json.loads(ra) != json.loads(rb):
            return _fail("the computed revert is the same under another naming: %s vs %s" % (ra, rb))
    return 0


def _revert_qualification_case() -> int:
    """A revert-then-read capture carries baseline reads and no after reads
    (the source's database is restored only by a restart): its contract
    PASSes on a refusal whose baseline reads are usable, and is INCONCLUSIVE
    when a baseline read did not answer 2xx."""
    own = {"kind": "basic", "credential_ref": "PARITY_ADMIN"}
    eff = {"id": "eff:owners-after-refused-delete", "method": "GET", "path": "/api/owners", "role": "unchanged_under_refusal"}
    sc = {"id": "sc:fixture-acct-off-delete-owners-1", "entry_point": EP["delete"], "method": "DELETE",
          "path": "/api/owners/1", "headers": {}, "identity": dict(own), "body_absent": True, "reset_before": True,
          "effects": [dict(eff)], "effects_identity": dict(own), "normalization": [],
          "effects_reader": {"strategy": "revert_then_read", "name": "boss", "credential_ref": "PARITY_ADMIN"},
          "qualify": {"intent": "negative", "expect_status_class": "4xx", "before_reads_usable": True}}
    refusal = ({"WWW-Authenticate": 'Basic realm="fixture"', "Location": None}, {"error": "unauthorized"})
    with tempfile.TemporaryDirectory(prefix="qualify-revert-") as td:
        root = build_root(Path(td))
        write_canonical(root / CORPUS_P, {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                                          "initial_state": {"reset": "restart the source", "dataset": "two owners"},
                                          "path_vars": {"ownerId": "1"}, "scenarios": [sc]})
        sha = corpus_digest(load_json(root / CORPUS_P))
        normalized = {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": "PARITY_ADMIN"}
        for status, want in ((200, "PASS"), (401, "INCONCLUSIVE")):
            out = _capture(root, sc, sha, 401, refusal[0], refusal[1], {eff["id"]: (status, [SEED_OWNER_1])},
                           {eff["id"]: (status, [SEED_OWNER_1])}, effects_identity=normalized)
            cap = load_json(out)
            cap["effects"] = []
            write_canonical(out, cap)
            p, q = _qualify(root)
            r = q["scenarios"][sc["id"]]
            if r["capability"] != want:
                return _fail("a revert-then-read capture with a %s baseline read qualifies %s: %s" % (status, want, r))
    return 0


def _enabled_cors_case() -> int:
    """CORS with security enabled (ADR-020): per source policy the browser
    preflight WITHOUT credentials, the actual request anonymous and as a
    declared identity the route accepts, and an authenticated OPTIONS typed as
    a diagnostic probe -- which the loader admits only under that type and
    which never counts as browser-preflight coverage. The requests are the
    disabled corpus's own; nothing states what the source answers."""
    from _scenarios import cors_coverage
    with tempfile.TemporaryDirectory(prefix="derive-enabled-cors-") as td:
        decided = []
        for n, label in ((PLAIN, "plain"), (RENAMED, "renamed")):
            root = _authz_root(Path(td), label, n, security=_authz_security(n), cors=True)
            _derive(root)
            base = load_json(root / CORPUS_P)
            if not base["cors_policies"]:
                return _fail("the fixture's disabled corpus exercises a CORS policy")
            p = _derive(root, "--security-mode", "enabled")
            if p.returncode != 0:
                return _fail("the enabled corpus derives with CORS (%s): %s%s" % (label, p.stdout, p.stderr))
            corpus = load_json(root / ENABLED_CORPUS_P)
            if [c["id"] for c in corpus["cors_policies"]] != [c["id"] for c in base["cors_policies"]]:
                return _fail("the enabled corpus declares the source's CORS policies: %s" % corpus["cors_policies"])
            pid = base["cors_policies"][0]["id"]
            by = {str(s["id"]): s for s in corpus["scenarios"] if s.get("cors_policy") == pid}
            kinds = {s["derived_from"]["kind"]: s for s in by.values()}
            want = {"cors-enabled-preflight", "cors-diagnostic-probe", "cors-enabled-actual-anonymous",
                    "cors-enabled-actual-authenticated"}
            if set(kinds) != want:
                return _fail("four CORS scenarios per policy: %s" % sorted(kinds))
            pre, probe = kinds["cors-enabled-preflight"], kinds["cors-diagnostic-probe"]
            anon, auth = kinds["cors-enabled-actual-anonymous"], kinds["cors-enabled-actual-authenticated"]
            base_by = {str(s["id"]): s for s in base["scenarios"]}
            if (pre["method"], pre["identity"], pre["scenario_type"]) != ("OPTIONS", {"kind": "none"}, "browser-preflight"):
                return _fail("the browser preflight carries no credentials: %s" % pre)
            if (probe["method"], probe["scenario_type"], probe["identity"]) != (
                    "OPTIONS", "diagnostic-probe", {"kind": "basic", "credential_ref": n.cred_all}):
                return _fail("the authenticated OPTIONS is a diagnostic probe as the identity the create's guard accepts: %s" % probe)
            if anon["identity"] != {"kind": "none"} or auth["identity"] != {"kind": "basic", "credential_ref": n.cred_one}:
                return _fail("the actual request anonymous and as the least-privileged declared identity: %s %s"
                             % (anon["identity"], auth["identity"]))
            for sc in by.values():
                src = base_by[sc["base_scenario"]]
                if (sc["method"], sc["path"], sc["headers"]) != (src["method"], src["path"], src["headers"]):
                    return _fail("the request is the disabled corpus's own: %s" % sc["id"])
                if sc["security_mode"] != "enabled" or "Origin" not in sc["headers"]:
                    return _fail("an enabled-mode cross-origin exchange: %s" % sc["id"])
                want_q = ({"intent": "observed", "usable_first_response": True} if sc is probe else
                          {"intent": "observed", "usable_first_response": True, "cors_browser_access": True})
                if sc["qualify"] != want_q:
                    return _fail("the capture decides; only browser exchanges record browser access: %s %s" % (sc["id"], sc["qualify"]))
            try:
                loaded = load_corpus(root, "enabled")
            except CorpusError as exc:
                return _fail("the loader admits the diagnostic probe with credentials: %s" % exc)
            if cors_coverage(loaded):
                return _fail("the enabled corpus covers its CORS policy: %s" % cors_coverage(loaded))
            without = dict(loaded, scenarios=[s for s in loaded["scenarios"] if s["id"] != pre["id"]])
            gaps = cors_coverage(without)
            if not gaps or "no preflight" not in gaps[0]:
                return _fail("a diagnostic probe never discharges browser-preflight coverage: %s" % gaps)
            # the prohibition stands for anything that is not a probe
            forged = load_json(root / ENABLED_CORPUS_P)
            for sc in forged["scenarios"]:
                if sc["id"] == pre["id"]:
                    sc["identity"] = {"kind": "basic", "credential_ref": n.cred_all}
            write_canonical(root / "verification" / "forged.json", forged)
            try:
                from _scenarios import CorpusError as _CE  # noqa: F401
                import importlib
                sm = importlib.import_module("_scenarios")
                bad = dict(forged, derived_from=None, approved_by="operator:test")
                write_canonical(root / ENABLED_CORPUS_P, bad)
                sm.load_corpus(root, "enabled")
                return _fail("a browser preflight with credentials is refused")
            except CorpusError as exc:
                if "diagnostic-probe" not in str(exc):
                    return _fail("the refusal names the probe type: %s" % exc)
            write_canonical(root / ENABLED_CORPUS_P, corpus)
            decided.append((root, n))
        (root, n), (other_root, other) = decided
        a = _enabled_decisions(other_root, _rename_map(other, n))
        b = _enabled_decisions(root)
        if a != b:
            first = [(x, y) for x, y in zip(json.dumps(a, indent=1).splitlines(), json.dumps(b, indent=1).splitlines()) if x != y][:4]
            return _fail("enabled CORS is decided the same under another naming: %s" % first)
    return 0


def _cors_access_qualification_case() -> int:
    """What the source's CORS answer lets a browser do is RECORDED: a 401
    preflight without CORS headers is matched parity but PREVENTS the
    exchange; a 200 carrying the permission headers PERMITS it. Neither is an
    expectation, so both qualify."""
    origin = "http://parity.invalid:4200"
    sc = {"id": "sc:cors-enabled-preflight-x", "entry_point": EP["create"], "method": "OPTIONS", "path": "/api/owners",
          "headers": {"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
          "identity": {"kind": "none"}, "body_absent": True, "reset_before": False, "effects": [], "normalization": [],
          "cors_policy": "cors:x", "scenario_type": "browser-preflight",
          "qualify": {"intent": "observed", "usable_first_response": True, "cors_browser_access": True}}
    with tempfile.TemporaryDirectory(prefix="qualify-cors-access-") as td:
        root = build_root(Path(td))
        write_canonical(root / CORPUS_P, {"schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                                          "initial_state": {"reset": "restart", "dataset": "seed"},
                                          "cors_policies": [{"id": "cors:x", "request_headers": ["Content-Type"]}],
                                          "scenarios": [sc]})
        sha = corpus_digest(load_json(root / CORPUS_P))
        none = {"Access-Control-Allow-Origin": None, "Access-Control-Allow-Methods": None, "Access-Control-Allow-Headers": None,
                "WWW-Authenticate": 'Basic realm="x"', "Location": None}
        ok = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET,POST",
              "Access-Control-Allow-Headers": "content-type", "Location": None}
        for status, headers, want in ((401, none, "prevents"), (200, ok, "permits")):
            _capture(root, sc, sha, status, headers, {} if status == 200 else {"error": "unauthorized"}, {}, {})
            _, q = _qualify(root)
            r = q["scenarios"][sc["id"]]
            if r["capability"] != "PASS" or r.get("browser_access") != want:
                return _fail("a %s preflight qualifies and records that the source %s the browser exchange: %s"
                             % (status, want, r))
        import importlib.util
        spec = importlib.util.spec_from_file_location("compose_for_test", RECEIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        probe = dict(sc, id="sc:cors-enabled-probe-x", scenario_type="diagnostic-probe")
        out = mod._cors_outcomes({"scenarios": [sc, probe]},
                                 {sc["id"]: {"browser_access": "prevents"}},
                                 {sc["id"]: [{"verdict": "PASS"}]})
        if (out[sc["id"]] != {"policy": "cors:x", "type": "browser-preflight", "browser_access": "prevents",
                              "verdict": "PASS", "discharges_browser_coverage": True}
                or out[probe["id"]]["discharges_browser_coverage"] is not False):
            return _fail("the receipt distinguishes a matched rejection and never lets a probe discharge coverage: %s" % out)
    return 0


def main() -> int:
    rc, root, td = _derivation_case()
    try:
        if rc:
            return rc
        assert root is not None
        if (_gap_cases() or _real_excerpt_case() or _methodless_mapping_case() or _methodless_qualification_case()
                or _path_variable_case() or _foreign_key_delete_case() or _authorization_policy_case()
                or _authorization_grammar_case() or _enabled_mode_case() or _enabled_constants_case()
                or _enabled_rename_case() or _enabled_decided_case()
                or _enabled_request_policy_case() or _enabled_variant_case()
                or _variant_effects_rule_case() or _enabled_variant_effects_case()
                or _enabled_variant_revert_case() or _revert_qualification_case()
                or _enabled_cors_case() or _cors_access_qualification_case()
                or _enabled_identity_case() or _enabled_regression_case()
                or _application_removal_case() or _qualification_case(root)
                or _effects_identity_qualification_case() or _receipt_case()):
            return 1
    finally:
        if td is not None:
            td.cleanup()
    print("OK: scenario-derivation (the corpus is derived from the frozen source's OpenAPI examples, seed rows and @CrossOrigin policies -- "
          "six scenarios over the write entry points and nothing for the reads, bodies are the document's own examples without id, "
          "the invalid body violates exactly one declared constraint, path_vars come from the seed; a required property without an example "
          "are gaps, never inventions; a mapping that declares NO HTTP method matches every method, so it derives one GET read scenario of its "
          "concrete path (no body, no reset, no effects) whose contract judges evidence usability only and RECORDS the status class the source "
          "gave -- 3xx and 2xx both PASS, a 5xx nobody named is INCONCLUSIVE with the failure recorded -- while a handler consuming a "
          "@RequestBody, a wildcard route and a servlet the structure model does not record derive nothing and say why, and every one of those "
          "decisions is the same under another package, type, member, route and parameter naming; a verbatim excerpt of petclinic's real document binds by operationId when its "
          "paths do not name the code's routes and a same-named method on another controller is a gap; no OpenAPI document refuses; the derivation is deterministic and never "
          "clobbers a hand-authored corpus; the loader accepts the derived corpus, refuses it after any edit or against another bundle, "
          "and refuses a placeholder approver and a body edited after derivation; a conflicting operationId on a path match is a typed gap; "
          "an operationId whose operation carries path variables the route cannot supply is a typed gap and no scenario, while a matching "
          "variable set still binds; a delete addresses the lowest seed row nothing references, an all-referenced table is a typed gap naming "
          "the constraint and earns one negative delete-referenced scenario instead, the schema is discovered beside the seed by content "
          "(initDB.sql) and recorded in the receipt, and a seed with no schema says its foreign keys are unknown; what a REFERENCED row "
          "proves is read from the application too: a cascade ALL / orphanRemoval relationship, an owned @ManyToMany join table or the "
          "constraint's own ON DELETE CASCADE derive a positive delete-cascading naming each referencing row a bound item route reads "
          "(capped at three, and unobservable children said to be so), the inverse @ManyToMany side keeps the negative, both carry the FK, "
          "the entity-to-table mapping and the removal evidence, and with no structure model neither scenario is derived and a typed gap "
          "names the reference; "
          "qualification judges evidence before intent: it PASSes captures that show the contract, FAILs a relative or foreign Location, a create "
          "with no new identity or a duplicated prior entity or a Location naming 999, a 400 without the errors header, one naming another field, "
          "or one with a changed list, and is INCONCLUSIVE with known_failures recorded for a 500 beside an unbound read-back, a non-JSON errors "
          "header, 500 read-backs, a null identity field, a missing or unbound retained body, no capture, another corpus, another request or no "
          "contract; a judged failure beside an unjudgeable predicate is FAIL and both stay on the record, a recorded FAIL or INCONCLUSIVE exits "
          "0 with its verdict printed while no capture at all is a refusal exiting 1; the parity receipt is INCONCLUSIVE for a derived corpus "
          "nobody qualified, a scenario qualified INCONCLUSIVE, unrecorded or stale, lists a positive FAIL as a fixture-failed coverage gap and "
          "an INCONCLUSIVE as an inconclusive-qualification one with the entry point INCONCLUSIVE, counts a negative PASS as negative "
          "coverage only, and an Operator-authored corpus keeps its behaviour; "
          "the source's authorization policies are read from the model and keyed by what they say -- a type policy with one member "
          "override is two policies mapped to the entry points each guards, the same two under another package, type, member and "
          "annotation spelling are the same two, a role set in either order is one policy, and a missing model or bundle is a reason "
          "rather than an empty answer; "
          "the enabled-mode corpus is derived per policy into its own path and the disabled one is byte-for-byte untouched: which roles "
          "a policy accepts is read from hasRole / hasAnyRole / a @RolesAllowed or @Secured list, with a constant reference resolved "
          "through the structure model's own field values -- @roles naming the type a component stereotype makes that bean and no "
          "class that merely lower-cases to it, a stereotype that states a name registering no other, and a constant the sealed model "
          "does not carry read back from the frozen source's own tree with the run recorded on the receipt, each scenario saying which "
          "model the value came from and both readings deriving the same corpus -- and an expression outside that grammar -- a "
          "combination, an authority, a bean call, a constant neither model records -- is a typed gap and no scenario; each policy "
          "guarding an entry point the disabled corpus carries a qualified-shaped "
          "scenario for is probed with an identity that holds the role, with nobody, with a credential declared invalid and with an "
          "authenticated identity that lacks it, reusing that scenario's method, path, headers and body bytes bound by its id and body "
          "digest; the allowed probe expects no status (the source's own answer is what the capture records) and keeps the base's effect "
          "assertions, the refusals expect any 4xx with the base read-backs unchanged for a write, the unauthenticated ones assert the "
          "WWW-Authenticate challenge on the first response, and every scenario names the policy, its expression, what the identity holds "
          "and the credential REFERENCE -- never a credential; the seeded identities' roles are read from the seed through the JPA "
          "identity mapping where the model provides one, a declaration the seed contradicts is a gap with the seed used, and an identity "
          "whose roles nobody knows, an undeclared invalid credential and no identity lacking the role are ADR-014 blockers rather than "
          "invented accounts; a policy guarding a GET the disabled corpus states nothing about gets a read base derived here from the "
          "entry point's own method and route and that corpus's own path values -- GET, no body, no effect, no reset, usable first "
          "response, citing no scenario -- while a route no value resolves keeps its auth-base gap and nothing invents a path; who the "
          "mode authenticates as comes from decisions.yaml by default, the decided identities derive exactly what the typed ones derive, "
          "each corpus says which declaration it came from and carries the decided switch forward, asking for both at once is a usage "
          "error, and an undeclared or refused security section derives nothing and records why without echoing what a field held; "
          "all of it is the same under another package, type, member, route, role, table and credential naming; a refuse-intent fixture "
          "variant's refused PUT, POST and DELETE carry the base read requests as unchanged_under_refusal read-backs taken as a declared "
          "identity that is neither the refused nor the invalid one and holds what the refused one holds, with after_equals_before; with "
          "no such identity the write carries none, names the missing identity and records a gap; refused reads and allow-intent "
          "variants are unaffected; a variant corpus from the unversioned derivation is refused with 'derive the variant again'; with no "
          "second identity the refused write is read REVERT-THEN-READ as its own identity -- the seeded column restored by a revert "
          "computed only from single-column UPDATEs over the declared dataset, typed REVERT_NOT_COMPUTABLE otherwise -- a declared "
          "second identity still wins, the strategy is recorded per reader, and its capture qualifies on usable baseline reads; every variant scenario declares reset_before (v3) and a v2 corpus is refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
