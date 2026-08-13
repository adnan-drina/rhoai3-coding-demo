# Scope-filtered compile / test-compile (Class A)

**Status:** binding (in-tree).

## Problem

Whole-tree `mvn -q compile` / `test-compile` with `expect: rc=0` is
**unsatisfiable mid-partition**: out-of-scope (OOS) files from later stories
fail the tree while AR-4.4 forbids fixing them. Workers corner into
`--skip-test-compile-gate` or typed BLOCK that halts the chain
(proven: product S-004 `t_98e3ed7b`).

## Rule

1. **Scoped gate:** run
 `python3 .hermes/enforcement/record-run-evidence/scripts/run-scoped-compile-gate.py \
 . --task-id <id> --body <typed body> --goal test-compile|compile`
2. FAIL-CLOSED only when Maven error paths intersect the body's
 `files_writable` (own scope).
3. OOS-only errors → gate **OK** with `reason=oos_only_compile_errors_scoped_ok`
 (artifact under `evidence/runs/<id>/scoped-*-gate.json`). Not a skip.
4. **`--skip-test-compile-gate` FORBIDDEN** on live seats. Fixture-only when
 `RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1`. Compliant fork when blocked:
 typed `needs_input` — do not bypass.
5. Checkpoint stamp (`stamp-implementer-checkpoint.py`) and wall/complete
 exit-eval route `compile` / `test_compile` through the scoped gate.
6. In-scope errors must be fixed before stamp/complete.

## Scripts

| Script | Role |
|--------|------|
| `run-scoped-compile-gate.py` | Scope-filter Maven errors vs `files_writable` |
| `run-test-compile-gate.py` | Thin wrapper → scoped `test-compile` |
| `stamp-implementer-checkpoint.py` | Requires scoped green for `src/test/**` |
| `evaluate-exit-criteria.py` | Intercepts compile/test_compile → scoped |

## Related

- `test-toolchain.md` — in-loop #1b invariant (now scoped)
- `complete-cmd-exit-criteria.md` — complete must evaluate cmd exits
- `implementer-checkpoint.md` — stamp refuse path
