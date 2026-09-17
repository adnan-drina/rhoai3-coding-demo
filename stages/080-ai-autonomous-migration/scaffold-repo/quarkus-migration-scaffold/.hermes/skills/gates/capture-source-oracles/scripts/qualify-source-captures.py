#!/usr/bin/env python3
"""Qualify the source captures against each scenario's own contract (a gate).

``CAPTURED`` records an HTTP observation, including an unexpected one: a
create the source answered 500 for is captured just as faithfully as one it
answered 201 for, and replaying either against the destination compares
nothing about what the scenario was for. The five-scenario review
(2026-09-14) listed what a capture has to SHOW before it may count as
coverage and put a person in charge of checking it; the project rule is a
gate with an audit trail instead, so each derived scenario carries a
``qualify`` block and this producer checks every capture against it.

Two results per scenario, not one (architect review of 708cfef9):

  evidence    USABLE or UNUSABLE -- can this capture be judged at all? The
              capture must exist, be CAPTURED, be bound to this corpus, this
              bundle and this very request; every retained body the contract
              reads must be present, digest-bound and complete; every
              read-back the contract reads must have been taken as the
              identity the scenario names for its effects (``effects_identity``
              -- a refused write's own caller is answered 401 by the
              read-backs too) and must have answered 2xx. Evidence
              is judged BEFORE intent: with unusable evidence the capability
              is INCONCLUSIVE, never FAIL, while ``known_failures`` still
              records what was observed (a 500 is recorded, not hidden).
  capability  PASS | FAIL | INCONCLUSIVE -- did the source demonstrate the
              operation the scenario intends? ``intent: positive`` (create,
              update, delete, cors) means it performed it; ``intent:
              negative`` (create-invalid) means it rejected as intended: the
              status, a parsed field error naming the field, and no effect.

The creation predicate is identity-aware, not count-based: the derivation
names the collection's ``identity_field`` from the OpenAPI response schema,
and a create qualifies only when exactly one entity with a NEW identity
appears, carrying the request body, every prior entity is kept unchanged, and
the Location's last path segment is that identity (a duplicate row with an
existing id and a Location pointing at 999 passed a count). No identity
field -> INCONCLUSIVE "collection identity not derivable". The ``errors``
header must parse as JSON (petclinic's BindingErrorsResponse is an array of
objects): non-JSON is INCONCLUSIVE, a parsed array without the field is FAIL.

Capability is judged over the predicates that COULD be judged: any judged one
failing is FAIL (a 400 carrying a well-formed errors header is usable
evidence, and an ``expect_status`` miss on it is a judged failure, not a
puzzle); none failing with at least one unjudgeable (``creates_one_entity``
where the document names no ``identity_field``) is INCONCLUSIVE; all judged
and passing is PASS. The unjudgeable predicate stays in the record either way.

Every record is bound to the exact capture it judged (``capture_sha256`` of
the capture file, ``request_sha256``, the corpus and bundle digests) so a
qualification that outlives its capture is stale, never reused.

Writes verification/source-oracles/scenarios/_qualification.json. A FAIL is a
RECORDED SOURCE FACT, not a refusal: the source did not demonstrate what the
scenario intends, which M4 turns into a coverage gap and which never becomes a
destination repair card. So exit 0 whenever a bound qualification document was
written, whatever its verdict, and 1 only on a refusal to JUDGE -- no corpus,
a corpus that is neither derived nor authored, a corpus whose digests no
longer bind, or no capture at all to judge. 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib, normalize_body, origin_of  # noqa: E402
from _source_store import compare_observations  # noqa: E402
from _scenarios import (CorpusError, DEFAULT_SECURITY_MODE, QUALIFICATION, QUALIFICATION_SCHEMA, SCENARIO_ORACLES,  # noqa: E402,F401
                        SECURITY_MODES, capture_receipt_path, capture_security_mode, capture_security_variant, corpus_digest,
                        effects_identity_of, load_corpus, normalize_security_mode, normalized_identity,
                        normalize_variant, qualification_path, request_of, scenario_oracles_dir, scenario_slug)

ensure_hermes_lib()
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402

PRODUCER = "qualify-source-captures.py"
# The capture directory this process is judging. One run judges ONE security
# mode (ADR-014); main() rebinds it from --security-mode so the retained-body
# fallback never reaches into the other mode's evidence.
_ORACLES_DIR = SCENARIO_ORACLES
KNOWN_CHECKS = ("expect_status", "expect_status_class", "usable_first_response", "location", "after_contains_body", "before_lacks_body",
                "creates_one_entity", "after_equals_before", "errors_header_names_field", "after_effect_status", "cors_allow_origin",
                "cors_expose_headers", "cors_allow_method", "cors_allow_headers", "before_reads_usable",
                "cors_browser_access", "db_unchanged")
CONTRACT_KEYS = ("intent", "identity_field")  # parameters of the contract, not checks
BODY_CHECKS = ("after_contains_body", "before_lacks_body", "creates_one_entity", "after_equals_before", "before_reads_usable")
# checks that read a read-back ROW without reading its body: they are about
# the state a request left just as much, so they are judged against the same
# identity question (whose probes these are)
READ_BACK_CHECKS = ("after_effect_status",)
HEADER_CHECKS = ("location", "errors_header_names_field", "cors_allow_origin", "cors_expose_headers", "cors_allow_method", "cors_allow_headers",
                 "cors_browser_access")
_STATUS_CLASS_RE = re.compile(r"^([1-5])xx$", re.IGNORECASE)


def _capture_idle_reason(root: Path, security_mode: str, variant: str = "") -> str:
    """Why this mode's capture recorded that it captured nothing; "" when it
    ran (or when there is no receipt at all, which is a different thing and
    stays the refusal it was)."""
    p = Path(root) / capture_receipt_path(security_mode, variant)
    if not p.is_file():
        return ""
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return ""
    if not isinstance(doc, dict) or str(doc.get("status") or "") != "idle":
        return ""
    return str(doc.get("reason") or "") or "the capture of this mode recorded that it captured nothing"


class Unusable(Exception):
    """Evidence that cannot be judged; the reason is the message."""


class Unjudgeable(Unusable):
    """A PREDICATE that cannot be judged although the evidence is sound: the
    document names no ``identity_field``, the contract names a check this gate
    does not implement. It leaves the capture usable, so a judged predicate
    that FAILS beside it still makes the verdict FAIL -- an unanswerable
    question about a create does not un-answer the answered ones."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _identity_label(identity: Any) -> str:
    """How an identity is SAID in a reason: by the variable holding its
    credential, never by what the variable holds."""
    ref = str((identity or {}).get("credential_ref") or "")
    if ref:
        return "credential_ref %s" % ref
    pair = [str((identity or {}).get(k) or "") for k in ("user_env", "password_env")]
    if all(pair):
        return "%s/%s" % tuple(pair)
    return "the request's own identity"


