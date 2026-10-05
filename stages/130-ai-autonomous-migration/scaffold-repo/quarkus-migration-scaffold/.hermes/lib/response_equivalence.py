"""ADR-025 (architect ruling 2026-09-30 on the M-3 reference qualification
findings 6-8): the three response equivalences the parity comparators apply,
each pure and self-contained, each decided from the SOURCE's side (the frozen
source oracle, the corpus and its root-path facts), never from a destination
response.

  challenge_set                 WWW-Authenticate as the set of parsed
                                challenges (RFC 9110 section 11.6.1)
  deserialization_advice        the source answered an unreadable request body
                                through its exception advice: {className,
                                exMessage}, whose VALUES are framework
                                diagnostics compared as present, non-empty
                                strings; status, media type and keys stay
                                enforced by the caller
  outside_application_root      a request outside the application root path is
                                answered by the servlet container: status only

Lives beside, not in, planner/ (no effect on the planner code fingerprint).
Python 3.9 compatible.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

ADR = "ADR-025"
# H-20/D-2 (v31): the advice's body keys are DERIVED from the source model (planner.exception_advice.shapes): the
# field names of the error type the advice references. No key set is assumed here.
# the source framework's request-body read failure: the exception class the
# source advice names when Spring's message converter could not read the body
# (spring-web HttpMessageNotReadableException; the frozen source oracle records it)
SOURCE_DESERIALIZATION_EXCEPTIONS = ("org.springframework.http.converter.HttpMessageNotReadableException",)
OUTSIDE_ROOT_SCOPE = ("a request outside the application root path is answered by the servlet container, not the "
                      "application: it is compared by status only; its body and headers are out of scope (%s)" % ADR)

_TCHAR = set("!#$%&'*+-.^_`|~0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_T68 = _TCHAR | set("/")   # token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"="


def adr_accepted(root: Optional[Path]) -> bool:
    """Is ADR-025 an accepted decision of this destination (decisions.yaml)?"""
    if root is None:
        return False
    try:
        from planner.decisions import accepted_adrs, load_decisions
        return ADR in accepted_adrs(load_decisions(Path(root)))
    except Exception:  # an unreadable decision file grants nothing
        return False


def _split_top_level(s: str) -> Optional[list]:
    """The list elements of a field value: commas outside quoted strings."""
    parts, buf, q, i, n = [], [], False, 0, len(s)
    while i < n:
        c = s[i]
        if q:
            buf.append(c)
            if c == "\\" and i + 1 < n:
                buf.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                q = False
        elif c == '"':
            q = True
            buf.append(c)
        elif c == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    if q:
        return None                     # an unterminated quoted-string
    parts.append("".join(buf))
    return [p.strip(" \t") for p in parts]


def _token_end(s: str, i: int) -> int:
    while i < len(s) and s[i] in _TCHAR:
        i += 1
    return i


def _param(e: str) -> Optional[Tuple[str, str]]:
    """auth-param = token BWS "=" BWS ( token / quoted-string ), the whole element."""
    k = _token_end(e, 0)
    name = e[:k]
    rest = e[k:].lstrip(" \t")
    if not name or not rest.startswith("="):
        return None
    v = rest[1:].lstrip(" \t")
    if v.startswith('"'):
        buf, j = [], 1
        while j < len(v):
            if v[j] == "\\" and j + 1 < len(v):
                buf.append(v[j + 1])
                j += 2
                continue
            if v[j] == '"':
                return (name.lower(), "".join(buf)) if not v[j + 1:].strip(" \t") else None
            buf.append(v[j])
            j += 1
        return None
    end = _token_end(v, 0)
    return (name.lower(), v) if end and end == len(v) else None


def _token68(r: str) -> bool:
    k = 0
    while k < len(r) and r[k] in _T68:
        k += 1
    return k > 0 and all(c == "=" for c in r[k:])


def parse_challenges(values: Any) -> Optional[list]:
    """The challenges of one or more WWW-Authenticate field lines, parsed by
    RFC 9110's grammar (sections 11.6.1 and 11.2):

        WWW-Authenticate = [ challenge *( OWS "," OWS challenge ) ]
        challenge  = auth-scheme [ 1*SP ( token68 / #auth-param ) ]
        auth-param = token BWS "=" BWS ( token / quoted-string )

    A comma separates both challenges and the parameters of one challenge; a
    list element that is `name=value` continues the current challenge, any
    other starts a new one. Field lines are joined with commas (section 5.3).
    Returns [(scheme lower-cased, ("token68", value) or sorted ((name
    lower-cased, value), ...))] or None when the value does not parse (the
    caller then compares the raw values). A quoted value is unquoted and
    unescaped, so a ',' inside quotes is part of the value; values keep their
    case (a realm is case-sensitive)."""
    lines = values if isinstance(values, (list, tuple)) else [values]
    joined = ", ".join(str(v) for v in lines if v is not None and str(v).strip())
    parts = _split_top_level(joined)
    if parts is None:
        return None
    out: list = []
    cur: Optional[list] = None          # [scheme, params list, token68]
    for e in parts:
        if not e:
            continue                    # empty list elements are allowed (section 5.6.1)
        k = _token_end(e, 0)
        if k == 0:
            return None
        if e[k:].lstrip(" \t").startswith("="):
            prm = _param(e)
            if prm is None or cur is None or cur[2] is not None:
                return None
            cur[1].append(prm)
            continue
        if k < len(e) and e[k] not in " \t":
            return None
        cur = [e[:k].lower(), [], None]
        out.append(cur)
        rest = e[k:].strip(" \t")
        if not rest:
            continue
        prm = _param(rest)
        if prm is not None:
            cur[1].append(prm)
        elif _token68(rest):
            cur[2] = rest
        else:
            return None
    return [(c[0], ("token68", c[2]) if c[2] is not None else tuple(sorted(c[1]))) for c in out]


def challenge_set(values: Any) -> Optional[frozenset]:
    """The challenges as a set: identical duplicates are one (RFC 9110
    section 11.6.1 processes challenges individually); None when unparseable."""
    got = parse_challenges(values)
    return None if got is None else frozenset(got)


def challenges_equal(expected: Any, observed: Any) -> bool:
    a, b = challenge_set(expected), challenge_set(observed)
    if a is None or b is None:
        return expected == observed
    return a == b


def _json_object(raw: Any) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        doc = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw))
    except (UnicodeDecodeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def deserialization_advice(source_status: Any, source_body: Any, shapes: Any) -> bool:
    """Did the SOURCE answer through its exception advice for a request-body
    deserialization failure? Decided from the frozen source's own response only:
    a 400 in one of the advice's shapes (``shapes``: planner.exception_advice.shapes,
    derived from the source model) one of whose values names the source framework's
    body-read failure. Used for the brief's specific first action; equivalence
    is advice_equivalent's, for every advice response (D-2)."""
    doc = _json_object(source_body)
    if str(source_status) != "400" or doc is None:
        return False
    if not _advice_shape(doc, shapes):
        return False
    return any(str(v) in SOURCE_DESERIALIZATION_EXCEPTIONS for v in doc.values() if isinstance(v, str))


def _advice_shape(doc: dict, shapes: Any) -> bool:
    keys = sorted(doc)
    return any(keys in (sh.get("body_keys") or []) for sh in shapes or [] if isinstance(sh, dict))


def advice_equivalent(source_status: Any, source_body: Any, observed_body: Any, shapes: Any) -> Tuple[bool, str] | None:
    """D-2 (2026-10-02, ADR-025 extended to every exception-advice response): None unless the SOURCE answered an
    error (4xx/5xx) whose body has the shape of one of its exception advices (model-derived key sets); then whether
    the destination kept those keys with present, non-empty values -- the values are each platform's own
    diagnostics (exception class names, provider messages). The status is compared apart, never here."""
    try:
        code = int(str(source_status))
    except ValueError:
        return None
    src = _json_object(source_body)
    if code < 400 or src is None or not _advice_shape(src, shapes):
        return None
    ok, why = advice_values_equivalent(source_body, observed_body)
    return ok, why.replace("for a request-body deserialization failure", "for an error")


def advice_values_equivalent(source_body: Any, observed_body: Any) -> Tuple[bool, str]:
    """The destination kept the advice's key set with present, non-empty string
    values (the values themselves are the platform's own diagnostics)."""
    src, got = _json_object(source_body), _json_object(observed_body)
    if src is None:
        return False, "the source body is not the advice's JSON object"
    if got is None:
        return False, "the destination body is not a JSON object (the advice's {%s} are owed)" % ", ".join(sorted(src))
    if sorted(got) != sorted(src):
        return False, "the destination keys %s are not the source advice's %s" % (sorted(got), sorted(src))
    # each value keeps the source value's JSON type and is not empty (a string with text, a present object)
    empty = [k for k in sorted(src) if got.get(k) is None or type(got.get(k)) is not type(src.get(k))
             or (isinstance(got.get(k), str) and not got[k].strip())]
    if empty:
        return False, "the destination leaves %s empty or not a string" % ", ".join(empty)
    return True, ("%s: the source answered its exception advice for a request-body deserialization failure; the keys "
                  "match and the values are present non-empty diagnostics of the destination's own framework" % ADR)


def outside_application_root(request_path: str, application_root: str) -> bool:
    """Is the request (its path as sent to the source) outside the source's
    application root path? Root '' or '/' contains everything."""
    root = "/" + str(application_root or "").strip().strip("/")
    if root == "/":
        return False
    p = "/" + str(request_path or "").split("?", 1)[0].lstrip("/")
    return not (p == root or p.startswith(root + "/"))


def scope_limitation(outside_scenarios: Iterable[str] = ()) -> dict:
    """The explicit scope limitation ADR-025 (3) records, for the completion map."""
    ids = sorted({str(x) for x in outside_scenarios if str(x)})
    return {"id": "outside-application-root", "adr": ADR, "limitation": OUTSIDE_ROOT_SCOPE,
            "owner": "scope-decision", "scenarios": ids,
            "evidence": ("decisions.yaml %s (architect ruling 2026-09-30 on the M-3 reference qualification findings 6-8); the "
                         "source's own 404 for such a request is the servlet container's error page" % ADR)}
