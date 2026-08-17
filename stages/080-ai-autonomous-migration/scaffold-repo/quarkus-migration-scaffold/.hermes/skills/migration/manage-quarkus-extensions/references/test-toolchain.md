# Test toolchain + in-loop testCompile (S-010 Class A)

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

## Harness-owned toolchain

Which assertion / HTTP test libraries ship is a **scaffold** decision, not
something each specimen rediscovers. Tip `pom.xml` MUST include (test scope):

- `io.rest-assured:rest-assured` (already)
- `org.assertj:assertj-core` (BOM-managed version preferred)

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-test-toolchain.py .
```

## In-loop invariant

A test-authoring story that never runs the build can only produce a valid
corpus by accident. For M3 bodies whose `files_in_scope` includes
`src/test/**`:

1. `exit_criteria` MUST include `check: test_compile` (cmd may still say
 `mvn -q test-compile`; evaluator routes through the **scoped** gate).
2. **Structural:**
 `stamp-implementer-checkpoint.py --completed src/test/...` **REFUSE**s unless
 `run-scoped-compile-gate.py --goal test-compile` is green for own
 `files_writable`. `--skip-test-compile-gate` is fixture-only when
 `RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1` — FORBIDDEN on live seats.
3. **Harness-driven stamp :** voluntary stamp decays.
 On wall/requeue and before `kanban_complete`, run
 `sync-checkpoint-from-test-writes.py` / `check-test-write-checkpoint-lag.py`
 so on-disk `src/test/**` writes cannot outrun the checkpoint.
4. Wall / soft-requeue / complete evaluate `test_compile` via scoped gate
 (`compile-scope-filtered.md`, `wall-exit-eval.md`,
 `complete-cmd-exit-criteria.md`).

Authoring gate: `check-kanban-body.py` refuses M3 bodies with test scope but
no `test_compile` exit.

**Fresh-run HOLD:** no `substrate=fresh_workspace` S-010 re-dispatch until this
structural gate is landed (`enforce-1b-before-fresh-run`).

## Wall-as-terminal

`timed_out` **must** evaluate cmd-shaped exits (at least `test_compile` when
present). See `.hermes/skills/gates/check-release-readiness/` (`apply-wall-requeue-policy.py`; no `governance/` folder). Advisory in-loop prose
alone does not cover budget-wall death.
