"""Cards from the work list (SAD v3 §8): the single home for kind → skill pins
and for deriving the next card. K4 converts exactly one card at a time:
the head cluster, or M4 VERIFY when the list is empty and nothing is
deferred. Titles are "M3 <cluster id>" and "M4 VERIFY"."""
from __future__ import annotations

import json
from typing import Any

from planner.budget import attempts_spent  # noqa: E402
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
# Every loop card pins the M3 index only (paved-road-m3: view fix-until-green,
# brief, patch per item, run-verify, advance, complete). The producer of a
# loop artifact is the transaction the index walks (k4_producers).
CARD_SKILLS: dict[str, list[str]] = {
    "build": ["paved-road-m3"],
    "config": ["paved-road-m3"],
    "compile": ["paved-road-m3"],
    "incident": ["paved-road-m3"],
    "test": ["paved-road-m3"],
    "parity": ["paved-road-m3"],
    # M4 pins the index only (paved-road-m4: oracles → parity → pre-verdict
    # runner → compose the verdict from measured exits → lint). The gate
    # skills are its steps; pinning them on the card made the phase a
    # checklist of tools instead of a road.
    "close": ["paved-road-m4"],
}

BODY_FENCE = "```json"

# One reference skill per cluster kind, named in the body and viewed only when
# the brief's advice is not enough (never pinned: pins on v5 loop cards became
# checklists and a whole-pom rewrite). build items need none: the brief carries
# the pom element, the BOM-managed set and the alias catalog.
REFERENCE_SKILLS: dict[str, str] = {
    "build": "",
    "config": "configure-quarkus-profiles",
    "compile": "spring-to-quarkus-patterns",
    "incident": "spring-to-quarkus-patterns",
    "test": "spring-to-quarkus-patterns",
    "parity": "spring-to-quarkus-patterns",
}


def card_title(head: dict[str, Any], attempt: int) -> str:
    """Readable card name: kind, file, item count, attempt. The cluster id
    stays in the body and the idempotency key."""
    n = len(head.get("items") or [])
    if head.get("label"):
        files = len(head.get("write_set") or [])
        return "M3 %s %s (%d item%s, %d file%s, attempt %d)" % (head.get("kind"), head["label"], n, "" if n == 1 else "s", files, "" if files == 1 else "s", attempt)
    name = str(head.get("path") or "").rsplit("/", 1)[-1] or str(head.get("path") or head.get("id"))
    return "M3 %s %s (%d item%s, attempt %d)" % (head.get("kind"), name, n, "" if n == 1 else "s", attempt)


def render_body(body: dict[str, Any]) -> str:
    """Card body a human can read on the board: a Markdown summary first, the
    exact machine body (what K1 validates) in one fenced json block after it.
    parse_body() recovers the machine body from either form."""
    ident = body.get("identity") or {}
    writes = [str(w.get("path") if isinstance(w, dict) else w) for w in body.get("write_set") or []]
    steps = [e.get("cmd") for e in body.get("exit_criteria") or [] if isinstance(e, dict) and e.get("cmd")]
    kind = str(ident.get("increment_kind") or "")
    ref = REFERENCE_SKILLS.get(kind, "")
    lines = [
        "## %s %s" % (body.get("phase") or "M3", ident.get("path") or ident.get("increment_id") or ""),
        "",
        "- **Cluster** `%s` (%s), attempt %s" % (ident.get("increment_id"), kind, ident.get("attempt")),
        "- **Write set**: %s" % (", ".join("`%s`" % w for w in writes) or "(none)"),
        "- **Items**: %d (the brief lists each one with its advice)" % len(body.get("item_ids") or []),
        "- **Receipt** `%s`, work list `%s`" % (str(body.get("receipt_sha256") or "")[:16], str(body.get("worklist_sha256") or "")[:16]),
        "- **Road**: `skill_view paved-road-m3` first (the pinned index); it views `fix-until-green`.",
        ("- **Reference** (only if the brief's advice is not enough): `skill_view %s`" % ref) if ref else "- **Reference**: none; the brief carries the pom element, the BOM-managed set and the alias catalog.",
        "",
        "**Do**: `python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root .` to read the brief; patch the write set one item at a time (never a whole-file rewrite, never tests, never a dependency or plugin the brief did not ask for, never an artifact the brief marks unmanaged, never satisfy an item by deleting the code or config it is about: a profile file's keys move to `application.properties` as `%<profile>.<key>`); then:",
        "",
    ]
    lines += ["    %s" % c for c in steps]
    lines += [
        "",
        "The tools decide: ACCEPTED commits and mints the next card; REVERTED re-mints this cluster; CONTINUE (exit 3, repair-family cards) keeps the candidate on the tree -- keep working THIS card on the members it names, then verify and advance again; VERIFICATION_PENDING retains the candidate without counting an attempt; DEFERRED stops the loop.",
        "Terminator: `kanban_complete` after ACCEPTED or REVERTED (the loop record is the audit; K2 allows it). `kanban_block` kind=needs_input naming the cluster after VERIFICATION_PENDING, DEFERRED or a `REFUSE: LOOP_*`. CONTINUE is not a verdict: neither complete nor block. Never `kanban_request_review` on a loop card; never retry inside this card after REVERTED (the retry is the next K4 card).",
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


def pending_cluster_ids(steps: dict[str, Any] | None) -> list[str]:
    """Clusters with an uncleared VERIFICATION_PENDING candidate (do not mint)."""
    out: list[str] = []
    for row in (steps or {}).get("pending") or []:
        if isinstance(row, dict) and row.get("cluster") and not row.get("cleared") and not row.get("rewound"):
            cid = str(row["cluster"])
            if cid not in out:
                out.append(cid)
    return out


def next_card(worklist: dict[str, Any], steps: dict[str, Any] | None) -> dict[str, Any] | None:
    """The one card the loop needs now, or None when the run cannot proceed
    (a deferred cluster is open, a pending candidate is retained, or nothing else is left)."""
    attempts = dict((steps or {}).get("attempts") or {})
    if pending_cluster_ids(steps):
        return None
    head = head_cluster(worklist)
    if head is not None:
        rk = str(head.get("retry_key") or head["id"])
        spent = attempts_spent(steps or {}, head["id"], rk)  # planner.budget: the one definition
        card = {
            "id": head["id"],
            "kind": head["kind"],
            "title": card_title(head, spent + 1),
            "phase": "M3",
            "path": head["path"],
            "write_set": list(head["write_set"]),
            "items": list(head["items"]),
            "attempt": spent + 1,
            "skills": list(CARD_SKILLS[head["kind"]]),
        }
        if head.get("gate"):
            card["gate"] = str(head["gate"])
        if head.get("batch_scope"):
            card["batch_scope"] = dict(head["batch_scope"])
        if head.get("retry_key"):
            card["retry_key"] = rk
        return card
    if worklist.get("deferred") or worklist.get("blocked_clusters"):
        return None
    m = worklist.get("measure") or {}
    if not m.get("known") or not all(v == 0 for v in (m.get("tuple") or [1])):
        return None
    # An empty work list means the tree compiles and its tests pass. It does
    # not mean the application was built or started: those are the transitions
    # out of the repair loop, and a gate that never ran is unknown, never
    # clean (pilot v7 minted M4 on a destination that could not be packaged).
    if not (worklist.get("runtime") or {}).get("ready"):
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
