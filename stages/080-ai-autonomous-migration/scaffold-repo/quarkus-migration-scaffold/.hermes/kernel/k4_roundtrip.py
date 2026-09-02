#!/usr/bin/env python3
"""K4 typed-schema round-trip: partition story fields must survive mint.

W3 (Architect ``190639ZA`` / ``194048ZA``): digest-compare minted bodies
against the serialized typed story. When ``dest_file`` is present, product
``src/main/java/*.java`` in ``files_writable`` must be that dest twin (or a
named supersede successor). dest-9 ``Application.java`` /
``GreetingResource.java`` REFUSE. Absence of ``dest_file`` is skip, not
inventory grounding.

Exit 0: typed slice matches and dest_file does not invent dest Java.
Exit 1: digest mismatch or dest_file invented dest Java.
Exit 2: usage.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from k4_convert import convert_file  # noqa: E402

# Fields M2 may stamp on a story. Copied into identity / files_writable.
# Absence on the partition is skip, not INVALID. Presence must survive.
TYPED_KEYS = (
    "operand_class",
    "endpoints",
    "dest_file",
    "files_writable",
    "acceptance_criteria",
    "kind",
    "extensions_declared",
    "extensions",
    "legacy_source",
)


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(obj: Any) -> str:
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


def _story_id(story: dict[str, Any]) -> str:
    return str(story.get("story_id") or story.get("id") or "").strip()


def _norm(path: Any) -> str:
    rel = str(path).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def _dest_file_grounded(story: dict[str, Any]) -> set[str] | None:
    """Named dest twins on the story. None = dest_file absent (skip)."""
    raw = story.get("dest_file")
    if raw in (None, "", []):
        return None
    grounded: set[str] = set()
    if isinstance(raw, str):
        if _norm(raw):
            grounded.add(_norm(raw))
    elif isinstance(raw, list):
        for item in raw:
            n = _norm(item)
            if n:
                grounded.add(n)
    else:
        return None
    succ = story.get("supersedes")
    if isinstance(succ, list):
        for item in succ:
            if isinstance(item, str) and _norm(item):
                grounded.add(_norm(item))
            elif isinstance(item, dict):
                for key in ("successors", "successor"):
                    raw_s = item.get(key)
                    if isinstance(raw_s, str):
                        raw_s = [raw_s]
                    if isinstance(raw_s, list):
                        grounded.update(_norm(s) for s in raw_s if _norm(s))
    return grounded


def dest_file_invented(story: dict[str, Any]) -> list[str]:
    """Product dest Java in files_writable not named as dest_file.

    Architect ``194048ZA``: dest_file in the typed slice must REFUSE dest-9
    Application.java / GreetingResource.java. Skip when dest_file is absent.
    pom / resources / tests are not dest twins.
    """
    grounded = _dest_file_grounded(story)
    if grounded is None:
        return []
    invented: list[str] = []
    seen: set[str] = set()
    for raw in story.get("files_writable") or []:
        n = _norm(raw)
        if not n or n in seen:
            continue
        seen.add(n)
        if n == "pom.xml" or n.startswith("src/main/resources/"):
            continue
        if n.startswith("src/test/"):
            continue
        if not n.startswith("src/main/java/") or not n.endswith(".java"):
            continue
        if n not in grounded:
            invented.append(n)
    return invented


def typed_slice(story: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in TYPED_KEYS:
        if key not in story:
            continue
        val = story[key]
        if val in (None, "", []):
            continue
        out[key] = val
    out["files_writable"] = [
        str(p) for p in (story.get("files_writable") or []) if str(p).strip()
    ]
    return out


def body_slice(body: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    out: dict[str, Any] = {}
    for key in keys:
        if key == "files_writable":
            out[key] = [
                str(p) for p in (body.get("files_writable") or []) if str(p).strip()
            ]
            continue
        if key in ident:
            out[key] = ident[key]
        elif key in body:
            out[key] = body[key]
    return out


def roundtrip_story(story: dict[str, Any], body: dict[str, Any]) -> list[str]:
    expected = typed_slice(story)
    got = body_slice(body, list(expected))
    if _digest(expected) == _digest(got):
        return []
    sid = _story_id(story) or "?"
    missing = [k for k in expected if k not in got]
    extra = [k for k in got if k not in expected]
    return [
        "K4_ROUNDTRIP %s digest mismatch missing=%s extra=%s"
        % (sid, ",".join(missing) or "-", ",".join(extra) or "-")
    ]


def roundtrip_result(
    partition: dict[str, Any], result: dict[str, Any]
) -> list[str]:
    gaps: list[str] = []
    by_id = {str(p.get("logical_id") or ""): p for p in result.get("payloads") or []}
    for story in partition.get("stories") or []:
        if not isinstance(story, dict):
            continue
        sid = _story_id(story)
        if not sid:
            continue
        payload = by_id.get(sid)
        if payload is None:
            gaps.append("K4_ROUNDTRIP missing payload %s" % sid)
            continue
        try:
            body = json.loads(str(payload.get("body") or "{}"))
        except json.JSONDecodeError as exc:
            gaps.append("K4_ROUNDTRIP %s body unreadable: %s" % (sid, exc))
            continue
        if not isinstance(body, dict):
            gaps.append("K4_ROUNDTRIP %s body is not an object" % sid)
            continue
        gaps.extend(roundtrip_story(story, body))
        sid_label = sid or "?"
        for path in dest_file_invented(story):
            gaps.append(
                "K4_ROUNDTRIP %s dest_file invented %s" % (sid_label, path)
            )
    return gaps


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAIL: pass a partition.json", file=sys.stderr)
        return 2
    path = Path(args[0])
    result, issues = convert_file(path)
    if issues or result is None:
        print("FAIL: K4 convert: %s" % issues, file=sys.stderr)
        return 1
    partition = json.loads(path.read_text(encoding="utf-8"))
    gaps = roundtrip_result(partition, result)
    if gaps:
        for g in gaps:
            print("REFUSE: " + g, file=sys.stderr)
        return 1
    print("OK: K4 round-trip (%d stor(ies))" % len(partition.get("stories") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
