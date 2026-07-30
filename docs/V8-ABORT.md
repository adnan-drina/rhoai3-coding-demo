# V8 abort — full wipe for V9

**When:** 2026-07-30 ~06:00 UTC  
**Workspace:** `coolstore-cart-service-v7` (in-place wipe; same DevWorkspace)  
**Policy:** Prefer abort/restart over continuing a mid-run patched migration.

## Why aborted

| Signal | Evidence |
|--------|----------|
| S02 characterization not harness-proven | Real model tests landed in HOLD loop by operator/agent, not OpenCode under G-PLACE/S-CHAR |
| Mid-run polish | O-T6b, G-PLACE, S-CHAR, L-M5e, O-RESUME, quality-advance gate landed during V8 |
| Throughput risk | V8 had already entered S03 M3 after S02 factory push — continuing would not prove S02 e2e |

## Reset performed

1. Killed outer-loop / supervisor / workers / driver.
2. Force-pushed `coolstore-cart-service-v7` `main` + `golden` → pristine `8c2102c`, then V9 harness sync + hygiene (`63a9abe`).
3. Hard-reset workspace `/projects/modernized`; wiped `/tmp` harness logs.
4. Deleted Sonar project `coolstore-cart-service-v7` (HTTP 204).
5. Re-pushed `quarkus-migration-scaffold` golden via `bootstrap-scaffold-repos.sh`.

## Restart

- Run label: **V9**
- Gate log: [`V9-QUALITY-GATE.md`](V9-QUALITY-GATE.md)
- Track B `outer-loop.sh` from clean tree; `WORKER_FIRST=true`; no `RESUME_*`
