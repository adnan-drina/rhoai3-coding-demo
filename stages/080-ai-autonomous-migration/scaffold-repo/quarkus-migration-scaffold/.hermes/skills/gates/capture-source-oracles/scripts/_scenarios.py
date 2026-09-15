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

# ---------------------------------------------------------------------------
# security mode (ADR-014)
# ---------------------------------------------------------------------------
# The frozen source has a security SWITCH, and the two settings are two
# different behaviours: with it disabled every request is anonymous, with it
# enabled the same request answers 401/403 unless it carries an identity the
# policy allows. A receipt that does not say which one it judged cannot be
# read: v9's captures were taken with the switch at its default and carried no
# mode at all, so an enabled-mode destination could have been "proved" against
# anonymous expectations. So the mode travels with every artifact, the
# comparison refuses to cross modes, and the two capture sets live in separate
# directories -- reuse is prevented by the path, not by remembering.
SECURITY_MODES = ("disabled", "enabled")
DEFAULT_SECURITY_MODE = "disabled"
CAPTURE_RECEIPT_NAME = "_capture.json"
QUALIFICATION_NAME = "_qualification.json"


class CorpusError(ValueError):
    pass


def normalize_security_mode(security_mode: Any) -> str:
    """The canonical mode name; a mode nobody declared is refused, never
    silently read as the default."""
    mode = str(security_mode if security_mode is not None else DEFAULT_SECURITY_MODE).strip().lower()
    if mode not in SECURITY_MODES:
        raise CorpusError("security mode %r is not one of %s" % (security_mode, ", ".join(SECURITY_MODES)))
    return mode


def _mode_suffix(security_mode: Any = DEFAULT_SECURITY_MODE) -> str:
    """"" for the default mode, so every existing path stays exactly where it
    is and a tree captured before ADR-014 keeps working."""
    mode = normalize_security_mode(security_mode)
    return "" if mode == DEFAULT_SECURITY_MODE else "-%s" % mode


