#!/usr/bin/env python3
"""The scenario corpus: what is replayed, against the source and the destination.

A parity claim is only as good as the sameness of the two requests. The
comparator used to send the recorded method and path with NO body, so a POST
that the source answered 201 for was replayed as an empty POST the destination
answered 400 for, and identical services compared FAIL. The fix is a corpus
that carries the complete request, and a replay that reconstructs it from the
corpus and verifies its digest before sending it.

A scenario is Operator-approved intent. It carries:

  method, path        the concrete URL, never a route pattern
  headers             what the request needs (content type, accept)
  identity            how the request authenticates, by ENV REFERENCE
  body_file/absent    the exact bytes, or an explicit statement that there
                      are none (a DELETE legitimately has no body)
  reset_before        whether the initial state is restored first
  effects             read-backs that prove what the write did; response
                      equality alone cannot (a DELETE answering 204 that
                      deleted nothing must fail its effect check)
  normalization       the permitted differences, named

Nothing here records an expected value. Expected values come only from the
captured source oracle.
"""
from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib  # noqa: E402

ensure_hermes_lib()
from planner.canonical import canonical_bytes, load_json, sha256_bytes  # noqa: E402
from planner.paths import STRUCTURE  # noqa: E402

CORPUS = Path("verification") / "scenarios" / "corpus.json"
SCENARIO_ORACLES = Path("verification") / "source-oracles" / "scenarios"
SCENARIO_PARITY = Path("verification") / "parity" / "scenarios"
SCHEMA = "rhoai3.scenario-corpus/v1"


class CorpusError(ValueError):
    pass


def scenario_slug(scenario_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(scenario_id))[:120]


def load_corpus(root: Path) -> dict[str, Any]:
    p = Path(root) / CORPUS
    if not p.is_file():
        raise CorpusError("missing %s (the Operator-approved scenario corpus)" % CORPUS)
    doc = load_json(p)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise CorpusError("%s is not a %s document" % (CORPUS, SCHEMA))
    if not doc.get("approved_by"):
        raise CorpusError("%s names no approver; scenario intent is the Operator's, not a worker's" % CORPUS)
    if doc.get("path_vars") is not None and not isinstance(doc.get("path_vars"), dict):
        raise CorpusError("%s path_vars must be a mapping of template variable to a value from the source's own seeded data" % CORPUS)
    seen: set[str] = set()
    for i, sc in enumerate(doc.get("scenarios") or []):
        if not isinstance(sc, dict):
            raise CorpusError("scenarios[%d] is not an object" % i)
        for field in ("id", "entry_point", "method", "path"):
            if not str(sc.get(field) or "").strip():
                raise CorpusError("scenarios[%d] has no %s" % (i, field))
        if sc["id"] in seen:
            raise CorpusError("scenario id %r appears twice" % sc["id"])
        seen.add(str(sc["id"]))
        if "{" in str(sc["path"]) or "*" in str(sc["path"]):
            raise CorpusError("scenario %s has path %r: a scenario carries a concrete URL, never a route pattern (the route stays in the inventory)" % (sc["id"], sc["path"]))
        if not sc.get("body_file") and not sc.get("body_absent"):
            raise CorpusError("scenario %s must either name a body_file or state body_absent: true (an absent body is a fact, not an omission)" % sc["id"])
        if sc.get("body_file") and sc.get("body_absent"):
            raise CorpusError("scenario %s both names a body and says it has none" % sc["id"])
        hdrs = {str(k).lower(): str(v) for k, v in (sc.get("headers") or {}).items()}
        if str(sc["method"]).upper() == "OPTIONS":
            # a preflight asks permission; it must ask the way a browser does
            if "origin" not in hdrs or "access-control-request-method" not in hdrs:
                raise CorpusError("scenario %s is an OPTIONS preflight and must carry Origin and Access-Control-Request-Method "
                                  "(and Access-Control-Request-Headers when the actual request sends any)" % sc["id"])
            if str((sc.get("identity") or {}).get("kind") or "none") != "none":
                raise CorpusError("scenario %s is a preflight: browsers send it without credentials, so it carries no identity" % sc["id"])
        if "origin" in hdrs and not sc.get("cors_policy"):
            raise CorpusError("scenario %s sends a cross-origin Origin and names no cors_policy; coverage is counted per policy" % sc["id"])
        if sc.get("cors_policy") and str(sc["cors_policy"]) not in {str(p.get("id")) for p in (doc.get("cors_policies") or [])}:
            raise CorpusError("scenario %s names cors_policy %r, which cors_policies does not declare" % (sc["id"], sc["cors_policy"]))
    return doc


