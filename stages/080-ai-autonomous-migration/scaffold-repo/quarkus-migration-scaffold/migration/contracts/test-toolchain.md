# Test toolchain + in-loop testCompile (S-010 Class A / Deputy E-20260810T104752Z)

**Status:** binding proving-min  
**Sources:** Deputy `E-20260810T104752Z` · Lead BIND `E-20260810T104932Z` defect 1

## Harness-owned toolchain

Which assertion / HTTP test libraries ship is a **scaffold** decision, not
something each specimen rediscovers. Tip `pom.xml` MUST include (test scope):

- `io.rest-assured:rest-assured` (already)
- `org.assertj:assertj-core` (BOM-managed version preferred)

```bash
python3 .hermes/skills/validation-release-gates/scripts/check-test-toolchain.py .
```

## In-loop invariant

A test-authoring story that never runs the build can only produce a valid
corpus by accident. For M3 bodies whose `files_in_scope` includes
`src/test/**`:

1. `exit_criteria` MUST include `check: test_compile` (cmd may still say
   `mvn -q test-compile`; evaluator routes through the **scoped** gate).
2. **Structural (Deputy E-20260810T115113Z + Architect E-20260811T175305Z):**
   `stamp-implementer-checkpoint.py --completed src/test/...` **REFUSE**s unless
   `run-scoped-compile-gate.py --goal test-compile` is green for own
   `files_writable`. `--skip-test-compile-gate` is fixture-only when
   `RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1` — FORBIDDEN on live seats.
3. **Harness-driven stamp (Deputy E-20260810T121112Z):** voluntary stamp decays.
   On wall/requeue and before `kanban_complete`, run
   `sync-checkpoint-from-test-writes.py` / `check-test-write-checkpoint-lag.py`
   so on-disk `src/test/**` writes cannot outrun the checkpoint.
4. Wall / soft-requeue / complete evaluate `test_compile` via scoped gate
   (`compile-scope-filtered.md`, `wall-exit-eval.md`,
   `complete-cmd-exit-criteria.md`).

Authoring gate: `check-kanban-body.py` refuses M3 bodies with test scope but
no `test_compile` exit.

**Fresh-run HOLD:** no `substrate=fresh_workspace` S-010 re-dispatch until this
structural gate is landed (Lead `enforce-1b-before-fresh-run`).

## Wall-as-terminal (Architect E-20260810T110403Z)

`timed_out` **must** evaluate cmd-shaped exits (at least `test_compile` when
present). See `migration/contracts/wall-exit-eval.md`. Advisory in-loop prose
alone does not cover budget-wall death.
