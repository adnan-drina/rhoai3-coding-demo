# R-M2.6 — M2 resume-from-artifacts

**BIND:** Architect `E-20260810T153830Z`.

When reclaiming or re-dispatching M2, if durable artifacts already exist:

| Present | Action |
|---------|--------|
| `migration/briefs/partition.json` + Spec Kit `spec.md` (+ `plan.md` if present) | Skip re-partition / re-specify / re-plan; jump `/speckit.tasks` → `create-m3-implementer.sh` |
| Missing any of the above | Full Job order from the M2 body (specify → plan → tasks) |

## Constraints

- Do **not** rewrite write-once `partition.json`.
- Do **not** mid-run digest-breaking body rewrite on a live task — tip body
  lands here; apply on next reclaim/redisp.
- Prefer R-M2.5 wall raise (3600s) over M2a/M2b split unless 3600+resume still
  dies before `tasks.md`.
