#!/usr/bin/env python3
"""F12 / AD-002G P0.1 — success-path request composition probe.

Hermes writes full request dumps on API failure by default. Setting
``HERMES_DUMP_REQUESTS=1`` also writes ``reason=preflight`` dumps before each
successful API call (see hermes-agent conversation_loop).

This script:
1. Scans ``$HERMES_HOME/sessions/request_dump_*.json``
2. Emits a **redacted composition summary** (sizes + heading presence only)
3. Exits 0 when ≥1 ``preflight`` dump exists (success-path provenance)

Never prints Authorization headers or raw dump bodies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.M)


def _msg_stats(messages: list) -> dict:
    roles: dict[str, dict] = {}
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "unknown")
        content = m.get("content")
        if isinstance(content, list):
            text = "".join(
                str(p.get("text", "")) if isinstance(p, dict) else str(p)
                for p in content
            )
        else:
            text = str(content or "")
        bucket = roles.setdefault(role, {"count": 0, "chars": 0})
        bucket["count"] += 1
        bucket["chars"] += len(text)
    return roles


def _headings(text: str, limit: int = 40) -> list[str]:
    found = [h.strip() for h in HEADING_RE.findall(text or "")]
    # Prefer unique order-preserving
    out: list[str] = []
    seen: set[str] = set()
    for h in found:
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def summarize_dump(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {"path": path.name, "error": str(exc)}

    reason = data.get("reason")
    req = data.get("request") or {}
    body = req.get("body") if isinstance(req, dict) else {}
    if not isinstance(body, dict):
        body = {}
    messages = body.get("messages") or []
    tools = body.get("tools") or body.get("functions") or []
    system_text = ""
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "system":
            c = m.get("content")
            system_text += c if isinstance(c, str) else str(c or "")

    return {
        "path": path.name,
        "reason": reason,
        "session_id": data.get("session_id"),
        "timestamp": data.get("timestamp"),
        "model": body.get("model"),
        "max_tokens": body.get("max_tokens"),
        "tool_count": len(tools) if isinstance(tools, list) else None,
        "message_roles": _msg_stats(messages if isinstance(messages, list) else []),
        "system_chars": len(system_text),
        "system_headings_sample": _headings(system_text),
        "skills_mandatory_present": "## Skills (mandatory)" in system_text
        or "Skills (mandatory)" in system_text,
        "agents_heading_present": "## AGENTS.md" in system_text or "# Agent Guide" in system_text,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--hermes-home",
        default=os.environ.get("HERMES_HOME", "/projects/modernized/.hermes/home"),
    )
    ap.add_argument(
        "--out",
        default="",
        help="Write JSON summary here (default: migration/derived under workspace)",
    )
    ap.add_argument(
        "--require-preflight",
        action="store_true",
        help="Exit 1 unless ≥1 reason=preflight dump exists",
    )
    args = ap.parse_args()
    home = Path(args.hermes_home)
    sessions = home / "sessions"
    dumps = sorted(sessions.glob("request_dump_*.json")) if sessions.is_dir() else []

    summaries = [summarize_dump(p) for p in dumps]
    preflight = [s for s in summaries if s and s.get("reason") == "preflight"]
    failure = [
        s
        for s in summaries
        if s and s.get("reason") in {"max_retries_exhausted", "non_retryable_client_error"}
    ]

    report = {
        "schema": "rhoai3.success-path-composition/v1",
        "finding": "F12",
        "ad": "AD-002G P0.1 / R14",
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hermes_home": str(home),
        "dump_count": len(dumps),
        "preflight_count": len(preflight),
        "failure_dump_count": len(failure),
        "how_to_capture": (
            "export HERMES_DUMP_REQUESTS=1 before a Hermes spawn; "
            "preflight dumps are written for every API call (redacted). "
            "Example: HERMES_DUMP_REQUESTS=1 hermes chat -q 'pong' -Q --max-turns 1 "
            "-s sdd-readiness,spring-to-quarkus-patterns"
        ),
        "preflight": preflight,
        "failure_sample": failure[:3],
        "verdict": "PASS" if preflight else "INCONCLUSIVE_NO_PREFLIGHT",
    }

    out = Path(args.out) if args.out else Path("/projects/modernized/migration/derived") / (
        f"success-path-composition-{report['stamped_at'].replace(':', '')}.json"
    )
    if not args.out and not Path("/projects/modernized/migration/derived").is_dir():
        # tip/local fallback
        out = Path("measurements/cleanroom-petclinic-e2e/v10-f12-success-path") / out.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"probe-success-path-composition: wrote {out} "
        f"dumps={len(dumps)} preflight={len(preflight)} verdict={report['verdict']}"
    )
    if args.require_preflight and not preflight:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