def scenario_oracles_dir(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    """Where the captures of ONE mode live. Every consumer resolves the
    directory through this function, so no two modes can ever share one."""
    return Path("verification") / "source-oracles" / ("scenarios" + _mode_suffix(security_mode))


def capture_receipt_path(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    return scenario_oracles_dir(security_mode) / CAPTURE_RECEIPT_NAME


def qualification_path(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    return scenario_oracles_dir(security_mode) / QUALIFICATION_NAME


def scenario_parity_dir(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    return Path("verification") / "parity" / ("scenarios" + _mode_suffix(security_mode))


def parity_receipt_path(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    return Path("verification") / "parity" / ("receipt%s.json" % _mode_suffix(security_mode))


def scenarios_dir(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    """Where the corpus of ONE mode lives. The default mode resolves to the
    directory CORPUS and DERIVE_RECEIPT already name, so nothing moves; the
    enabled mode gets its own, and the two corpora cannot be confused for one
    another by forgetting which was derived last."""
    return Path("verification") / ("scenarios" + _mode_suffix(security_mode))


def corpus_path(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    return scenarios_dir(security_mode) / "corpus.json"


def derive_receipt_path(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    return scenarios_dir(security_mode) / "_derive.json"


def scenario_bodies_dir(security_mode: Any = DEFAULT_SECURITY_MODE) -> Path:
    """Where a derivation writes request bodies. The enabled mode writes none:
    it REUSES the disabled corpus's requests, bodies included, so the two
    modes send the same bytes and a difference in the answer is the security
    switch and nothing else."""
    return scenarios_dir(security_mode) / "bodies"


def capture_security_mode(root: Path, security_mode: Any = DEFAULT_SECURITY_MODE) -> tuple[str, str]:
    """(the mode the capture receipt in that directory RECORDS, why-unknown).

    "" with a reason is not "disabled": a capture taken before modes were
    bound recorded no mode, and the caller decides whether that is
    compatible with what it was asked for."""
    mode = normalize_security_mode(security_mode)
    rel = capture_receipt_path(mode)
    p = Path(root) / rel
    if not p.is_file():
        return "", "no capture receipt %s in this tree" % rel.as_posix()
    try:
        doc = load_json(p)
    except (OSError, ValueError) as exc:
        return "", "%s could not be read: %s" % (rel.as_posix(), exc)
    recorded = str((doc or {}).get("security_mode") or "") if isinstance(doc, dict) else ""
    if not recorded:
        return "", "%s records no security_mode (a capture taken before the mode was bound)" % rel.as_posix()
    return recorded, ""


def scenario_slug(scenario_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(scenario_id))[:120]


def load_corpus(root: Path, security_mode: Any = DEFAULT_SECURITY_MODE) -> dict[str, Any]:
    """The corpus of one security mode. The default mode reads exactly the
    path (and states exactly the refusals) it always did."""
    corpus_rel = corpus_path(security_mode)
    p = Path(root) / corpus_rel
    if not p.is_file():
        raise CorpusError("missing %s (the Operator-approved scenario corpus)" % corpus_rel)
    doc = load_json(p)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise CorpusError("%s is not a %s document" % (corpus_rel, SCHEMA))
    if doc.get("path_vars") is not None and not isinstance(doc.get("path_vars"), dict):
        raise CorpusError("%s path_vars must be a mapping of template variable to a value from the source's own seeded data" % corpus_rel)
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
        identity_gap = identity_shape_gap(sc.get("identity"))
        if identity_gap:
            raise CorpusError("scenario %s %s" % (sc["id"], identity_gap))
        if "origin" in hdrs and not sc.get("cors_policy"):
            raise CorpusError("scenario %s sends a cross-origin Origin and names no cors_policy; coverage is counted per policy" % sc["id"])
        if sc.get("cors_policy") and str(sc["cors_policy"]) not in {str(p.get("id")) for p in (doc.get("cors_policies") or [])}:
            raise CorpusError("scenario %s names cors_policy %r, which cors_policies does not declare" % (sc["id"], sc["cors_policy"]))
    # a corpus that names a mode must be the mode that was asked for: a
    # corpus is copied, and reading the enabled one as the disabled one would
    # judge 401s against anonymous expectations (the reuse ADR-014 forbids)
    recorded = str(doc.get("security_mode") or "")
    if recorded and recorded != normalize_security_mode(security_mode):
        raise CorpusError("%s records security_mode %r; this is the %s corpus"
                          % (corpus_rel, recorded, normalize_security_mode(security_mode)))
    # provenance last: it recomputes request digests, which assumes the
    # scenarios are well-formed (checked above)
    provenance_gap = corpus_provenance_gap(root, doc, security_mode)
    if provenance_gap:
        raise CorpusError(provenance_gap)
    return doc


_PLACEHOLDER_MARKS = ("TODO", "<", ">")


def is_derived(doc: dict[str, Any]) -> bool:
    """A corpus that names its producer rather than a person."""
    return isinstance(doc.get("derived_from"), dict) and not doc.get("approved_by")


def corpus_provenance_gap(root: Path, doc: dict[str, Any], security_mode: Any = DEFAULT_SECURITY_MODE) -> str:
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
    corpus_rel = corpus_path(security_mode)
    receipt_rel = derive_receipt_path(security_mode)
    approved = doc.get("approved_by")
    if approved:
        text = str(approved)
        if any(m in text for m in _PLACEHOLDER_MARKS):
            return "%s approved_by %r is a placeholder, not an approver" % (corpus_rel, text)
        return ""
    derived = doc.get("derived_from")
    if not isinstance(derived, dict):
        return ("%s is neither derived (derived_from) nor hand-authored (approved_by); "
                "derive it from the frozen source's evidence (derive-source-scenarios.py)" % corpus_rel)
    rp = Path(root) / receipt_rel
    if not rp.is_file():
        return "%s says it is derived but there is no derivation receipt %s beside it" % (corpus_rel, receipt_rel)
    try:
        receipt = load_json(rp)
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (receipt_rel, exc)
    if not isinstance(receipt, dict) or receipt.get("schema") != DERIVATION_SCHEMA:
        return "%s is not a %s document" % (receipt_rel, DERIVATION_SCHEMA)
    if receipt.get("status") != "ok":
        return "%s records status %r, so the derivation did not complete" % (receipt_rel, receipt.get("status"))
    have = corpus_digest(doc)
    if str(receipt.get("corpus_sha256") or "") != have:
        return ("%s digest %s is not the one the derivation receipt recorded (%s): the corpus was edited after derivation, "
                "and an edit has no provenance" % (corpus_rel, have[:12], str(receipt.get("corpus_sha256") or "")[:12]))
    bp = Path(root) / EVIDENCE_BUNDLE
    if not bp.is_file():
        return "%s is derived but there is no %s in this tree to bind it to" % (corpus_rel, EVIDENCE_BUNDLE)
    try:
        bundle_sha = digest(load_json(bp))
    except (OSError, ValueError) as exc:
        return "%s could not be read: %s" % (EVIDENCE_BUNDLE, exc)
    if str(receipt.get("evidence_bundle_sha256") or "") != bundle_sha:
        return ("%s was derived against evidence bundle %s, this tree's bundle is %s: derive it again"
                % (corpus_rel, str(receipt.get("evidence_bundle_sha256") or "")[:12], bundle_sha[:12]))
    # the corpus digest binds body FILENAMES only; the receipt binds the body
    # bytes and every complete request digest, and each is recomputed here (a
    # body edited after derivation passed the corpus digest: architect review
    # of 708cfef9, body_only_edit_after_derivation)
    bodies = receipt.get("bodies")
    requests = receipt.get("requests")
    if not isinstance(bodies, dict) or not isinstance(requests, dict):
        return "%s binds no body or request digests (bodies/requests); derive the corpus again" % receipt_rel
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
    ident_ref = str(identity.get("credential_ref") or "")
    # The REFERENCES travel with the request and are digested: which account a
    # request runs as is part of what makes it the same request. The values
    # never appear here. Dropping password_env made every authenticated replay
    # INCONCLUSIVE with both credentials present.
    # ``credential_ref`` joins them only when a scenario names one: adding an
    # empty key to every request would change the digest of every scenario
    # already captured, and a mode nobody uses must not invalidate the other
    # mode's evidence.
    ident: dict[str, Any] = {"kind": ident_kind, "user_env": ident_user_env, "password_env": ident_password_env}
    if ident_ref:
        ident["credential_ref"] = ident_ref
    digest_input = {
        "method": str(sc["method"]).upper(), "path": str(sc["path"]),
        "headers": dict(sorted(headers.items())),
        "identity": dict(ident),
        "body_sha256": sha256_bytes(body) if body is not None else "",
        "body_absent": body is None,
    }
    return {
        "method": digest_input["method"], "path": digest_input["path"], "headers": headers,
        "identity": dict(ident),
        "body": body, "body_sha256": digest_input["body_sha256"], "body_absent": body is None,
        "request_sha256": sha256_bytes(canonical_bytes(digest_input)),
    }


def auth_headers(identity: dict[str, Any]) -> tuple[dict[str, str], str]:
    """(headers, gap). Credentials come from the environment by NAME; a missing
    one is a gap the caller must report, never a silent anonymous request."""
    return auth_headers_for(identity, None)


# ---------------------------------------------------------------------------
# credentials: the evidence carries the REFERENCE (ADR-014)
# ---------------------------------------------------------------------------
# Two shapes name the same thing. ``user_env``/``password_env`` names the two
# halves separately; ``credential_ref`` names ONE variable holding
# ``user:password``, which is the shape the enabled-mode capture is driven
# with (``--credential-ref NAME``) because the capture then has a single name
# to declare, record and refuse to confuse with configuration. Neither shape
# ever puts a credential -- or the Authorization header built from one -- into
# a corpus, a capture or a receipt.
CREDENTIAL_SEPARATOR = ":"
_IDENTITY_VALUE_KEYS = ("password", "secret", "token", "authorization", "credential")
_IDENTITY_KINDS = ("none", "basic")


def identity_shape_gap(identity: Any) -> str:
    """Why this ``identity`` may not be used; "" when it is well-formed.

    Accepts ``none`` and ``basic``. A ``basic`` identity names either a
    ``credential_ref`` or both ``user_env`` and ``password_env``; a key that
    would hold the credential ITSELF is refused outright, because a corpus is
    read, digested and copied into every receipt downstream of it."""
    if identity in (None, {}):
        return ""
    if not isinstance(identity, dict):
        return "identity is not an object"
    for key in sorted(identity):
        if str(key).lower() in _IDENTITY_VALUE_KEYS:
            return ("identity carries %r: evidence names the environment variable that holds a credential "
                    "(credential_ref, or user_env/password_env), never the credential" % str(key))
    kind = str(identity.get("kind") or "none")
    if kind not in _IDENTITY_KINDS:
        return "declares identity kind %r; the loader accepts %s" % (kind, " and ".join(_IDENTITY_KINDS))
    if kind == "basic" and not str(identity.get("credential_ref") or "") and not (
            str(identity.get("user_env") or "") and str(identity.get("password_env") or "")):
        return ("authenticates with basic and names no credential_ref (nor user_env and password_env); "
                "the request cannot be made without a named credential")
    return ""


def credential_env_values(credential_refs: Any) -> set[str]:
    """Every string the named credential variables hold, and each half of a
    ``user:password`` one. Used to keep a credential out of the recorded
    configuration -- the halves count because the password half is the one
    that would be pasted into a property by mistake."""
    out: set[str] = set()
    for ref in (credential_refs or []):
        raw = os.environ.get(str(ref), "")
        if not raw:
            continue
        out.add(raw)
        if CREDENTIAL_SEPARATOR in raw:
            user, _, password = raw.partition(CREDENTIAL_SEPARATOR)
            out.update(x for x in (user, password) if x)
    return out


def credential_conflicts(source_config: dict[str, str], credential_refs: Any) -> list[str]:
    """The configuration KEYS whose value is a credential the environment
    holds under one of the named references.

    ``source_config`` is recorded verbatim on the capture receipt -- that is
    what makes the mode reproducible -- so a credential passed as
    configuration would be written into the evidence. Naming the key (never
    the value) is enough to fix it."""
    values = credential_env_values(credential_refs)
    return sorted(k for k, v in (source_config or {}).items() if str(v) in values)


def parse_assignments(items: Any, what: str = "--source-config") -> dict[str, str]:
    """``KEY=VALUE`` repetitions as a mapping. The harness never knows the KEY:
    which switch turns the source's security on is an argument it records, not
    a name it carries."""
    out: dict[str, str] = {}
    for item in (items or []):
        text = str(item)
        key, sep, value = text.partition("=")
        if not sep or not key.strip():
            raise CorpusError("%s %r is not KEY=VALUE" % (what, text))
        if key.strip() in out:
            raise CorpusError("%s names %s twice" % (what, key.strip()))
        out[key.strip()] = value
    return out


def auth_headers_for(identity: dict[str, Any], credential_refs: Any = None) -> tuple[dict[str, str], str]:
    """(headers, gap) for one identity, with the credential read at request
    time from the environment.

    ``credential_refs`` is the allow-list the caller declared (None = no
    restriction, the historical behaviour). A scenario naming a reference the
    caller did not declare is a GAP, not a quiet anonymous request: the
    capture reads only variables it was told to read, so what a capture may
    touch is on its own command line and on its receipt."""
    ident = identity or {}
    kind = str(ident.get("kind") or "none")
    if kind in ("", "none"):
        return {}, ""
    if kind != "basic":
        return {}, "identity kind %r is not supported; the corpus must describe how the request authenticates" % kind
    ref = str(ident.get("credential_ref") or "")
    if ref:
        if credential_refs is not None and ref not in {str(r) for r in credential_refs}:
            return {}, ("identity names credential_ref %s, which this capture was not given (pass --credential-ref %s); "
                        "a credential is never read from an undeclared variable" % (ref, ref))
        raw = os.environ.get(ref, "")
        if not raw:
            return {}, "identity needs %s in the environment (it holds user%spassword)" % (ref, CREDENTIAL_SEPARATOR)
        user, sep, password = raw.partition(CREDENTIAL_SEPARATOR)
        if not sep or not user or not password:
            return {}, "the credential %s does not hold user%spassword" % (ref, CREDENTIAL_SEPARATOR)
    else:
        user = os.environ.get(str(ident.get("user_env") or ""), "")
        password = os.environ.get(str(ident.get("password_env") or ""), "")
        if not user or not password:
            return {}, "identity needs %s and %s in the environment" % (ident.get("user_env"), ident.get("password_env"))
    token = base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
    return {"Authorization": "Basic %s" % token}, ""


# ---------------------------------------------------------------------------
# the source's own authorization policies (ADR-014)
# ---------------------------------------------------------------------------
_AUTHZ_ANNOTATIONS = ("PreAuthorize", "RolesAllowed", "Secured")


def _authz_expression(simple: str, values: Any) -> str:
    """The policy a single annotation states, as one comparable expression.

    ``@PreAuthorize`` carries an expression; ``@RolesAllowed`` and
    ``@Secured`` carry a role SET, so their roles are sorted -- two handlers
    that list the same roles in another order state one policy, not two."""
    vals = values if isinstance(values, dict) else {}
    raw = vals.get("value")
    if raw is None and len(vals) == 1:
        raw = list(vals.values())[0]
    items = raw if isinstance(raw, list) else ([] if raw in (None, "") else [raw])
    texts = [str(x) for x in items if str(x).strip()]
    if simple == "PreAuthorize":
        return " ".join(texts).strip()
    return ", ".join(sorted(texts))


def _authz_of(annotations: Any) -> list[tuple[str, str]]:
    """[(annotation simple name, expression)] for one member or type."""
    out: list[tuple[str, str]] = []
    for a in (annotations or []):
        if not isinstance(a, dict):
            continue
        fqn = str(a.get("fqn") or a.get("name") or "")
        simple = fqn.rsplit(".", 1)[-1]
        if simple not in _AUTHZ_ANNOTATIONS:
            continue
        values = a.get("values") if a.get("values") is not None else a.get("attributes") or {}
        out.append((simple, _authz_expression(simple, values)))
    return sorted(set(out))


def source_authorization_policy_map(root: Path) -> tuple[dict[str, dict[str, Any]], str]:
    """({policy id: {"annotation", "expression", "entry_points", "types",
    "members"}}, why-unknown) -- the DISTINCT authorization policies the frozen
    source states, and which entry points each one guards.

    Read from M1's structure model (``@PreAuthorize``, ``@RolesAllowed``,
    ``@Secured``) and joined to the evidence bundle's entry points, never from
    text and never from a specimen's own role names: the id is the digest of
    the annotation and its expression, so the same policy on six handlers is
    one policy and a renamed controller states the same set. A member's own
    annotation overrides its type's, the way the platform resolves it.

    Enabled-mode scenario derivation (allowed identity / anonymous / invalid
    credentials / authenticated without the role) is a later change; it
    consumes this map, so the policies it must cover are named here rather
    than inferred from a controller's text. An unreadable model or a missing
    bundle is a REASON: "no policies" and "not read" must not look alike."""
    sp = Path(root) / STRUCTURE
    if not sp.is_file():
        return {}, "M1's structural model %s is not in this tree, so the source's authorization policies are unknown" % STRUCTURE
    try:
        model = load_json(sp)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (STRUCTURE, exc)
    bp = Path(root) / EVIDENCE_BUNDLE
    if not bp.is_file():
        return {}, ("%s is not in this tree, so which entry points the source's authorization policies guard is unknown"
                    % EVIDENCE_BUNDLE)
    try:
        bundle = load_json(bp)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (EVIDENCE_BUNDLE, exc)
    by_member: dict[tuple[str, str], list[str]] = {}
    by_type: dict[str, list[str]] = {}
    for e in (bundle.get("entry_points") or []):
        if not isinstance(e, dict):
            continue
        eid, etype, member = str(e.get("id") or ""), str(e.get("type") or ""), str(e.get("member") or "")
        if not eid or not etype:
            continue
        by_member.setdefault((etype, member), []).append(eid)
        by_type.setdefault(etype, []).append(eid)
    out: dict[str, dict[str, Any]] = {}

    def add(simple: str, expression: str, fqn: str, member: str, eids: list[str]) -> None:
        pid = "authz:%s" % sha256_bytes(canonical_bytes({"annotation": simple, "expression": expression}))[:12]
        row = out.setdefault(pid, {"annotation": simple, "expression": expression,
                                   "entry_points": [], "types": [], "members": []})
        for eid in eids:
            if eid not in row["entry_points"]:
                row["entry_points"].append(eid)
        if fqn and fqn not in row["types"]:
            row["types"].append(fqn)
        label = "%s#%s" % (fqn, member) if member else fqn
        if label not in row["members"]:
            row["members"].append(label)

    for t in (model.get("types") or []):
        if not isinstance(t, dict):
            continue
        fqn = str(t.get("fqn") or "")
        type_policies = _authz_of(t.get("annotations"))
        covered: set[str] = set()
        for m in (t.get("methods") or []):
            if not isinstance(m, dict):
                continue
            sig = str(m.get("signature") or m.get("name") or "")
            eids = by_member.get((fqn, sig)) or by_member.get((fqn, str(m.get("name") or ""))) or []
            own = _authz_of(m.get("annotations"))
            for simple, expression in (own or type_policies):
                add(simple, expression, fqn, sig, eids)
            covered.update(eids)
        # a type-level policy guards whatever the type answers that no member
        # of the model claimed (a supertype or marker entry point)
        rest = [eid for eid in (by_type.get(fqn) or []) if eid not in covered]
        for simple, expression in type_policies:
            add(simple, expression, fqn, "", rest)
    for row in out.values():
        row["entry_points"].sort()
        row["types"].sort()
        row["members"].sort()
    return dict(sorted(out.items())), ""


def source_authorization_policies(root: Path) -> tuple[list[str], str]:
    """(the authorization policy ids the FROZEN source states, why-unknown);
    see source_authorization_policy_map."""
    policies, why = source_authorization_policy_map(root)
    return sorted(policies), why


# ---------------------------------------------------------------------------
# what a policy ACCEPTS: the supported expression grammar (ADR-014)
# ---------------------------------------------------------------------------
# The enabled-mode derivation needs one thing from each policy: which roles it
# lets through. Everything else about an authorization expression -- a method
# argument, a bean call, a boolean combination -- is a question this grammar
# does not answer, and an expression it cannot read is a typed GAP with no
# scenarios rather than a guess: deriving "authenticated without the role"
# from an expression nobody parsed would name an identity the source may well
# accept, and the negative scenario would be a false expectation.
#
# Supported: hasRole(<role>), hasAnyRole(<role>, ...), and the role LIST of
# @RolesAllowed / @Secured, where <role> is a quoted literal or a constant
# reference that resolves through M1's structure model (@roles.OWNER_ADMIN,
# #roles.OWNER_ADMIN, Roles.OWNER_ADMIN, T(a.b.Roles).OWNER_ADMIN). The
# constant is read from the model's own field values, never from a specimen's
# role names: the harness does not know what a role is called.
ROLE_PREFIX = "ROLE_"
# a field's recorded constant value; M1's model carries the literal under
# whichever of these keys its extractor writes
_CONSTANT_VALUE_KEYS = ("constant", "constant_value", "value", "literal", "initializer")
_ROLE_CALLS = ("hasRole", "hasAnyRole")
_ROLE_SET_ANNOTATIONS = ("RolesAllowed", "Secured")
# the challenge a source sends with an unauthenticated refusal; asserted on
# the FIRST response of the scenarios that provoke it (redirects are never
# followed, so there is no second one to read)
CHALLENGE_HEADER = "WWW-Authenticate"


def _unquote(text: str) -> str:
    t = str(text).strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        return t[1:-1]
    return t


def source_role_constants(root: Path) -> tuple[dict[str, dict[str, str]], str]:
    """({constants type, lower-cased simple name: {field: literal}},
    why-unknown) -- the string constants M1's structure model records.

    A source that spells its roles once in a constants type and refers to them
    from every ``@PreAuthorize`` (``hasRole(@roles.OWNER_ADMIN)``) has put the
    role NAME in the model's field values; the expression alone carries only a
    reference. Two types with the same simple name and different values
    resolve to neither: an ambiguous reference is not a role."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return {}, "M1's structural model %s is not in this tree, so a role constant cannot be resolved" % STRUCTURE
    try:
        model = load_json(p)
    except (OSError, ValueError) as exc:
        return {}, "%s could not be read: %s" % (STRUCTURE, exc)
    out: dict[str, dict[str, str]] = {}
    ambiguous: set[str] = set()
    for t in (model.get("types") or []):
        if not isinstance(t, dict):
            continue
        simple = str(t.get("fqn") or "").rsplit(".", 1)[-1].strip().lower()
        if not simple:
            continue
        fields: dict[str, str] = {}
        for f in (t.get("fields") or []):
            if not isinstance(f, dict) or not str(f.get("name") or ""):
                continue
            for key in _CONSTANT_VALUE_KEYS:
                raw = f.get(key)
                if isinstance(raw, str) and _unquote(raw):
                    fields[str(f["name"])] = _unquote(raw)
                    break
        if not fields:
            continue
        if simple in out and out[simple] != fields:
            ambiguous.add(simple)
        out[simple] = fields
    for simple in ambiguous:
        out.pop(simple, None)
    return dict(sorted(out.items())), ""


def _role_token(token: str, constants: dict[str, dict[str, str]], *, literal_ok: bool) -> tuple[str, str]:
    """(the role a single argument names, why-not).

    ``literal_ok`` says whether a bare word is a role NAME: it is in a
    ``@RolesAllowed`` value list (the model records those as strings) and it
    is not inside a SpEL call, where a bare word is a reference to something
    this grammar has not read."""
    tok = str(token).strip()
    if not tok:
        return "", "an empty role"
    if tok[0] in ("'", '"'):
        role = _unquote(tok)
        return (role, "") if role else ("", "the empty string is not a role")
    ref = tok
    if ref.startswith("T(") and ")" in ref:
        ref = ref[ref.index(")") + 1:].lstrip(".")
        ref = "%s.%s" % (tok[2:tok.index(")")].rsplit(".", 1)[-1], ref) if ref else ""
    ref = ref.lstrip("@#")
    if "." in ref:
        owner, _, field = ref.rpartition(".")
        owner = owner.rsplit(".", 1)[-1].strip().lower()
        if owner in constants and field in constants[owner]:
            return constants[owner][field], ""
        return "", "the constant %s resolves to no string field of a type the structure model records" % tok
    if literal_ok:
        return tok, ""
    return "", "%s is neither a quoted role nor a constant this model resolves" % tok


def _balanced(text: str) -> bool:
    """Whether every parenthesis in ``text`` closes inside it."""
    depth = 0
    for ch in str(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _split_args(text: str) -> list[str]:
    """The top-level comma-separated arguments of a call; a comma inside
    ``T(a.b.C)`` is not an argument separator."""
    out: list[str] = []
    depth, current = 0, ""
    for ch in str(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth <= 0:
            out.append(current)
            current = ""
            continue
        current += ch
    out.append(current)
    return [a.strip() for a in out if a.strip()]


def authorization_roles(annotation: str, expression: str,
                        constants: dict[str, dict[str, str]] | None = None) -> tuple[list[str], str]:
    """(the roles this policy ACCEPTS, why-unsupported).

    "" for the reason and a non-empty list is the only readable answer; an
    expression outside the grammar returns ([], reason) and the caller records
    a typed gap rather than deriving anything for it."""
    consts = constants or {}
    text = str(expression or "").strip()
    if not text:
        return [], "the policy states no expression"
    if str(annotation) in _ROLE_SET_ANNOTATIONS:
        roles: list[str] = []
        for tok in _split_args(text):
            role, why = _role_token(tok, consts, literal_ok=True)
            if why:
                return [], why
            roles.append(role)
        return sorted(dict.fromkeys(roles)), ""
    call = re.fullmatch(r"([A-Za-z]\w*)\s*\((.*)\)", text, re.DOTALL)
    # the call has to BE the whole expression: ``hasRole('A') or hasRole('B')``
    # matches that pattern too, and reading it as one call would derive a
    # "lacks the role" identity the source in fact lets through
    if call is not None and not _balanced(call.group(2)):
        return [], "the expression combines terms (%s); a combination is not one role test" % text
    if call is None or call.group(1) not in _ROLE_CALLS:
        return [], "only %s and the role lists of %s are read" % (
            ", ".join("%s(...)" % c for c in _ROLE_CALLS), ", ".join("@%s" % a for a in _ROLE_SET_ANNOTATIONS))
    args = _split_args(call.group(2))
    if not args or (call.group(1) == "hasRole" and len(args) != 1):
        return [], "%s takes %s" % (call.group(1), "exactly one role" if call.group(1) == "hasRole" else "at least one role")
    roles = []
    for tok in args:
        role, why = _role_token(tok, consts, literal_ok=False)
        if why:
            return [], why
        roles.append(role)
    return sorted(dict.fromkeys(roles)), ""


def role_matches(held: Any, accepted: Any) -> bool:
    """Whether an identity holding ``held`` satisfies a policy accepting
    ``accepted``. A platform that prefixes authorities (Spring's ``hasRole``
    prepends ``ROLE_``) makes ``ADMIN`` and ``ROLE_ADMIN`` the same role, and
    a seeded row may be stored either way; nothing else is folded."""
    def forms(role: Any) -> set[str]:
        r = str(role or "").strip()
        if not r:
            return set()
        return {r, r[len(ROLE_PREFIX):] if r.startswith(ROLE_PREFIX) else ROLE_PREFIX + r}
    return bool(forms(held) & forms(accepted))
