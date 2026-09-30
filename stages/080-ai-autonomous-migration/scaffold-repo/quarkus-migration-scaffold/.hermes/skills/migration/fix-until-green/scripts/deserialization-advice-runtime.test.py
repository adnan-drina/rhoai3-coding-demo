#!/usr/bin/env python3
"""ADR-025 (1): a request-body deserialization failure keeps the source
ExceptionControllerAdvice's response, over HTTP on the pinned platform.

The source's @ControllerAdvice/@ExceptionHandler(Exception.class) answered an
unreadable body (malformed JSON, a wrong value type) with 400, text/plain and
the JSON object {className, exMessage}. On the destination the platform's own
body reader fails BEFORE any handler and its built-in mappers answer an empty
400: the advice the compatibility layer registers never sees the failure
(M-3 2026-09-30, owner-create-malformed / owner-create-pets-not-a-list).

fixtures/handler-location-package gets the source's advice verbatim, twice:

  advice-only  the advice alone: an empty 400 (the M-3 shape, refused here)
  mapped       plus the catalog's action (compat-mapping migration_recipes
               deserialization-advice-response): a jakarta.ws.rs.ext.ExceptionMapper
               for the reader's exception that answers through the advice's own
               handler method

and the mapped variant must answer both failures with 400, the source's media
type and exactly the keys {className, exMessage} as non-empty strings -- the
VALUES are the destination's own diagnostics and are never impersonated
(ADR-025) -- while a readable body still creates (201). SKIP with the reason
when a prerequisite is missing.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_runtime_fixture as rt  # noqa: E402

FIXTURE = rt.FIXTURES / "handler-location-package"
PKG = "src/main/java/org/acme/ledger/rest/"
ADVICE = """package org.acme.ledger.rest;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@ControllerAdvice
public class ExceptionControllerAdvice {

    @ExceptionHandler(Exception.class)
    public ResponseEntity<String> exception(Exception e) {
        ObjectMapper mapper = new ObjectMapper();
        ErrorInfo errorInfo = new ErrorInfo(e);
        String respJSONstring = "{}";
        try {
            respJSONstring = mapper.writeValueAsString(errorInfo);
        } catch (JsonProcessingException e1) {
            e1.printStackTrace();
        }
        return ResponseEntity.badRequest().body(respJSONstring);
    }

    private class ErrorInfo {
        public final String className;
        public final String exMessage;

        public ErrorInfo(Exception ex) {
            this.className = ex.getClass().getName();
            this.exMessage = ex.getLocalizedMessage();
        }
    }
}
"""
# the catalog's action, written the way the row states it
MAPPER = {
    # the reader rethrows a value-type failure as Jackson's MismatchedInputException (the platform's built-in mapper
    # for that type answers an empty 400 unless the application maps it)
    "RequestBodyMismatchMapper.java": """package org.acme.ledger.rest;

import com.fasterxml.jackson.databind.exc.MismatchedInputException;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;
import org.springframework.http.ResponseEntity;

@Provider
public class RequestBodyMismatchMapper implements ExceptionMapper<MismatchedInputException> {
    @Override
    public Response toResponse(MismatchedInputException e) {
        ResponseEntity<String> answer = new ExceptionControllerAdvice().exception(e);
        return Response.status(answer.getStatusCode().value()).type("text/plain;charset=UTF-8").entity(answer.getBody()).build();
    }
}
""",
    # ...and wraps a malformed document (Jackson's StreamReadException) in a 400 WebApplicationException; every other
    # WebApplicationException keeps the response it already carries
    "RequestBodyUnreadableMapper.java": """package org.acme.ledger.rest;

import com.fasterxml.jackson.core.exc.StreamReadException;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.ExceptionMapper;
import jakarta.ws.rs.ext.Provider;
import org.springframework.http.ResponseEntity;

@Provider
public class RequestBodyUnreadableMapper implements ExceptionMapper<WebApplicationException> {
    @Override
    public Response toResponse(WebApplicationException e) {
        if (!(e.getCause() instanceof StreamReadException)) {
            return e.getResponse();
        }
        ResponseEntity<String> answer = new ExceptionControllerAdvice().exception((Exception) e.getCause());
        return Response.status(answer.getStatusCode().value()).type("text/plain;charset=UTF-8").entity(answer.getBody()).build();
    }
}
""",
}
CASES = {"malformed": b'{"name": ', "wrong-type": b'{"name": "x", "id": "not-a-number"}'}


def exercise(base: str) -> dict:
    out = {}
    for k, raw in CASES.items():
        st, h, body = rt.http("POST", base + "/api/entries", raw=raw)
        try:
            doc = json.loads(body) if body else None
        except ValueError:
            doc = body
        out[k] = {"status": st, "content_type": h.get("content-type"), "body": doc}
    st, _h, _b = rt.http("POST", base + "/api/entries", {"name": "ok"})
    out["readable"] = {"status": st}
    return out


def main() -> int:
    got = {}
    try:
        rt.need_tools("mvn", "java", "javac")
        with tempfile.TemporaryDirectory(prefix="deser-advice-rt-") as td:
            for label in ("advice-only", "mapped"):
                root = Path(td) / label
                shutil.copytree(FIXTURE, root)
                (root / PKG / "ExceptionControllerAdvice.java").write_text(ADVICE, encoding="utf-8")
                if label == "mapped":
                    for name, text in MAPPER.items():
                        (root / PKG / name).write_text(text, encoding="utf-8")
                ok, out = rt.package(root)
                if not ok:
                    print("FAIL: %s packages: %s" % (label, out[-900:]), file=sys.stderr)
                    return 1
                with rt.boot(root, "/ledger/api/entries/1/archive") as base:
                    got[label] = exercise(base + "/ledger")
    except rt.Skip as exc:
        print("SKIP: deserialization-advice-runtime: %s" % exc)
        return 0
    for k, v in got.items():
        print("%-12s %s" % (k, json.dumps(v)[:600]))
    a, m = got["advice-only"], got["mapped"]
    if any(a[k]["status"] != 400 or (a[k]["body"] not in (None, "")) for k in CASES):
        print("FAIL: the advice alone must reproduce the M-3 shape (an empty 400 from the platform)", file=sys.stderr)
        return 1
    for k in CASES:
        r = m[k]
        body = r["body"]
        if (r["status"] != 400 or not str(r["content_type"] or "").lower().startswith("text/plain")
                or not isinstance(body, dict) or sorted(body) != ["className", "exMessage"]
                or not all(isinstance(body[x], str) and body[x].strip() for x in body)):
            print("FAIL: %s: the mapped failure answers 400 text/plain with exactly non-empty {className, exMessage}: %s"
                  % (k, r), file=sys.stderr)
            return 1
        if "springframework" in body["className"]:
            print("FAIL: the destination must not impersonate the source's framework class: %s" % body, file=sys.stderr)
            return 1
    if m["readable"]["status"] != 201:
        print("FAIL: a readable body still creates: %s" % m["readable"], file=sys.stderr)
        return 1
    print("OK: deserialization-advice-runtime (pinned platform %s, packaged jar over HTTP: the source advice alone answers an "
          "empty 400 for a malformed and a wrong-type body; with the catalog's reader-exception mapper both answer 400 text/plain "
          "with non-empty {className, exMessage} of the destination's own exception (%s), and a readable body still creates)"
          % (rt.pin()["version"], ", ".join(sorted({m[k]["body"]["className"] for k in CASES}))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
