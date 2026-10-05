# Test toolchain + in-loop testCompile (S-010 Class A)

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

## Harness-owned toolchain

Which assertion / HTTP test libraries ship is a **scaffold** decision, not
something each specimen rediscovers. Tip `pom.xml` MUST include (test scope):

- `io.quarkus:quarkus-junit5` — **the JUnit 5 runner `@QuarkusTest` resolves
  against.** Without it `@QuarkusTest` and the JUnit 5 annotations do not
  compile, and the failure lands on whichever story first writes a test rather
  than on the story that authored the pom (dest-6 `us1_greeting` blocked on
  exactly this; Operator `E-20260825T200914ZO`). BOM-managed version.
- `io.rest-assured:rest-assured` (already)
- `org.assertj:assertj-core` at `.hermes/pins.json` `assertj_core`
  (RH `quarkus-bom` dest-cited 0 assertj hits — Architect 125110ZA B;
  do not invent `@version`)

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-test-toolchain.py .
```

## In-loop invariant

A test-authoring story that never **runs** the tests can only produce a valid
corpus by accident. For M3 bodies whose `files_writable` / `files_in_scope`
includes `src/test/**`:

1. `exit_criteria` MUST include a Maven **test|verify** cmd (`mvn -q test`).
 `mvn test-compile` is in-loop compile, **not** an exit
 (Lead:test-compile-is-not-an-exit-criterion;
 Lead:setup-test-toolchain-claim-is-vacuous — an empty test tree always
 passes). Do not `mvn clean` — M4
 snapshots surefire.
2. **Structural:**
 `stamp-implementer-checkpoint.py --completed src/test/...` **REFUSE**s unless
 `run-scoped-compile-gate.py --goal test-compile` is green for own
 `files_writable`. `--skip-test-compile-gate` is fixture-only when
 `RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1` — FORBIDDEN on live seats.
3. **Harness-driven stamp :** voluntary stamp decays.
 On wall/requeue and before `kanban_complete`, run
 `sync-checkpoint-from-test-writes.py` / `check-test-write-checkpoint-lag.py`
 so on-disk `src/test/**` writes cannot outrun the checkpoint.
4. Wall / soft-requeue / complete evaluate the **test** cmd via scoped gate
 (`compile-scope-filtered.md`, `wall-exit-eval.md`,
 `complete-cmd-exit-criteria.md`). Compile-only remains legal only for
 stories that write no test.

Authoring gate: `check-kanban-body.py` refuses M3 bodies with test scope but
no `mvn test|verify` exit.

**Fresh-run HOLD:** no `substrate=fresh_workspace` S-010 re-dispatch until this
structural gate is landed (`enforce-1b-before-fresh-run`).

## Wall-as-terminal

`timed_out` **must** evaluate cmd-shaped exits (at least `test_compile` when
present). KEEP skill `check-release-readiness` (no `governance/` folder).
Parked wall policy in `.hermes/_park/requeue/` is **retired** (Operator
GO `155455Z`) and is not this KEEP skill (rebuild later, never dump).
Advisory in-loop prose alone does not cover budget-wall death.
