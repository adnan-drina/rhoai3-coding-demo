#!/usr/bin/env python3
"""The scenario corpus: what is replayed, against the source and the destination.

A parity claim is only as good as the sameness of the two requests. The
comparator used to send the recorded method and path with NO body, so a POST
that the source answered 201 for was replayed as an empty POST the destination
answered 400 for, and identical services compared FAIL. The fix is a corpus
that carries the complete request, and a replay that reconstructs it from the
corpus and verifies its digest before sending it.

A scenario is derived from the frozen source's own evidence (the OpenAPI
document, the seed data and M1's structure model: derive-source-scenarios.py)
and bound to the evidence bundle by digest; a hand-authored corpus that names
an ``approved_by`` is the exception, kept for a specimen whose evidence cannot
be derived. The corpus used to be "Operator-approved intent" with a signature
standing in for provenance, which is a human sign-off by another name; the
project rule is verification gates and an audit trail, never a signature. A
scenario carries:

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
from planner.canonical import canonical_bytes, digest, load_json, sha256_bytes  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, STRUCTURE  # noqa: E402

CORPUS = Path("verification") / "scenarios" / "corpus.json"
DERIVE_RECEIPT = Path("verification") / "scenarios" / "_derive.json"
DERIVATION_SCHEMA = "rhoai3.scenario-derivation/v1"
SCENARIO_ORACLES = Path("verification") / "source-oracles" / "scenarios"
SCENARIO_PARITY = Path("verification") / "parity" / "scenarios"
QUALIFICATION = SCENARIO_ORACLES / "_qualification.json"
QUALIFICATION_SCHEMA = "rhoai3.scenario-qualification/v1"
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
    # provenance last: it recomputes request digests, which assumes the
    # scenarios are well-formed (checked above)
    provenance_gap = corpus_provenance_gap(root, doc)
    if provenance_gap:
        raise CorpusError(provenance_gap)
    return doc


_PLACEHOLDER_MARKS = ("TODO", "<", ">")


def is_derived(doc: dict[str, Any]) -> bool:
    """A corpus that names its producer rather than a person."""
    return isinstance(doc.get("derived_from"), dict) and not doc.get("approved_by")


def corpus_provenance_gap(root: Path, doc: dict[str, Any]) -> str:
    """Why this corpus may NOT be trusted; "" when its provenance holds.

    Two provenances are accepted. A DERIVED corpus (``derived_from``) is bound
    to the derivation receipt beside it: the receipt says ``status: ok``, its
    ``corpus_sha256`` equals this document's digest (a derived corpus edited
    after derivation no longer matches and is refused -- the edit is a hand
    author with no name) and its ``evidence_bundle_sha256`` equals the digest
    of the bundle in this tree (a corpus derived from another frozen source
    proves nothing about this one). A hand-AUTHORED corpus names a person in
    ``approved_by``; a placeholder (``TODO``, ``<who>``) is not a name. The
    wording never says "missing": capture-source-scenarios.py reads that word
    as "no corpus at all", which is idle, and a broken binding is not idle."""
    approved = doc.get("approved_by")
    if approved:
        text = str(approved)
        if any(m in text for m in _PLACEHOLDER_MARKS):
            return "%s approved_by %r is a placeholder, not an approver" % (CORPUS, text)
        return ""
    derived = doc.get("derived_from")
    if not isinstance(derived, dict):
        return ("%s is neither derived (derived_from) nor hand-authored (approved_by); "
                "derive it from the frozen source's evidence (derive-source-scenarios.py)" % CORPUS)
    rp = Path(root) / DERIVE_RECEIPT
    if not rp.is_file():
        return "%s says it is derived but there is no derivation receipt %s beside it" % (CORPUS, DERIVE_RECEIPT)
    try:
        receipt = load_json(rp)
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (DERIVE_RECEIPT, exc)
    if not isinstance(receipt, dict) or receipt.get("schema") != DERIVATION_SCHEMA:
        return "%s is not a %s document" % (DERIVE_RECEIPT, DERIVATION_SCHEMA)
    if receipt.get("status") != "ok":
        return "%s records status %r, so the derivation did not complete" % (DERIVE_RECEIPT, receipt.get("status"))
    have = corpus_digest(doc)
    if str(receipt.get("corpus_sha256") or "") != have:
        return ("%s digest %s is not the one the derivation receipt recorded (%s): the corpus was edited after derivation, "
                "and an edit has no provenance" % (CORPUS, have[:12], str(receipt.get("corpus_sha256") or "")[:12]))
    bp = Path(root) / EVIDENCE_BUNDLE
    if not bp.is_file():
        return "%s is derived but there is no %s in this tree to bind it to" % (CORPUS, EVIDENCE_BUNDLE)
    try:
        bundle_sha = digest(load_json(bp))
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (EVIDENCE_BUNDLE, exc)
    if str(receipt.get("evidence_bundle_sha256") or "") != bundle_sha:
        return ("%s was derived against evidence bundle %s, this tree's bundle is %s: derive it again"
                % (CORPUS, str(receipt.get("evidence_bundle_sha256") or "")[:12], bundle_sha[:12]))
    # the corpus digest binds body FILENAMES only; the receipt binds the body
    # bytes and every complete request digest, and each is recomputed here (a
    # body edited after derivation passed the corpus digest: architect review
    # of 708cfef9, body_only_edit_after_derivation)
    bodies = receipt.get("bodies")
    requests = receipt.get("requests")
    if not isinstance(bodies, dict) or not isinstance(requests, dict):
        return "%s binds no body or request digests (bodies/requests); derive the corpus again" % DERIVE_RECEIPT
    for sc in doc.get("scenarios") or []:
        if not isinstance(sc, dict):
            continue
        sid = str(sc.get("id"))
        bf = str(sc.get("body_file") or "")
        if bf:
            bp = Path(root) / bf
            if not bp.is_file():
                return "body/request edited after derivation: %s names body_file %s, which is absent" % (sid, bf)
            if sha256_bytes(bp.read_bytes()) != str(bodies.get(bf) or ""):
                return "body/request edited after derivation: %s (%s) no longer has the bytes the derivation wrote" % (bf, sid)
        try:
            have = request_of(root, sc)["request_sha256"]
        except CorpusError as exc:
            return "body/request edited after derivation: %s" % exc
        if have != str(requests.get(sid) or ""):
            return "body/request edited after derivation: %s request digest %s is not the derived %s" % (sid, have[:12], str(requests.get(sid) or "")[:12])
    return ""


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


def source_cors_policy_map(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    """({policy id: {"kind", "values", "types"}}, why-unknown) -- the CORS
    policies the FROZEN source declares, with the annotation values and the
    types that carry each one.

    Read from M1's structural model of the source, never from text: every
    distinct @CrossOrigin configuration is one policy (the same annotation on
    six controllers is one policy, a different exposedHeaders is another), and
    a type wired to Spring's CORS configuration API is a global policy. The id
    is the digest of the annotation values, so the derivation, the coverage
    check and the parity receipt name the same policy. An unreadable model is
    a reason, not an empty map: "no policies" and "not read" must not look the
    same."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return {}, "M1's structural model %s is not in this tree, so the source's CORS policies are unknown" % STRUCTURE
    try:
        doc = load_json(p)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (STRUCTURE, exc)
    out: dict[str, dict[str, Any]] = {}
    for t in doc.get("types") or []:
        fqn_t = str(t.get("fqn") or "")
        anns = list(t.get("annotations") or [])
        for m in t.get("methods") or []:
            anns.extend(m.get("annotations") or [])
        for a in anns:
            fqn = str(a.get("fqn") or a.get("name") or "")
            if fqn == "org.springframework.web.bind.annotation.CrossOrigin" or fqn.rsplit(".", 1)[-1] == "CrossOrigin":
                values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
                pid = "crossorigin:%s" % sha256_bytes(canonical_bytes(values))[:12]
                row = out.setdefault(pid, {"kind": "crossorigin", "values": values, "types": []})
                if fqn_t and fqn_t not in row["types"]:
                    row["types"].append(fqn_t)
        refs = [str(x) for x in (t.get("type_refs") or t.get("refs") or [])] + [str(x) for x in (t.get("supertypes") or [])]
        if any(r.startswith(_CORS_API) for r in refs):
            out["global:%s" % fqn_t] = {"kind": "global", "values": {}, "types": [fqn_t]}
    for row in out.values():
        row["types"].sort()
    return dict(sorted(out.items())), ""


