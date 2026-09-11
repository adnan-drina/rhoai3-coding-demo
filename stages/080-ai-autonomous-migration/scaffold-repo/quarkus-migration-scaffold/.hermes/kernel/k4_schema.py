"""K4 converter/mint schema (AD-019 §4 K4, work-list model; SAD v3 §8).

Not a skill. Not dest-apply. Input is ``evidence/planning/worklist.json``
plus an ADMITTED ``admission-receipt.json`` — never a partition, never a
DAG, never prose. K4 emits exactly one card: the head cluster, or M4
VERIFY when the list is empty and nothing is deferred. Does not import
create_task. Does not shell ``hermes kanban`` except from ``k4_mint.py --exec``.
"""
from __future__ import annotations

WRITER_ID = "mint-writer"
VERIFIER_ID = "mint-verifier"
CLOSE_ID = "M4_VERIFY"
IMPL = "implementer"
SHA256_RE = r"^[0-9a-f]{64}$"
KEY_PREFIX = "k4:"
RECEIPT_STEM = 16
KINDS = ("build", "config", "compile", "incident", "test", "parity", "close")
M3_KINDS = frozenset({"build", "config", "compile", "incident", "test", "parity"})

REMEDY = {
    "K4_SCHEMA": "K4 reads evidence/planning/worklist.json and admission-receipt.json. Do not import create_task.",
    "K4_RECEIPT": (
        "K4 emits zero commands unless admission-receipt.json is ADMITTED and every seal "
        "(bundle, work list, bootstrap, decisions.yaml, contracts, pins) matches disk. Run "
        "verify → advance to re-admit; never edit an artifact."
    ),
    "K4_ACTIVATION": "K4 re-derives the activation/pilot verdict from .hermes/pins.json; a receipt text never overrides it.",
    "K4_PINS": "Mandatory tool pins must be present and match their producer receipts (TOOL_UNPINNED / TOOL_PIN_MISMATCH).",
    "K4_LOOP": (
        "No card can be minted: a deferred (manual) cluster is open, a VERIFICATION_PENDING "
        "candidate is retained (restore it and re-verify; do not mint a new attempt), or the "
        "measure is not fully known. kanban_block kind=needs_input naming the cluster."
    ),
    "K4_SCOPE": "M3 bodies need files_writable equal to the cluster write set; the close card writes only evidence/ and verification/.",
    "K4_CREATED_CARDS": "Manifest created_cards is the exact one-element payload list ([] forbids).",
    "K4_FACTORY": "Dest mint-writer / mint-verifier LLM cards are retired. k4_mint.py is CLI translation.",
    "K4_ASSIGNEE": "M3/M4 assignee=implementer.",
    "K4_PARENT": "The parent is the previous accepted step's card (from verification/loop/steps.json) plus the M2 card; never invented.",
    "K4_MINT_CREATE": "Mint argv is hermes kanban create with inline --body. No create_task, swarm, decompose, link, daemon --force.",
    "K4_MINT_TITLE": "Titles are 'M3 <kind> <file> (<n> items, attempt <k>)' for cluster cards (planner.cards.card_title) and 'M4 VERIFY' for the close card.",
    "K4_MINT_RETRIES": "Every create passes --max-retries 1 (CLI).",
    "K4_MINT_PARENT": "Resolve parents from minted t_* ids; do not invent parents.",
    "K4_MINT_ID": "Parse create --json for task_id or id (t_*). Serialize creates; created_cards is the real t_* list.",
    "K4_MINT_KEY": "Idempotency key is k4:<cluster>:<attempt>:<receipt_digest[:16]>; never a fixed key.",
    "K4_MINT_WORKSPACE": "--workspace dir:/projects/modernized (or a subdirectory); scratch workspaces are OBJECT.",
    "K4_MINT_SKILLS": "Every card pins its kind skills (planner.cards.CARD_SKILLS); at least one producer.",
    "K4_PRODUCER": "A card must pin at least one skill that produces its primary artifact (k4_producers.py).",
    "K4_NO_PRODUCER": "A card must pin at least one skill that produces its primary artifact; checkers do not count; on a loop card fix-until-green is the producer (k4_producers.py).",
    "K4_BOARD": "After --exec the live board must equal the expected loop cards (K3 live comparator); foreign or missing cards refuse.",
}
