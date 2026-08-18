# Hermes-invoked M3 mint (binding)

**Status:** binding · **Authority:** Architect `E-20260817T165300Z` /
`E-20260817T170800Z` / `E-20260817T173800Z` (ack_gate AMEND) /
`E-20260817T173950Z` / `E-20260817T181020Z` (2.4). **OBJECT** Cursor or
demo-user `mint-m3-wave.sh` / `handover-mint.py --parent` as the create
path.

The **wave-holder worker** (Hermes session on the M3 holder card) mints.
Lint stays agent-invoked via `execute_code`. Create is native
`kanban_create`. Bare `kanban create` (zero skills) is still forbidden.

Do not grow `handover-mint.py` (parser halt `061824Z`). Run it as **lint
only** (`--write`, **no** `--parent`, **no** `--ensure-wave-holder`).

## Fail-closed kind map (Architect `E-20260818T094316Z` / `094840Z`)

Copy this table into the **holder card body**. Dest-forbidden rewrite and
A-8 planning refuse are **not** parent waits.

| Refusal class | `hermes kanban block --kind` | Why |
|---|---|---|
| A-8 refuse (`endpoints_multi` / `endpoints_uncovered` / lint exit 1) | `needs_input` | Defect is in `tasks.md`; do not dest-rewrite |
| Dest-forbidden rewrite (`tasks.md` outside write-set) | `needs_input` | OBJECT dest-rewrite |
| Missing parent / unsigned ack_gate | `dependency` | Auto-promotes when that parent completes |
| Mint growth / dest-rewrite impulse | do not | OBJECT; halt `061824Z`; mint **1088** |

`dependency` self-clears and does **not** count toward
`BLOCK_RECURRENCE_LIMIT`. Argv: **`--kind` before the task id**.
Do not restore `park-on-block-loop.py`.

Holder create `--skill`: official `one-three-one-rule` only.
Do **not** pin `dispatch-phase` on the holder (I-10 B / `25a7c1e9`);
path-invoke this Procedure. Keep the five names in `skills.disabled`.
Do **not** pin `check-spec-readiness` on the holder until story bodies exist.

## Sequence

1. Confirm this session is the wave holder (`HERMES_KANBAN_TASK` is the
   holder id). Holder must **not** be `done`/`archived` (HKN-2 /
   `PARENT_DONE`). `PARK_AT_BIRTH` children **auto-promote** when every
   parent is `done` — do not `--parent` a done card.
2. Lint + assemble (no create):

   ```text
   python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py /projects/modernized --write
   ```

   Receipt `source` must be `handover-mint`. Path-A authored partition is
   refuse (`PATH_A_PARTITION`).
3. Create **`ack_gate` first** (see ack_gate card). Do **not** parent it
   on the holder. Sticky-block it. **Assert `status=blocked` from
   `kanban show`** — do not trust `kanban block` exit 0
   (`204830Z` silent no-op if `--kind` is after the task id).
   Then snapshot this new id (After create).
4. For each story in `evidence/briefs/partition.json` whose
   `identity.story_id` has a body under `evidence/bodies/`:
   - Skip if a child of the holder already has title prefix `{story_id}:`
     or `{story_id} `.
   - Run the **pre-create gates** below via `execute_code` on that body.
   - `kanban_create` with skills, `initial_status=blocked` /
     `--initial-status blocked` (**not** the park protection — Architect
     `113650Z`; the unfinished `ack_gate` parent is), `idempotency_key`,
     `workspace_kind=dir`,
     `workspace_path`, `max_runtime_seconds`, `assignee=default`,
     `created-by` / `created_by` = holder id, `--parent REQUIRED` twice
     (holder + ack_gate), parents **`[holder, ack_gate]`** (gate is a
     parent, not a holder-child). Snapshot this new id (After create).
     Immediately `hermes kanban show <id> --json` and **refuse unless
     `status=todo`** (not `ready`/`running`) **and** `parents` include the
     unfinished `ack_gate`. OBJECT requiring story `status==blocked`.
     Do **not** add this assert to `handover-mint.py` (1088 freeze).
     **Do NOT dispatch here.**
5. After all stories exist (or were skipped), **`kanban_complete` this
   holder**. The gate must stay `blocked` (sticky event). Children stay
   `blocked` because `ack_gate` is incomplete. `dispatch --dry-run` must
   select **none, including the gate**.
6. Do **not** `kanban_list` / `kanban_unblock` from this worker (those
   tools are orchestrator-mode at v0.20.2). Idempotency + skip-by-title
   replace list-then-skip. Unpark is **completing** the blocked gate, not
   unblock.

## ack_gate card

