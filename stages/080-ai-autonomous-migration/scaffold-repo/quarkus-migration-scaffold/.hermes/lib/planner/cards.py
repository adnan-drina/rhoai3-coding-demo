"""Cards from the work list (SAD v3 §8): the single home for kind → skill pins
and for deriving the next card. K4 converts exactly one card at a time:
the head cluster, or M4 VERIFY when the list is empty and nothing is
deferred. Titles are "M3 <cluster id>" and "M4 VERIFY"."""
from __future__ import annotations

import json
from typing import Any

from planner.worklist import head_cluster

CLOSE_ID = "M4_VERIFY"
CLUSTER_KINDS = ("build", "config", "compile", "incident", "test", "parity")
KINDS = CLUSTER_KINDS + ("close",)

# producer first; fix-until-green is the common procedure, never a producer
# One skill per loop card. Pilot v5 (2026-09-09, card t_3efca989) measured
# what the story-era pom skills do on a loop card: they pulled the worker
# toward Jacoco/Sonar/assertj/mapstruct/package-root changes no incident asked
# for and a whole-pom rewrite that timed out. The brief carries the incidents
# and their advice; fix-until-green carries the procedure; nothing else.
CARD_SKILLS: dict[str, list[str]] = {
    "build": ["fix-until-green"],
    "config": ["fix-until-green"],
    "compile": ["fix-until-green"],
    "incident": ["fix-until-green"],
    "test": ["fix-until-green"],
    "parity": ["fix-until-green"],
    "close": ["compose-m4-verdict", "check-release-readiness", "check-domain-parity", "capture-source-oracles"],
}

BODY_FENCE = "```json"


def card_title(head: dict[str, Any], attempt: int) -> str:
    """Readable card name: kind, file, item count, attempt. The cluster id
    stays in the body and the idempotency key."""
    n = len(head.get("items") or [])
    name = str(head.get("path") or "").rsplit("/", 1)[-1] or str(head.get("path") or head.get("id"))
    return "M3 %s %s (%d item%s, attempt %d)" % (head.get("kind"), name, n, "" if n == 1 else "s", attempt)


def render_body(body: dict[str, Any]) -> str:
    """Card body a human can read on the board: a Markdown summary first, the
    exact machine body (what K1 validates) in one fenced json block after it.
    parse_body() recovers the machine body from either form."""
    ident = body.get("identity") or {}
    writes = [str(w.get("path") if isinstance(w, dict) else w) for w in body.get("write_set") or []]
    steps = [e.get("cmd") for e in body.get("exit_criteria") or [] if isinstance(e, dict) and e.get("cmd")]
    lines = [
        "## %s %s" % (body.get("phase") or "M3", ident.get("path") or ident.get("increment_id") or ""),
        "",
        "- **Cluster** `%s` (%s), attempt %s" % (ident.get("increment_id"), ident.get("increment_kind"), ident.get("attempt")),
        "- **Write set**: %s" % (", ".join("`%s`" % w for w in writes) or "(none)"),
        "- **Items**: %d (the brief lists each one with its advice)" % len(body.get("item_ids") or []),
        "- **Receipt** `%s`, work list `%s`" % (str(body.get("receipt_sha256") or "")[:16], str(body.get("worklist_sha256") or "")[:16]),
        "",
        "**Do**: `python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .` to read the brief; patch the write set one item at a time (never a whole-file rewrite, never tests); then:",
        "",
    ]
    lines += ["    %s" % c for c in steps]
    lines += [
        "",
        "The tools decide: ACCEPTED commits and mints the next card; REVERTED re-mints this cluster; DEFERRED stops the loop.",
        "Terminator: `kanban_request_review` (reviewer=reviewer), then end the turn. Never `kanban_complete`.",
        "",
        "<details><summary>machine body (K1)</summary>",
        "",
        BODY_FENCE,
        json.dumps(body, sort_keys=True, separators=(",", ":")),
        "```",
        "",
        "</details>",
    ]
    return "\n".join(lines)


def parse_body(text: Any) -> dict[str, Any]:
    """The machine body from a card body: pure JSON, or the fenced json block
    render_body() writes. {} when neither parses."""
    if isinstance(text, dict):
        return text
    raw = str(text or "")
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    i = raw.find(BODY_FENCE)
    if i < 0:
        return {}
    j = raw.find("```", i + len(BODY_FENCE))
    if j < 0:
        return {}
    try:
        parsed = json.loads(raw[i + len(BODY_FENCE):j].strip())
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def next_card(worklist: dict[str, Any], steps: dict[str, Any] | None) -> dict[str, Any] | None:
    """The one card the loop needs now, or None when the run cannot proceed
    (a deferred cluster is open and nothing else is left)."""
    attempts = dict((steps or {}).get("attempts") or {})
    head = head_cluster(worklist)
    if head is not None:
        return {
            "id": head["id"],
            "kind": head["kind"],
            "title": card_title(head, int(attempts.get(head["id"], 0)) + 1),
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
