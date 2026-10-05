"""One answer to "how much patience does this problem have left".

The planner, the issued card, the brief, a rejection and a deferral each used
to compute it their own way: the brief subtracted the rejected rows it could
find from max_attempts, advance raised the limit only for a clearance whose
cluster id equalled the RETRY KEY it was passed, and a clearance recorded the
attempts counted against the cluster id while the attempts were counted
against the retry key. Three of those disagreed on v8 (architect recovery
review, 2026-09-11). Everything now asks this module.

Nothing here deletes history. A deferral clearance raises the budget by what
the problem had spent when it was cleared; the attempts and the cards they
minted stay on record (the live-board comparator expects every one of them).
"""
from __future__ import annotations

from typing import Any


def retry_key_for(steps: dict[str, Any], cluster: str, fallback: str = "") -> str:
    """The key a cluster's attempts are counted against, as recorded."""
    return str(((steps or {}).get("retry_keys") or {}).get(cluster) or fallback or cluster)


def attempts_spent(steps: dict[str, Any], cluster: str, key: str) -> int:
    """How many rejections this PROBLEM has cost.

    Counted against the retry key. An older run counted against the cluster id;
    those records are kept and still count, so an upgrade cannot hand a
    problem a fresh budget it had already spent."""
    attempts = (steps or {}).get("attempts") or {}
    spent = int(attempts.get(key, 0) or 0)
    if key != cluster:
        spent = max(spent, int(attempts.get(cluster, 0) or 0))
    return spent


def _clearances(steps: dict[str, Any], cluster: str, key: str) -> list[dict[str, Any]]:
    ids = {cluster, key}
    mapped = (steps or {}).get("retry_keys") or {}
    return [c for c in ((steps or {}).get("deferral_clearances") or [])
            if str(c.get("cluster") or "") in ids or str(c.get("retry_key") or "") in ids
            or str(mapped.get(str(c.get("cluster") or "")) or "") in ids]


def attempt_budget(steps: dict[str, Any], cluster: str, limit: int, key: str = "") -> int:
    """How many rejected attempts this problem may spend before it defers:
    ``limit`` fresh attempts from where it stood at its latest clearance.

    A clearance is matched by the cluster it named, by the retry key it
    recorded, or by the key that cluster maps to -- whichever of the two
    identities the caller holds."""
    key = key or retry_key_for(steps, cluster)
    spent_at = [int(c.get("attempts") or 0) for c in _clearances(steps, cluster, key)]
    return int(limit) + (max(spent_at) if spent_at else 0)


def budget(steps: dict[str, Any], cluster: str, key: str, limit: int) -> dict[str, Any]:
    """The whole answer, for anything that shows or records it."""
    key = key or retry_key_for(steps, cluster)
    spent = attempts_spent(steps, cluster, key)
    lim = attempt_budget(steps, cluster, limit, key)
    return {"retry_key": key, "spent": spent, "limit": lim, "left": max(0, lim - spent),
            "clearances": len(_clearances(steps, cluster, key)), "max_attempts": int(limit)}
