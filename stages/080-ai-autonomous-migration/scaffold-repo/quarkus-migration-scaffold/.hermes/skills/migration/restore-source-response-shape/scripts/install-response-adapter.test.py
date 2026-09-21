#!/usr/bin/env python3
"""restore-source-response-shape selftest (no JVM): policy rendering from the
SOURCE model, restrictive-policy fixtures, the installer's authority, conflicts,
profile refusal and idempotency, the media-type decision, and the structural
facts about the Java templates that the runtime check (runtime-check.sh)
proves on the real HTTP layer.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
for parent in HERE.parents:
    if (parent / "lib" / ".hermes-lib").is_file():
        sys.path.insert(0, str(parent / "lib"))
        break
import response_adapters as ra  # noqa: E402

FIXTURE = SKILL / "fixtures" / "runtime"
INSTALL = HERE / "install-response-adapter.py"
fails = 0


def check(cond: bool, name: str, detail: object = "") -> None:
    global fails
    if cond:
        print("ok", name)
    else:
        fails += 1
        print("FAIL", name, detail, file=sys.stderr)


def run(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(INSTALL), "--root", str(root), *args], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def tree(td: Path, structure: dict | None = None) -> Path:
    root = td / "dest"
    (root / "evidence" / "structure").mkdir(parents=True)
    (root / "src" / "main" / "resources").mkdir(parents=True)
    doc = structure if structure is not None else json.loads((FIXTURE / "evidence/structure/structure.json").read_text())
    (root / "evidence/structure/structure.json").write_text(json.dumps(doc))
    (root / ra.APP_PROPERTIES).write_text("quarkus.http.root-path=/shop/\n# keep me\nquarkus.http.cors.origins=http://stale.example\n"
                                          "unrelated.key=1\n")
    return root


def worklist(root: Path, items: list[dict]) -> None:
    p = root / "evidence/planning/worklist.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": "rhoai3.worklist/v1", "items": items, "clusters": []}))


def main() -> int:
    base = json.loads((FIXTURE / "evidence/structure/structure.json").read_text())

    # --- rendering: the SOURCE policy decides -------------------------------
    with tempfile.TemporaryDirectory() as d:
        root = tree(Path(d))
        policy = ra.cors_policy(root)
        rules = {tuple(r["types"]): r for r in policy["rules"]}
        narrow = rules[("org.example.shop.rest.NarrowController",)]
        wide = rules[("org.example.shop.rest.ItemController",)]
        check(narrow["origins"] == ["http://allowed.example"] and narrow["methods"] == ["GET"]
              and narrow["headers"] == ["X-Allowed"] and narrow["allow_credentials"] and narrow["max_age"] == "600",
              "restrictive policy rendered exactly as declared", narrow)
        check(wide["origins"] == ["*"] and wide["headers"] == ["*"] and wide["methods"] is None
              and wide["max_age"] == "1800" and not wide["allow_credentials"] and wide["exposed_headers"] == "errors, content-type",
              "@CrossOrigin defaults: any origin, any header, the handler's own methods, 1800, no credentials", wide)
        check(wide["mappings"] == ["GET /api/items", "POST /api/items", "GET /api/items/*/name/{name}", "PUT /api/items/{itemId}"],
              "handler mappings combine the class and method paths and keep their verbs", wide["mappings"])
        check(not any("other" in m for r in policy["rules"] for m in r["mappings"]),
              "a controller without @CrossOrigin is in no rule (no permission outside the source policy)")
        sec = policy["security"]
        check(sec["precedes_cors"] and sec["preflight_authenticated_when"] == ["fixture.security.enable=true"],
              "security without cors() precedes CORS; anonymous refused only while the switch is on", sec)
        props = dict(ra.cors_properties(policy))
        check(props["quarkus.http.cors.origins"] == "*" and props["quarkus.http.cors.methods"] == "GET,POST,PUT",
              "platform rows are the union of what the source grants", props)
        check("quarkus.http.cors.access-control-max-age" not in props,
              "differing max-ages are left to the per-rule adapter rows", props)
        check(props["rhoai3.source-cors.rule.0.origins"] == "http://allowed.example"
              and "rhoai3.source-cors.rule.0.exposed-headers" not in props,
              "the restrictive rule is not widened by the permissive one", props)

        # the rendering is from the SOURCE model: a renamed specimen renders the same shape
        renamed = copy.deepcopy(base)
        for t in renamed["types"]:
            t["fqn"] = t["fqn"].replace("org.example.shop", "com.acme.ledger")
        (root / "evidence/structure/structure.json").write_text(json.dumps(renamed))
        again = ra.cors_properties(ra.cors_policy(root))
        check([k for k, _ in again] == list(props) and dict(again) == props,
              "identifiers aside, a renamed source renders the same rows")

        # restrictive-only source: no wildcard anywhere, platform origins are exactly the declared ones
        only = copy.deepcopy(base)
        only["types"] = [t for t in only["types"] if not t["fqn"].endswith("ItemController")]
        (root / "evidence/structure/structure.json").write_text(json.dumps(only))
        rp = dict(ra.cors_properties(ra.cors_policy(root)))
        check(rp["quarkus.http.cors.origins"] == "http://allowed.example" and rp["quarkus.http.cors.headers"] == "X-Allowed"
              and rp["quarkus.http.cors.methods"] == "GET" and rp["quarkus.http.cors.access-control-allow-credentials"] == "true"
              and "*" not in "".join(rp.values()),
              "a restrictive source yields no wildcard at the platform or in the adapter", rp)

        # method-level @CrossOrigin covers only its own handler
        meth = copy.deepcopy(base)
        other = next(t for t in meth["types"] if t["fqn"].endswith("OtherController"))
        other["methods"].append({"name": "shared", "annotations": [
            {"fqn": "org.springframework.web.bind.annotation.GetMapping", "values": {"value": ["/shared"]}},
            {"fqn": "org.springframework.web.bind.annotation.CrossOrigin", "values": {"origins": ["http://partner.example"]}}]})
        (root / "evidence/structure/structure.json").write_text(json.dumps(meth))
        mp = ra.cors_policy(root)
        partner = [r for r in mp["rules"] if r["origins"] == ["http://partner.example"]]
        check(len(partner) == 1 and partner[0]["mappings"] == ["GET /api/other/shared"],
              "a method-level @CrossOrigin grants only its own handler", partner)

        # refusals, by name
        glob = copy.deepcopy(base)
        glob["types"].append({"fqn": "org.example.shop.WebConfig", "supertypes": [],
                              "type_refs": ["org.springframework.web.servlet.config.annotation.CorsRegistry"],
                              "annotations": [], "methods": []})
        (root / "evidence/structure/structure.json").write_text(json.dumps(glob))
        try:
            ra.cors_policy(root)
            check(False, "a CorsRegistry policy is refused")
        except ra.Refuse as exc:
            check(exc.code == "CORS_POLICY_UNRENDERABLE", "a CorsRegistry policy is refused, not guessed", exc)
        none = copy.deepcopy(base)
        for t in none["types"]:
            t["annotations"] = [a for a in t["annotations"] if not a["fqn"].endswith("CrossOrigin")]
        (root / "evidence/structure/structure.json").write_text(json.dumps(none))
        try:
            ra.cors_policy(root)
            check(False, "a source with no @CrossOrigin renders nothing")
        except ra.Refuse as exc:
            check(exc.code == "CORS_POLICY_EMPTY", "a source with no @CrossOrigin renders nothing", exc)
        (root / "evidence/structure/structure.json").unlink()
        try:
            ra.cors_policy(root)
            check(False, "no model, no policy")
        except ra.Refuse as exc:
            check(exc.code == "CORS_POLICY_UNKNOWN", "no model, no policy", exc)

    # --- the media-type decision --------------------------------------------
    diff = ra.media_type_difference("application/json;charset=UTF-8", "application/json")
    check(diff == {"media_type": "application/json", "extra": [("charset", "UTF-8")], "missing": []}, "parameter difference", diff)
    check(ra.media_type_difference("text/html", "application/json") is None, "another media type is not a parameter difference")
    check(ra.media_type_difference("application/json", "application/json") is None, "equal values differ in nothing")
    dec = ra.media_type_decision([diff, ra.media_type_difference("application/problem+json; charset=UTF-8", "application/problem+json")])
    check(dec == {"parameter": "charset", "value": "UTF-8", "media_types": ["application/json", "application/problem+json"]},
          "one common parameter decides; its media types are the recorded ones", dec)
    for bad, why in (([], "nothing recorded"),
                     ([ra.media_type_difference("application/json;charset=UTF-8;v=1", "application/json")], "two parameters"),
                     ([diff, ra.media_type_difference("application/json;charset=ISO-8859-1", "application/json")], "two values"),
                     ([ra.media_type_difference("application/json", "application/json;charset=UTF-8")], "a missing parameter")):
        try:
            ra.media_type_decision(bad)
            check(False, "undecidable: " + why)
        except ra.Refuse as exc:
            check(exc.code == "MEDIA_TYPE_UNDECIDED", "undecidable: " + why, exc)

    # --- the installer -------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        root = tree(Path(d))
        rc, out = run(root, "--adapter", "cors")
        check(rc == 1 and "ADAPTER_UNAUTHORIZED" in out, "no obligation, no install", out)
        worklist(root, [{"id": "parity:m", "rule_id": "PARITY_CONTENT_TYPE", "owed": ra.contract(ra.MEDIA_TYPE)}])
        rc, out = run(root, "--adapter", "cors")
        check(rc == 1 and "ADAPTER_UNAUTHORIZED" in out, "a media-type obligation never authorizes the CORS adapter", out)
        cors_item = {"id": "parity:c", "rule_id": "PARITY_CORS", "owed": ra.contract(ra.CORS)}
        worklist(root, [cors_item])
        issued = root / "verification/loop/issued.json"
        issued.parent.mkdir(parents=True)
        issued.write_text(json.dumps({"cluster": "u:x", "task_id": "t_x", "write_set": [ra.APP_PROPERTIES]}))
        rc, out = run(root, "--adapter", "cors")
        check(rc == 1 and "write set" in out and not (root / ra.adapter_path(ra.CORS)).exists(),
              "an issued card must already hold both paths", out)
        issued.write_text(json.dumps({"cluster": "u:x", "task_id": "t_x", "write_set": [ra.adapter_path(ra.CORS), ra.APP_PROPERTIES]}))
        rc, out = run(root, "--adapter", "cors", "--check")
        check(rc == 1 and "ADAPTER_NOT_INSTALLED" in out, "--check before install refuses", out)
        before = (root / ra.APP_PROPERTIES).read_text()
        rc, out = run(root, "--adapter", "cors", "--print")
        check(rc == 0 and (root / ra.APP_PROPERTIES).read_text() == before and not (root / ra.adapter_path(ra.CORS)).exists(),
              "--print writes nothing", out[:200])
        rc, out = run(root, "--adapter", "cors")
        check(rc == 0 and "1 replaced" in out, "installs on the obligation and replaces the stale family row", out)
        text = (root / ra.APP_PROPERTIES).read_text()
        check("unrelated.key=1" in text and "# keep me" in text and "http://stale.example" not in text,
              "unrelated rows and comments are preserved", text)
        check((root / ra.adapter_path(ra.CORS)).read_bytes() == ra.template_bytes(ra.CORS), "adapter bytes are the template")
        receipt = json.loads((root / "evidence/response-adapters/cors.json").read_text())
        check(receipt["authority"] == {"kind": "obligation", "items": ["parity:c"], "card": "t_x"}
              and receipt["replaced"] == [{"key": "quarkus.http.cors.origins", "value": "http://stale.example"}],
              "the receipt names the authority and every replaced row", receipt["authority"])
        rc, out = run(root, "--adapter", "cors")
        check(rc == 0 and "unchanged" in out and (root / ra.APP_PROPERTIES).read_text() == text, "re-running changes nothing", out)
        rc, out = run(root, "--adapter", "cors", "--check")
        check(rc == 0, "--check after install passes", out)
        # a hand-widened row after the block is caught
        (root / ra.APP_PROPERTIES).write_text(text + "quarkus.http.cors.methods=GET,POST,PUT,DELETE,PATCH\n")
        rc, out = run(root, "--adapter", "cors", "--check")
        check(rc == 1 and "quarkus.http.cors.methods" in out, "--check names a widened row", out)
        rc, out = run(root, "--adapter", "cors")
        check(rc == 0 and (root / ra.APP_PROPERTIES).read_text() == text, "re-install restores the rendering", out)
        # profile-scoped row of the family: refused, nothing written
        (root / ra.APP_PROPERTIES).write_text(text + "%dev.quarkus.http.cors.origins=*\n")
        rc, out = run(root, "--adapter", "cors")
        check(rc == 1 and "CONFIG_PROFILE_CONFLICT" in out, "a profile-scoped family row refuses", out)
        (root / ra.APP_PROPERTIES).write_text(text)
        # an adapter file with other content: refused, not overwritten
        (root / ra.adapter_path(ra.CORS)).write_text("package io.rhoai3.migration.response;\nclass SourceCorsResponseAdapter {}\n")
        rc, out = run(root, "--adapter", "cors")
        check(rc == 1 and "ADAPTER_CONFLICT" in out
              and (root / ra.adapter_path(ra.CORS)).read_text().startswith("package io.rhoai3.migration.response;\nclass"),
              "conflicting adapter content refuses and is left alone", out)
        # the harness's OWN earlier release is upgraded in place, on the record
        import hashlib
        old_bytes = b"package io.rhoai3.migration.response;\n// an earlier harness release\n"
        ra.PRIOR_TEMPLATES[ra.CORS][hashlib.sha256(old_bytes).hexdigest()] = "test release"
        (root / ra.adapter_path(ra.CORS)).write_bytes(old_bytes)
        rows_now = ra.cors_properties(ra.cors_policy(root))
        up = ra.install(root, ra.CORS, rows_now, basis={}, authority={"kind": "test"})
        check((root / ra.adapter_path(ra.CORS)).read_bytes() == ra.template_bytes(ra.CORS)
              and up.get("upgraded_from", {}).get("release") == "test release",
              "an earlier harness release is upgraded in place and recorded", up.get("upgraded_from"))
        check(all(len(k) == 64 for k in ra.PRIOR_TEMPLATES[ra.CORS]), "prior template digests are full sha256")

        # media type: decided from the obligation's own differences; the CORS block is not disturbed
        worklist(root, [cors_item, {"id": "parity:m", "rule_id": "PARITY_CONTENT_TYPE",
                                    "owed": dict(ra.contract(ra.MEDIA_TYPE), differences=[
                                        {"media_type": "application/json", "extra": [["charset", "UTF-8"]], "missing": []}])}])
        issued.unlink()
        rc, out = run(root, "--adapter", "media-type", "--parameter", "charset=ISO-8859-1", "--media-type", "text/plain")
        check(rc == 1 and "Operator step" in out, "a worker cannot choose the parameter", out)
        rc, out = run(root, "--adapter", "media-type")
        after = (root / ra.APP_PROPERTIES).read_text()
        check(rc == 0 and "rhoai3.source-media-type.parameter=charset" in after
              and "rhoai3.source-media-type.media-types=application/json" in after
              and after.startswith(text.rstrip("\n")), "media-type rows are decided by the obligation and appended", out)
        rc, out = run(root, "--adapter", "cors")
        check(rc == 0 and (root / ra.APP_PROPERTIES).read_text() == after,
              "re-installing one capability never reorders the other's block", out)
        # an Operator step is recorded as such
        rc, out = run(root, "--adapter", "cors", "--operator-step", "ADR-019")
        check(rc == 1 and "reason" in out, "an Operator step names its reason", out)
        rc, out = run(root, "--adapter", "cors", "--operator-step", "ADR-019", "--reason", "bounded Operator application on v9")
        receipt = json.loads((root / "evidence/response-adapters/cors.json").read_text())
        check(rc == 0 and receipt["authority"]["kind"] == "operator-step" and receipt["authority"]["adr"] == "ADR-019",
              "the receipt records the Operator step", receipt["authority"])

    # --- the templates: structural facts the runtime check proves ------------
    cors = ra.template_bytes(ra.CORS).decode("utf-8")
    media = ra.template_bytes(ra.MEDIA_TYPE).decode("utf-8")
    check("EARLY_PRIORITY = SecurityHandlerPriorities.CORS + 100;" in cors
          and "filters.register(ctx -> early(policy, ctx), EARLY_PRIORITY)" in cors,
          "the CORS adapter is a route filter registered above the platform's CORS filter")
    check("LATE_PRIORITY = Math.max(1, SecurityHandlerPriorities.AUTHORIZATION / 2);" in cors,
          "the deferred decisions run after the platform's authorization filter")
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", cors, flags=re.S)
    check("Content-Type" not in code and "CONTENT_TYPE" not in code, "the CORS adapter never touches Content-Type")
    check("boolean granted = response.headers().contains(ALLOW_ORIGIN);" in cors and "if (!granted || decision.kind != Kind.ALLOW)" in cors,
          "a response the platform did not grant leaves without CORS headers")
    check("ctx.put(SAME_ORIGIN, origin);\n            request.headers().remove(ORIGIN);" in cors
          and "request.headers().set(ORIGIN, sameOrigin);" in cors,
          "a same-origin request is hidden from the platform CORS filter and gets its Origin back before routing (ADR-020)")
    check(re.search(r'if \(origin == null\) \{\s*ctx\.next\(\);\s*return;', cors) is not None,
          "a request without Origin is passed through untouched")
    # H6a: the statuses the planner treats as CORS-typed come from here, and
    # the template must still write exactly them
    own = [r for r in ra.CORS_REJECTIONS if r["body"]]
    check(len(own) == 1 and 'REJECTED_BODY = "%s";' % own[0]["body"] in cors
          and "response.setStatusCode(%d).end(REJECTED_BODY);" % own[0]["status"] in cors,
          "the adapter's own refusal is the one CORS_REJECTIONS records (status and body)")
    check(ra.cors_rejection(403, own[0]["body"]).startswith("the adapter") and ra.cors_rejection(403, "")
          and ra.cors_rejection(400, "") == "" and ra.cors_rejection(403, '{"errors":[]}') != "" ,
          "cors_rejection names the producer of a 403 and nothing for another status")
    for name, text in (("cors", cors), ("media", media)):
        check(ra.adapter_type(name if name == "cors" else ra.MEDIA_TYPE).rsplit(".", 1)[-1] in text
              and "package %s;" % ra.ADAPTER_PACKAGE in text, "%s template declares its contract type" % name)
        lowered = text.lower()
        check(not any(tok in lowered for tok in ("petclinic", "owner", "vet", "errors, content-type", "9966")),
              "%s template carries no application value" % name)
    check("name.equalsIgnoreCase(parameter) && v.equalsIgnoreCase(value)" in media
          and "types.contains(parts.get(0).trim().toLowerCase(Locale.ROOT))" in media,
          "the media-type adapter removes only the decided parameter value from the decided media types")
    engine = (Path(ra.__file__)).read_text(encoding="utf-8").lower()
    check(not any(tok in engine for tok in ("petclinic", "samples.", "9966")), "the engine names no specimen")
    check(shutil.which("mvn") is None or (HERE / "runtime-check.sh").is_file(), "runtime-check.sh ships beside the installer")

    print("OK: restore-source-response-shape (%s)" % ("all checks" if not fails else "%d failure(s)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
