# Body-digest match scopes to own story at complete (Class A)

**Status:** binding (in-tree).

## Problem

`exit_criteria` body_digest cmds pass `--body <own.json>` without `--expect`.
`check-body-digest-match.py` previously fell through to a **whole-corpus**
sidecar scan. Parked siblings with stale stamps (S-003 / S-008 / S-009) failed
the cmd for an honest in-scope completion (`t_c9b03f60`), then the worker
rationalized OOS-scoped-OK and Hermes still accepted `kanban_complete`
(COMPLETE-CMD leak; assert receipt `ok=false`).

## Rule

1. **`--body` alone** (no `--expect`, no `--sidecar`): check **only** that body's
 own sidecar (`<body>.sha256.json`). Fail-closed if missing/mismatched.
2. **`--body` + `--expect`**: check that pair only (card digest path).
3. **No `--body`**: harness inventory may still scan all `*.sha256.json`
 sidecars (create-path / restamp hygiene) — not an exit criterion.
4. Complete path continues to require green
 `assert-complete-exit-criteria.py` before `kanban_complete`
 (`complete-cmd-exit-criteria.md`).

## Related

- `body-immutability.md` — AR-4.3 immutability after dispatch
- `complete-cmd-exit-criteria.md` — cmd exits at complete
- `compile-scope-filtered.md` — same class (own-scope vs whole-tree)
