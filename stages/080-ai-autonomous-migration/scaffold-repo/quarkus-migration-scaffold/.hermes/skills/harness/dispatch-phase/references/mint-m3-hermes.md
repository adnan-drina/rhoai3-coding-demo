# Hermes-invoked M3 mint (binding)

**Status:** binding · **Authority:** Architect `E-20260817T165300Z` /
`E-20260817T170800Z` (Phase 2). **OBJECT** Cursor or demo-user
`mint-m3-wave.sh` / `handover-mint.py --parent` as the create path.

The **wave-holder worker** (Hermes session on the M3 holder card) mints.
Lint stays agent-invoked via `execute_code`. Create is native
`kanban_create`. Bare `kanban create` (zero skills) is still forbidden.

Do not grow `handover-mint.py` (parser halt `061824Z`). Run it as **lint
only** (`--write`, **no** `--parent`, **no** `--ensure-wave-holder`).

## Sequence

1. Confirm this session is the wave holder (`HERMES_KANBAN_TASK` is the
   holder id). Holder must **not** be `done`/`archived` (HKN-2).
2. Lint + assemble (no create):

   ```text
   python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py /projects/modernized --write
   ```

   Receipt `source` must be `handover-mint`. Path-A authored partition is
   refuse.
3. For each story in `evidence/briefs/partition.json` whose
   `identity.story_id` has a body under `evidence/bodies/`:
   - Skip if a child of the holder already has title prefix `{story_id}:`
     or `{story_id} `.
   - Run the **pre-create gates** below via `execute_code` on that body.
   - `kanban_create` with skills, `initial_status=blocked`,
     `idempotency_key`, `workspace_kind=dir`, `workspace_path`,
     `max_runtime_seconds`, `assignee=default`, parents
     **`[holder, ack_gate]`**.
4. Create **`ack_gate` first** (step 3a), then story cards. AR-1.1 is the
   gate card: Deputy/Operator `kanban_complete` on it is the grant. Do
   not treat `evidence/acks/*.yaml` as the unpark switch.
5. After all stories exist (or were skipped), **`kanban_complete` this
   holder**. Safe only while `ack_gate` is still incomplete (`191420Z` /
   `192510Z`).
6. Do **not** `kanban_list` / `kanban_unblock` from this worker (those
   tools are orchestrator-mode at v0.20.2). Idempotency + skip-by-title
   replace list-then-skip. Unpark is completing the gate, not unblock.

## ack_gate card

Create before story cards:

- title: `M3 ACK GATE: brief-identity`
- assignee: `default` (required; tasks without assignee never dispatch)
- `initial_status`: `blocked` (must not be dispatchable work)
- parents: `[holder]` only
- `idempotency_key`: `migration-m3-ack-gate-v1`
- skills: `check-spec-readiness` (non-empty; bare create OBJECT)
- body: wait for Deputy/Operator complete; do not implement dest code

Story children parents: **`[holder, ack_gate]`**. Create-time `blocked`
is not sticky; the incomplete gate parent is what holds them.

## Pre-create gates (moved from create-m3-implementer; do not drop)

Run per body, fail-closed, via `execute_code`:

1. `check-create-path-tip-sync.py`
2. `check-phase-body-script-refs.py`
3. `stamp-body-dependencies.py --body <body> --write`
4. `check-interface-closure.py --body <body>`
5. `stamp-destination-inventory.py --body <body> --write`
6. `check-partition-coverage.py --write-receipt evidence/receipts/partition-coverage/latest.json`
7. `assert-quarantine-tombstones.py`
8. `assert-mint-constraints-complete.py --body <body> --inject` then without `--inject`
9. `assert-constraints-preserved.py --body <body> --snapshot-before`
10. `assert-dependency-closure.py --body <body>`
11. `check-kanban-body.py --body <body>`
12. `check-phase-attach-matrix.py`
13. `assert-bundle-skills-exist.py --bundle m3-implementer`
14. `stamp-body-digest.py` (AR-4.3)
15. `check-surgical-scopes.py` + `check-semantic-exits.py` + `check-operand-count.py --wall-fit`
16. `assert-mint-oracles.py --body <body> --skip-task-id`

Attach skills from `m3-attach-skills.py <body>` (B-16). Max runtime from
`read-phase-dispatch.py --phase M3` or body `runtime_budget_sec`.
Workspace `dir:/projects/modernized`. Profile `default` must exist
(`hermes profile show default`).

Title: `{story_id}: M3 IMPLEMENT: {story_id}` (prefix once). Card markdown
≤1500 chars; standing procedure stays in `m3-implementer-standing.md`.

`idempotency_key`: `migration-m3-{story_id}-v1`.

## After create (same session)

- Prove each new id has both parent links (holder + ack_gate).
- Status must be `blocked` or `triage`. `ready`/`todo`/`running` is refuse.
- Append `evidence/derived/created-story-cards.json`.
- Emit unsigned `evidence/acks/ack-request-<story>.yaml` for the record;
  **unpark is still completing `ack_gate`**, not signing the file.
- Run `assert-m2b-created-cards-claim.sh` (partition set equality) after
  the wave.

## Scratch proof (Phase 2.5, before any v21 dest)

On a **scratch** board, not attempt-10: gate + seven creates + holder
complete → seven stay blocked → gate complete → seven promote →
`hermes kanban dispatch --dry-run` lists seven. File the reproduction
before Operator announces v21.

## Retired control-plane scripts

`mint-m3-wave.sh` and `create-m3-implementer.sh` remain in tree so
create-path tip-sync pins still match (Phase 3 drops those pins together
with `park-on-block-loop.py`). They are **not** the mint path. Do not
invoke them from Cursor, from M2, or from the demo user.
