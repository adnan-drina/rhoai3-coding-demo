#!/usr/bin/env python3
"""scenario-derivation selftest: the corpus is a producer output, not a signature.

The control: a frozen source whose OpenAPI document carries examples, whose
seed names row 1 and whose one controller carries a @CrossOrigin policy. The
derivation must produce exactly the create / create-invalid / update / delete
/ cors-actual / cors-preflight scenarios from those inputs and nothing for the
reads; a required property with no example is a gap and no scenario (never an
invented value); an entry point with no HTTP method is a gap. The loader must
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
from _scenarios import CorpusError, DERIVE_RECEIPT, QUALIFICATION, SCENARIO_ORACLES, corpus_digest, load_corpus, scenario_slug, source_cors_policies  # noqa: E402
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


def _api_docs(drop_telephone_example: bool = False) -> str:
    tel_example = "" if drop_telephone_example else "          example: '6085551023'\n"
    return (
        "openapi: 3.0.1\n"
        "info:\n  title: Spring PetClinic\n  description: |\n    Sample application.\n  version: '1.0'\n"
        "servers:\n  - url: http://localhost:9966/petclinic/api\n"
        "paths:\n"
        "  /owners:\n"
        "    post:\n      operationId: addOwner\n      requestBody:\n        content:\n          application/json:\n"
        "            schema:\n              $ref: '#/components/schemas/OwnerFields'\n        required: true\n"
        "      responses:\n        201:\n          description: created\n"
        "    get:\n      operationId: listOwners\n      responses:\n        '200':\n          description: ok\n"
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


def build_root(td: Path, *, drop_telephone_example: bool = False, servlet: bool = False, api_docs: str | None = None,
               extra_eps: list[dict[str, Any]] | None = None) -> Path:
    root = td / "dest"
    copy = td / "frozen"
    res = copy / "src" / "main" / "resources"
    (res / "db" / "hsqldb").mkdir(parents=True)
    (copy / "pom.xml").write_text("<project/>", encoding="utf-8")
    (res / "api-docs.yml").write_text(api_docs if api_docs is not None else _api_docs(drop_telephone_example), encoding="utf-8")
    (res / "db" / "hsqldb" / "populateDB.sql").write_text(
        "INSERT INTO owners VALUES (1, 'George', 'Franklin', '110 W. Liberty St.', 'Madison', '6085551023');\n"
        "INSERT INTO owners VALUES (2, 'Betty', 'Davis', '638 Cardinal Ave.', 'Sun Prairie', '6085551749');\n"
        "INSERT INTO types VALUES (1, 'cat');\n", encoding="utf-8")
    (res / "db" / "hsqldb" / "schema.sql").write_text(
        "CREATE TABLE owners (\n  id INTEGER IDENTITY PRIMARY KEY,\n  first_name VARCHAR(30),\n  last_name VARCHAR(30),\n"
        "  address VARCHAR(255),\n  city VARCHAR(80),\n  telephone VARCHAR(20)\n);\n", encoding="utf-8")
    write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(copy), "source_digest": "fixture-source-digest"})
    write_canonical(root / STRUCTURE, {"types": [
        {"fqn": CONTROLLER, "annotations": [{"fqn": "org.springframework.web.bind.annotation.CrossOrigin", "values": {"exposedHeaders": ["errors, content-type"]}}]},
        {"fqn": "a.OwnerDto", "annotations": []}]})
    eps = [_entry("list", "GET", "/api/owners", "getOwners()"), _entry("get", "GET", "/api/owners/{ownerId}", "getOwner(int)"),
           _entry("create", "POST", "/api/owners", "addOwner(a.OwnerDto)"), _entry("update", "PUT", "/api/owners/{ownerId}", "updateOwner(int,a.OwnerDto)"),
           _entry("delete", "DELETE", "/api/owners/{ownerId}", "deleteOwner(int)")]
    if servlet:
        eps.append({"id": "ep:a.RedirectServlet#:http", "kind": "http", "type": "a.RedirectServlet", "member": "", "path": "src/main/java/a/RedirectServlet.java", "http_method": "", "http_path": "/"})
    if extra_eps is not None:
        eps = list(extra_eps)  # the caller's bundle, not the fixture controller's
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
        if len(create) != 1 or len(invalid) != 1 or len(update) != 1:
            return _fail("the real controller's create, invalid create and update bind by operationId: %s\ngaps: %s" % (sorted(sc), corpus["gaps"]))
        if not any("operationId addOwner" in e for e in create[0]["derived_from"]["evidence"]) or not any("operationId updateOwner" in e for e in update[0]["derived_from"]["evidence"]):
            return _fail("the binding evidence names the operationId: %s" % create[0]["derived_from"])
        body = json.loads((root / create[0]["body_file"]).read_text())
        if body != {"firstName": "George", "lastName": "Franklin", "address": "110 W. Liberty St.", "city": "Madison", "telephone": "6085551023"}:
            return _fail("the create body is the real document's OwnerFields examples: %s" % body)
        if create[0]["path"] != "/api/owners" or update[0]["path"] != "/api/owners/1" or json.loads((root / update[0]["body_file"]).read_text()) != body:
            return _fail("concrete paths are the code's routes, bodies the document's: %s %s" % (create[0]["path"], update[0]["path"]))
        inv = json.loads((root / invalid[0]["body_file"]).read_text())
        changed = [k for k in body if inv.get(k) != body[k]]
        if changed != ["firstName"] or re.fullmatch(r"^[a-zA-Z]*$", inv["firstName"]) is not None or invalid[0]["qualify"]["errors_header_names_field"] != "firstName":
            return _fail("the invalid body breaks exactly the first constrained property of the real schema: %s" % inv)
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
    want = {"sc:create-owners", "sc:create-invalid-owners", "sc:update-owners-1", "sc:delete-owners-1",
            "sc:cors-actual-%s" % short, "sc:cors-preflight-%s" % short}
    got = {str(s["id"]) for s in corpus["scenarios"]}
    if got != want:
        return _fail("the derived ids are exactly the six rules over the write entry points (nothing for the reads): %s" % sorted(got)), None, td
    if corpus.get("approved_by") is not None or corpus["derived_from"]["producer"] != "derive-source-scenarios.py":
        return _fail("a derived corpus names its producer, not a person: %s" % corpus.get("derived_from")), None, td
    if corpus["derived_from"]["evidence_bundle_sha256"] != digest(load_json(root / EVIDENCE_BUNDLE)) or not corpus["derived_from"]["openapi"]["sha256"]:
        return _fail("derived_from binds the bundle and names the OpenAPI input: %s" % corpus["derived_from"]), None, td
    sc = {str(s["id"]): s for s in corpus["scenarios"]}
    create_body = json.loads((root / sc["sc:create-owners"]["body_file"]).read_text())
    expected_body = {k: v for k, v in SEED_OWNER_1.items() if k != "id"}
    if create_body != expected_body:
        return _fail("the create body is the document's examples without id: %s" % create_body), None, td
    if sc["sc:create-owners"]["qualify"] != {"expect_status": [201], "location": "absolute-under-base", "after_contains_body": True, "after_adds_one_body": True}:
        return _fail("the create scenario carries its qualification contract: %s" % sc["sc:create-owners"].get("qualify")), None, td
    if sc["sc:create-owners"]["headers"].get("Origin") is None or sc["sc:create-owners"].get("cors_policy") != pols[0]:
        return _fail("a create on a controller carrying a CORS policy sends Origin and names the policy: %s" % sc["sc:create-owners"]), None, td
    invalid = json.loads((root / sc["sc:create-invalid-owners"]["body_file"]).read_text())
    if re.fullmatch(r"^[0-9]*$", invalid["telephone"]) is not None:
        return _fail("the invalid body's telephone must violate its pattern: %r" % invalid["telephone"]), None, td
    if {k: v for k, v in invalid.items() if k != "telephone"} != {k: v for k, v in create_body.items() if k != "telephone"}:
        return _fail("only telephone differs in the invalid body: %s" % invalid), None, td
    if re.fullmatch(r"^[a-zA-Z]*$", invalid["firstName"]) is None:
        return _fail("every other constrained field stays valid: %s" % invalid), None, td
    if sc["sc:create-invalid-owners"]["qualify"].get("errors_header_names_field") != "telephone":
        return _fail("the invalid scenario names the rejected field: %s" % sc["sc:create-invalid-owners"]["qualify"]), None, td
    update_body = json.loads((root / sc["sc:update-owners-1"]["body_file"]).read_text())
    if update_body != expected_body or sc["sc:update-owners-1"]["path"] != "/api/owners/1":
        return _fail("the update writes the examples over the seeded row (id is readOnly and not sent): %s %s" % (update_body, sc["sc:update-owners-1"]["path"])), None, td
    if [e["path"] for e in sc["sc:update-owners-1"]["effects"]] != ["/api/owners/1", "/api/owners"]:
        return _fail("the update reads back the item and the collection: %s" % sc["sc:update-owners-1"]["effects"]), None, td
    d = sc["sc:delete-owners-1"]
    if not d.get("body_absent") or d["qualify"] != {"expect_status": [200, 204], "after_effect_status": {"eff:owners-1-after-delete": 404}}:
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
        if not any("ep:a.RedirectServlet#:http" in g and "no HTTP method" in g for g in corpus["gaps"]):
            return _fail("a servlet entry point with no method is a gap: %s" % corpus["gaps"])
        if "sc:delete-owners-1" not in ids:
            return _fail("the delete needs no example and is still derived: %s" % sorted(ids))
        bodies = root / "verification" / "scenarios" / "bodies"
        if bodies.is_dir() and any(p.name.startswith("create") for p in bodies.iterdir()):
            return _fail("no body is written for a scenario that is not emitted")
    with tempfile.TemporaryDirectory(prefix="derive-refuse-") as td:
        root = build_root(Path(td))
        (Path(td) / "frozen" / "src" / "main" / "resources" / "api-docs.yml").unlink()
        p = _derive(root)
        if p.returncode != 1 or "REFUSE" not in p.stderr or "OpenAPI" not in p.stderr:
            return _fail("no OpenAPI document is a refusal: rc=%s %s" % (p.returncode, p.stderr))
        if load_json(root / DERIVE_RECEIPT)["status"] != "blocked" or (root / CORPUS_P).exists():
            return _fail("a refusal leaves a blocked receipt and no corpus")
    return 0


def _retain(root: Path, sid: str, name: str, payload: Any) -> tuple[dict[str, Any], str]:
    raw = json.dumps(payload).encode("utf-8")
    sha = normalize_body(raw, "application/json")[1]
    return retain_body(root / SCENARIO_ORACLES / "bodies" / scenario_slug(sid), name, raw, sha), sha


def _capture(root: Path, sc: dict[str, Any], corpus_sha: str, status: int, headers: dict[str, Any], body: Any,
             before: dict[str, tuple[int, Any]], after: dict[str, tuple[int, Any]]) -> Path:
    sid = str(sc["id"])
    ev, sha = _retain(root, sid, "response", body)
    rec: dict[str, Any] = {
        "schema": "rhoai3.source-scenario/v1", "scenario": sid, "entry_point": sc["entry_point"],
        "evidence_bundle_sha256": digest(load_json(root / EVIDENCE_BUNDLE)), "corpus_sha256": corpus_sha,
        "source": {"base_url": BASE, "analysis_copy_digest": "fixture-source-digest"}, "status": "CAPTURED", "reason": "",
        "request": {"method": sc["method"], "path": sc["path"], "headers": dict(sc.get("headers") or {})},
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
    _capture(root, sc["sc:create-invalid-owners"], corpus_sha, 400, invalid_hdrs, {"error": "bad request"},
             {"eff:owners-list-after-invalid-create": (200, seeded)}, {"eff:owners-list-after-invalid-create": (200, seeded)})
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
    verdicts = {sid: r["verdict"] for sid, r in q["scenarios"].items()}
    if p.returncode != 0 or q["verdict"] != "PASS" or set(verdicts.values()) != {"PASS"} or q["corpus_sha256"] != corpus_sha:
        return _fail("captures that show what every scenario says are PASS: rc=%s %s %s%s" % (p.returncode, verdicts, p.stdout, p.stderr))
    checks = {c["check"]: c for c in q["scenarios"]["sc:create-owners"]["checks"]}
    if set(checks) != {"expect_status", "location", "after_contains_body", "after_adds_one_body"} or not all(c["ok"] is True for c in checks.values()):
        return _fail("the create's checks are exactly its contract: %s" % checks)
    # a relative Location is not the source's absolute form under its base
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, dict(good_create, Location="/petclinic/api/owners/11"), created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    if p.returncode != 1 or r["verdict"] != "FAIL" or not any(c["check"] == "location" and c["ok"] is False for c in r["checks"]) or "sc:create-owners" not in p.stderr:
        return _fail("a relative Location FAILs and names location: %s %s" % (r, p.stderr))
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
    if r["verdict"] != "FAIL" or not any(c["check"] == "after_adds_one_body" and c["ok"] is False for c in r["checks"]):
        return _fail("a 201 whose read-back gained no matching row FAILs: %s" % r)
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    # the 400 without the errors header the source exposes
    _capture(root, sc["sc:create-invalid-owners"], corpus_sha, 400, dict(invalid_hdrs, errors=None), {"error": "bad request"},
             {"eff:owners-list-after-invalid-create": (200, seeded)}, {"eff:owners-list-after-invalid-create": (200, seeded)})
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-invalid-owners"]
    if r["verdict"] != "FAIL" or not any(c["check"] == "errors_header_names_field" and c["ok"] is False for c in r["checks"]):
        return _fail("a 400 without the errors header FAILs: %s" % r)
    # ... and a 400 that nevertheless changed the list
    _capture(root, sc["sc:create-invalid-owners"], corpus_sha, 400, invalid_hdrs, {"error": "bad request"},
             {"eff:owners-list-after-invalid-create": (200, seeded)}, {"eff:owners-list-after-invalid-create": (200, seeded + [created])})
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-invalid-owners"]["verdict"] != "FAIL":
        return _fail("a rejected create that changed the list FAILs")
    _capture(root, sc["sc:create-invalid-owners"], corpus_sha, 400, invalid_hdrs, {"error": "bad request"},
             {"eff:owners-list-after-invalid-create": (200, seeded)}, {"eff:owners-list-after-invalid-create": (200, seeded)})
    # a missing retained body cannot be checked
    cap_p = root / SCENARIO_ORACLES / (scenario_slug("sc:create-owners") + ".json")
    cap = load_json(cap_p)
    Path(cap["effects"][0]["evidence"]["body_file"]).unlink()
    p, q = _qualify(root)
    r = q["scenarios"]["sc:create-owners"]
    if r["verdict"] != "INCONCLUSIVE" or not any(c["check"] == "after_contains_body" and c["ok"] is None and "absent" in c["detail"] for c in r["checks"]):
        return _fail("a missing retained body is INCONCLUSIVE with the reason: %s" % r)
    # a retained body whose bytes are not the recorded digest is not evidence
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    cap = load_json(cap_p)
    Path(cap["effects"][0]["evidence"]["body_file"]).write_bytes(json.dumps(seeded + [created, {"id": 12}]).encode())
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["verdict"] != "INCONCLUSIVE" or "digest" not in q["scenarios"]["sc:create-owners"]["reason"]:
        return _fail("a retained body that does not match its digest is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    # a row retained without digests is bytes of unknown origin
    _capture(root, sc["sc:create-owners"], corpus_sha, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    cap = load_json(cap_p)
    cap["effects"][0]["evidence"].pop("raw_body_sha256")
    write_canonical(cap_p, cap)
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["verdict"] != "INCONCLUSIVE" or "not digest-bound" not in q["scenarios"]["sc:create-owners"]["reason"]:
        return _fail("a retained body without its digests is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    # no capture at all, and a capture of another corpus
    cap_p.unlink()
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["verdict"] != "INCONCLUSIVE" or q["scenarios"]["sc:create-owners"]["reason"] != "no capture":
        return _fail("no capture is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    _capture(root, sc["sc:create-owners"], "1" * 64, 201, good_create, created,
             {"eff:owners-list-after-create": (200, seeded)}, {"eff:owners-list-after-create": (200, seeded + [created])})
    p, q = _qualify(root)
    if q["scenarios"]["sc:create-owners"]["verdict"] != "INCONCLUSIVE" or "corpus" not in q["scenarios"]["sc:create-owners"]["reason"]:
        return _fail("a capture bound to another corpus is INCONCLUSIVE: %s" % q["scenarios"]["sc:create-owners"])
    # a scenario without a contract cannot be qualified
    bare = json.loads(json.dumps(corpus))
    for s in bare["scenarios"]:
        s.pop("qualify", None)
    write_canonical(root / CORPUS_P, bare)
    rec = load_json(root / DERIVE_RECEIPT)
    rec["corpus_sha256"] = corpus_digest(bare)
    write_canonical(root / DERIVE_RECEIPT, rec)
    p, q = _qualify(root)
    if p.returncode != 1 or any(r["verdict"] != "INCONCLUSIVE" or "no qualification contract" not in r["reason"] for r in q["scenarios"].values()):
        return _fail("a scenario without a qualify block is INCONCLUSIVE: %s" % q["scenarios"])
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
                                                "evidence_bundle_sha256": digest(load_json(root / EVIDENCE_BUNDLE)), "corpus_sha256": corpus_digest(corpus)})
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
                                               "scenarios": {"sc:read-x": {"verdict": "INCONCLUSIVE", "reason": "no capture"}}, "verdict": "INCONCLUSIVE"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "capture not qualified: sc:read-x INCONCLUSIVE" not in row["reason"] or doc["coverage_gaps"]:
            return _fail("a scenario qualified INCONCLUSIVE makes its entry point INCONCLUSIVE: %s" % row)
        # a qualification that FAILED: the capture is still faithful parity
        # evidence, so the entry point is judged on parity and the scenario
        # is a coverage gap on the receipt
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"verdict": "FAIL", "reason": "expect_status: status 500"}}, "verdict": "FAIL"})
        p = subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        doc = load_json(root / "verification" / "parity" / "receipt.json")
        row = next(r for r in doc["entry_points"] if r["entry_point"] == ep)
        if p.returncode != 0 or doc["verdict"] != "PASS" or row["verdict"] != "PASS":
            return _fail("a FAIL qualification does not make the parity receipt INCONCLUSIVE: %s %s%s" % (row, p.stdout, p.stderr))
        if doc["coverage_gaps"] != [{"scenario": "sc:read-x", "entry_point": ep, "reason": "capture not qualified: FAIL: expect_status: status 500"}] or "coverage gap sc:read-x" not in p.stdout:
            return _fail("the FAIL is a coverage gap on the receipt, printed: %s %s" % (doc["coverage_gaps"], p.stdout))
        # a qualification with no record for the scenario
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha, "scenarios": {}, "verdict": "INCONCLUSIVE"})
        subprocess.run([sys.executable, str(RECEIPT), "--root", str(root)], text=True, capture_output=True)
        row = next(r for r in load_json(root / "verification" / "parity" / "receipt.json")["entry_points"] if r["entry_point"] == ep)
        if row["verdict"] != "INCONCLUSIVE" or "has no qualification record" not in row["reason"]:
            return _fail("a scenario with no qualification record is INCONCLUSIVE: %s" % row)
        # ... and PASS once qualified
        write_canonical(root / QUALIFICATION, {"schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
                                               "scenarios": {"sc:read-x": {"verdict": "PASS", "reason": ""}}, "verdict": "PASS"})
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
        if _gap_cases() or _real_excerpt_case() or _qualification_case(root) or _receipt_case():
            return 1
    finally:
        if td is not None:
            td.cleanup()
    print("OK: scenario-derivation (the corpus is derived from the frozen source's OpenAPI examples, seed rows and @CrossOrigin policies -- "
          "six scenarios over the write entry points and nothing for the reads, bodies are the document's own examples without id, "
          "the invalid body violates exactly one declared constraint, path_vars come from the seed; a required property without an example "
          "and a servlet with no method are gaps, never inventions; a verbatim excerpt of petclinic's real document binds by operationId when its "
          "paths do not name the code's routes and a same-named method on another controller is a gap; no OpenAPI document refuses; the derivation is deterministic and never "
          "clobbers a hand-authored corpus; the loader accepts the derived corpus, refuses it after any edit or against another bundle, "
          "and refuses a placeholder approver; qualification PASSes captures that show the contract, FAILs a relative or foreign Location, "
          "a read-back without the created row, a 400 without the errors header or with a changed list, and is INCONCLUSIVE without a "
          "retained, digest-bound body, without a capture, against another corpus or without a contract; the parity receipt is "
          "INCONCLUSIVE for a derived corpus nobody qualified or a scenario qualified INCONCLUSIVE or unrecorded, lists a FAIL qualification as a "
          "coverage gap while the entry point is judged on parity, and an Operator-authored corpus keeps its behaviour)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
