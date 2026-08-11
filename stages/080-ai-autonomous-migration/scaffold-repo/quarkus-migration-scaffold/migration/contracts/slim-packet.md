# Slim attach packet (AD-002F / AD-H §16.8 / AR-1.5)

**Status:** binding proving-min  
**Sources:** Architect BIND `E-20260810T093846Z` · AD-002F progressive disclosure

## Rule

Standing context **MUST NOT** drown the task packet. Per-phase attach is
**protocol + role + needed skills/tools only** — not “delete all platform text.”

## Measured matrix (tip)

| Phase | Attach law | Enforcer |
|-------|------------|----------|
| M3 | **exact** `{sdd-readiness, spring-to-quarkus-patterns}` | `check-phase-attach-matrix.py` |
| M2 | **min** `{sdd-readiness, role-authority}` (+ role-specific helpers) | same |
| M1/M4/M5 | required minimums; helpers allowed | same |

Create helpers refuse when the matrix drifts (`create-m3-implementer.sh`).

**M3 born-parked (Deputy `E-20260811T131900Z`):** `create-m3-implementer.sh`
creates with `--initial-status blocked` and does **not** call
`kanban dispatch`. Unpark remains gate-driven (M2b adherence PASS +
brief-identity ack + serial order). Todo-born + auto-dispatch is a serial breach.

**created_cards attribution (Operator `E-20260811T133000Z` #5):** create-m3
requires `--parent <M2b task>` and stamps `--created-by <parent>`. Parent
completion must pass those child ids in `created_cards` (see
`check-created-cards-claim.py`). `created_cards=[]` to skip the claim check
is **REJECT** when `migration/derived/created-cards-<parent>.json` is nonempty.

**Block signals worker (Operator `E-20260811T133000Z` #2):** use
`.hermes/home/scripts/block-and-signal-worker.sh` — board block alone does not
kill in-flight workers.

## Headroom note

Slim M3 preload is the workhorse + body lint only. Workers consult additional
references via `skill_view` (AD-002G hard-invoke). Unused preloads need
`skills_unused` (AD-002E).

```bash
python3 .hermes/skills/phase-dispatch/scripts/check-phase-attach-matrix.py .
```
