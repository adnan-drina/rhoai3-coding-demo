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