Create **before** story cards. Do **not** set `parents: [holder]`.
Holder complete must not `recompute_ready` the gate (`173800Z`).

- title: `M3 ACK GATE: brief-identity`
- assignee: `default` (required; tasks without assignee never dispatch)
- create as `todo` or `ready` (not create-time `blocked` — block-on-already-blocked is refused `194210Z`)
- **no holder parent**
- then sticky-block with argv order **`--kind` before task id**:

  ```text
  hermes kanban block --kind needs_input <ack_gate_id> "unsigned brief-identity"
  ```

  Wrong order (`block <id> --kind …`) prints top-level usage, **exits 0**,
  and does **not** block (`204830Z`). After the command, `kanban show`
  **must** report `status=blocked`. If not, REFUSE the mint — do not
  continue to story creates.
- `idempotency_key`: `migration-m3-ack-gate-v1`
- skills: `check-spec-readiness` (non-empty; bare create OBJECT)
- body: wait for Deputy/Operator `kanban_complete`; do not implement dest code

Story children parents: **`[holder, ack_gate]`**. Create-time `blocked`
is not sticky; the incomplete gate parent holds them. Sticky-block is
**only** for the gate (OBJECT Option B on story cards).

Deputy/Operator grant = `kanban_complete` on the **blocked** gate
(accepted at v0.20.2; `204830Z`). Do not treat `evidence/acks/*.yaml` as
the unpark switch.

## Pre-create gates (moved from create-m3-implementer; do not drop)

Run per body, fail-closed, via `execute_code`.
`identity.story_id required`.
Paths are repo-relative from `/projects/modernized` (Operator `173010Z` C1).
Bare filenames resolve under the wrong skill tree and become typed BLOCK
(`exit 2` = missing script — do not invent paths).

1. `python3 .hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py /projects/modernized`
2. `python3 .hermes/skills/harness/dispatch-phase/scripts/check-phase-body-script-refs.py /projects/modernized`
3. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py --body <body> --write`
4. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-interface-closure.py --body <body>`
5. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py --body <body> --write`
6. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py --write-receipt evidence/receipts/partition-coverage/latest.json`
7. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py`
8. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py --body <body> --inject` then without `--inject`
9. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py --body <body> --snapshot-before`
10. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py --body <body>`
11. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-kanban-body.py --body <body>`
12. `python3 .hermes/skills/harness/dispatch-phase/scripts/check-phase-attach-matrix.py /projects/modernized`
13. `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-bundle-skills-exist.py /projects/modernized --bundle m3-implementer`
14. `python3 .hermes/skills/harness/record-run-evidence/scripts/stamp-body-digest.py` (AR-4.3)
15. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-surgical-scopes.py` + `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-semantic-exits.py` + `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py --wall-fit`
16. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-oracles.py --body <body> --skip-task-id`
17. `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-skills-not-disabled.py /projects/modernized` with `--skill` once per line of `m3-attach-skills.py` stdout (B3 / `25a7c1e9`). Intersection with `skills.disabled` ⇒ refuse. Do **not** grow `handover-mint.py`.

Attach skills from `python3 .hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py <body>` (B-16).
skills = full m3-attach-skills.py stdout
(`kanban_create` skills: every line of that stdout, order-stable).
Dropping any name is refuse — v22 setup/foundational kept only
`check-spec-readiness` while attach printed three/four (`035010Z`).
Max runtime from `python3 .hermes/skills/harness/dispatch-phase/scripts/read-phase-dispatch.py --yaml .hermes/phase-dispatch.yaml --phase M3` or body
`runtime_budget_sec`. Workspace `dir:/projects/modernized`. Profile
`default` must exist (`hermes profile show default`).

Title: `{story_id}: M3 IMPLEMENT: {story_id}` (prefix once).

## Card body contract (binding — `035010Z` / `224320Z`)

Phase 2.4 verified `kanban_create` *arguments* and never inventoried the
*markdown* `create-m3-implementer.sh` composed. Argument parity is not
contract parity. **Do not** grow `handover-mint.py`. **Do not** resurrect
`create-m3-implementer.sh`. Put this prose on every story card.

After `stamp-body-digest.py` (step 14), read `body_sha256` (64-hex) from
stdout / the sidecar. Card markdown **must** include all of:

1. Typed body path: `evidence/bodies/m3-{story_id}.json`
2. AR-4.3 64-hex (`body_sha256`)
3. `python3 .hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py --expect <digest> --body evidence/bodies/m3-{story_id}.json .` — mismatch ⇒ REFUSE
4. Pointer: `.hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md`
   (BANK-DEST-INV-HARDINVOKE-1 / `refs.destination_inventory`, Pre-v12 R5
   hard-invoke traps). Standing procedure stays there — do not paste it.
5. Pre-complete: `assert-complete-exit-criteria.py` (rc≠0 ⇒ REFUSE complete)
6. Constraints: workspace `dir:/projects/modernized`; do not re-plan;
   max-runtime from phase-dispatch; AD-008 (no MiniMax); AD-002E
   (`skill_view` each attached skill or typed `skills_unused`)

Template (fill; keep card markdown ≤1500 chars — **F6 card budget exceeded**
if over 1500 chars):

```text
Typed body: evidence/bodies/m3-{story_id}.json
AR-4.3 digest: {64-hex}
Verify: python3 .hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py --expect {64-hex} --body evidence/bodies/m3-{story_id}.json .
  mismatch ⇒ REFUSE