def cors_coverage(doc: dict[str, Any], source_policies: list[str] | None = None) -> list[str]:
    """What the corpus does NOT cover of the source's CORS behaviour; [] = covered.

    Per declared policy: an actual request carrying a cross-origin Origin, and
    an OPTIONS preflight with Origin, Access-Control-Request-Method and every
    request header the policy needs. A policy the SOURCE declares that the
    corpus does not name is a gap too. Missing coverage makes parity
    INCONCLUSIVE; it is never a pass on CORS."""
    gaps: list[str] = []
    scenarios = list(doc.get("scenarios") or [])
    declared = {str(p.get("id")): p for p in (doc.get("cors_policies") or []) if p.get("id")}
    for pid, pol in sorted(declared.items()):
        mine = [sc for sc in scenarios if str(sc.get("cors_policy") or "") == pid]
        lower = [(sc, {str(k).lower(): str(v) for k, v in (sc.get("headers") or {}).items()}) for sc in mine]
        actual = [sc for sc, h in lower if str(sc.get("method")).upper() != "OPTIONS" and "origin" in h]
        need = {str(x).strip().lower() for x in (pol.get("request_headers") or []) if str(x).strip()}
        pre = [sc for sc, h in lower if str(sc.get("method")).upper() == "OPTIONS" and "origin" in h
               and "access-control-request-method" in h
               and need <= {t.strip().lower() for t in h.get("access-control-request-headers", "").split(",") if t.strip()}]
        if not actual:
            gaps.append("cors policy %s has no actual cross-origin exchange" % pid)
        if not pre:
            gaps.append("cors policy %s has no preflight carrying Origin, Access-Control-Request-Method%s"
                        % (pid, (" and " + ", ".join(sorted(need))) if need else ""))
    for sp in sorted(set(source_policies or []) - set(declared)):
        gaps.append("the source declares cors policy %s and the corpus does not cover it" % sp)
    return gaps


_CORS_API = ("org.springframework.web.cors.", "org.springframework.web.servlet.config.annotation.CorsRegistry",
             "org.springframework.web.servlet.config.annotation.CorsRegistration")


def source_cors_policies(root: Path) -> tuple[list[str], str]:
    """(the CORS policies the FROZEN source declares, why-unknown).

    Read from M1's structural model of the source, never from text: every
    distinct @CrossOrigin configuration is one policy (the same annotation on
    six controllers is one policy, a different exposedHeaders is another), and
    a type wired to Spring's CORS configuration API is a global policy. An
    unreadable model is a reason, not an empty list: "no policies" and "not
    read" must not look the same."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return [], "M1's structural model %s is not in this tree, so the source's CORS policies are unknown" % STRUCTURE
    try:
        doc = load_json(p)
    except (OSError, ValueError) as exc:
        return [], "%s could not be read: %s" % (STRUCTURE, exc)
    out: set[str] = set()
    for t in doc.get("types") or []:
        anns = list(t.get("annotations") or [])
        for m in t.get("methods") or []:
            anns.extend(m.get("annotations") or [])
        for a in anns:
            fqn = str(a.get("fqn") or a.get("name") or "")
            if fqn == "org.springframework.web.bind.annotation.CrossOrigin" or fqn.rsplit(".", 1)[-1] == "CrossOrigin":
                values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
                out.add("crossorigin:%s" % sha256_bytes(canonical_bytes(values))[:12])
        refs = [str(x) for x in (t.get("type_refs") or t.get("refs") or [])] + [str(x) for x in (t.get("supertypes") or [])]
        if any(r.startswith(_CORS_API) for r in refs):
            out.add("global:%s" % t.get("fqn"))
    return sorted(out), ""


def corpus_digest(doc: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(doc))


def scenario(doc: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    for sc in doc.get("scenarios") or []:
        if str(sc.get("id")) == scenario_id:
            return sc
    raise CorpusError("no scenario %r in %s" % (scenario_id, CORPUS))


def request_of(root: Path, sc: dict[str, Any]) -> dict[str, Any]:
    """The complete request a scenario describes, with its digest.

    The digest covers method, path, headers, identity kind and the body bytes,
    so a replay can prove it is sending what was recorded rather than
    something that merely looks like it."""
    body: bytes | None = None
    if sc.get("body_file"):
        p = Path(root) / str(sc["body_file"])
        if not p.is_file():
            raise CorpusError("scenario %s names body_file %s, which does not exist" % (sc["id"], sc["body_file"]))
        body = p.read_bytes()
    headers = {str(k): str(v) for k, v in (sc.get("headers") or {}).items()}
    identity = sc.get("identity") or {}
    ident_kind = str(identity.get("kind") or "none")
    ident_user_env = str(identity.get("user_env") or "")
    ident_password_env = str(identity.get("password_env") or "")
    # The REFERENCES travel with the request and are digested: which account a
    # request runs as is part of what makes it the same request. The values
    # never appear here. Dropping password_env made every authenticated replay
    # INCONCLUSIVE with both credentials present.
    digest_input = {
        "method": str(sc["method"]).upper(), "path": str(sc["path"]),
        "headers": dict(sorted(headers.items())),
        "identity": {"kind": ident_kind, "user_env": ident_user_env, "password_env": ident_password_env},
        "body_sha256": sha256_bytes(body) if body is not None else "",
        "body_absent": body is None,
    }
    return {
        "method": digest_input["method"], "path": digest_input["path"], "headers": headers,
        "identity": {"kind": ident_kind, "user_env": ident_user_env, "password_env": ident_password_env},
        "body": body, "body_sha256": digest_input["body_sha256"], "body_absent": body is None,
        "request_sha256": sha256_bytes(canonical_bytes(digest_input)),
    }


def auth_headers(identity: dict[str, Any]) -> tuple[dict[str, str], str]:
    """(headers, gap). Credentials come from the environment by NAME; a missing
    one is a gap the caller must report, never a silent anonymous request."""
    kind = str((identity or {}).get("kind") or "none")
    if kind in ("", "none"):
        return {}, ""
    if kind != "basic":
        return {}, "identity kind %r is not supported; the corpus must describe how the request authenticates" % kind
    user = os.environ.get(str(identity.get("user_env") or ""), "")
    password = os.environ.get(str(identity.get("password_env") or ""), "")
    if not user or not password:
        return {}, "identity needs %s and %s in the environment" % (identity.get("user_env"), identity.get("password_env"))
    token = base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
    return {"Authorization": "Basic %s" % token}, ""
