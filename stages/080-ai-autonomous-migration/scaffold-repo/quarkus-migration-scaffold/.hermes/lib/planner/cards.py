"""Cards from the work list (SAD v3 §8): the single home for kind → skill pins
and for deriving the next card. K4 converts exactly one card at a time:
the head cluster, or M4 VERIFY when the list is empty and nothing is
deferred. Titles are "M3 <cluster id>" and "M4 VERIFY"."""
from __future__ import annotations

from typing import Any

from planner.worklist import head_cluster

CLOSE_ID = "M4_VERIFY"
CLUSTER_KINDS = ("build", "config", "compile", "incident", "test", "parity")
KINDS = CLUSTER_KINDS + ("close",)

# producer first; fix-until-green is the common procedure, never a producer
CARD_SKILLS: dict[str, list[str]] = {
    "build": ["manage-quarkus-extensions", "author-destination-pom", "reference-rh-quarkus-pom", "fix-until-green"],
    "config": ["configure-quarkus-profiles", "fix-until-green"],
    "compile": ["spring-to-quarkus-patterns", "form-entity-persistence", "fix-until-green"],
    "incident": ["spring-to-quarkus-patterns", "form-entity-persistence", "fix-until-green"],
    "test": ["spring-to-quarkus-patterns", "fix-until-green"],
    "parity": ["spring-to-quarkus-patterns", "fix-until-green"],
    "close": ["compose-m4-verdict", "check-release-readiness", "check-domain-parity", "capture-source-oracles"],
}


def next_card(worklist: dict[str, Any], steps: dict[str, Any] | None) -> dict[str, Any] | None:
    """The one card the loop needs now, or None when the run cannot proceed
    (a deferred cluster is open and nothing else is left)."""
    attempts = dict((steps or {}).get("attempts") or {})
    head = head_cluster(worklist)
    if head is not None:
        return {
            "id": head["id"],
            "kind": head["kind"],
            "title": "M3 %s" % head["id"],
            "phase": "M3",
            "path": head["path"],
            "write_set": list(head["write_set"]),
            "items": list(head["items"]),
            "attempt": int(attempts.get(head["id"], 0)) + 1,
            "skills": list(CARD_SKILLS[head["kind"]]),
        }
    if worklist.get("deferred") or worklist.get("blocked_clusters"):
        return None
    m = worklist.get("measure") or {}
    if not m.get("known") or not all(v == 0 for v in (m.get("tuple") or [1])):
        return None
    return {
        "id": CLOSE_ID,
        "kind": "close",
        "title": "M4 VERIFY",
        "phase": "M4",
        "path": "",
        "write_set": ["evidence/verdicts/", "verification/"],
        "items": [],
        "attempt": 1,
        "skills": list(CARD_SKILLS["close"]),
    }


def idempotency_key(card_id: str, attempt: int, receipt_digest: str) -> str:
    return "k4:%s:%d:%s" % (card_id, attempt, receipt_digest[:16])
