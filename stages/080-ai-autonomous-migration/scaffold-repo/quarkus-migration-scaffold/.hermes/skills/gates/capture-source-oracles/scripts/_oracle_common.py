"""Shared helpers for source-oracle capture and parity comparison (not a CLI)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


ensure_hermes_lib()
from planner.canonical import canonical_bytes, load_json, sha256_bytes  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402

ASSERTED_RESPONSE_HEADERS = (
    "Location",
    "Access-Control-Allow-Origin",
    "Access-Control-Allow-Methods",
    "Access-Control-Allow-Headers",
    "Access-Control-Expose-Headers",
    "Access-Control-Allow-Credentials",
    "Access-Control-Max-Age",
)


# Headers whose value is a LIST (Fetch: comma-separated tokens, order and
# case not significant for methods and header names). Compared as token sets;
# the raw values are still recorded on both sides.
LIST_HEADERS = ("Access-Control-Allow-Methods", "Access-Control-Allow-Headers", "Access-Control-Expose-Headers")
CORS_ACTUAL = ("Access-Control-Allow-Origin", "Access-Control-Allow-Credentials", "Access-Control-Expose-Headers")
CORS_PREFLIGHT = ("Access-Control-Allow-Origin", "Access-Control-Allow-Credentials", "Access-Control-Allow-Methods",
                  "Access-Control-Allow-Headers", "Access-Control-Max-Age")
LOCATION_STATUSES = frozenset({201, 301, 302, 303, 307, 308})


def is_preflight(method: str, headers: dict[str, str] | None) -> bool:
    """An OPTIONS exchange carrying Origin and Access-Control-Request-Method.
    It asks permission; it writes nothing, so it declares no effects."""
    h = {str(k).lower() for k in (headers or {})}
    return str(method).upper() == "OPTIONS" and "origin" in h and "access-control-request-method" in h


def required_headers(method: str, status: Any, request_headers: dict[str, str] | None) -> list[str]:
    """Which asserted headers this exchange's capture must have COVERED.

    A Location on a 201 or a redirect; the CORS permission headers on any
    exchange that carries a cross-origin Origin (the preflight set on a
    preflight -- Expose-Headers belongs to the ACTUAL request, not to the
    preflight). Coverage means the capture recorded a header MAP: a recorded
    null for one of these is a legitimate observation (a source that grants no
    credential permission records none) and is compared as recorded. What is
    refused is comparing an exchange like this against a capture that has no
    header map at all -- INCONCLUSIVE, never a quiet skip."""
    need: list[str] = []
    try:
        code = int(status)
    except (TypeError, ValueError):
        code = 0
    if code in LOCATION_STATUSES:
        need.append("Location")
    if any(str(k).lower() == "origin" for k in (request_headers or {})):
        need.extend(CORS_PREFLIGHT if is_preflight(method, request_headers) else CORS_ACTUAL)
    return list(dict.fromkeys(need))


def origin_of(url: str) -> str:
    parts = urllib.parse.urlsplit(str(url or ""))
    return "%s://%s" % (parts.scheme, parts.netloc) if parts.scheme and parts.netloc else ""


def map_origin(value: str | None, source_origin: str, dest_origin: str) -> str | None:
    """Rewrite ONLY the declared source origin to the declared destination
    origin. Path, escaping, query and fragment are the value's own and are
    compared as they are; a value on any other origin is left alone."""
    if not value or not source_origin or not dest_origin:
        return value
    if value == source_origin or value.startswith(tuple(source_origin + c for c in "/?#")):
        return dest_origin + value[len(source_origin):]
    return value


def asserted_headers(msg: Any, extra: tuple[str, ...] | list[str] = ()) -> dict[str, str | None]:
    """The header contract for CORS and Location, plus every header the SOURCE
    itself exposes (``extra``: its CORS exposedHeaders, read from M1's model --
    a source that exposes an ``errors`` header has made that header part of
    its contract, and a 400 whose errors moved elsewhere must not pass).
    Absent keys are None.

    Captures that predate this map omit ``headers`` entirely; comparators must
    not invent expected values for those. New captures always record the map."""
    out: dict[str, str | None] = {}
    keys = list(ASSERTED_RESPONSE_HEADERS) + [k for k in extra if k and k not in ASSERTED_RESPONSE_HEADERS]
    for key in keys:
        val = None
        if msg is not None:
            try:
                raw = msg.get(key)
            except Exception:
                raw = None
            val = str(raw) if raw not in (None, "") else None
        out[key] = val
    return out


def _tokens(value: str | None) -> frozenset[str] | None:
    if value is None:
        return None
    return frozenset(t.strip().lower() for t in str(value).split(",") if t.strip())


def header_diffs(expected: Any, observed: Any, *, source_origin: str = "", dest_origin: str = "") -> list[str]:
    """Diffs for asserted headers. A missing expected map is a legacy capture
    (the caller decides whether this exchange REQUIRED one: required_headers).

    Location is compared after mapping the declared source origin to the
    declared destination origin, and nothing else; list-valued CORS headers
    are compared as token sets. Each diff names the raw values."""
    if not isinstance(expected, dict):
        return []
    got = observed if isinstance(observed, dict) else {}
    diffs: list[str] = []
    for key, want in expected.items():
        have = got.get(key)
        if key == "Location":
            mapped = map_origin(want, source_origin, dest_origin)
            if have != mapped:
                diffs.append("header Location %s vs %s (source %s)" % (have, mapped, want))
            continue
        if key in LIST_HEADERS:
            if _tokens(have) != _tokens(want):
                diffs.append("header %s %s vs %s" % (key, have, want))
            continue
        if have != want:
            diffs.append("header %s %s vs %s" % (key, have, want))
    return diffs


ORACLES = Path("verification") / "source-oracles"
PARITY = Path("verification") / "parity"
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b")
IDEMPOTENT = frozenset({"GET", "HEAD"})


def slug(entry_point_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", entry_point_id)[:120]


def entry_points(root: Path) -> list[dict[str, Any]]:
    p = root / EVIDENCE_BUNDLE
    if not p.is_file():
        return []
    return list(load_json(p).get("entry_points") or [])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The FIRST response is the observation. Following a redirect recorded
    the target's answer as the source's and dropped the Location that said
    where it pointed (architect review, 2026-09-11)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


RETAINED_BODY_CAP = 1 << 20  # 1 MiB per retained body; larger ones are cut and say so


def retain_body(out_dir: Path, name: str, raw: bytes, sha: str) -> dict[str, Any]:
    """Keep a response body as EVIDENCE beside the capture, bound by digest.

    A receipt that keeps a 200-character sample cannot show that the created
    owner is in the list or the rejected one absent; a digest alone cannot
    name either. The full bytes are written to
    ``<out_dir>/<name>.body`` and the record says where and how long. The
    parity body_sha256 stays the caller's normalized digest (canonical JSON
    for a JSON response). raw_body_sha256 binds the complete response bytes;
    retained_sha256 binds the file, including when it is a truncated prefix.
    Qualification requiring the complete body must refuse truncated evidence."""
    out_dir.mkdir(parents=True, exist_ok=True)
    kept = raw[:RETAINED_BODY_CAP]
    p = out_dir / ("%s.body" % name)
    p.write_bytes(kept)
    return {"body_file": p.as_posix(), "body_bytes": len(raw), "retained_bytes": len(kept),
            "truncated": len(kept) < len(raw), "body_sha256": sha,
            "raw_body_sha256": hashlib.sha256(raw).hexdigest(),
            "retained_sha256": hashlib.sha256(kept).hexdigest()}


def http_observe(base_url: str, method: str, path: str, body: bytes | None = None, timeout: float = 20.0,
                 headers: dict[str, str] | None = None, assert_headers: tuple[str, ...] | list[str] = (),
                 keep_body: bool = False) -> dict[str, Any]:
    """One request, recorded, redirects NOT followed. The body and the headers
    are sent as given: a replay that drops them is not a replay (the
    destination comparator used to send no body at all, so every recorded
    write compared FAIL)."""
    url = base_url.rstrip("/") + (path if path.startswith("/") else "/" + path)
    req = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if body is not None and not any(k.lower() == "content-type" for k in (headers or {})):
        req.add_header("Content-Type", "application/json")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            hdrs = asserted_headers(resp.headers, assert_headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
        hdrs = asserted_headers(exc.headers, assert_headers)
    except (urllib.error.URLError, OSError) as exc:
        return {"status": 0, "body_kind": "unreachable", "body_sha256": "", "error": str(exc),
                "headers": asserted_headers(None)}
    kind, sha, sample = normalize_body(raw, ctype)
    out = {"status": status, "body_kind": kind, "body_sha256": sha, "body_sample": sample, "headers": hdrs,
           "redirects_followed": False, "url": url}
    if keep_body:
        out["raw"] = raw  # the caller retains it as evidence (retain_body); never written into a canonical record
    return out


# ---------------------------------------------------------------------------
# where two bodies differ (H1a): a digest says THAT they differ, this says WHERE
# ---------------------------------------------------------------------------
BODY_DIFF_CAP = 50        # differences listed; more are counted and the diff says truncated
_SHORT = 80               # characters of a value quoted in a difference
DESTINATION_BODIES = "_bodies"   # beside the verdicts; "_" keeps it out of the record partition


def _short(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"))
    return text if len(text) <= _SHORT else text[:_SHORT - 1] + "…"


def _canon(value: Any) -> bytes:
    return canonical_bytes(value)


def _kind_of(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    return {dict: "object", list: "array", str: "string"}.get(type(value), type(value).__name__)


def _json_differences(expected: Any, observed: Any, path: str, out: list[dict[str, Any]]) -> None:
    ek, ok = _kind_of(expected), _kind_of(observed)
    if ek != ok:
        out.append({"path": path, "kind": "type", "expected": ek, "observed": ok})
        return
    if ek == "object":
        for key in sorted(set(expected) | set(observed)):
            sub = "%s.%s" % (path, key) if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", str(key)) else "%s[%s]" % (path, json.dumps(key))
            if key not in observed:
                out.append({"path": sub, "kind": "missing", "expected": _short(expected[key]), "observed": None})
            elif key not in expected:
                out.append({"path": sub, "kind": "extra", "expected": None, "observed": _short(observed[key])})
            else:
                _json_differences(expected[key], observed[key], sub, out)
        return
    if ek == "array":
        if _canon(expected) == _canon(observed):
            return
        if sorted(_canon(x) for x in expected) == sorted(_canon(x) for x in observed):
            # the same elements, in another order: one difference for the list
            out.append({"path": path, "kind": "order", "expected": _short(expected[:3]), "observed": _short(observed[:3])})
            return
        if len(expected) != len(observed):
            out.append({"path": path, "kind": "length", "expected": len(expected), "observed": len(observed)})
        for i in range(min(len(expected), len(observed))):
            _json_differences(expected[i], observed[i], "%s[%d]" % (path, i), out)
        return
    if expected != observed:
        out.append({"path": path, "kind": "value", "expected": _short(expected), "observed": _short(observed)})


def _pattern(path: str) -> str:
    return re.sub(r"\[\d+\]", "[*]", path)


def _summary(differences: list[dict[str, Any]], total: int) -> str:
    if not differences:
        return "no difference"
    groups: dict[tuple[str, str], int] = {}
    for d in differences:
        key = (d["kind"], _pattern(d["path"]))
        groups[key] = groups.get(key, 0) + 1
    if all(d["kind"] == "order" for d in differences):
        return "; ".join("same elements, different order at %s (%d list%s)" % (pat, n, "" if n == 1 else "s")
                         for (_k, pat), n in sorted(groups.items(), key=lambda kv: kv[0][1]))
    parts = ["%s at %s (%d)" % (kind, pat, n) for (kind, pat), n in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0]))]
    return "%d difference(s): %s" % (total, "; ".join(parts[:6]) + ("; …" if len(parts) > 6 else ""))


def body_diff(expected_raw: bytes | None, observed_raw: bytes | None, *, unavailable: str = "",
              truncated_input: bool = False) -> dict[str, Any]:
    """Where the destination's body differs from the source's.

    ``{"kind": "json"|"text"|"unavailable", "differences": [{"path", "kind",
    "expected", "observed"}], "order_only", "summary", "truncated"}``. A JSON
    list holding the same elements in another order is ONE ``order``
    difference at its path; the summary collapses indices to ``[*]``. Values
    are shortened; nothing is quoted but the values at differing paths."""
    if expected_raw is None or observed_raw is None:
        return {"kind": "unavailable", "differences": [], "order_only": False, "truncated": False,
                "summary": unavailable or "no retained body to compare"}
    try:
        e = json.loads(expected_raw.decode("utf-8"))
        o = json.loads(observed_raw.decode("utf-8"))
        kind = "json"
    except (UnicodeDecodeError, ValueError):
        kind = "text"
    diffs: list[dict[str, Any]] = []
    if kind == "json":
        _json_differences(e, o, "$", diffs)
    elif expected_raw != observed_raw:
        el = expected_raw.decode("utf-8", errors="replace").splitlines()
        ol = observed_raw.decode("utf-8", errors="replace").splitlines()
        if sorted(el) == sorted(ol):
            diffs.append({"path": "lines", "kind": "order", "expected": _short(el[:3]), "observed": _short(ol[:3])})
        else:
            if len(el) != len(ol):
                diffs.append({"path": "lines", "kind": "length", "expected": len(el), "observed": len(ol)})
            for i in range(max(len(el), len(ol))):
                a = el[i] if i < len(el) else None
                b = ol[i] if i < len(ol) else None
                if a != b:
                    diffs.append({"path": "line %d" % (i + 1), "kind": "value" if a is not None and b is not None
                                  else ("missing" if b is None else "extra"),
                                  "expected": None if a is None else _short(a), "observed": None if b is None else _short(b)})
    total = len(diffs)
    return {"kind": kind, "differences": diffs[:BODY_DIFF_CAP], "order_only": bool(diffs) and all(d["kind"] == "order" for d in diffs),
            "summary": _summary(diffs, total), "truncated": total > BODY_DIFF_CAP or truncated_input,
            **({"total": total} if total > BODY_DIFF_CAP else {})}


def retained_bytes(root: Path, evidence: Any, fallback: Path | None = None) -> tuple[bytes | None, str]:
    """(the retained body bytes a record names, why-not), verified against the
    digest the record carries."""
    ev = evidence if isinstance(evidence, dict) else {}
    cands = []
    if ev.get("body_file"):
        bf = Path(str(ev["body_file"]))
        cands += [bf, Path(root) / bf, (fallback.parent / bf.name) if fallback else None]
    if fallback is not None:
        cands.append(fallback)
    for c in cands:
        if c is not None and c.is_file():
            raw = c.read_bytes()
            want = str(ev.get("retained_sha256") or "")
            if want and hashlib.sha256(raw).hexdigest() != want:
                return None, "the retained body %s is not the one its record digested" % c.name
            if ev.get("truncated"):
                return raw, "truncated"
            return raw, ""
    return None, "the record retains no body (re-capture to keep one)"


def normalize_body(raw: bytes, content_type: str) -> tuple[str, str, str]:
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
        return "json", sha256_bytes(canonical_bytes(parsed)), text[:200]
    except (json.JSONDecodeError, ValueError):
        pass
    return ("text" if "text" in content_type or not raw else "bytes"), hashlib.sha256(raw).hexdigest(), text[:200]


def normalize_observation(path: Path) -> tuple[str, int]:
    lines = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = TIMESTAMP_RE.sub("<ts>", ln).strip()
        if s:
            lines.append(s)
    uniq = sorted(set(lines))
    return sha256_bytes("\n".join(uniq).encode("utf-8")), len(uniq)


# --- the bounded navigation walk (ADR-016), shared by the SOURCE capture and
# the destination comparison so both record the same shape ------------------
NAV_OK = "ok"
NAV_DEAD = "dead"
NAV_LOOP = "loop"
NAV_TOO_MANY = "too-many-hops"


def split_url(url: str) -> tuple[str, str]:
    """(origin, path?query) -- http_observe takes a base and a path, and the
    navigation walks whole URLs. An address with no scheme and host is not one
    this walk can follow, and comes back with an empty origin."""
    parts = urllib.parse.urlsplit(str(url or ""))
    if not parts.scheme or not parts.netloc:
        return "", ""
    rest = parts.path or "/"
    if parts.query:
        rest = rest + "?" + parts.query
    return "%s://%s" % (parts.scheme, parts.netloc), rest


def navigate(start: str, headers: dict[str, str] | None, max_hops: int, observe: Any = None) -> dict[str, Any]:
    """Follow at most ``max_hops`` redirects from ``start``, one hop at a time,
    and say where it ended.

    ``ok`` is a 2xx at the end; ``dead`` is a 4xx, a 5xx or a connection that
    could not be made (and a redirect that names no target: an address nobody
    can follow is not a redirect); ``loop`` is a URL this walk already visited;
    ``too-many-hops`` is a chain still redirecting when the budget ran out.
    Each hop records the URL it asked, the status it got and the Location it
    was sent on to, so the record shows the walk rather than only its end.
    ``final`` (H11) records the LAST hop's status, Content-Type, body kind
    and body digest: "final hop 2xx" alone let a meta-refresh stub pass for
    the real UI (dest v9 t_0527c69b), and only the page's kind can say what
    answered."""
    observe = observe or http_observe
    hops: list[dict[str, Any]] = []
    seen: set[str] = set()
    url = str(start or "")
    terminal = ""
    final_status = 0
    final: dict[str, Any] = {}
    for _ in range(max(1, int(max_hops))):
        if url in seen:
            terminal = NAV_LOOP
            break
        seen.add(url)
        origin, rest = split_url(url)
        if not origin:
            hops.append({"url": url, "status": 0, "error": "not an absolute address this check can follow"})
            terminal = NAV_DEAD
            break
        got = observe(origin, "GET", rest, headers=dict(headers or {}), assert_headers=("Content-Type",))
        status = int(got.get("status") or 0)
        hdrs = got.get("headers") if isinstance(got.get("headers"), dict) else {}
        location = hdrs.get("Location")
        hop: dict[str, Any] = {"url": url, "status": status}
        if location:
            hop["location"] = str(location)
        if not status:
            hop["error"] = str(got.get("error") or "")[:200]
        hops.append(hop)
        final_status = status
        final = {"url": url, "status": status, "content_type": str(hdrs.get("Content-Type") or "").split(";")[0].strip().lower(),
                 "body_kind": str(got.get("body_kind") or ""), "body_sha256": str(got.get("body_sha256") or "")}
        if not status:
            terminal = NAV_DEAD
            break
        if 300 <= status < 400:
            if not location:
                terminal = NAV_DEAD
                break
            url = urllib.parse.urljoin(url, str(location))
            continue
        terminal = NAV_OK if 200 <= status < 300 else NAV_DEAD
        break
    else:
        terminal = NAV_TOO_MANY
    return {"start": str(start or ""), "hops": hops, "final_status": final_status, "terminal": terminal, "final": final}


def final_page_differs(dest_final: dict[str, Any] | None, source_final: dict[str, Any] | None) -> str:
    """Why the destination walk's final page is not the kind the source's is:
    the content type or the body kind differ (a digest never has to match --
    two Swagger UIs are two different pages). "" when they agree or when the
    source recorded no final hop (nothing to compare against)."""
    d, s = dict(dest_final or {}), dict(source_final or {})
    if not s or not s.get("status") or not d:
        return ""
    diffs = []
    for key in ("content_type", "body_kind"):
        if str(s.get(key) or "") and str(d.get(key) or "") != str(s.get(key) or ""):
            diffs.append("%s %s vs %s" % (key.replace("_", "-"), d.get(key) or "none", s.get(key)))
    return "; ".join(diffs)
