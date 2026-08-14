# Story scope and exit (GRX merge)

**Status:** binding · **Replaces:** `partition-coverage`, `surgical-scopes`,
`dependency-closure`, `interface-closure`, `compile-scope-filtered`,
`story-sizing`, `complete-cmd-exit-criteria`, `product-tests`,
`runnable-db-security` (and retired `semantic-exits` → skill
`derive-story-oracles`).

One concern: *what may this story touch* **and** *how do we know it is done* —
including the **relationship** between them (T-8 / v17 wrong-class oracles).

## Binding rules (precision lives in the lints)

1. **Write-set legality** — `check-surgical-scopes.py`,
   `check-partition-coverage.py`, `assert-dependency-closure.py`,
   interface/compile-scope filters.
2. **Class-legal exits** — stamp `exit_criteria` only from
   `OPERAND_CLASS_SEMANTIC_EXITS[operand_class]` via skill
   `derive-story-oracles`. Foreign semantic exits FAIL even beside a legal one
   (dual-oracle refuse).
3. **Sizing / wall-fit** — `check-operand-count.py --wall-fit`.
4. **Complete-cmd / product / DB security** — respective gates under
   check-spec-readiness / check-domain-parity / check-release-readiness.

## Bank vocabulary (tip-sync / doctrine pins)

- **Partition coverage** is specimen-agnostic: compare write-set size to the
  **runtime inventory count**, not a hard-coded specimen N.
- **Compile-scope filter** — only `files_writable` (and declared read-set) may
  enter compile/test scope for the story.
- **Complete-cmd** stamps `complete-exit-ok.json` when exit criteria hold.
- **Interface closure** bank id: `BANK-CREATE-PATH-IFACE-1`.
- **Dependency closure** bank id: `BANK-DEP-CLOSURE-1`.
- **Story sizing / DD6** — foundation asserts resolve under story-sizing rules
  (`operand_class` taxonomy); DD6 stays named here so tip sync catches drift.
- **Oracle-design failure classes** (must still refuse): wrong-class · vacuous
  pass · comment-satisfiable — see skill `derive-story-oracles`
  `references/failure-classes.md`.
