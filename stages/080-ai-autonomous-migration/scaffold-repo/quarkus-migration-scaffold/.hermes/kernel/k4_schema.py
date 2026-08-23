"""K4 mint converter schema (AD-019 §4 K4). Not a skill. Not dest-apply.

Write-set source is the typed partition row. PATH_TOKEN over tasks.md is
OBJECT. Does not import create_task. Does not shell hermes kanban.
Does not read type-inventory reached_from (partition files_writable only).
"""
from __future__ import annotations

WRITER_ID = "mint-writer"
VERIFIER_ID = "mint-verifier"
ORCH = "orchestrator"
IMPL = "implementer"
PATH_TOKEN_MARKERS = ("PATH_TOKEN",)
SHA256_RE = r"^[0-9a-f]{64}$"

REMEDY = {
    "K4_SCHEMA": (
        "Partition needs type_inventory_sha256 (64 hex) and stories[] with "
        "story_id, files_writable[], and parents[] from the import graph. "
        "Do not import create_task."
    ),
    "K4_PATH_TOKEN": (
        "Do not scrape write-sets from tasks.md. Copy files_writable from the "
        "typed partition row for that logical story_id."
    ),
    "K4_SCOPE": "M3 payloads need non-empty files_writable copied from the partition.",
    "K4_CREATED_CARDS": (
        "Manifest created_cards must be the exact non-empty payload logical_id "
        "list in create order ([] skips — forbid). Worker maps those to Hermes "
        "t_* after kanban_create."
    ),
    "K4_PLANNING_DEFECT": (
        "A path named in tasks.md but absent from the partition is a planning "
        "defect. Report every such path. Do not grow the write-set from prose."
    ),
    "K4_ASSIGNEE": "mint-writer and mint-verifier assignee=orchestrator; M3 assignee=implementer.",
    "K4_PARENT": (
        "M3 parents come from the partition import-graph plus the mint-verifier "
        "as common parent. Not Dependencies English."
    ),
}
