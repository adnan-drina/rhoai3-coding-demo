# O-M3ALL prediction table — FROZEN (wave 2)
# frozen_at: 2026-08-03T11:28:30Z
# re-freeze: TIDY-3 / W4-142 (wake #12) — prior freeze 2026-08-03T08:02:47Z was for a
# wave that died at M2 SEQUENCE lint×2 (app HEAD 10790d6); M2 never committed, so the
# baseline event for row 1 never occurred under that freeze.
# harness_delta: O-M2COMPOSE, O-M2-429, O-ORCH429BACKOFF, O-M2RETRYINLINE, O-M2CORPUS,
#   O-MONSTART (commit 5fcab70)
# whole-set_fields_fp: none (rebind at M3-ALL OPERATOR_GATE)
# Judge restart on row 1 (time to first plan defect). Rename-class is the control.

## Wave-1 attribution (honest — do not reuse as wave-2 "already proved")

| Metric | Wave-1 measured (v4 flight 1) | Notes |
|---|---|---|
| **Time to first plan defect detected** | **MET on substance** — M2 lint×2 FAIL stopped before any M4 (~minutes from M2 SEQUENCE start; gate-layer proof) | Rows 2+ **not reached** (no M3 whole-set, no M4 seats, no ship). L3 evidence is M2-gate-only. |
| S03 repository tasks declaring `Port` | not reached | — |
| Tasks declaring `Oracle` | not reached | — |
| Reimplement-class task seat cost | not reached | — |
| Rename-class task seat cost | not reached | — |
| M3 revisions to reach accepted plan | not reached | — |
| Whole-set lint clean before first M4 | not reached | — |
| Plans passing current lint | not reached (M2 roadmap RED; corpus seeded) | See `tests/fixtures/m2-corpus/v4-m2-lintx2-10790d6/` |
| S03 outcome | not reached | wave died at M2 |

## Wave-2 predictions (under test after next GO)

| Metric | Prior baseline (v3 / pre-v4) | Predicted this wave |
|---|---|---|
| **Time to first plan defect detected** | ≈4.7–6.0h (outcome-to-outcome) | ≤30 min from M2 commit (or honest M2 FAIL stop, as wave-1) |
| S03-equivalent repository tasks declaring `Port` | 0 of 5 | all repository-kind tasks declare Port |
| Tasks declaring `Oracle` | 1 of 5 | all (skeleton-generated field) |
| Reimplement-class task seat cost | 11 seats, ~3h | ≤4 seats |
| Rename-class task seat cost | 1 seat, 5 min | unchanged (control) |
| M3 revisions to reach accepted plan | 7 | ≤3 |
| Whole-set lint clean before first M4 | not computable | GREEN, recorded |
| Plans passing current lint at OPERATOR_GATE | 1 of 3 (S01 only historically) | whole-set GREEN |
| First story ship (no debt-freeze on T-004-class) | debt-freeze, T-004 unresolved | shipped |

frozen host copy at 2026-08-03T11:28:30Z (TIDY-3 wave-2 re-freeze)
