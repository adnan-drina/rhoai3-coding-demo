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
             before: dict[str, tuple[int, Any]], after: dict[str, tuple[int, Any]], request_sha: str | None = None) -> Path:
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
    for key, rows in (("before", before), ("effects", after)):
        for eff in sc.get("effects") or []:
            st, payload = rows[eff["id"]]
            ev, sha = _retain(root, sid, "%s-%s" % ("before" if key == "before" else "after", scenario_slug(eff["id"])), payload)
            rec[key].append({"id": eff["id"], "method": "GET", "path": eff["path"], "status": st, "body_kind": "json", "body_sha256": sha, "evidence": ev})
    out = root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json")
    write_canonical(out, rec)
    return out


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


def main() -> int:
    rc, root, td = _derivation_case()
    try:
        if rc:
            return rc
        assert root is not None
        if (_gap_cases() or _real_excerpt_case() or _methodless_mapping_case() or _methodless_qualification_case()
                or _path_variable_case() or _foreign_key_delete_case()
                or _application_removal_case() or _qualification_case(root) or _receipt_case()):
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
          "coverage only, and an Operator-authored corpus keeps its behaviour)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
