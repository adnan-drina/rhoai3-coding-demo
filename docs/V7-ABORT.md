# V7 abort — compromised S01 run

**When:** 2026-07-29 ~21:36 UTC  
**Workspace:** `coolstore-cart-service-v7` (reused in-place; no RHDH recreate)  
**Policy note:** Prefer abort/restart over continuing a problematic migration.

## Why aborted (not ship-patched)

| Signal | Evidence |
|--------|----------|
| S01 scope contamination | Roadmap S01 = `pom.xml` + remove bootstrap only; tree had full model/service/REST harvest (S02–S04) |
| Milestone / fidelity debt | `T-007` milestone RED → debt; M5 evaluate exhausted without clean evaluate commit |
| Preflight collapse | Quarkus ARC `@RestClient` unsatisfied, then sonar coverage ~17% vs 80% on premature classes |
| MiniMax misuse (pre-fix) | Rewrite batches + preflight thrash on rate-limited MiniMax while Qwen idle |
| Acceptance gap | `AcceptanceEndpoint` still returned ceremonial `"OK"` (banked G-OK; would fail honest S04) |

A surgical strip made preflight GREEN, but that would have **shipped a compromised story ledger** (exhausted tasks, debt, skipped evaluate). Per overnight mandate: restart.

## Reset performed

1. Killed outer-loop / supervisor / workers.
2. Force-pushed `coolstore-cart-service-v7` `main` → pristine `8c2102c` (`initial commit`); created `golden` at same SHA.
3. Hard-reset workspace `/projects/modernized` to that baseline; wiped `/tmp` harness logs.
4. Deleted Sonar project `coolstore-cart-service-v7` (fresh new-code baseline).
5. Overlay + commit WORKER_FIRST harness for the V8 restart.

## Restart

- Same DevWorkspace / project name (operator unavailable for RHDH create).
- Run label: **V8** (docs/driver); Track B `outer-loop.sh` from clean tree.

## Carry into V8 (must not recur)

- Enforce S01 scope: no model/service/REST under `src/main` until owning stories.
- `WORKER_FIRST`: all M4 coding on Qwen; MiniMax orch/escalation only.
- Abort again on package drift, false-green already-complete, or ceremonial acceptance at deploy.
