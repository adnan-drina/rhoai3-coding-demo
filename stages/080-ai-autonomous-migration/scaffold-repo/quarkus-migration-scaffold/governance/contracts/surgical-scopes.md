# Surgical M3 scopes (AD-H §16.9 / AR-4.4)

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).
**GR4 (E-20260814T114609Z):** cross-story write overlap is **not** owned here —
see `partition-coverage.md` (sole owner since F4 / `effdad9c`).
**GR3 / T-8 (Z2):** class-legal exit derivation replaces the retired
`semantic-exits.md` family table. Guidance skill: `derive-story-oracles`.

## Rule

1. Separate **readable deps** (`files_readable` / `readable_deps`) from
   **allowed writes** (`files_writable` / `write_set`).
2. `exit_criteria` MUST include endpoint/semantic checks — compile/residue/skills
   alone are insufficient (`specimen_agnostic.py` vocab +
   `OPERAND_CLASS_SEMANTIC_EXITS`).
3. **Every** named semantic exit must be legal for `identity.operand_class`
   (T-8 dual-oracle refuse). At-least-one legal exit is **not** enough if a
   wrong-class exit is also present.
4. Diff outside `files_writable` → REFUSE (`check-write-set.py` / write fence).

Compat: if only `files_in_scope` is present, destination paths in that list are
treated as the write set; legacy/referent paths are readable-only.

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-surgical-scopes.py .
```
