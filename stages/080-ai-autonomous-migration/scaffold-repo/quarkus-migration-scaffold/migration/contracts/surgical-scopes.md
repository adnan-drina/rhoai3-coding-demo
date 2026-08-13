# Surgical M3 scopes (AD-H §16.9 / AR-4.4)

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

## Rule

1. Separate **readable deps** (`files_readable` / `readable_deps`) from
 **allowed writes** (`files_writable` / `write_set`).
2. Destination write ownership is **non-overlapping** across concurrent M3
 bodies, or bodies declare explicit `sequence_after: [story_id, …]`.
3. `exit_criteria` MUST include endpoint/semantic checks — compile/residue/skills
 alone are insufficient.
4. Diff outside `files_writable` → REFUSE (`check-write-set.py` / write fence).

Compat: if only `files_in_scope` is present, destination paths in that list are
treated as the write set; legacy/referent paths are readable-only.

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-surgical-scopes.py .
```
