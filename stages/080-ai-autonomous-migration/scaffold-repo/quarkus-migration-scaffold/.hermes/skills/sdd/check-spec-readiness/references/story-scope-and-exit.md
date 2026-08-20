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
2. **Class-legal exit names** — `operand_class` is a **set** (string or
   list) used for B-16 skill attachment and the union of
   `OPERAND_CLASS_SEMANTIC_EXITS` names. The exit **cmd** is the phase
   acceptance criteria (T-8 AMEND / Architect E-20260816T115106Z).
   **OBJECT dropping the field. OBJECT a default `mvn -q test` on every
   card.** Foreign semantic names vs the union FAIL even beside a legal
   one (dual-oracle refuse). Unknown tokens fail-closed (empty legal
   set — do not inherit the full vocab). `user_story` is AC-sourced.
   `bootstrap` → `app_boots`; `persistence` → `mapping_valid`
   (Architect E-20260814T181701Z). Skill `derive-story-oracles`.
3. **Sizing / wall-fit** — `check-operand-count.py --wall-fit`.
4. **Complete-cmd / product / DB security** — respective gates under
   check-spec-readiness / check-domain-parity / check-release-readiness.
5. **SR-13 discriminating exit (L2a mint / L2a complete)** — `assert-mint-oracles.py`.
   The test proving **this card's AC** lives in **this** `files_writable`.
   A test-shaped `exit_criteria[].cmd` (`mvn … test` or `mvn … verify`)
   must name `proves` test source(s) that sit in **this** `files_writable`.
   Each `proves` path that exists must contain an executable `@Test`
   (B-1); at complete the named class must appear in
   `target/surefire-reports`. **`evaluate-exit-criteria.py` must run
   `mvn … test|verify` as `-Dtest=<proves FQCNs>`** (`task_scoped_tests`).
   An unscoped `mvn -q test` that executes sibling-story tests is refuse —
   do not treat a green isolation run plus a red full suite as a body-mint
   defect. An unrelated dest `src/test` file must not
   satisfy the oracle. `true`, a script/`curl` card exit, and a test cmd
   with no named proving test refuse. `mvn test-compile` is not
   test-shaped for L2a. Compile-shaped cmds are unchanged. Shape (`shlex`
   + Maven vehicle) is necessary and not sufficient. Golden does not
   require `mvn` on PATH. Do not stamp `failIfNoTests=true` as a mint
   recipe (the story that needs a test is the story that adds it).
   Live HTTP acceptance belongs to M4/M5 gate scripts, not card exits.
6. **File-granular ownership (A-5)** — grouping and ownership are separate
   steps. After grouping, the handover assigns each destination file
   **exactly one owner**. **pom owner unique** — `pom.xml` has one writer;
   later phases do not keep it. Overlaps are a partition defect, not a
   grouping feature. Worktrees do not relax that invariant.

## Bank vocabulary (tip-sync / doctrine pins)

- **Partition coverage** is specimen-agnostic: compare write-set size to the
  **runtime inventory count**, not a hard-coded specimen N.
- **Compile-scope filter** — only `files_writable` (and declared read-set) may
  enter compile/test scope for the story.
- **Complete-cmd** stamps `complete-exit-ok.json` when exit criteria hold.
- **Interface closure** bank id: `BANK-CREATE-PATH-IFACE-1`.
- **Write-set subset** — `body.files_writable` ⊆ partition story declared
  frame (`assert-body-writeset-subset-of-partition`). Inheritance-reachable
  unowned dest twins are assigned onto that frame (V34-5) before subset.
  Endpoint coverage is not write-set coverage.
- **Dependency closure** bank id: `BANK-DEP-CLOSURE-1`. `provider: generated`
  is a third kind (build output); DEST_MISS is skipped; generator inputs
  (spec + dest build file) must be owned (`GENERATOR_INPUTS`).
- **Dest pom extensions (V35-EXTENSIONS)** — setup wrote an under-specified
  pom; missing hibernate-orm, hibernate-validator, and the OpenAPI generator
  are the same defect. `assert-dest-pom-extensions.py` parses the **dest**
  pom in this story's write-set. Required set =
  `identity.extensions_apply` ∪ `evidence/required-extensions.json`.
  Do **not** call `generator_input_paths()` / `iter_build_files()` (those
  union legacy). Generator `inputSpec` matching is a **case** of this
  predicate (`assert-dest-generator-configured.py`), not a sibling
  complete-path gate. Wired on `assert-complete-exit-criteria.py`. T013
  already requires configure-in-pom; `assert-tasks-generator-uptake.py`
  enforces plan uptake.
- **Story sizing / DD6** — foundation asserts resolve under story-sizing rules
  (`operand_class` taxonomy); DD6 stays named here so tip sync catches drift.
- **Oracle-design failure classes** (must still refuse): wrong-class · vacuous
  pass · comment-satisfiable — see skill `derive-story-oracles`
  `references/failure-classes.md`.
