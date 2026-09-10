"""Shared helpers for source-oracle capture and parity comparison (not a CLI)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
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


def http_observe(base_url: str, method: str, path: str, body: bytes | None = None, timeout: float = 20.0,
                 headers: dict[str, str] | None = None) -> dict[str, Any]:
    """One request, recorded. The body and the headers are sent as given: a
    replay that drops them is not a replay (the destination comparator used to
    send no body at all, so every recorded write compared FAIL)."""
    url = base_url.rstrip("/") + (path if path.startswith("/") else "/" + path)
    req = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if body is not None and not any(k.lower() == "content-type" for k in (headers or {})):
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
    except (urllib.error.URLError, OSError) as exc:
        return {"status": 0, "body_kind": "unreachable", "body_sha256": "", "error": str(exc)}
    kind, sha, sample = normalize_body(raw, ctype)
    return {"status": status, "body_kind": kind, "body_sha256": sha, "body_sample": sample}


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