Standing: .hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md
Pre-complete: python3 .hermes/skills/gates/check-release-readiness/scripts/assert-complete-exit-criteria.py . --task-id {id} --body evidence/bodies/m3-{story_id}.json
## Exit Criteria
- {from body.exit_criteria, one line each}
## Files Writable
- {from body.files_writable, one path each}
## Constraints
- workspace: dir:/projects/modernized
- Do not re-plan. max-runtime: {seconds}. AD-008. AD-002E.
```

A four-line operands/exit/files summary **without** path + digest +
standing + `--expect` + Constraints is refuse. Do not dest-rewrite cards
after create to chase this (`192117Z`).

`idempotency_key`: `migration-m3-{story_id}-v1`.

## After create (same session)

- Immediately after each story `kanban_create`, `hermes kanban show <id> --json`
  and **refuse unless `status=todo`** (not `ready`/`running`) **and**
  `parents` include the unfinished `ack_gate`. `initial_status` is **not**
  the protection (`113650Z`). OBJECT story `status==blocked`. Do **not**
  grow `handover-mint.py` for this (1088 freeze).
- Immediately after each `kanban_create` (ack_gate skip write-set cache;
  every **story** id), emit dest write-set **cache** (not fence policy):

  ```text
  python3 .hermes/skills/harness/enforce-authority-boundary/scripts/emit-write-set-cache.py \
    --root . --task-id <new_id> --body evidence/bodies/m3-{story_id}.json
  ```

  File `evidence/runtime/write-sets/<t_hex>.json` must exist and be
  non-empty before the next story create (Architect 35099226). `task_id`
  in that file is Hermes `t_<hex>` hygiene. Do **not** rewrite the typed
  body `task_id` (AR-4.3 digest). Fence policy is spawn env
  `HERMES_KANBAN_FILES_WRITABLE`, not this file.
- Immediately after each `kanban_create` (ack_gate and every story id),
  fail-open once per new id:

  ```text
  bash .hermes/skills/harness/record-run-evidence/scripts/snapshot-card-boundary.sh create || true
  ```

  Hermes has no create-hook. Absence is silent (`|| true`); this text is
  the contract (`182330Z`). Do **not** run this as a pre-create gate.
- Prove each new id has both parent links (holder + ack_gate) via
  `read-link-graph.py --expect-parent`.
- Status must be `blocked` or `triage` (`PARK_AT_BIRTH`). `ready`/`todo`/`running` is refuse.
- **Card-contract assert:** `hermes kanban show <id>` markdown must contain
  `evidence/bodies/m3-`, a 64-hex, `m3-implementer-standing.md`, and
  `check-body-digest-match.py --expect`. Skills on the card must equal
  full `m3-attach-skills.py` stdout. Any miss → typed `needs_input` BLOCK;
  do not create the next story; do not `kanban_complete` this holder.
- Assert ack_gate is still `blocked` after holder complete.
- Append `evidence/derived/created-story-cards.json`.
- Emit unsigned `evidence/acks/ack-request-<story>.yaml` for the record;
  **unpark is still completing `ack_gate`**, not signing the file.
- Run `assert-m2b-created-cards-claim.sh` (partition set equality) after
  the wave.
- Worker complete-cmd (not mint): `assert-complete-exit-criteria.py` and
  `assert-card-body-digest-match.py` before `kanban_complete` (standing
  procedure).

## Scratch proof (Phase 2.5)

Filed `monitoring/v21/20260817-phase25-seven-card-scratch.md`. Authoring
the Procedure is not that proof.

## Retired control-plane scripts (2.4)

`mint-m3-wave.sh` and `create-m3-implementer.sh` are **deleted**. Do not
restore them. Do not invoke them from Cursor, from M2, or from the demo
user. Pre-create gates live in this Procedure; tip-sync pins target this
file.
