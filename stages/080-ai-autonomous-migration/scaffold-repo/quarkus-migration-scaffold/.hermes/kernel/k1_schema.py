"""K1 body schema (AD-019 §4 K1). Generated from the SAD section, not a corpus.

Not a skill. Loader + validator consume these constants.
"""
from __future__ import annotations

REQUIRED_TOP = ("task_id", "role", "phase", "refs", "identity")
REF_KEYS = ("key", "path", "sha256")
PHASES = frozenset({"M1", "M2", "M3", "M4", "M5", "FACTORY"})
REACHABILITY_PHASES = frozenset({"M2", "M3", "M4", "M5"})
TYPE_INVENTORY_KEY = "type-inventory"
HERMES_ID_RE = r"^t_[0-9a-f]{8,}$"
SHA256_RE = r"^[0-9a-f]{64}$"
PENDING_SHA = "pending"

# Failure codes stay the §6.1 table. Each refuse names a legal remedy.
REMEDY = {
    "BODY_SCHEMA": (
        "Use a logical story_id as task_id (not a Hermes t_* card id before "
        "kanban_create). Include role, phase, and refs[] of {key,path,sha256}."
    ),
    "BODY_INLINE": (
        "Body never carries derived content. Put blobs on disk and digest-ref them."
    ),
    "BODY_REF_UNKNOWN": "Use a refs[].key from the phase vocabulary or type-inventory.",
    "BODY_REF_MISSING": (
        "Add the missing refs[] entry (M2+ that consume reachability need "
        "key=type-inventory with path+sha256 of evidence/type-inventory.json)."
    ),
    "BODY_REF_SHA256": "sha256 must be 64 lowercase hex (or typed pending where allowed).",
    "BODY_REF_DIGEST": "Recompute sha256 of the file at refs[].path; stamp both copies.",
    "BODY_SCOPE": (
        "M3 requires non-empty files_in_scope and files_writable copied from "
        "the typed partition row (not grep of tasks.md)."
    ),
    "BODY_EXIT": "M3–M5 require non-empty exit_criteria[] with check plus cmd or assert.",
    "BODY_HERMES_ID": (
        "Do not freeze a Hermes card id in task_id or the digest before create. "
        "Cards receive the logical id; Hermes ids are assigned at kanban_create."
    ),
    "BODY_GENERATED": (
        "Omit stored generated booleans. Classify generated at read time from path."
    ),
}

INLINE_MARKERS = (
    r"(?i)(BEGIN\s+FINDINGS|BEGIN\s+BLOB|-----BEGIN|"
    r"<html|package\s+com\.|class\s+\w+\s*\{)"
)
