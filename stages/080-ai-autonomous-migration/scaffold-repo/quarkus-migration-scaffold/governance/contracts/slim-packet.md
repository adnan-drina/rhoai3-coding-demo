# Slim attach packet (AD-002F / AD-H §16.8 / AR-1.5)

**Status:** binding proving-min
**Basis:** AD-002F progressive disclosure

## Rule

Standing context **MUST NOT** drown the task packet. Per-phase attach is
**protocol + task type + needed guidance skills/tools only** — not “delete all
platform text.” Enforcement packages under `.hermes/enforcement/` are
path-invoked and are **not** card-attached.

## Measured matrix (tip)

| Phase | Attach law | Enforcer |
|-------|------------|----------|
| M3 | **exact** `{check-spec-readiness, spring-to-quarkus-patterns}` | `check-phase-attach-matrix.py` |
| M2 | **min** `{check-spec-readiness}` (+ phase helpers as listed) | same |
| M1/M4/M5 | required minimums; guidance helpers allowed | same |

Create helpers refuse when the matrix drifts (`create-m3-implementer.sh`).

**M3 born-parked :** `create-m3-implementer.sh`
creates with `--initial-status blocked` and does **not** call
`kanban dispatch`. Unpark remains gate-driven (M2b adherence PASS +
brief-identity ack + serial order). Todo-born + auto-dispatch is a serial breach.

**created_cards attribution:** create-m3
requires `--parent <M2b task>` and stamps `--created-by <parent>`. Parent
completion must pass those child ids in `created_cards` (see
`check-created-cards-claim.py`). `created_cards=[]` to skip the claim check
is **REJECT** when `evidence/derived/created-cards-<parent>.json` is nonempty.

**Story id on card (Operator E-20260813T180236Z):** create-m3 refuses bodies
without `identity.story_id` and prefixes the Kanban title
`${story_id}: …` so completion is arithmetic (`partition ids ⊆ titled cards`),
not an unverifiable "N/N done" claim. Also stamps
`evidence/derived/created-story-cards.json`.

**Block signals worker:** use
`.hermes/home/scripts/block-and-signal-worker.sh` — board block alone does not
kill in-flight workers.

## Headroom note

Slim M3 preload is the workhorse + body lint only. Workers consult additional
references via `skill_view` (AD-002G hard-invoke). Unused preloads need
`skills_unused` (AD-002E).

```bash
python3 .hermes/enforcement/dispatch-phase/scripts/check-phase-attach-matrix.py .
```
