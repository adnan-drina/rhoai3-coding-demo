"""K3 mint-verifier procedure (AD-019 §4 K3). Not a skill. Not dest PID reclaim.

Native parents ADOPT hold/release. REFUSE is not claimed control on this pin
(dest live-PID was MEASURED, not refuse-as-control GO).
"""
from __future__ import annotations

TERMINATORS = frozenset({"kanban_complete", "kanban_request_review", "kanban_block"})
LEGAL_REFUSE = "kanban_block"
OBJECT_VERIFIER_REVIEW = "kanban_request_review"
WRITER_ROLE = "mint-writer"
VERIFIER_ROLE = "mint-verifier"
ORCH = "orchestrator"
IMPL = "implementer"
ACK_GATE_MARKERS = ("ack_gate", "ack-gate", "human_ack")
RELEASE_STATUSES = frozenset({"done", "archived"})

REMEDY = {
    "K3_SCHEMA": (
        "Graph snapshot needs cards[] with id/role/assignee/status/parents. "
        "Dest factory cards are retired (both absent) or leftover (both "
        "present). Do not import create_task."
    ),
    "K3_CREATED_CARDS": (
        "Mint-writer complete must carry the exact manifest created_cards set. "
        "Empty list is forbidden (native skip)."
    ),
    "K3_VERIFIER_MISSING": (
        "Add one mint-verifier card (check, not write) assigned to orchestrator."
    ),
    "K3_VERIFIER_PARENT": (
        "Every M3 root must list the mint-verifier as a parent so native "
        "unfinished-parent hold keeps M3 todo until the verifier is done or archived."
    ),
    "K3_TERMINATOR": (
        "Verifier ACCEPT is kanban_complete. Verifier REFUSE is sticky "
        "kanban_block (not kanban_request_review — a reviewer complete would "
        "release M3). Same-card review on the mint-writer is OBJECT."
    ),
    "K3_ACK_GATE": "Delete the human-completed ack_gate. Native parents replace it.",
    "K3_DAEMON": "OBJECT hermes kanban daemon and kanban daemon --force.",
    "K3_ASSIGNEE": "M2/M3/M4 assignee=implementer. Dest factory cards are not minted.",
    "K3_REFUSE_CLAIM": (
        "Do not stamp claimed_refuse_control. Dest live-PID reclaim is MEASURED, "
        "not a refuse-as-control GO."
    ),
}
