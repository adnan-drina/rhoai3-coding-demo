#!/usr/bin/env python3
"""O-SHIPNOPRSTALE — decide if an existing PipelineRun is fresh for this ship session.

When git push is Everything up-to-date, O-SHIPNOPR may judge an existing
PipelineRun — but only if that run belongs to *this* ship session. Prior
Failed/Succeeded runs from abandoned rounds must not open Deploy/Build/Gate
fix seats (V10 S02: Failed …-push-7dsdg after GREEN closing preflight).

Fresh means:
  1. PipelineRun creationTimestamp is at/after ship-session start, AND
  2. when both revision and HEAD are supplied, they share the same commit
     (prefix match OK for short SHAs).

O-SHIPPREPUSHSESSION (W4-670): if revision and HEAD match (same tip already
on remote before SHIP_ONLY), accept as fresh even when the PipelineRun was
created slightly before ship-session-started — the pre-push trap. Mismatched
revision stays stale.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone


def _parse_ts(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s:
        return None
    if s.isdigit():
        return float(s)
    # RFC3339 / Kubernetes creationTimestamp
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def _sha_match(pr_rev: str, head: str) -> bool:
    a = (pr_rev or "").strip().lower()
    b = (head or "").strip().lower()
    if not a or not b:
        return True  # unknown → do not block on SHA
    n = min(len(a), len(b), 40)
    if n < 7:
        return a == b
    return a[:n] == b[:n]


def decide(
    pr_created: str,
    session_started: str,
    pr_revision: str = "",
    head_sha: str = "",
) -> str:
    if not (pr_created or "").strip():
        return "no-pr"
    pr_ts = _parse_ts(pr_created)
    sess_ts = _parse_ts(session_started)
    if pr_ts is None or sess_ts is None:
        # Missing/unparseable session stamp → refuse to judge prior runs
        return "stale"
    # O-SHIPPREPUSHSESSION: same-revision tip already built before session
    # (credential/resume pre-push) is honest evidence — not an abandoned round.
    # Require both SHAs present so unknown-revision pre-session stays stale.
    same_tip = (
        bool((pr_revision or "").strip())
        and bool((head_sha or "").strip())
        and _sha_match(pr_revision, head_sha)
    )
    if same_tip:
        return "fresh"
    if pr_ts + 0.5 < sess_ts:  # small skew tolerance
        return "stale"
    if not _sha_match(pr_revision, head_sha):
        return "stale"
    return "fresh"


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: shipnoprstale-decide.py <pr_created> <session_started> "
            "[pr_revision] [head_sha]",
            file=sys.stderr,
        )
        return 2
    pr_rev = sys.argv[3] if len(sys.argv) > 3 else ""
    head = sys.argv[4] if len(sys.argv) > 4 else ""
    print(decide(sys.argv[1], sys.argv[2], pr_rev, head))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
