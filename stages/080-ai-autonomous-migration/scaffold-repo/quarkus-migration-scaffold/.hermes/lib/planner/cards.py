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
OWED_ADAPTER_RULE = "unit/owed-adapter/v1"
OWED_ADAPTER_SKILL = "restore-source-response-shape"

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


def _machine_body(body: dict[str, Any]) -> list[str]:
    return [
        "",
        "<details><summary>machine body (K1)</summary>",
        "",
        BODY_FENCE,
        json.dumps(body, sort_keys=True, separators=(",", ":")),
        "```",
        "",
        "</details>",
    ]


def _close_prose(body: dict[str, Any]) -> str:
    """The M4 VERIFY card, in the prose a human reads on the board.

    A close card used to be rendered with the M3 loop's prose: "it views
    fix-until-green", "read the brief", "run-verify then advance", "complete
    after ACCEPTED". Only the machine body carried M4's own exits, and the
    markdown is what `hermes kanban show` displays -- so the card told the
    worker to run the repair loop on a phase that has no repair loop, and to
    end on a terminator K2 refuses here (measured on v9's t_32c82390)."""
    lines = [
        "## M4 VERIFY",
        "",
        "- **Receipt** `%s`, work list `%s`" % (str(body.get("receipt_sha256") or "")[:16], str(body.get("worklist_sha256") or "")[:16]),
        "- **Write set**: `evidence/verdicts/`, `verification/` — evidence only. YOU do not edit the product tree at M4. "
        "The one exception is not yours: the harness generates `src/parity-test/` and commits it (ADR-015), which is why "
        "the tree is still retrievable when the verdict is composed.",
        "- **Road**: `skill_view paved-road-m4` first (the pinned index; its `steps.json` is the contract).",
        "",
        "**Do**, in this order:",
        "",
    ]
    # The producer is a SKILL, not a command, so it has no exit cmd to list --
    # and a Do list that jumps from the pre-verdict runner to the verdict
    # linter never says who writes the verdict in between.
    for e in body.get("exit_criteria") or []:
        if not isinstance(e, dict) or not e.get("cmd"):
            continue
        if str(e.get("check")) == "generate_tests":
            lines.append("    skill_view generate-product-tests   # ADR-015: the harness writes the product acceptance tests; you never author or weaken one")
        if str(e.get("check")) == "commit_tests":
            lines.append("    # assert-retrievable-tree refuses the generated files while they are untracked; this commits them, and only them")
        if str(e.get("check")) == "rescan":
            lines.append("    # the analyzer over the tree as just committed; the floor on the next line judges its record (verification/mta-rescan/findings.json), never evidence/mta-findings.json")
        if str(e.get("check")) == "verdict_schema":
            lines.append("    skill_view compose-m4-verdict   # author evidence/verdicts/m4-verdict.json from the exits above")
        lines.append("    %s" % e["cmd"])
    if not any(str((e or {}).get("check")) == "verdict_schema" for e in (body.get("exit_criteria") or []) if isinstance(e, dict)):
        lines.append("    skill_view compose-m4-verdict   # author evidence/verdicts/m4-verdict.json from the exits above")
    lines += [
        "",
        "Then read `evidence/verdicts/m4-verdict.json`: it is COMPOSED from the exit codes above and nothing else. "
        "`REFUSE` is a verdict — the honest result of a measurement — not a failure to close, and not something to "
        "re-run the phase hoping to change. Parity is the batch runner, once: there is no per-entry-point loop for "
        "you to drive, and `verification/parity/_run.json` records what actually ran. "
        "The generated product tests are the harness's (`evidence/tests/generated-manifest.json` lists every one of "
        "them with its digest): they are written to `src/parity-test/java`, the pre-verdict runner is what compiles "
        "and runs them (`-Pm4-parity`), and the release floor refuses when a byte of one moved. A generated case "
        "that fails is a parity finding for the destination, never an expectation to edit. They are also COMMITTED "
        "here, by `commit-generated-tests.py`, and only they: `assert-retrievable-tree` still requires `src/` and "
        "`pom.xml` to be committed, an untracked generated file is dirt to it, and a verdict composed over a tree "
        "nobody can retrieve says nothing about what was measured. Anything else you changed under `src/`, you "
        "commit — that step refuses to sweep it into the harness's commit.",
        "Terminator: `kanban_request_review` with `reviewer=reviewer`, once the verdict file exists — for EVERY "
        "verdict it can hold. Never `kanban_complete` (K2 refuses it on this card). Never `kanban_block` for a "
        "REFUSE verdict; block only when the phase could not measure at all (no destination, no database, no "
        "corpus). Never dest-dispatch M5.",
    ]
    return "\n".join(lines + _machine_body(body))


def render_body(body: dict[str, Any]) -> str:
    """Card body a human can read on the board: a Markdown summary first, the
    exact machine body (what K1 validates) in one fenced json block after it.
    parse_body() recovers the machine body from either form."""
    ident = body.get("identity") or {}
    writes = [str(w.get("path") if isinstance(w, dict) else w) for w in body.get("write_set") or []]
    steps = [e.get("cmd") for e in body.get("exit_criteria") or [] if isinstance(e, dict) and e.get("cmd")]
    kind = str(ident.get("increment_kind") or "")
    if kind == "close":
        return _close_prose(body)
    ref = REFERENCE_SKILLS.get(kind, "")
    if str((body.get("unit") or {}).get("rule") or "") == OWED_ADAPTER_RULE:
        # ADR-019: a card owed a harness adapter installs it through its capability
        ref = OWED_ADAPTER_SKILL
    cid = str(ident.get("increment_id") or "")
    brief_cmd = "python3 .hermes/skills/migration/fix-until-green/scripts/brief.py --root ."
    if cid:
        brief_cmd += " --cluster %s" % cid
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
        "**Do**: `%s` to read the brief; patch the write set one item at a time (never a whole-file rewrite, never tests, never a dependency or plugin the brief did not ask for, never an artifact the brief marks unmanaged, never satisfy an item by deleting the code or config it is about: a profile file's keys move to `application.properties` as `%%<profile>.<key>`); then:" % brief_cmd,
        "",
    ]
    lines += ["    %s" % c for c in steps]
    lines += [
        "",
        "The tools decide: ACCEPTED commits and mints the next card; REVERTED re-mints this cluster; CONTINUE (exit 3, repair-family cards) keeps the candidate on the tree -- keep working THIS card on the members it names, then verify and advance again; VERIFICATION_PENDING retains the candidate without counting an attempt; DEFERRED stops the loop.",
        "Terminator: `kanban_complete` after ACCEPTED or REVERTED (the loop record is the audit; K2 allows it). `kanban_block` kind=needs_input naming the cluster after VERIFICATION_PENDING, DEFERRED or a `REFUSE: LOOP_*`. CONTINUE is not a verdict: neither complete nor block. Never `kanban_request_review` on a loop card; never retry inside this card after REVERTED (the retry is the next K4 card).",
    ]
    return "\n".join(lines + _machine_body(body))


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
        # A formed unit carries its sealed identity onto the card: the rule, the
        # symbols, the documented targets, the evidence and the completion
        # checks. The MEMBERS stay in the sealed inventory the card's refs point
        # at -- a body is not where an inventory lives.
        if head.get("unit"):
            card["unit"] = dict(head["unit"])
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