def _header(headers: Any, name: str) -> str | None:
    if not isinstance(headers, dict):
        return None
    for k, v in headers.items():
        if str(k).lower() == name.lower():
            return None if v is None else str(v)
    return None


def _tokens(value: str | None) -> set[str]:
    return {t.strip().lower() for t in str(value or "").split(",") if t.strip()}


def _body_path(root: Path, scenario_id: str, recorded: str) -> Path | None:
    p = Path(recorded)
    if p.is_file():
        return p
    if (root / recorded).is_file():
        return root / recorded
    alt = root / _ORACLES_DIR / "bodies" / scenario_slug(scenario_id) / p.name
    return alt if alt.is_file() else None


def retained_body(root: Path, scenario_id: str, row: dict[str, Any], what: str) -> bytes:
    """The retained bytes of a capture row, verified against the digests the
    capture recorded: the file digest (retained_sha256), the complete-body
    digest (raw_body_sha256, so the body is whole) and the row's parity
    digest (body_sha256, canonical JSON for JSON) recomputed from the bytes.
    Anything that does not add up is UNUSABLE evidence, not a body."""
    ev = row.get("evidence") if isinstance(row, dict) else None
    if not isinstance(ev, dict) or not ev.get("body_file"):
        raise Unusable("%s has no retained body (a capture that predates retention cannot be qualified)" % what)
    p = _body_path(root, scenario_id, str(ev["body_file"]))
    if p is None:
        raise Unusable("%s retained body %s is absent" % (what, ev["body_file"]))
    if not ev.get("retained_sha256") or not ev.get("raw_body_sha256"):
        raise Unusable("%s retained body not digest-bound (no retained_sha256/raw_body_sha256 on the evidence row)" % what)
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != ev["retained_sha256"]:
        raise Unusable("%s retained body digest %s is not the recorded %s" % (what, sha[:12], str(ev["retained_sha256"])[:12]))
    if ev.get("truncated"):
        raise Unusable("%s retained body is truncated (%s of %s bytes); a partial list proves neither presence nor absence"
                       % (what, ev.get("retained_bytes"), ev.get("body_bytes")))
    if sha != ev["raw_body_sha256"]:
        raise Unusable("%s retained body is not the complete response (digest %s vs raw %s)" % (what, sha[:12], str(ev["raw_body_sha256"])[:12]))
    want = str(row.get("body_sha256") or ev.get("body_sha256") or "")
    if want and normalize_body(raw, "")[1] != want:
        raise Unusable("%s retained body does not normalize to the recorded body_sha256 %s" % (what, want[:12]))
    return raw


def _read_back_body(root: Path, sid: str, row: dict[str, Any], what: str) -> Any:
    """A read-back the contract reads must have answered 2xx with a verified,
    complete retained JSON body."""
    status = int(row.get("status") or 0)
    if not 200 <= status < 300:
        raise Unusable("%s answered %s, not 2xx; its body cannot stand for the collection" % (what, row.get("status")))
    raw = retained_body(root, sid, row, what)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Unusable("%s retained body is not JSON" % what)


