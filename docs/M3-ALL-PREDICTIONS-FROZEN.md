# O-M3ALL prediction table — FROZEN
# frozen_at: 2026-08-03T08:02:47Z
# whole-set_fields_fp: none
# Judge restart on row 1 (time to first plan defect). Rename-class is the control.

| Metric | This wave (measured) | Predicted next wave |
|---|---|---|
| **Time to first plan defect detected** | ≈4.7–6.0h (outcome-to-outcome) | ≤30 min from M2 commit |
| S03 repository tasks declaring `Port` | 0 of 5 | 5 of 5 |
| Tasks declaring `Oracle` | 1 of 5 | all (skeleton-generated field) |
| Reimplement-class task seat cost | 11 seats, ~3h | ≤4 seats |
| Rename-class task seat cost | 1 seat, 5 min | unchanged (control) |
| M3 revisions to reach accepted plan (S03) | 7 | ≤3 |
| Whole-set lint clean before first M4 | not computable | GREEN, recorded |
| Plans passing current lint | 1 of 3 (S01 only) | 3 of 3 |
| S03 outcome | debt-freeze, T-004 unresolved | shipped |
frozen host copy at 2026-08-03T08:02:47Z
