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

1. `exit_criteria` MUST include `check: test_compile` with
   `cmd: mvn -q test-compile` (or equivalent) and `expect: rc=0`
2. Implementer MUST run that command **after batches of test writes** and
   before `kanban_complete`; red `testCompile` → typed terminal / fix deps —
   not silent progress to Review

Authoring gate: `check-kanban-body.py` refuses M3 bodies with test scope but
no `test_compile` exit.

## Wall-as-terminal (Architect E-20260810T110403Z)

`timed_out` **must** evaluate cmd-shaped exits (at least `test_compile` when
present). See `migration/contracts/wall-exit-eval.md`. Advisory in-loop prose
alone does not cover budget-wall death.