def _objects(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            out.extend(_objects(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_objects(v))
    return out


def _entities(parsed: Any) -> list[dict[str, Any]]:
    """The entities a collection read-back lists: the top-level array of
    objects, or the first array-of-objects value of an envelope object."""
    if isinstance(parsed, list):
        return [o for o in parsed if isinstance(o, dict)]
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list) and v and all(isinstance(o, dict) for o in v):
                return list(v)
        return [parsed]
    return []


def _matches(obj: dict[str, Any], body: dict[str, Any]) -> bool:
    return all(k in obj and obj[k] == v for k, v in body.items())


def _request_body(root: Path, sc: dict[str, Any]) -> dict[str, Any]:
    if not sc.get("body_file"):
        raise Unusable("the scenario sends no body, so nothing can be looked for in the read-back")
    p = root / str(sc["body_file"])
    if not p.is_file():
        raise Unusable("body_file %s is absent" % sc["body_file"])
    body = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise Unusable("body_file %s is not a JSON object" % sc["body_file"])
    return body


def _rows(cap: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in (cap.get(key) or []) if isinstance(r, dict)}


def _errors_elements(value: str) -> list[dict[str, Any]]:
    """petclinic's BindingErrorsResponse: a JSON array of objects. Anything
    that does not parse is UNUSABLE (not a rejection the gate can read)."""
    try:
        parsed = json.loads(value)
    except ValueError:
        raise Unusable("errors header not parseable as JSON: %r" % value[:120])
    return _objects(parsed)


def _status_class(want: Any) -> tuple[int, int]:
    """(low, high) of a ``4xx``-style class; the contract states what it means
    by "the source refused", and an unreadable class is not a silent pass."""
    m = _STATUS_CLASS_RE.match(str(want or ""))
    if m is None:
        raise Unjudgeable("expect_status_class %r is not a status class like '4xx'" % want)
    return int(m.group(1)) * 100, int(m.group(1)) * 100 + 99


def _expected(q: dict[str, Any], status: int) -> bool:
    """Whether the contract names this status at all (list or class)."""
    if "expect_status" in q:
        allowed = q["expect_status"] if isinstance(q["expect_status"], list) else [q["expect_status"]]
        if any(int(x) == status for x in allowed):
            return True
    if "expect_status_class" in q:
        try:
            low, high = _status_class(q["expect_status_class"])
        except Unjudgeable:
            return False
        return low <= status <= high
    return False


def _creates_one_entity(root: Path, sid: str, sc: dict[str, Any], cap: dict[str, Any], identity: str | None) -> tuple[bool, str]:
    if not identity:
        raise Unjudgeable("collection identity not derivable (identity_field null); a create cannot be judged")
    body = _request_body(root, sc)
    before, after = _rows(cap, "before"), _rows(cap, "effects")
    if not before or not after or set(before) != set(after):
        raise Unusable("before and after read-backs do not pair up")
    problems: list[str] = []
    new_identity: Any = None
    for eid in sorted(before):
        b_ents = _entities(_read_back_body(root, sid, before[eid], "before %s" % eid))
        a_ents = _entities(_read_back_body(root, sid, after[eid], "after %s" % eid))
        if any(identity not in o for o in b_ents + a_ents):
            raise Unusable("%s: an entity carries no %r identity; the read-back cannot be judged by identity" % (eid, identity))
        before_ids = {json.dumps(o[identity], sort_keys=True) for o in b_ents}
        new = [o for o in a_ents if json.dumps(o[identity], sort_keys=True) not in before_ids]
        if len(new) != 1:
            problems.append("%s: %d entit%s with a new %s after the create, expected exactly one" % (eid, len(new), "y" if len(new) == 1 else "ies", identity))
        else:
            new_identity = new[0][identity]
            if not _matches(new[0], body):
                missing = sorted(k for k, v in body.items() if k not in new[0] or new[0][k] != v)
                problems.append("%s: the new entity %s does not carry the request body (differs in %s)" % (eid, json.dumps(new_identity), ", ".join(missing)))
        after_by_id = {}
        for o in a_ents:
            after_by_id.setdefault(json.dumps(o[identity], sort_keys=True), []).append(o)
        for o in b_ents:
            key = json.dumps(o[identity], sort_keys=True)
            kept = after_by_id.get(key) or []
            if len(kept) != 1 or kept[0] != o:
                problems.append("%s: prior entity %s is %s after the create" % (eid, json.dumps(o[identity]), "duplicated" if len(kept) > 1 else "changed" if kept else "gone"))
    loc = _header((cap.get("response") or {}).get("headers"), "Location")
    last = urllib.parse.urlsplit(loc or "").path.rstrip("/").rsplit("/", 1)[-1]
    if new_identity is not None:
        if last != str(new_identity):
            problems.append("Location %r does not end with the new identity %s" % (loc, json.dumps(new_identity)))
    else:
        problems.append("Location %r names no newly created entity (last segment %r)" % (loc, last))
    if problems:
        return False, "; ".join(problems)
    return True, "exactly one new entity %s carrying the body, prior entities kept, Location names it" % json.dumps(new_identity)


def qualify_scenario(root: Path, sc: dict[str, Any], cap: dict[str, Any] | None, corpus_sha: str, bundle_sha: str,
                     capture_sha: str) -> dict[str, Any]:
    sid = str(sc["id"])
    q = sc.get("qualify")
    intent = str((q or {}).get("intent") or "positive")
    checks: list[dict[str, Any]] = []
    evidence_reasons: list[str] = []
    unjudged: list[str] = []
    known_failures: list[str] = []
    try:
        request_sha = request_of(root, sc)["request_sha256"]
    except CorpusError as exc:
        request_sha = ""
        evidence_reasons.append(str(exc))
    base = {"intent": intent, "capture_sha256": capture_sha, "request_sha256": request_sha,
            "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha}

    if str(sc.get("scenario_type") or ""):
        base["scenario_type"] = str(sc["scenario_type"])

    def finish(capability: str, reason: str) -> dict[str, Any]:
        usable = not evidence_reasons
        return dict(base, verdict=capability, capability=capability,
                    evidence={"status": "USABLE" if usable else "UNUSABLE", "reasons": list(evidence_reasons)},
                    known_failures=list(known_failures), unjudged=list(unjudged), reason=reason[:400], checks=checks)

    def record(name: str, ok: bool | None, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        if ok is False:
            known_failures.append("%s: %s" % (name, detail))

    if not isinstance(q, dict) or not q:
        evidence_reasons.append("no qualification contract (the scenario carries no qualify block)")
        return finish("INCONCLUSIVE", evidence_reasons[0])
    # ---- evidence first: is this the capture of THIS scenario, and whole? ----
    if cap is None:
        evidence_reasons.append("no capture")
        return finish("INCONCLUSIVE", "no capture")
    if str(cap.get("status")) != "CAPTURED":
        evidence_reasons.append("capture status %s: %s" % (cap.get("status"), cap.get("reason") or ""))
        return finish("INCONCLUSIVE", evidence_reasons[-1])
    if str(cap.get("corpus_sha256") or "") != corpus_sha:
        evidence_reasons.append("capture bound to corpus %s, this is %s" % (str(cap.get("corpus_sha256"))[:12], corpus_sha[:12]))
    if bundle_sha and str(cap.get("evidence_bundle_sha256") or "") != bundle_sha:
        evidence_reasons.append("capture bound to evidence bundle %s, this tree's is %s" % (str(cap.get("evidence_bundle_sha256"))[:12], bundle_sha[:12]))
    recorded_req = str((cap.get("request") or {}).get("request_sha256") or "")
    if request_sha and recorded_req != request_sha:
        evidence_reasons.append("capture answers request %s, the scenario describes %s (not this scenario's capture)" % (recorded_req[:12] or "(none)", request_sha[:12]))
    # WHOSE read-backs these are. A contract that reads them is judging the
    # state a request left, and a capture that took them as somebody else --
    # the refused caller, whose probes answer 401 -- is evidence about another
    # question. Named here rather than left to surface as "answered 401, not
    # 2xx", which says what happened and not why.
    declared_effects_identity = effects_identity_of(sc)
    want_effects_identity = normalized_identity(declared_effects_identity) if declared_effects_identity is not None else {}
    got_effects_identity = cap.get("effects_identity") if isinstance(cap.get("effects_identity"), dict) else {}
    if any(k in q for k in BODY_CHECKS + READ_BACK_CHECKS) and want_effects_identity != got_effects_identity:
        evidence_reasons.append("the scenario takes its read-backs as %s and the capture took them as %s; re-capture the source so "
                                "the read-backs are the ones the contract judges"
                                % (_identity_label(want_effects_identity), _identity_label(got_effects_identity)))
    if evidence_reasons:
        return finish("INCONCLUSIVE", "; ".join(evidence_reasons))
    resp = cap.get("response") or {}
    headers = resp.get("headers")
    req_headers = (cap.get("request") or {}).get("headers") or sc.get("headers") or {}
    before, after = _rows(cap, "before"), _rows(cap, "effects")
    if any(k in q for k in HEADER_CHECKS) and not isinstance(headers, dict):
        evidence_reasons.append("the capture recorded no header map")
    # a server error the contract does not name is not the operation's answer:
    # nothing else in the contract can be read off it, so the evidence is
    # UNUSABLE and the capability INCONCLUSIVE -- with the 500 on the record
    status = int(resp.get("status") or 0)
    if 500 <= status < 600 and not _expected(q, status):
        record("expect_status", False, "status %s, expected one of %s"
               % (status, q.get("expect_status") if "expect_status" in q else q.get("expect_status_class") or "a non-5xx answer"))
        evidence_reasons.append("the source answered %s, which the contract does not name; a server error is not the operation's answer" % status)
        return finish("INCONCLUSIVE", "; ".join(evidence_reasons))
    # ---- the checks; an Unusable raised inside is evidence, not a verdict ----
    for name, want in q.items():
        if name in CONTRACT_KEYS:
            continue
        try:
            if name == "expect_status":
                allowed = [int(x) for x in (want if isinstance(want, list) else [want])]
                record(name, int(resp.get("status") or 0) in allowed, "status %s, expected one of %s" % (resp.get("status"), allowed))
            elif name == "expect_status_class":
                low, high = _status_class(want)
                got = int(resp.get("status") or 0)
                record(name, low <= got <= high, "status %s, expected any %s" % (resp.get("status"), str(want)))
            elif name == "usable_first_response":
                # A mapping that declares no HTTP method answers a GET, but
                # WHICH answer is its own: petclinic's root mapping redirects
                # (3xx), another such mapping renders (2xx). Neither class is
                # knowable a priori, so the contract asks only what evidence
                # can settle -- a first response the comparator can compare --
                # and the class the source actually gave is RECORDED. A 5xx is
                # already unusable evidence above; an answer that never came is
                # unusable here.
                if want is not True:
                    raise Unjudgeable("usable_first_response must be true; the contract states no expected status class")
                got = int(resp.get("status") or 0)
                if not got:
                    raise Unusable("the capture records no first response (%s)" % (resp.get("error") or "no status"))
                observed = "%dxx" % (got // 100)
                checks.append({"check": name, "ok": True, "observed_status_class": observed,
                               "detail": "first response %s (%s), redirects not followed; the contract expects no status class and records this one" % (got, observed)})
            elif name == "location":
                if want != "absolute-under-base":
                    raise Unjudgeable("unknown location rule %r" % want)
                if not isinstance(headers, dict):
                    raise Unusable("the capture recorded no header map")
                loc = _header(headers, "Location")
                base_url = str((cap.get("source") or {}).get("base_url") or "")
                base_origin = origin_of(base_url)
                base_path = urllib.parse.urlsplit(base_url).path.rstrip("/")
                if not base_origin:
                    raise Unusable("the capture records no source.base_url to judge Location against")
                parts = urllib.parse.urlsplit(loc or "")
                absolute = bool(parts.scheme and parts.netloc)
                under = (parts.path == base_path or parts.path.startswith(base_path + "/")) if base_path else True
                ok = absolute and origin_of(loc or "") == base_origin and under
                record(name, ok, "Location %r%s; base %s" % (loc, "" if absolute else " is not absolute", base_url))
            elif name == "creates_one_entity":
                ok, detail = _creates_one_entity(root, sid, sc, cap, q.get("identity_field"))
                record(name, ok, detail)
            elif name == "after_contains_body":
                body = _request_body(root, sc)
                if not after:
                    raise Unusable("the capture recorded no after-effects")
                missing = [eid for eid, row in sorted(after.items()) if not any(_matches(o, body) for o in _objects(_read_back_body(root, sid, row, "after %s" % eid)))]
                record(name, not missing, "the request body %s %s" % ("is absent from" if missing else "is present in", ", ".join(missing) or ", ".join(sorted(after))))
            elif name == "before_lacks_body":
                body = _request_body(root, sc)
                if not before:
                    raise Unusable("the capture recorded no before read-backs")
                present = [eid for eid, row in sorted(before.items()) if any(_matches(o, body) for o in _objects(_read_back_body(root, sid, row, "before %s" % eid)))]
                record(name, not present, "the request body %s before the request (%s)" % ("was already present" if present else "was absent", ", ".join(present) or ", ".join(sorted(before))))
            elif name == "after_equals_before":
                if not before or not after or set(before) != set(after):
                    raise Unusable("before and after read-backs do not pair up")
                for eid in sorted(before):
                    _read_back_body(root, sid, before[eid], "before %s" % eid)
                    _read_back_body(root, sid, after[eid], "after %s" % eid)
                diff = [eid for eid in sorted(before) if before[eid].get("body_sha256") != after[eid].get("body_sha256") or before[eid].get("status") != after[eid].get("status")]
                record(name, not diff, "read-backs %s" % ("changed: " + ", ".join(diff) if diff else "unchanged: " + ", ".join(sorted(before))))
            elif name == "cors_browser_access":
                # RECORDED, not expected: whether the source's answer lets a
                # browser complete this exchange. A matched rejection is
                # parity; it is not a demonstrated permission (ADR-020)
                if want is not True:
                    raise Unjudgeable("cors_browser_access must be true")
                if not isinstance(headers, dict):
                    raise Unusable("the capture recorded no header map")
                sent = _header(req_headers, "Origin")
                got = int(resp.get("status") or 0)
                allow = _header(headers, "Access-Control-Allow-Origin")
                why_not: list[str] = []
                if not 200 <= got < 300:
                    why_not.append("status %s" % got)
                if not sent or allow not in (sent, "*"):
                    why_not.append("Access-Control-Allow-Origin %r for Origin %r" % (allow, sent))
                if str(sc.get("method") or "").upper() == "OPTIONS":
                    wanted = str(_header(req_headers, "Access-Control-Request-Method") or "").lower()
                    methods = _tokens(_header(headers, "Access-Control-Allow-Methods"))
                    if wanted and wanted not in methods and "*" not in methods:
                        why_not.append("Access-Control-Allow-Methods %r lacks %s" % (_header(headers, "Access-Control-Allow-Methods"), wanted))
                    need = _tokens(_header(req_headers, "Access-Control-Request-Headers"))
                    have = _tokens(_header(headers, "Access-Control-Allow-Headers"))
                    if need and not need <= have and "*" not in have:
                        why_not.append("Access-Control-Allow-Headers %r lacks %s" % (_header(headers, "Access-Control-Allow-Headers"),
                                                                                    sorted(need - have)))
                outcome = "permits" if not why_not else "prevents"
                base["browser_access"] = outcome
                checks.append({"check": name, "ok": True, "observed_browser_access": outcome,
                               "detail": ("the source's answer lets a browser complete the exchange" if not why_not else
                                          "the source PREVENTS the browser exchange (%s); matching it is parity, not a "
                                          "demonstrated permission" % "; ".join(why_not))})
            elif name == "db_unchanged":
                # ADR-021: the no-effect claim is a DATABASE claim over the
                # declared scope -- two retained observations, before and
                # after the request, compared again here from their bytes.
                # The HTTP read-backs are kept beside it and never qualify it.
                if want is not True:
                    raise Unjudgeable("db_unchanged must be true")
                se = cap.get("source_effects") if isinstance(cap.get("source_effects"), dict) else {}
                db = se.get("db") if isinstance(se.get("db"), dict) else {}
                files = []
                for which in ("before", "after"):
                    row = db.get(which) if isinstance(db.get(which), dict) else {}
                    fp = Path(str(row.get("path") or ""))
                    fp = fp if fp.is_absolute() else root / fp
                    if not row or not fp.is_file():
                        raise Unusable("no %s database observation of the declared scope is retained (%s)"
                                       % (which, se.get("reason") or "the capture records none"))
                    if hashlib.sha256(fp.read_bytes()).hexdigest() != str(row.get("sha256") or ""):
                        raise Unusable("the %s database observation is not the one the capture digested" % which)
                    files.append(fp)
                again = compare_observations(files[0], files[1])
                recorded = (db.get("comparison") or {}).get("equal")
                if recorded is not again["equal"]:
                    raise Unusable("the recorded database comparison (%s) is not what its observations show (%s)"
                                   % (recorded, again["equal"]))
                http_same = (bool(before) and set(before) == set(after)
                             and all(before[k].get("body_sha256") == after[k].get("body_sha256")
                                     and before[k].get("status") == after[k].get("status") for k in before))
                detail = ("the declared scope (%s) is unchanged across the request" % ", ".join(again["tables"])
                          if again["equal"] else
                          "the request changed the database: %s" % "; ".join(
                              "%s %d→%d rows" % (t, d["before_count"], d["after_count"])
                              for t, d in sorted(again["differences"].items())))
                if after and http_same != again["equal"]:
                    detail += ("; the HTTP read-backs say %s -- the database evidence decides, and both are kept"
                               % ("unchanged" if http_same else "changed"))
                record(name, again["equal"], detail)
            elif name == "before_reads_usable":
                # revert-then-read: the source's after reads cannot be taken
                # (its database is restored only by a restart), so what the
                # destination's post-revert reads are judged against is these
                # baseline reads -- each declared one present, 2xx, and whole
                if want is not True:
                    raise Unjudgeable("before_reads_usable must be true")
                declared = sorted(str(e.get("id") or e.get("path")) for e in (sc.get("effects") or []))
                if not declared or sorted(before) != declared:
                    raise Unusable("the baseline read-backs %s are not the declared %s" % (sorted(before), declared))
                for eid in declared:
                    _read_back_body(root, sid, before[eid], "baseline %s" % eid)
                record(name, True, "baseline read-backs recorded: %s" % ", ".join(declared))
            elif name == "errors_header_names_field":
                if not isinstance(headers, dict):
                    raise Unusable("the capture recorded no header map")
                val = _header(headers, "errors")
                if not val:
                    record(name, False, "errors header absent")
                    continue
                elements = _errors_elements(val)
                hit = any(any(str(v) == str(want) for v in el.values()) for el in elements)
                record(name, hit, "errors header %s an element naming %s (%d element(s))" % ("carries" if hit else "carries no", want, len(elements)))
            elif name == "after_effect_status":
                if not isinstance(want, dict):
                    raise Unjudgeable("after_effect_status must map effect id to status")
                bad = []
                for eid, status in sorted(want.items()):
                    row = after.get(str(eid))
                    if row is None:
                        raise Unusable("effect %s was not captured" % eid)
                    if int(row.get("status") or 0) != int(status):
                        bad.append("%s answered %s, expected %s" % (eid, row.get("status"), status))
                record(name, not bad, "; ".join(bad) or "effects answered as the contract names")
            elif name == "cors_allow_origin":
                if not isinstance(headers, dict):
                    raise Unusable("the capture recorded no header map")
                sent = _header(req_headers, "Origin")
                got = _header(headers, "Access-Control-Allow-Origin")
                record(name, bool(sent) and got in (sent, "*"), "Access-Control-Allow-Origin %r for Origin %r" % (got, sent))
            elif name in ("cors_expose_headers", "cors_allow_headers"):
                if not isinstance(headers, dict):
                    raise Unusable("the capture recorded no header map")
                hdr = "Access-Control-Expose-Headers" if name == "cors_expose_headers" else "Access-Control-Allow-Headers"
                got = _tokens(_header(headers, hdr))
                need = {str(x).strip().lower() for x in (want or [])}
                record(name, need <= got, "%s %r %s %s" % (hdr, _header(headers, hdr), "covers" if need <= got else "lacks", sorted(need if need <= got else need - got)))
            elif name == "cors_allow_method":
                if not isinstance(headers, dict):
                    raise Unusable("the capture recorded no header map")
                got = _tokens(_header(headers, "Access-Control-Allow-Methods"))
                record(name, str(want).lower() in got, "Access-Control-Allow-Methods %r, need %s" % (_header(headers, "Access-Control-Allow-Methods"), want))
            else:
                raise Unjudgeable("unknown qualification check %r" % name)
        except Unjudgeable as exc:
            # the evidence is sound; this one predicate has no answer
            unjudged.append("%s: %s" % (name, exc))
            checks.append({"check": name, "ok": None, "detail": str(exc)})
        except Unusable as exc:
            evidence_reasons.append("%s: %s" % (name, exc))
            checks.append({"check": name, "ok": None, "detail": str(exc)})
    if evidence_reasons:
        # unusable evidence: INCONCLUSIVE, never FAIL; the observed failures
        # (a 500, a missing header) stay on the record in known_failures
        return finish("INCONCLUSIVE", "; ".join(evidence_reasons))
    if known_failures:
        # a judged predicate failed. An unjudgeable one beside it does not
        # soften that: the source answered, and the answer was not the
        # contract's (v9: a 400 with a well-formed errors header against a
        # create whose identity_field the document never named was reported
        # INCONCLUSIVE, so the mismatch went unrecorded)
        return finish("FAIL", "; ".join(known_failures + unjudged))
    if unjudged:
        return finish("INCONCLUSIVE", "; ".join(unjudged))
    return finish("PASS", "")


def main(argv: list[str] | None = None) -> int:
    global _ORACLES_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--security-mode", choices=list(SECURITY_MODES), default=DEFAULT_SECURITY_MODE,
                    help="which security mode's captures to judge (ADR-014). The mode the capture receipt RECORDS wins: "
                         "a directory whose captures were taken in another mode is a refusal, never a re-judgement")
    ap.add_argument("--fixture-variant", default="", metavar="NAME",
                    help="judge the captures of a declared fixture VARIANT of that mode's baseline (ADR-014), under the "
                         "variant's own directory; the variant the capture receipt RECORDS wins the same way the mode does")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        security_mode = normalize_security_mode(args.security_mode)
        variant = normalize_variant(args.fixture_variant, security_mode)
    except CorpusError as exc:
        print("REFUSE: QUALIFY_CAPTURES %s" % exc, file=sys.stderr)
        return 1
    _ORACLES_DIR = scenario_oracles_dir(security_mode, variant)
    oracles_dir = _ORACLES_DIR
    # The mode is read from the capture receipt, not assumed from the
    # argument: a qualification names the mode it judged, and a directory
    # holding another mode's captures is a refusal to judge. A capture taken
    # before modes were bound records none, and is judged as what it was
    # asked for -- with the mode still written down.
    recorded_mode, mode_why = capture_security_mode(root, security_mode, variant)
    if recorded_mode and recorded_mode != security_mode:
        print("REFUSE: QUALIFY_CAPTURES mode mismatch: %s holds captures taken in the %s mode, this run was asked for %s"
              % (oracles_dir.as_posix(), recorded_mode, security_mode), file=sys.stderr)
        return 1
    # ... and the same for the fixture variant: a capture taken against a
    # varied dataset is evidence about that dataset, and judging it as the
    # baseline's would contract it against expectations nobody measured
    recorded_variant, variant_why = capture_security_variant(root, security_mode, variant)
    if variant_why:
        print("REFUSE: QUALIFY_CAPTURES variant mismatch: %s" % variant_why, file=sys.stderr)
        return 1
    # The capture of this mode may have been IDLE: a security section nobody
    # declared, or a declared credential the workspace does not hold. That is
    # a recorded blocker (ADR-014), and there is nothing to judge -- so the
    # qualification says so and carries the capture's own reason forward,
    # rather than refusing over a corpus that was never derived. A judgement
    # is never invented for it: the verdict is INCONCLUSIVE with no scenario.
    idle_why = _capture_idle_reason(root, security_mode, variant)
    if idle_why:
        out = root / qualification_path(security_mode, variant)
        write_canonical(out, {
            "schema": QUALIFICATION_SCHEMA, "producer": PRODUCER, "at": _now(),
            "corpus_sha256": "", "evidence_bundle_sha256": "",
            "security_mode": security_mode, "security_mode_recorded": recorded_mode, "security_mode_note": "" if recorded_mode else mode_why,
        "security_variant": variant, "security_variant_recorded": recorded_variant,
            "status": "idle", "reason": idle_why,
            "scenarios": {}, "total": 0, "not_passed": 0, "verdict": "INCONCLUSIVE",
        })
        print("OK: nothing to qualify in the %s security mode (%s) → %s" % (security_mode, idle_why, out.relative_to(root)))
        return 0
    try:
        # the corpus of THIS mode: the captures under the mode's own
        # directory were replayed from it, and only it can contract them
        corpus = load_corpus(root, security_mode, variant)
    except CorpusError as exc:
        print("REFUSE: QUALIFY_CAPTURES %s" % exc, file=sys.stderr)
        return 1
    corpus_sha = corpus_digest(corpus)
    bundle_p = root / EVIDENCE_BUNDLE
    bundle_sha = digest(load_json(bundle_p)) if bundle_p.is_file() else ""
    scenarios = list(corpus.get("scenarios") or [])
    # a refusal to JUDGE: the corpus names requests and the source was never
    # asked any of them. That is not a verdict about the source, so no
    # qualification document is written for it
    if scenarios and not any((root / oracles_dir / (scenario_slug(str(sc["id"])) + ".json")).is_file() for sc in scenarios):
        print("REFUSE: QUALIFY_CAPTURES no capture under %s for any of the %d scenario(s) the corpus names; capture the source first "
              "(capture-source-scenarios.py)" % (oracles_dir, len(scenarios)), file=sys.stderr)
        return 1
    results: dict[str, dict[str, Any]] = {}
    for sc in scenarios:
        sid = str(sc["id"])
        cp = root / oracles_dir / (scenario_slug(sid) + ".json")
        cap = None
        capture_sha = ""
        if cp.is_file():
            raw = cp.read_bytes()
            capture_sha = hashlib.sha256(raw).hexdigest()
            try:
                cap = json.loads(raw.decode("utf-8"))
            except ValueError as exc:
                results[sid] = {"verdict": "INCONCLUSIVE", "capability": "INCONCLUSIVE", "intent": str((sc.get("qualify") or {}).get("intent") or "positive"),
                                "evidence": {"status": "UNUSABLE", "reasons": ["capture unreadable: %s" % exc]}, "known_failures": [],
                                "reason": "capture unreadable: %s" % exc, "checks": [], "capture_sha256": capture_sha, "request_sha256": "",
                                "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha}
                continue
        results[sid] = qualify_scenario(root, sc, cap, corpus_sha, bundle_sha, capture_sha)
    not_passed = sorted(sid for sid, r in results.items() if r["capability"] != "PASS")
    verdict = "PASS" if results and not not_passed else "FAIL" if any(r["capability"] == "FAIL" for r in results.values()) else "INCONCLUSIVE"
    out = root / qualification_path(security_mode, variant)
    write_canonical(out, {
        "schema": QUALIFICATION_SCHEMA, "producer": PRODUCER, "at": _now(),
        "corpus_sha256": corpus_sha, "evidence_bundle_sha256": bundle_sha,
        "security_mode": security_mode, "security_mode_recorded": recorded_mode, "security_mode_note": "" if recorded_mode else mode_why,
        "security_variant": variant, "security_variant_recorded": recorded_variant,
        "scenarios": dict(sorted(results.items())), "total": len(results), "not_passed": len(not_passed), "verdict": verdict,
    })
    for sid in not_passed:
        r = results[sid]
        print("  - %s %s (evidence %s): %s" % (sid, r["capability"], r["evidence"]["status"], r["reason"]), file=sys.stderr)
    if verdict == "PASS":
        print("OK: %d capture(s) qualified against the corpus %s → %s" % (len(results), corpus_sha[:12], out.relative_to(root)))
        return 0
    # FAIL and INCONCLUSIVE are RECORDED SOURCE FACTS, not refusals. The gate
    # ran, judged every capture and bound the verdicts to them; M4 turns a
    # non-PASS into a coverage gap and never into a destination repair card.
    # Exiting 1 here made the M1 step fail on what the source actually does.
    print("OK: qualification %s (%d of %d not qualified) → %s" % (verdict, len(not_passed), len(results), out.relative_to(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