def source_cors_policies(root: Path) -> tuple[list[str], str]:
    """(the CORS policy ids the FROZEN source declares, why-unknown); see
    source_cors_policy_map."""
    policies, why = source_cors_policy_map(root)
    return sorted(policies), why


def source_exposed_headers(root: Path) -> tuple[list[str], str]:
    """(the response headers the FROZEN source exposes to cross-origin
    callers, why-unknown) -- every ``exposedHeaders`` value of every
    ``@CrossOrigin`` in M1's structure model, split on commas.

    A header the source chose to expose is part of its behaviour: petclinic
    answers a validation failure as 400 with the errors in an ``errors`` header
    and exposes exactly that header. Asserting the CORS permission set alone
    would let a destination drop or move those errors and still pass. Read
    from the model, never from text; unreadable is a reason, not an empty
    list."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return [], "M1's structural model %s is not in this tree, so the source's exposed headers are unknown" % STRUCTURE
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
            if fqn.rsplit(".", 1)[-1] != "CrossOrigin":
                continue
            values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
            raw = values.get("exposedHeaders") if isinstance(values, dict) else None
            for item in (raw if isinstance(raw, list) else [raw] if raw else []):
                for tok in str(item).split(","):
                    if tok.strip():
                        out.add(tok.strip())
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
