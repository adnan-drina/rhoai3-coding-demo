"""K1 body schema (AD-019 §4 K1, work-list model, SAD v3 §8).

Not a skill. Loader + validator consume these constants.

A loop-card body (phase M3 / M4) is typed and inline. It carries the
admission receipt digest, the work-list digest, the cluster id, kind and
attempt, the exact write set, the work-list item ids, and the paths plus
digests of the planning artifacts. It never carries graphs, source
snippets, MTA prose, or LLM-authored acceptance text; those stay by
reference in the worker worktree.
"""
from __future__ import annotations

REQUIRED_TOP = ("task_id", "role", "phase", "refs", "identity")
REF_KEYS = ("key", "path", "sha256")
PHASES = frozenset({"M1", "M2", "M3", "M4", "M5", "FACTORY"})
REACHABILITY_PHASES = frozenset({"M2", "M3", "M4", "M5"})
INCREMENT_PHASES = frozenset({"M3", "M4"})
TYPE_INVENTORY_KEY = "type-inventory"
HERMES_ID_RE = r"^t_[0-9a-f]{8,}$"
SHA256_RE = r"^[0-9a-f]{64}$"
PENDING_SHA = "pending"

INCREMENT_KINDS = frozenset({"build", "config", "compile", "incident", "test", "parity", "close"})
ARTIFACT_KEYS = ("evidence-bundle", "worklist", "admission-receipt")
INCREMENT_REQUIRED = (
    "receipt_sha256",
    "worklist_sha256",
    "increment_id",
    "increment_kind",
    "attempt",
    "write_set",
    "item_ids",
    "artifacts",
)
# Keys that would mean a graph / prose payload was inlined.
PROSE_KEYS = frozenset({"nodes", "edges", "codeSnip", "code_snip", "incidents", "violations", "tasks_md", "acceptance_text", "story_text"})

# Failure codes stay the §6.1 table. Each refuse names a legal remedy.
REMEDY = {
    "BODY_SCHEMA": (
        "Use a logical increment id as task_id (not a Hermes t_* card id before "
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
        "M3 requires non-empty files_in_scope and files_writable equal to the "
        "cluster write_set paths from the sealed work list (never prose)."
    ),
    "BODY_EXIT": "M3–M5 require non-empty exit_criteria[] with check plus cmd or assert.",
    "BODY_HERMES_ID": (
        "Do not freeze a Hermes card id in task_id or the digest before create. "
        "Cards receive the logical id; Hermes ids are assigned at kanban_create."
    ),
    "BODY_GENERATED": (
        "Omit stored generated booleans. Classify generated at read time from path."
    ),
    "BODY_RECEIPT": (
        "Increment bodies carry receipt_sha256 (64 hex) equal to the ADMITTED "
        "admission-receipt.json receipt_digest. K4 stamps it; workers never edit it."
    ),
    "BODY_INCREMENT": (
        "Loop-card bodies carry increment_id (the cluster id, or M4_VERIFY), "
        "increment_kind (build|config|compile|incident|test|parity|close), attempt, "
        "worklist_sha256 (64 hex) and item_ids[] from the sealed work list."
    ),
    "BODY_WRITE_SET": (
        "write_set[] is the exact admitted list of {path, source_path, source_sha256}; "
        "files_writable must equal its paths. Do not widen from prose."
    ),
    "BODY_ARTIFACTS": (
        "artifacts[] must name the planning artifacts (evidence-bundle, worklist, "
        "admission-receipt) with path and 64-hex sha256."
    ),
    "BODY_PROSE": (
        "Body must not inline the work list, MTA incident prose, source snippets, or "
        "LLM-authored acceptance text. Reference artifacts by path + digest."
    ),
}

INLINE_MARKERS = (
    r"(?i)(BEGIN\s+FINDINGS|BEGIN\s+BLOB|-----BEGIN|"
    r"<html|package\s+com\.|class\s+\w+\s*\{)"
)
